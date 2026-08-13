"""Run everything, from the repo root.

    python run.py              # the main app + family dashboard, opens browser
    python run.py --all        # also the three standalone apps
    python run.py --only care  # just one (care|family|face|voice|meds)
    python run.py --check      # verify setup without starting anything
    python run.py --list       # show the apps and their ports

Each app is started by importing its own server module, so no app opens its own
browser tab and the ports are decided here. Ctrl+C stops all of them.
"""

import os
import sys
import time
import signal
import socket
import argparse
import threading
import webbrowser
import subprocess
from urllib.request import urlopen
from urllib.error import URLError

HERE = os.path.dirname(os.path.abspath(__file__))

# key -> (folder, server module, default port, what it is, in the default set)
APPS = {
    "care": ("eld_care_assist", "server", 8100,
             "Elder Care Assistant - check-in, talk, mood, medicines, report", True),
    "family": ("fam_dashboard", "server", 8300,
               "Family Dashboard - how they are, alerts, contacts", True),
    "face": ("Face_rec", "web_app", 8000,
             "Face emotion monitor (standalone)", False),
    "voice": ("voice_rec", "web_app", 8001,
              "Voice emotion monitor (standalone)", False),
    "meds": ("med_mgmt", "web_app", 8002,
             "Medication manager (standalone)", False),
}

MAIN = "care"          # the one the browser opens


def app_dir(key):
    return os.path.join(HERE, APPS[key][0])


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) != 0


def wait_until_up(port, timeout=90):
    """Poll the app's index page until it answers."""
    deadline = time.time() + timeout
    url = f"http://127.0.0.1:{port}/"
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as r:
                if r.status == 200:
                    return True
        except (URLError, OSError):
            pass
        time.sleep(0.7)
    return False


def start(key, port):
    """Launch one app by importing its server module -- no browser of its own."""
    folder, module, _, _, _ = APPS[key]
    directory = app_dir(key)
    code = (
        "import sys; sys.path.insert(0, %r)\n"
        "import %s as m\n"
        "m.serve(port=%d)" % (directory, module, port)
    )
    creationflags = 0
    if os.name == "nt":
        # Own process group, so Ctrl+C here does not race the children.
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.Popen([sys.executable, "-c", code], cwd=directory,
                            creationflags=creationflags)


def check():
    """Report what is present without starting anything."""
    print(f"Python : {sys.version.split()[0]}")
    print(f"Using  : {sys.executable}\n")

    ok = True
    env = os.path.join(HERE, ".env")
    has_key = False
    if os.path.exists(env):
        try:
            with open(env, encoding="utf-8") as fh:
                has_key = any(l.strip().startswith("GROQ_API_KEY=")
                              and len(l.split("=", 1)[1].strip()) > 10
                              for l in fh)
        except OSError:
            pass
    print(f"Groq key   : {'found in .env' if has_key else 'NOT SET'}")
    if not has_key:
        print("             Conversation, check-in summaries and prescription")
        print("             reading need it. Copy .env.example to .env.")

    face_model = os.path.exists(os.path.join(
        HERE, "Face_rec", "models", "emotion-ferplus-8.onnx"))
    voice_model = os.path.isdir(os.path.join(HERE, "voice_rec", "models", "ja-ser"))
    print(f"Face model : {'ready' if face_model else 'missing  (cd Face_rec && python download_models.py)'}")
    print(f"Voice model: {'ready' if voice_model else 'missing  (cd voice_rec && python download_models.py, 1.2 GB)'}")

    # Checked against THIS interpreter -- pipecat installed into a different
    # Python is the usual reason hands-free voice fails at the click.
    import importlib.util
    try:
        pipecat = importlib.util.find_spec("pipecat") is not None
    except (ImportError, ValueError):
        pipecat = False
    print(f"Hands-free : {'ready' if pipecat else 'missing'}")
    if not pipecat:
        print("             Voice conversation and the spoken check-in need it:")
        print(f'             "{sys.executable}" -m pip install '
              '"pipecat-ai[webrtc,groq,silero]"')

    print("\nApps:")
    for key, (folder, module, port, what, default) in APPS.items():
        path = os.path.join(HERE, folder, module + ".py")
        exists = os.path.exists(path)
        free = port_free(port)
        mark = "ok " if exists else "MISSING"
        note = "" if free else f"  (port {port} already in use)"
        if not exists:
            ok = False
        print(f"  {mark} {key:7} {folder:18} :{port}{note}")
    return ok


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--all", action="store_true",
                        help="start the standalone apps as well")
    parser.add_argument("--only", metavar="APP",
                        help="start just one: " + "|".join(APPS))
    parser.add_argument("--check", action="store_true",
                        help="verify setup without starting")
    parser.add_argument("--list", action="store_true",
                        help="list the apps and ports")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    if args.list:
        for key, (folder, _, port, what, default) in APPS.items():
            tag = "default" if default else "with --all"
            print(f"{key:7} :{port}  {what}   [{tag}]")
        return 0

    if args.check:
        return 0 if check() else 1

    if args.only:
        if args.only not in APPS:
            print(f"Unknown app '{args.only}'. Choose from: {', '.join(APPS)}")
            return 1
        wanted = [args.only]
    elif args.all:
        wanted = list(APPS)
    else:
        wanted = [k for k, v in APPS.items() if v[4]]

    print(f"Python : {sys.version.split()[0]}")
    print(f"Using  : {sys.executable}\n")

    # Refuse to start anything if a port is taken -- half-started is worse.
    clashes = [(k, APPS[k][2]) for k in wanted if not port_free(APPS[k][2])]
    if clashes:
        for key, port in clashes:
            print(f"Port {port} is already in use ({key}).")
        print("\nStop whatever is using it, or start the others with --only.")
        return 1

    missing = [k for k in wanted
               if not os.path.exists(os.path.join(app_dir(k), APPS[k][1] + ".py"))]
    if missing:
        print("Missing app folders: " + ", ".join(missing))
        return 1

    procs = {}
    try:
        for key in wanted:
            port = APPS[key][2]
            print(f"Starting {key:7} on http://127.0.0.1:{port} ...")
            procs[key] = start(key, port)

        # The first app to load pulls in the ONNX models, so give it room.
        ready = []
        for key in wanted:
            port = APPS[key][2]
            if procs[key].poll() is not None:
                print(f"  {key}: exited immediately (code {procs[key].returncode})")
                continue
            if wait_until_up(port):
                ready.append(key)
                print(f"  {key}: ready")
            else:
                print(f"  {key}: did not answer in time (it may still be loading)")

        if not ready:
            print("\nNothing came up. Run 'python run.py --check' to see why.")
            return 1

        main_key = MAIN if MAIN in ready else ready[0]
        url = f"http://127.0.0.1:{APPS[main_key][2]}"
        print("\n" + "=" * 58)
        for key in ready:
            print(f"  {APPS[key][3]}\n      http://127.0.0.1:{APPS[key][2]}")
        print("=" * 58)
        print(f"\nOpening {url}")
        print("Press Ctrl+C to stop everything.\n")
        if not args.no_browser:
            threading.Timer(0.8, lambda: webbrowser.open(url)).start()

        # Stay alive until Ctrl+C, and notice if a child dies.
        while True:
            for key, p in list(procs.items()):
                if p.poll() is not None:
                    print(f"{key} stopped (code {p.returncode}).")
                    procs.pop(key)
            if not procs:
                print("All apps have stopped.")
                return 1
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping...")
        return 0
    finally:
        for key, p in procs.items():
            if p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=6)
                except Exception:             # noqa: BLE001
                    p.kill()
        print("Stopped.")


if __name__ == "__main__":
    sys.exit(main())
