"""One-click start: runs the Streamlit app on a free local port and opens it in the browser.

Used as the entry point of GreenLCC.exe (scripts/build_exe.py) and works from source too:  python launcher.py
Close this window to stop the app.
"""
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def app_dir() -> Path:
    # PyInstaller unpacks bundled files under sys._MEIPASS; from source, use this file's folder
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))


def free_port(preferred: int = 8501) -> int:
    for port in [preferred, *range(8502, 8600)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError("No free port between 8501 and 8599")


def open_when_ready(port: int, timeout: float = 90) -> None:
    end = time.time() + timeout
    while time.time() < end:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                webbrowser.open(f"http://localhost:{port}")
                return
        time.sleep(0.5)


def main() -> None:
    root = app_dir()
    os.chdir(root)
    sys.path.insert(0, str(root))
    port = free_port()
    print(f"GreenLCC India is starting on http://localhost:{port}  (close this window to stop it)")
    if "--no-browser" not in sys.argv:
        threading.Thread(target=open_when_ready, args=(port,), daemon=True).start()

    from streamlit.web import cli as stcli

    sys.argv = ["streamlit", "run", str(root / "app.py"), "--server.port", str(port), "--server.headless", "true",
                "--global.developmentMode", "false", "--browser.gatherUsageStats", "false"]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
