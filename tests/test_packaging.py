from pathlib import Path

import main


def test_run_starts_browser_and_local_server(monkeypatch):
    timers = []
    server_calls = []

    class FakeTimer:
        daemon = False

        def __init__(self, interval, function, args):
            self.interval = interval
            self.function = function
            self.args = args
            timers.append(self)

        def start(self):
            self.function(*self.args)

    opened = []
    monkeypatch.setattr(main.threading, "Timer", FakeTimer)
    monkeypatch.setattr(main.webbrowser, "open", opened.append)
    monkeypatch.setattr(main.uvicorn, "run", lambda *args, **kwargs: server_calls.append((args, kwargs)))

    main.run()

    assert timers[0].daemon is True
    assert opened == ["http://127.0.0.1:8000"]
    assert server_calls == [((main.app,), {"host": "127.0.0.1", "port": 8000})]


def test_python_builder_creates_one_file_with_frontend_assets():
    script = (Path(__file__).parents[1] / "build_exe.py").read_text(encoding="utf-8")

    assert '"npm.cmd" if sys.platform == "win32" else "npm"' in script
    assert '"ci", cwd=FRONTEND' in script
    assert '"run", "build", cwd=FRONTEND' in script
    assert '"--onefile"' in script
    assert '"--add-data"' in script
    assert '"--workpath"' in script
    assert "shutil.rmtree(BUILD_DIR, ignore_errors=True)" in script
    assert "Taskloom.exe" in script
