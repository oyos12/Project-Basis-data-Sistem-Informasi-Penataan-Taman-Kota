# run_both.py
import os
import sys
import signal
import socket
import threading
import subprocess
from pathlib import Path
from shutil import which

PY = sys.executable or "python"

ROOT = Path(__file__).resolve().parent

# You can override these paths via environment variables if needed
APP  = os.environ.get("APP_PATH")  or str(ROOT / "app.py")            # MySQL-backed API (port 5000)
AUTH = os.environ.get("AUTH_PATH") or str(ROOT / "auth_sqlite.py")    # SQLite auth API (port 5001)
INIT = os.environ.get("INIT_DB_PATH") or str(ROOT / "init_db.py")     # DB initializer (optional)

PORT_APP  = int(os.environ.get("APP_PORT", 5000))
PORT_AUTH = int(os.environ.get("AUTH_PORT", 5001))

env_app = os.environ.copy()
env_auth = os.environ.copy()
env_app["PYTHONUNBUFFERED"] = "1"
env_auth["PYTHONUNBUFFERED"] = "1"
# location for auth sqlite file can be overridden via ENV
env_auth.setdefault("AUTH_SQLITE_PATH", str(ROOT / "auth.sqlite3"))

def stream(prefix: str, proc: subprocess.Popen):
    for line in iter(proc.stdout.readline, b""):
        try:
            sys.stdout.write(f"[{prefix}] {line.decode(errors='replace')}")
        except Exception:
            # Fallback raw
            sys.stdout.write(f"[{prefix}] {line!r}\n")
    try:
        proc.stdout.close()
    except Exception:
        pass

def start(cmd, env, prefix: str) -> subprocess.Popen:
    """
    Start a python subprocess and stream its output with a prefix.
    Creates a new process group for easier termination on all platforms.
    """
    creationflags = 0
    preexec = None
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # so we can send CTRL_BREAK_EVENT
    else:
        # start in a new process group on POSIX
        preexec = os.setsid

    p = subprocess.Popen(
        [PY, "-u"] + cmd,
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=False,
        creationflags=creationflags,
        preexec_fn=preexec,
    )
    t = threading.Thread(target=stream, args=(prefix, p), daemon=True)
    t.start()
    return p

# -------------------------
# Optional: run DB initializer once
# -------------------------
def run_init_db():
    """
    Run the database initializer once before starting services.
    - Set SKIP_INIT_DB=1 to skip.
    - Override script path with INIT_DB_PATH env var.
    """
    if os.environ.get("SKIP_INIT_DB") == "1":
        print("[INIT] Skipping DB initialization (SKIP_INIT_DB=1).")
        return

    candidates = [os.environ.get("INIT_DB_PATH"), str(ROOT / "init_db.py")]
    init_path = next((p for p in candidates if p and os.path.exists(p)), None)
    if not init_path:
        print("[INIT] init_db.py not found. Skipping DB initialization.")
        return

    print(f"[INIT] Running: {init_path}")
    proc = subprocess.run([PY, "-u", init_path], cwd=ROOT, env=env_app,
                          capture_output=True, text=True)
    if proc.stdout:
        for line in proc.stdout.splitlines():
            print(f"[INIT] {line}")
    if proc.stderr:
        for line in proc.stderr.splitlines():
            print(f"[INIT-ERR] {line}", file=sys.stderr)

    if proc.returncode != 0:
        print(f"[INIT] init_db exited with code {proc.returncode}", file=sys.stderr)
        # Uncomment to abort on failure:
        # sys.exit(proc.returncode)
    else:
        print("[INIT] Database initialization completed.")

# -------------------------
# Port helpers (optional kill-on-use)
# -------------------------
def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        try:
            return s.connect_ex((host, port)) == 0
        except Exception:
            return False

def kill_port_windows(port: int):
    ps = which("powershell")
    if not ps:
        print(f"[PORT] PowerShell not available; cannot free port {port} automatically.", file=sys.stderr)
        return
    cmd = [
        ps, "-NoProfile", "-Command",
        f"$p=(Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue).OwningProcess;"
        f"if($p){{ Stop-Process -Id $p -Force }}"
    ]
    subprocess.run(cmd, capture_output=True)

def kill_port_posix(port: int):
    # Try lsof first
    if which("lsof"):
        try:
            p = subprocess.run(["lsof", "-t", f"-i:{port}"], capture_output=True, text=True)
            pids = [int(x) for x in p.stdout.split() if x.strip().isdigit()]
            for pid in pids:
                try:
                    os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
        except Exception:
            pass
    else:
        print(f"[PORT] lsof not found; cannot free port {port} automatically.", file=sys.stderr)

def ensure_port_free(port: int):
    if not is_port_in_use(port):
        return
    if os.environ.get("KILL_PORTS") == "1":
        print(f"[PORT] Port {port} busy. Attempting to free it...")
        if os.name == "nt":
            kill_port_windows(port)
        else:
            kill_port_posix(port)
        if is_port_in_use(port):
            print(f"[PORT] Could not free port {port}. You may need to stop the process manually.", file=sys.stderr)
        else:
            print(f"[PORT] Port {port} freed.")
    else:
        print(f"[PORT] WARNING: Port {port} is already in use. Set KILL_PORTS=1 to auto-kill the holder.", file=sys.stderr)

# -------------------------
# Graceful shutdown & interactive quit
# -------------------------
def terminate_process(p: subprocess.Popen):
    if p.poll() is not None:
        return
    try:
        if os.name == "nt":
            # Send CTRL_BREAK to the process group; fallback to terminate
            try:
                p.send_signal(signal.CTRL_BREAK_EVENT)
            except Exception:
                p.terminate()
        else:
            # kill the whole group
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except Exception:
                p.terminate()
    except Exception:
        pass

def wait_for_quit(stop_callback):
    """
    Allow stopping both servers by typing 'q' + Enter in this terminal.
    """
    try:
        print("Type 'q' and press Enter to stop both servers.")
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            if line.strip().lower() in ("q", "quit", "exit"):
                stop_callback()
                break
    except Exception:
        # stdin might be closed; ignore
        pass

def main():
    # Optionally ensure ports are free
    ensure_port_free(PORT_APP)
    ensure_port_free(PORT_AUTH)

    # Run DB initializer first
    run_init_db()

    procs = []

    def stop_all():
        for p in procs:
            terminate_process(p)

    # Start interactive "q" listener
    tq = threading.Thread(target=wait_for_quit, args=(stop_all,), daemon=True)
    tq.start()

    try:
        procs.append(start([APP],  env_app,  f"DATA:{PORT_APP}"))
        procs.append(start([AUTH], env_auth, f"AUTH:{PORT_AUTH}"))

        # Wait for any process to exit
        while True:
            alive = [p for p in procs if p.poll() is None]
            if not alive:
                break
            for p in list(alive):
                try:
                    p.wait(timeout=0.5)
                except Exception:
                    pass
    finally:
        stop_all()
        # Ensure termination
        for p in procs:
            try:
                p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                except Exception:
                    pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
