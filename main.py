import argparse
import os
import threading
import webbrowser
from pathlib import Path

import uvicorn

from backend.app import main as backend_main

app = backend_main.app

__all__ = ["app"]


DEFAULT_PORT = 8003


def runtime_options(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an isolated Taskloom instance")
    parser.add_argument("--host", default="127.0.0.1", help="Address to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to bind (default: {DEFAULT_PORT})")
    parser.add_argument("--data-dir", type=Path, help="Directory for this instance's sessions and profiles")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the dashboard in a browser")
    options = parser.parse_args(argv)
    if not 1 <= options.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    return options


def configure_instance_storage(port: int, data_dir: Path | None = None) -> Path:
    """Point mutable data at one directory per server instance.

    Explicit TASKLOOM_*_PATH variables remain authoritative.  Port 8003
    keeps using the legacy directory so an upgrade does not hide history.
    """
    custom_dir = data_dir is not None
    if custom_dir:
        root = data_dir.expanduser()
    elif port == DEFAULT_PORT:
        root = Path.home() / ".taskloom"
    else:
        root = Path.home() / ".taskloom" / "instances" / f"port-{port}"
    root = root.resolve()
    session_path = root / "sessions.json"
    profile_path = root / "profiles.json"
    if custom_dir:
        os.environ["TASKLOOM_SESSIONS_PATH"] = str(session_path)
        os.environ["TASKLOOM_PROFILES_PATH"] = str(profile_path)
    else:
        os.environ.setdefault("TASKLOOM_SESSIONS_PATH", str(session_path))
        os.environ.setdefault("TASKLOOM_PROFILES_PATH", str(profile_path))
    return root


def run(argv: list[str] | None = None) -> None:
    options = runtime_options([] if argv is None else argv)
    data_root = configure_instance_storage(options.port, options.data_dir)
    # backend.app.main is imported for ASGI compatibility. Reload persisted
    # state after selecting this CLI instance's storage namespace.
    backend_main.tasks.clear()
    backend_main.tasks.update(backend_main.load_tasks())
    display_host = "127.0.0.1" if options.host in {"0.0.0.0", "::"} else options.host
    url = f"http://{display_host}:{options.port}"
    print(f"Taskloom is available at {url}")
    print(f"Instance data: {data_root}")
    if not options.no_browser:
        browser = threading.Timer(1.0, webbrowser.open, args=(url,))
        browser.daemon = True
        browser.start()
    uvicorn.run(app, host=options.host, port=options.port)


if __name__ == "__main__":
    import sys

    run(sys.argv[1:])
