"""Start the Elder Care Assistant and open it in your browser.

    python run.py            # start the server and open the browser
    python run.py --check    # verify setup without starting
    python run.py --yes      # install missing packages without asking
    python run.py --port 8200

Launches with sys.executable -- the interpreter running this file -- so there
is no python/python3 ambiguity and no shell involved.
"""

import os
import sys
import threading
import webbrowser
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

# import name -> pip name
REQUIRED = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "requests": "requests",
    "cv2": "opencv-python",
    "onnxruntime": "onnxruntime",
    "numpy": "numpy",
    "PIL": "Pillow",
}

DEFAULT_PORT = 8100


def missing_packages():
    import importlib
    missing = []
    for module, pip_name in REQUIRED.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(pip_name)
    return missing


def ensure_packages(assume_yes):
    missing = missing_packages()
    if not missing:
        return True

    print("Missing packages: " + ", ".join(missing))
    if not assume_yes:
        if not sys.stdin.isatty():
            print(f"\nInstall with:\n    {sys.executable} -m pip install "
                  + " ".join(missing))
            return False
        try:
            if input("Install them now? [Y/n] ").strip().lower() not in ("", "y", "yes"):
                print("Skipped. The app cannot start without them.")
                return False
        except EOFError:
            return False

    print("Installing...")
    if subprocess.run([sys.executable, "-m", "pip", "install", *missing]).returncode != 0:
        print("pip failed.")
        return False
    return not missing_packages()


def report_features():
    """Say up front which optional pieces are present, without blocking."""
    sys.path.insert(0, HERE)
    import config
    import engines

    st = engines.status()
    print(f"Groq key   : {'found' if st['groq'] else 'NOT SET'}")
    if not st["groq"]:
        print("             Check-in summaries, chat and reports need it.")
        print(f"             Add GROQ_API_KEY to {config.ENV_PATH}")
    print(f"Face model : {'ready' if st['face'] else 'missing'}"
          + ("" if st["face"] else "   (cd Face_rec && python download_models.py)"))
    print(f"Voice model: {'ready' if st['voice'] else 'missing'}"
          + ("" if st["voice"] else "   (cd voice_rec && python download_models.py, 1.2 GB)"))
    print(f"Medicines  : {'ready' if st['medications'] else 'missing'}")
    return True


def main():
    args = sys.argv[1:]
    assume_yes = "--yes" in args or "-y" in args
    check_only = "--check" in args
    port = DEFAULT_PORT
    if "--port" in args:
        try:
            port = int(args[args.index("--port") + 1])
        except (IndexError, ValueError):
            print("--port needs a number, e.g. --port 8200")
            return 1

    print(f"Python : {sys.version.split()[0]}")
    print(f"Using  : {sys.executable}")
    os.chdir(HERE)

    if not ensure_packages(assume_yes):
        return 1
    print("Packages   : OK")

    report_features()

    if check_only:
        print("\n--check passed. Run without --check to start.")
        return 0

    url = f"http://127.0.0.1:{port}"
    print(f"\nElder Care Assistant is running at {url}")
    print("Press Ctrl+C to stop.\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    import server
    try:
        server.serve(port=port)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
