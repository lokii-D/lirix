from __future__ import annotations

import argparse
import os
import select
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GuardConfig:
    command: list[str]
    cwd: Path
    inactivity_seconds: int
    hard_timeout_seconds: int


def parse_args() -> GuardConfig:
    parser = argparse.ArgumentParser(description="Run pytest with inactivity watchdog")
    parser.add_argument("--cwd", default=".")
    parser.add_argument("--inactivity-seconds", type=int, default=180)
    parser.add_argument("--hard-timeout-seconds", type=int, default=1800)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error("missing command")
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    return GuardConfig(
        command=command,
        cwd=Path(args.cwd).resolve(),
        inactivity_seconds=args.inactivity_seconds,
        hard_timeout_seconds=args.hard_timeout_seconds,
    )


def main() -> int:
    cfg = parse_args()
    proc = subprocess.Popen(
        cfg.command,
        cwd=str(cfg.cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        preexec_fn=os.setsid if hasattr(os, "setsid") else None,
    )
    assert proc.stdout is not None
    last_output = time.monotonic()
    start = last_output

    try:
        while True:
            now = time.monotonic()
            if proc.poll() is not None:
                break

            ready, _, _ = select.select([proc.stdout], [], [], 1)
            if ready:
                line = proc.stdout.readline()
                if line:
                    last_output = time.monotonic()
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    continue

            if now - last_output > cfg.inactivity_seconds:
                print(
                    f"\n[watchdog] No pytest output for {cfg.inactivity_seconds}s; terminating.",
                    file=sys.stderr,
                )
                break
            if now - start > cfg.hard_timeout_seconds:
                print(
                    f"\n[watchdog] Hard timeout {cfg.hard_timeout_seconds}s reached; terminating.",
                    file=sys.stderr,
                )
                break
    finally:
        if proc.poll() is None:
            try:
                if hasattr(os, "killpg") and proc.pid:
                    os.killpg(proc.pid, signal.SIGTERM)
                else:
                    proc.terminate()
            except OSError:
                pass
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    if hasattr(os, "killpg") and proc.pid:
                        os.killpg(proc.pid, signal.SIGKILL)
                    else:
                        proc.kill()
                except OSError:
                    pass

    return proc.returncode if proc.returncode is not None else 124


if __name__ == "__main__":
    raise SystemExit(main())
