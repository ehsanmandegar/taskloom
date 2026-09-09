import threading
import webbrowser

import uvicorn

from backend.app.main import app

__all__ = ["app"]


def run() -> None:
    url = "http://127.0.0.1:8000"
    print(f"Taskloom is available at {url}")
    browser = threading.Timer(1.0, webbrowser.open, args=(url,))
    browser.daemon = True
    browser.start()
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
