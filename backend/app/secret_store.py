"""Small secret store for credentials such as GitHub tokens.

On Windows values are encrypted with DPAPI (CryptProtectData), so they can only be decrypted by
the same Windows user on the same machine. Elsewhere they are stored in a file readable only by
the owner (mode 0600). Project JSON files never contain the secrets themselves.
"""

from __future__ import annotations

import base64
import json
import os
import uuid
from pathlib import Path

from .file_lock import FileLock, replace_with_retry

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    _crypt32 = ctypes.windll.crypt32
    _kernel32 = ctypes.windll.kernel32
    _CRYPTPROTECT_UI_FORBIDDEN = 0x1
    _ENTROPY = b"taskloom-secret-store"

    def _dpapi(data: bytes, protect: bool) -> bytes:
        data_buffer = ctypes.create_string_buffer(data, len(data))  # kept alive for the call
        entropy_buffer = ctypes.create_string_buffer(_ENTROPY, len(_ENTROPY))
        source = _Blob(len(data), ctypes.cast(data_buffer, ctypes.POINTER(ctypes.c_char)))
        entropy = _Blob(len(_ENTROPY), ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_char)))
        result = _Blob()
        function = _crypt32.CryptProtectData if protect else _crypt32.CryptUnprotectData
        if not function(ctypes.byref(source), None, ctypes.byref(entropy), None, None,
                        _CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(result)):
            raise OSError(f"DPAPI {'encryption' if protect else 'decryption'} failed (Windows error {ctypes.GetLastError()})")
        try:
            return ctypes.string_at(result.pbData, result.cbData)
        finally:
            _kernel32.LocalFree(result.pbData)


class SecretStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    @property
    def scheme(self) -> str:
        return "dpapi" if os.name == "nt" else "file-0600"

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}

    def _write(self, entries: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(f"{self.path.name}.{uuid.uuid4().hex}.tmp")
        temp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
        if os.name != "nt":
            os.chmod(temp, 0o600)
        replace_with_retry(temp, self.path)

    def _encode(self, value: str) -> dict:
        raw = value.encode("utf-8")
        if os.name == "nt":
            return {"scheme": "dpapi", "value": base64.b64encode(_dpapi(raw, protect=True)).decode("ascii")}
        return {"scheme": "plain", "value": base64.b64encode(raw).decode("ascii")}

    @staticmethod
    def _decode(entry: dict) -> str:
        raw = base64.b64decode(entry["value"])
        if entry.get("scheme") == "dpapi":
            raw = _dpapi(raw, protect=False)
        return raw.decode("utf-8")

    def has(self, name: str) -> bool:
        return name in self._read()

    def get(self, name: str) -> str | None:
        entry = self._read().get(name)
        return self._decode(entry) if entry else None

    def set(self, name: str, value: str) -> None:
        with FileLock(self.path.with_name(self.path.name + ".lock")):
            entries = self._read()
            entries[name] = self._encode(value)
            self._write(entries)

    def delete(self, name: str) -> None:
        with FileLock(self.path.with_name(self.path.name + ".lock")):
            entries = self._read()
            if entries.pop(name, None) is not None:
                self._write(entries)
