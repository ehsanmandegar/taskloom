"""A small, read-only MCP server for project Markdown guides.

The server intentionally uses only the Python standard library so it can start
with the same Python installation that runs Taskloom. MCP messages over stdio
are newline-delimited JSON-RPC messages.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import sys
from typing import Any, TextIO


SERVER_NAME = "taskloom-guides"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
MAX_GUIDE_BYTES = 1_000_000
SKIPPED_DIRECTORIES = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}


@dataclass(frozen=True)
class Guide:
    path: Path
    label: str

    @property
    def uri(self) -> str:
        return self.path.as_uri()


class GuideCatalog:
    """Discover and safely read Markdown files below configured roots."""

    def __init__(self, roots: list[Path]):
        if not roots:
            raise ValueError("At least one guide root is required")

        resolved: list[Path] = []
        for root in roots:
            candidate = root.expanduser().resolve()
            if not candidate.exists():
                raise ValueError(f"Guide root does not exist: {root}")
            if candidate.is_file() and candidate.suffix.casefold() != ".md":
                raise ValueError(f"Guide file must be Markdown: {root}")
            if not candidate.is_dir() and not candidate.is_file():
                raise ValueError(f"Guide root must be a file or directory: {root}")
            if candidate not in resolved:
                resolved.append(candidate)
        self.roots = resolved

    def guides(self) -> list[Guide]:
        paths: list[Path] = []
        for root in self.roots:
            if root.is_file():
                paths.append(root)
                continue
            for directory, names, files in os.walk(root, followlinks=False):
                names[:] = sorted(
                    name for name in names if name.casefold() not in SKIPPED_DIRECTORIES
                )
                base = Path(directory)
                for name in sorted(files):
                    if Path(name).suffix.casefold() != ".md":
                        continue
                    candidate = (base / name).resolve()
                    try:
                        candidate.relative_to(root)
                    except ValueError:
                        # Do not expose file symlinks that escape a directory root.
                        continue
                    paths.append(candidate)

        unique_paths = sorted(set(paths), key=lambda path: str(path).casefold())
        return [Guide(path=path, label=self._label(path)) for path in unique_paths]

    def list_guides(self) -> list[dict[str, Any]]:
        return [
            {
                "path": guide.label,
                "uri": guide.uri,
                "size_bytes": guide.path.stat().st_size,
            }
            for guide in self.guides()
        ]

    def read_guide(self, selector: str) -> str:
        guide = self._select(selector)
        size = guide.path.stat().st_size
        if size > MAX_GUIDE_BYTES:
            raise ValueError(
                f"Guide is too large to read ({size} bytes; limit is {MAX_GUIDE_BYTES})"
            )
        return guide.path.read_text(encoding="utf-8")

    def search_guides(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            raise ValueError("Search query cannot be empty")
        if isinstance(max_results, bool) or not isinstance(max_results, int):
            raise ValueError("max_results must be an integer")
        if not 1 <= max_results <= 100:
            raise ValueError("max_results must be between 1 and 100")

        needle = query.casefold()
        matches: list[dict[str, Any]] = []
        for guide in self.guides():
            for line_number, line in enumerate(self.read_guide(guide.uri).splitlines(), start=1):
                if needle in line.casefold():
                    matches.append(
                        {
                            "path": guide.label,
                            "uri": guide.uri,
                            "line": line_number,
                            "text": line.strip(),
                        }
                    )
                    if len(matches) == max_results:
                        return matches
        return matches

    def resource(self, uri: str) -> Guide:
        return self._select(uri)

    def _select(self, selector: str) -> Guide:
        if not isinstance(selector, str) or not selector.strip():
            raise ValueError("Guide path or URI is required")
        selector = selector.strip()
        guides = self.guides()

        uri_matches = [guide for guide in guides if guide.uri == selector]
        if uri_matches:
            return uri_matches[0]

        requested = Path(selector).expanduser()
        candidates: set[Path] = set()
        if requested.is_absolute():
            candidates.add(requested.resolve())
        else:
            for root in self.roots:
                if root.is_dir():
                    candidates.add((root / requested).resolve())

        matches = [
            guide
            for guide in guides
            if guide.path in candidates or guide.label == selector
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            choices = ", ".join(guide.uri for guide in matches)
            raise ValueError(f"Guide path is ambiguous; use one of these URIs: {choices}")
        raise ValueError(f"Guide is not available from the configured roots: {selector}")

    def _label(self, path: Path) -> str:
        labels: list[str] = []
        for root in self.roots:
            if root.is_file() and path == root:
                labels.append(root.name)
            elif root.is_dir():
                try:
                    labels.append(path.relative_to(root).as_posix())
                except ValueError:
                    pass
        return min(labels, key=lambda label: (len(Path(label).parts), len(label)))


def tool_definitions() -> list[dict[str, Any]]:
    read_only = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
    return [
        {
            "name": "list_guides",
            "description": "List Markdown guides available in the configured project roots.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
            "annotations": read_only,
        },
        {
            "name": "read_guide",
            "description": "Read a project guide by the path or URI returned by list_guides.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Guide path or file URI."}
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            "annotations": read_only,
        },
        {
            "name": "search_guides",
            "description": "Search project guides and return matching lines with locations.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1},
                    "max_results": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 100,
                        "default": 20,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            "annotations": read_only,
        },
    ]


class McpServer:
    def __init__(self, catalog: GuideCatalog):
        self.catalog = catalog

    def handle(self, request: dict[str, Any]) -> tuple[Any, bool]:
        method = request.get("method")
        params = request.get("params") or {}

        if method == "initialize":
            return {
                "protocolVersion": params.get("protocolVersion", DEFAULT_PROTOCOL_VERSION),
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"subscribe": False, "listChanged": False},
                },
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "Use this read-only server for project documentation. Call list_guides to "
                    "discover Markdown files, read_guide for full contents, and search_guides "
                    "to find relevant passages. Paths outside configured roots are unavailable."
                ),
            }, False
        if method == "ping":
            return {}, False
        if method == "tools/list":
            return {"tools": tool_definitions()}, False
        if method == "tools/call":
            return self._call_tool(params), False
        if method == "resources/list":
            return {
                "resources": [
                    {
                        "uri": guide.uri,
                        "name": guide.label,
                        "mimeType": "text/markdown",
                    }
                    for guide in self.catalog.guides()
                ]
            }, False
        if method == "resources/read":
            guide = self.catalog.resource(params.get("uri", ""))
            return {
                "contents": [
                    {
                        "uri": guide.uri,
                        "mimeType": "text/markdown",
                        "text": self.catalog.read_guide(guide.uri),
                    }
                ]
            }, False
        if method in {"resources/templates/list", "prompts/list"}:
            key = "resourceTemplates" if method.startswith("resources/") else "prompts"
            return {key: []}, False
        if method == "logging/setLevel":
            return {}, False
        if method == "shutdown":
            return None, True
        raise LookupError(f"Method not found: {method}")

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            if name == "list_guides":
                value: Any = self.catalog.list_guides()
            elif name == "read_guide":
                value = self.catalog.read_guide(arguments.get("path", ""))
            elif name == "search_guides":
                value = self.catalog.search_guides(
                    arguments.get("query", ""), arguments.get("max_results", 20)
                )
            else:
                raise ValueError(f"Unknown tool: {name}")
        except (OSError, UnicodeError, ValueError) as exc:
            return {"content": [{"type": "text", "text": str(exc)}], "isError": True}

        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
        return {"content": [{"type": "text", "text": text}], "isError": False}


def serve(catalog: GuideCatalog, input_stream: TextIO, output_stream: TextIO) -> None:
    server = McpServer(catalog)
    for raw_line in input_stream:
        if not raw_line.strip():
            continue
        request_id: Any = None
        try:
            request = json.loads(raw_line)
            if not isinstance(request, dict):
                raise TypeError("JSON-RPC request must be an object")
            request_id = request.get("id")
            method = request.get("method")
            if not isinstance(method, str):
                raise TypeError("JSON-RPC method must be a string")
            if "id" not in request:
                continue
            result, stop = server.handle(request)
            response = {"jsonrpc": "2.0", "id": request_id, "result": result}
        except json.JSONDecodeError as exc:
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc.msg}"},
            }
            stop = False
        except (TypeError, ValueError) as exc:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": str(exc)},
            }
            stop = False
        except LookupError as exc:
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": str(exc)},
            }
            stop = False
        except Exception as exc:  # Keep protocol errors on stdout, never tracebacks.
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": f"Internal error: {exc}"},
            }
            stop = False

        output_stream.write(json.dumps(response, ensure_ascii=False) + "\n")
        output_stream.flush()
        if stop:
            break


def main() -> None:
    # MCP stdio is UTF-8; Windows may otherwise inherit a legacy console code page.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Serve project Markdown guides over MCP stdio")
    parser.add_argument(
        "--root",
        action="append",
        type=Path,
        help="Markdown file or directory to expose; repeat for multiple roots (default: current directory)",
    )
    args = parser.parse_args()
    try:
        catalog = GuideCatalog(args.root or [Path.cwd()])
    except ValueError as exc:
        parser.error(str(exc))
    serve(catalog, sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
