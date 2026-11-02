#!/usr/bin/env python3
"""Opt-in native Wayland keyboard supervisor. Never reads text-entry contents."""
import argparse
import fcntl
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

REQUIRED = frozenset({
    "zwlr_layer_shell_v1", "zwp_virtual_keyboard_manager_v1",
    "zwp_input_method_manager_v2", "zwp_text_input_manager_v3",
})


def missing_protocols(output):
    advertised = set(re.findall(r"interface:\s*['\"]([a-zA-Z0-9_]+)['\"]", output))
    return sorted(REQUIRED - advertised)


def keyboard_command(binary, height):
    if not 120 <= height <= 800:
        raise ValueError("Keyboard height must be between 120 and 800 logical pixels")
    return [binary, "--auto", "--hidden", "-H", str(height), "-L", str(height)]


def safe_environment(source):
    env = dict(source)
    # Protocol traces can contain password/surrounding-text data.
    env.pop("WAYLAND_DEBUG", None)
    env.pop("WVKBD_DEBUG", None)
    env["PICALENDAR_NATIVE_KEYBOARD"] = "1"
    return env


def check(binary, env):
    if not env.get("WAYLAND_DISPLAY") or not env.get("XDG_RUNTIME_DIR"):
        raise RuntimeError("Run inside the kiosk user's active Wayland session, not sudo")
    if not shutil.which(binary):
        raise RuntimeError("wvkbd missing; install a build supporting --auto and --hidden")
    if not shutil.which("wayland-info"):
        raise RuntimeError("Install wayland-utils to check compositor capabilities")
    info = subprocess.run(["wayland-info"], env=env, capture_output=True,
                          text=True, timeout=10)
    if info.returncode:
        raise RuntimeError("Cannot query the active Wayland compositor")
    missing = missing_protocols(info.stdout)
    if missing:
        raise RuntimeError("Compositor lacks: " + ", ".join(missing) +
                           ". Stock Cage may need replacement or protocol patches; "
                           "this draft does not change compositors automatically.")
    help_result = subprocess.run([binary, "--help"], env=env, capture_output=True,
                                 text=True, timeout=5)
    help_text = help_result.stdout + help_result.stderr
    if not all(option in help_text for option in ("--auto", "--hidden")):
        raise RuntimeError("Installed wvkbd is too old: --auto and --hidden required")


def stop(process):
    if process is None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def supervise(args):
    env = safe_environment(os.environ)
    command = keyboard_command(args.binary, args.height)
    check(args.binary, env)
    if args.check:
        print("Keyboard binary and Wayland protocol checks passed (not an end-to-end test)")
        return 0
    if not args.command:
        raise RuntimeError("Supply a kiosk command after --")
    runtime = Path(env["XDG_RUNTIME_DIR"])
    lock_path = runtime / "picalendar-touch-keyboard.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock_path, flags, 0o600)
    with os.fdopen(fd, "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("A PiCalendar touch-keyboard session is already running")
        requested_stop = False
        def request_stop(signum, frame):
            nonlocal requested_stop
            requested_stop = True
        previous = {s: signal.signal(s, request_stop) for s in (signal.SIGINT, signal.SIGTERM)}
        keyboard = kiosk = None
        try:
            # Never inherit debug/key-output flags or persist keyboard stdout/stderr.
            keyboard = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                        start_new_session=True)
            time.sleep(0.3)
            if keyboard.poll() is not None:
                raise RuntimeError("Keyboard failed to start (details intentionally not logged)")
            if requested_stop:
                return 130
            kiosk = subprocess.Popen(args.command, env=env, start_new_session=True)
            while not requested_stop:
                result = kiosk.poll()
                if result is not None:
                    return result
                if keyboard.poll() is not None:
                    raise RuntimeError("Keyboard exited; stopping touch kiosk rather than leaving unusable login")
                time.sleep(0.2)
            return 130
        finally:
            stop(kiosk)
            stop(keyboard)
            for signum, handler in previous.items():
                signal.signal(signum, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", default="wvkbd-deskintl")
    parser.add_argument("--height", type=int, default=300)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command[:1] == ["--"]:
        args.command = args.command[1:]
    try:
        return supervise(args)
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
        print("Touch keyboard: " + str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
