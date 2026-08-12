"""Start the Medication Manager and open it in your browser.

    python run.py            # start the server and open the browser
    python run.py --check    # verify setup without starting
    python run.py --yes      # install missing packages without asking
    python run.py --port 8080

Launches with sys.executable -- the interpreter running this file -- so there
is no python/python3 ambiguity and no shell involved.
"""

import os
import sys
import threading
import webbrowser
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

REQUIRED = {
    "requests": "requests",
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
}


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
            print(f"\nInstall with:\n    {sys.executable} -m pip install -r requirements.txt")
            return False
        try:
            if input("Install them now? [Y/n] ").strip().lower() not in ("", "y", "yes"):
                print("Skipped. The app cannot start without them.")
                return False
        except EOFError:
            return False

    print("Installing...")
    if subprocess.run([sys.executable, "-m", "pip", "install", "-r",
                       os.path.join(HERE, "requirements.txt")]).returncode != 0:
        print(f"\npip failed. Try:\n    {sys.executable} -m pip install -r requirements.txt")
        return False

    still = missing_packages()
    if still:
        print("Still missing after install: " + ", ".join(still))
        return False
    return True


def check_config():
    """Report on the shared config, but never block startup on it.

    The app is usable without a key -- you just cannot run AI extraction, and
    the UI says so plainly rather than failing at an odd moment.
    """
    sys.path.insert(0, HERE)
    try:
        import groq_client
    except FileNotFoundError as e:
        print(f"\nConfig problem: {e}")
        return False
    except Exception as e:                    # noqa: BLE001
        print(f"\nCould not load config: {e}")
        return False

    if groq_client.ready():
        print("Groq key: found")
    else:
        print("Groq key: NOT SET")
        print("  " + groq_client.missing_key_message().replace("\n", "\n  "))
        print("  The app will still run; AI reading of prescriptions is disabled.")
    return True


def main():
    args = sys.argv[1:]
    assume_yes = "--yes" in args or "-y" in args
    check_only = "--check" in args
    port = 8002
    if "--port" in args:
        try:
            port = int(args[args.index("--port") + 1])
        except (IndexError, ValueError):
            print("--port needs a number, e.g. --port 8080")
            return 1

    print(f"Python : {sys.version.split()[0]}")
    print(f"Using  : {sys.executable}")
    os.chdir(HERE)

    if not ensure_packages(assume_yes):
        return 1
    print("Packages: OK")

    if not check_config():
        return 1

    if check_only:
        print("\n--check passed. Run without --check to start.")
        return 0

    url = f"http://127.0.0.1:{port}"
    print(f"\nMedication Manager is running at {url}")
    print("Press Ctrl+C to stop.\n")
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    import web_app
    try:
        web_app.serve(port=port)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
