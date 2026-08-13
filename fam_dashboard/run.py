"""Start the Family Dashboard and open it in your browser.

    python run.py            # start the server and open the browser
    python run.py --check    # verify setup without starting
    python run.py --port 8400

Reads the data written by eld_care_assist and med_mgmt, so those apps do not
need to be running -- only to have been used at least once.
"""

import os
import sys
import threading
import webbrowser
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))

REQUIRED = {"fastapi": "fastapi", "uvicorn": "uvicorn", "requests": "requests"}
DEFAULT_PORT = 8300


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
                return False
        except EOFError:
            return False
    print("Installing...")
    if subprocess.run([sys.executable, "-m", "pip", "install", *missing]).returncode != 0:
        return False
    return not missing_packages()


def report_sources():
    sys.path.insert(0, HERE)
    import config

    care = config.care_db_exists()
    med = config.med_db_exists()
    print(f"Care data  : {'found' if care else 'not found'}")
    if not care:
        print(f"             Expected at {config.CARE_DB}")
        print("             Run eld_care_assist and complete one check-in first.")
    print(f"Medicines  : {'found' if med else 'not found'}")
    if not med:
        print("             Add a prescription in med_mgmt or eld_care_assist.")
    print(f"Groq key   : {'found' if config.groq_ready() else 'NOT SET'}"
          + ("" if config.groq_ready() else "   (the written update needs it)"))
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
            print("--port needs a number, e.g. --port 8400")
            return 1

    print(f"Python : {sys.version.split()[0]}")
    print(f"Using  : {sys.executable}")
    os.chdir(HERE)

    if not ensure_packages(assume_yes):
        return 1
    print("Packages   : OK")
    report_sources()

    if check_only:
        print("\n--check passed. Run without --check to start.")
        return 0

    url = f"http://127.0.0.1:{port}"
    print(f"\nFamily Dashboard is running at {url}")
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
