"""Launcher for the conversation / care-record app.

    python run.py              # FastAPI + Next.js -- the primary UI
    python run.py --api        # FastAPI backend only
    python run.py --streamlit  # Streamlit UI (single process fallback)
    python run.py --check      # verify setup without starting anything
    python run.py --yes        # install anything missing without asking
    python run.py --port 8600  # override the API port

Everything runs through sys.executable -- the interpreter running this file --
so there is no python/python3 ambiguity and no shell involved.

The two UIs share the same backend code and the same ChromaDB store, so it
does not matter which one you start.
"""

import os
import sys
import time
import shutil
import signal
import threading
import webbrowser
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
WEB_DIR = os.path.join(HERE, "web")

# import name -> pip name
BASE_DEPS = {
    "dotenv": "python-dotenv",
    "groq": "groq",
    "chromadb": "chromadb",
}
STREAMLIT_DEPS = {
    "streamlit": "streamlit",
    "pyttsx3": "pyttsx3",
    "schedule": "schedule",
}
API_DEPS = {
    "fastapi": "fastapi",
    "uvicorn": "uvicorn",
    "multipart": "python-multipart",
    # api/main.py imports pipecat at module level for the hands-free call.
    "pipecat": "pipecat-ai[webrtc,groq,silero]",
}

DEFAULT_STREAMLIT_PORT = 8501
# 8000 matches web/lib/api.ts's fallback. Note the sibling Face_rec app also
# defaults to 8000 -- use --port here if you want both running at once.
DEFAULT_API_PORT = 8000
WEB_PORT = 3000


def missing(deps):
    import importlib
    out = []
    for module, pip_name in deps.items():
        try:
            importlib.import_module(module)
        except ImportError:
            out.append(pip_name)
    return out


def ensure(deps, assume_yes, label):
    need = missing(deps)
    if not need:
        return True

    print(f"Missing {label} packages: " + ", ".join(need))
    if any("pipecat" in n for n in need):
        print("  (pipecat is a large install -- it pulls in the voice pipeline)")

    if not assume_yes:
        if not sys.stdin.isatty():
            print(f"\nInstall with:\n    {sys.executable} -m pip install " + " ".join(need))
            return False
        try:
            if input("Install them now? [Y/n] ").strip().lower() not in ("", "y", "yes"):
                print("Skipped. Cannot start without them.")
                return False
        except EOFError:
            return False

    print("Installing...")
    if subprocess.run([sys.executable, "-m", "pip", "install", *need]).returncode != 0:
        print(f"\npip failed. Try:\n    {sys.executable} -m pip install " + " ".join(need))
        return False

    still = missing(deps)
    if still:
        print("Still missing after install: " + ", ".join(still))
        return False
    return True


def check_key():
    """Report on GROQ_API_KEY without blocking startup.

    config.py calls load_dotenv(), which searches parent folders too -- so a
    shared .env at the repo root above this project is picked up automatically.
    """
    sys.path.insert(0, HERE)
    try:
        import config
    except Exception as e:                    # noqa: BLE001
        print(f"Could not load config.py: {e}")
        return False

    if config.GROQ_API_KEY:
        local = os.path.join(HERE, ".env")
        parent = os.path.join(os.path.dirname(HERE), ".env")
        where = local if os.path.exists(local) else (
            parent if os.path.exists(parent) else "the environment")
        print(f"Groq key: found (from {where})")
    else:
        print("Groq key: NOT SET")
        print("  Create a .env file here with:  GROQ_API_KEY=gsk_your_key_here")
        print("  (copy .env.example). The app starts, but chat, transcription")
        print("  and reports will fail until it is set.")
    return True


def init_database():
    """Create the ChromaDB collections up front.

    First run also downloads a local embedding model (~80 MB), which is a long
    silent pause if it happens once the UI is already up.
    """
    print("Database: initialising (first run downloads an embedding model)...")
    code = ("import sys; sys.path.insert(0, %r)\n"
            "from core.database import init_db, list_tables\n"
            "init_db(); print('Database: OK -', ', '.join(list_tables()))" % HERE)
    return subprocess.run([sys.executable, "-c", code], cwd=HERE).returncode == 0


def ensure_node_modules(assume_yes):
    npm = shutil.which("npm")
    if not npm:
        print("npm not found. Install Node.js 18+ to run the Next.js UI, or use")
        print("the Streamlit UI instead:  python run.py")
        return None
    if os.path.isdir(os.path.join(WEB_DIR, "node_modules")):
        return npm

    print("web/node_modules is missing -- the frontend needs 'npm install' first.")
    if not assume_yes:
        if not sys.stdin.isatty():
            print(f"\nRun:\n    cd {WEB_DIR} && npm install")
            return None
        try:
            if input("Run npm install now? [Y/n] ").strip().lower() not in ("", "y", "yes"):
                return None
        except EOFError:
            return None

    print("Running npm install (this takes a couple of minutes)...")
    if subprocess.run([npm, "install"], cwd=WEB_DIR, shell=(os.name == "nt")).returncode != 0:
        print("npm install failed.")
        return None
    return npm


def open_later(url, delay=2.0):
    threading.Timer(delay, lambda: webbrowser.open(url)).start()


def run_streamlit(port):
    url = f"http://localhost:{port}"
    print(f"\nStreamlit UI at {url}")
    print("Press Ctrl+C to stop.\n")
    # Streamlit opens its own browser tab, so no need to do it here.
    return subprocess.call(
        [sys.executable, "-m", "streamlit", "run", "app.py",
         "--server.port", str(port)], cwd=HERE)


def run_api(port, open_browser=True):
    url = f"http://localhost:{port}/docs"
    print(f"\nAPI at http://localhost:{port}  (docs: {url})")
    print("Press Ctrl+C to stop.\n")
    if open_browser:
        open_later(url)
    return subprocess.call(
        [sys.executable, "-m", "uvicorn", "api.main:app",
         "--host", "0.0.0.0", "--port", str(port)], cwd=HERE)


def run_web(api_port, npm):
    """FastAPI and the Next.js dev server together."""
    procs = []
    try:
        print(f"\nStarting API on http://localhost:{api_port} ...")
        procs.append(subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.main:app",
             "--host", "0.0.0.0", "--port", str(api_port)], cwd=HERE))

        time.sleep(2)
        if procs[0].poll() is not None:
            print("The API exited immediately -- see the error above.")
            return 1

        # web/lib/api.ts falls back to localhost:8000. Pass the real port so a
        # custom --port still reaches the API without editing .env.local.
        web_env = dict(os.environ)
        web_env["NEXT_PUBLIC_API_BASE_URL"] = f"http://localhost:{api_port}"

        print(f"Starting Next.js on http://localhost:{WEB_PORT} ...")
        procs.append(subprocess.Popen(
            [npm, "run", "dev"], cwd=WEB_DIR, env=web_env,
            shell=(os.name == "nt")))

        url = f"http://localhost:{WEB_PORT}"
        print(f"\nOpen {url}")
        print("Microphone features need localhost or HTTPS.")
        print("Press Ctrl+C to stop both.\n")
        open_later(url, 6.0)

        while True:                            # exit as soon as either dies
            for p in procs:
                if p.poll() is not None:
                    print(f"\nA process exited (code {p.returncode}); shutting down.")
                    return p.returncode or 0
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping...")
        return 0
    finally:
        for p in procs:
            if p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=5)
                except Exception:              # noqa: BLE001
                    p.kill()


def main():
    args = sys.argv[1:]
    assume_yes = "--yes" in args or "-y" in args
    check_only = "--check" in args
    want_api = "--api" in args
    # --web is still accepted, but it is now the default.
    want_streamlit = "--streamlit" in args

    port = None
    if "--port" in args:
        try:
            port = int(args[args.index("--port") + 1])
        except (IndexError, ValueError):
            print("--port needs a number, e.g. --port 8600")
            return 1

    mode = "streamlit" if want_streamlit else ("api" if want_api else "web")
    print(f"Python : {sys.version.split()[0]}")
    print(f"Using  : {sys.executable}")
    print(f"Mode   : {mode}")
    os.chdir(HERE)

    if not ensure(BASE_DEPS, assume_yes, "core"):
        return 1
    needed = STREAMLIT_DEPS if mode == "streamlit" else API_DEPS
    if not ensure(needed, assume_yes, mode):
        return 1
    print("Packages: OK")

    if not check_key():
        return 1

    npm = None
    if mode == "web":
        npm = ensure_node_modules(assume_yes)
        if not npm:
            return 1

    if not init_database():
        print("Database initialisation failed.")
        return 1

    if check_only:
        print("\n--check passed. Run without --check to start.")
        return 0

    if mode == "streamlit":
        return run_streamlit(port or DEFAULT_STREAMLIT_PORT)
    if mode == "api":
        return run_api(port or DEFAULT_API_PORT)
    return run_web(port or DEFAULT_API_PORT, npm)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)
