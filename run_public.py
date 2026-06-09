"""Start LocalDocChat with a public Cloudflare tunnel URL."""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CLOUDFLARED = ROOT / "cloudflared.exe"
CLOUDFLARED_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/"
    "cloudflared-windows-amd64.exe"
)
PORT = 8090
PUBLIC_URL_FILE = ROOT / "public-url.txt"


def setup_env() -> None:
    os.chdir(ROOT)
    os.environ["PUBLIC_ACCESS"] = "true"
    os.environ["HOST"] = "0.0.0.0"


def kill_port(port: int) -> None:
    if sys.platform != "win32":
        return
    result = subprocess.run(
        ["netstat", "-ano"],
        capture_output=True,
        text=True,
        check=False,
    )
    pids: set[str] = set()
    for line in result.stdout.splitlines():
        if f":{port}" in line and "LISTENING" in line:
            parts = line.split()
            if parts:
                pids.add(parts[-1])
    for pid in pids:
        if pid.isdigit() and int(pid) != os.getpid():
            subprocess.run(
                ["taskkill", "/PID", pid, "/F"],
                capture_output=True,
                check=False,
            )


def wait_for_server(timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{PORT}/api/health", timeout=2
            ) as resp:
                if resp.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(0.5)
    return False


def ensure_cloudflared() -> Path:
    if CLOUDFLARED.exists():
        return CLOUDFLARED
    sibling = ROOT.parent / "SecureDocChat" / "cloudflared.exe"
    if sibling.exists():
        return sibling
    print("Downloading cloudflared...")
    urllib.request.urlretrieve(CLOUDFLARED_URL, CLOUDFLARED)
    return CLOUDFLARED


def main() -> int:
    setup_env()
    kill_port(PORT)
    time.sleep(1)

    print("Starting LocalDocChat server (Ollama + Qwen)...")
    log_file = open(ROOT / "server.log", "w", encoding="utf-8")
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(PORT),
            "--log-level",
            "warning",
        ],
        cwd=ROOT,
        env=os.environ.copy(),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    if not wait_for_server():
        print("ERROR: Server failed to start on port", PORT)
        server.terminate()
        return 1

    print(f"Server ready on http://127.0.0.1:{PORT}")

    cloudflared = ensure_cloudflared()
    print("\nCreating public tunnel (this may take 10-20 seconds)...")
    print("Using HTTP/2 protocol for better compatibility on mobile networks.\n")

    tunnel = subprocess.Popen(
        [
            str(cloudflared),
            "tunnel",
            "--protocol",
            "http2",
            "--url",
            f"http://127.0.0.1:{PORT}",
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    public_url: str | None = None
    url_pattern = re.compile(r"https://[\w-]+\.trycloudflare\.com")

    try:
        assert tunnel.stdout is not None
        for line in tunnel.stdout:
            print(line, end="")
            match = url_pattern.search(line)
            if match and public_url is None:
                public_url = match.group(0)
                PUBLIC_URL_FILE.write_text(public_url + "\n", encoding="utf-8")
                banner = (
                    "\n"
                    + "=" * 62
                    + f"\n  YOUR PUBLIC URL (open this on any device):\n  {public_url}\n"
                    + "=" * 62
                    + f"\n\n  Saved to: {PUBLIC_URL_FILE.name}\n"
                    + "  Do NOT use http://192.168.x.x:8090 from outside your Wi-Fi.\n"
                    + "  Keep this window open while using the app.\n"
                )
                print(banner, flush=True)
                if sys.platform == "win32":
                    os.startfile(PUBLIC_URL_FILE)  # noqa: S606

        return tunnel.wait() or 0
    except KeyboardInterrupt:
        print("\nShutting down...")
        return 0
    finally:
        tunnel.terminate()
        server.terminate()
        try:
            tunnel.wait(timeout=5)
        except subprocess.TimeoutExpired:
            tunnel.kill()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
        print("Stopped.")


if __name__ == "__main__":
    raise SystemExit(main())
