"""
Non-blocking key reads for the run board.

The board repaints in place, so the terminal's own scrollback cannot reach the table. Instead the
run reads keys itself: the arrows move a window over the samples in flight, and `q` stops
spawning new ones. Reading runs on a daemon thread and never blocks the pipeline; where there is
no terminal (a redirected log, a test, an IDE pane) `start()` simply does nothing.
"""
from __future__ import annotations

import queue
import sys
import threading

# Windows sends a prefix byte and then a code; POSIX sends an escape sequence.
WINDOWS_CODES = {"H": "up", "P": "down", "I": "pgup", "Q": "pgdn", "G": "home", "O": "end"}
POSIX_CODES = {"A": "up", "B": "down", "5~": "pgup", "6~": "pgdn", "H": "home", "F": "end", "1~": "home", "4~": "end"}
PLAIN_KEYS = {"q": "quit", "Q": "quit", "\x03": "quit"}   # Ctrl+C usually reaches the process as a signal; if the console hands it to us instead, stop cleanly


def decode_windows(prefix: str, code: str) -> str | None:
    """`msvcrt` returns '\\x00' or '\\xe0' first for a special key, then its code."""
    if prefix in ("\x00", "\xe0"):
        return WINDOWS_CODES.get(code)
    return PLAIN_KEYS.get(prefix)


def decode_posix(sequence: str) -> str | None:
    """'\\x1b[A' and friends; anything else falls through to the plain keys."""
    if sequence.startswith("\x1b["):
        return POSIX_CODES.get(sequence[2:])
    return PLAIN_KEYS.get(sequence)


class KeyReader:
    """Keys the board has not handled yet. `drain()` returns them in order and empties the queue."""

    def __init__(self) -> None:
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._restore = None
        self.reason: str | None = None      # why key reading is off, when it is

    @property
    def active(self) -> bool:
        return self._thread is not None

    def unavailable_reason(self) -> str | None:
        """None when keys can be read, otherwise why they cannot."""
        if sys.platform == "win32":
            # The console hands keys to the process through CONIN$, whatever stdin is bound to,
            # so ask it rather than trusting isatty: a wrapper can redirect stdin and keys still work.
            try:
                import msvcrt

                msvcrt.kbhit()
                return None
            except Exception as e:  # noqa: BLE001
                return f"no console attached ({type(e).__name__})"
        try:
            if sys.stdin is None or not sys.stdin.isatty():
                return "the input is not a terminal"
        except (AttributeError, ValueError) as e:
            return f"the input cannot be read ({type(e).__name__})"
        return None

    def available(self) -> bool:
        return self.unavailable_reason() is None

    def push(self, key: str) -> None:
        self._queue.put(key)

    def drain(self) -> list[str]:
        keys = []
        while True:
            try:
                keys.append(self._queue.get_nowait())
            except queue.Empty:
                return keys

    def start(self) -> bool:
        if self._thread is not None:
            return False
        self.reason = self.unavailable_reason()
        if self.reason is not None:
            return False
        loop = self._windows_loop if sys.platform == "win32" else self._posix_loop
        try:
            loop_ready = loop is self._windows_loop or self._posix_setup()
        except Exception:  # noqa: BLE001
            return False
        if not loop_ready:
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=loop, name="key-reader", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        self._thread = None
        if self._restore is not None:
            restore, self._restore = self._restore, None
            try:
                restore()
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ platform loops
    def _windows_loop(self) -> None:
        import msvcrt

        while not self._stop.is_set():
            if not msvcrt.kbhit():
                self._stop.wait(0.05)
                continue
            char = msvcrt.getwch()
            key = decode_windows(char, msvcrt.getwch() if char in ("\x00", "\xe0") else "")
            if key:
                self.push(key)

    def _posix_setup(self) -> bool:
        import termios
        import tty

        fd = sys.stdin.fileno()
        saved = termios.tcgetattr(fd)
        self._restore = lambda: termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        tty.setcbreak(fd)
        return True

    def _posix_loop(self) -> None:
        import select

        while not self._stop.is_set():
            if not select.select([sys.stdin], [], [], 0.05)[0]:
                continue
            char = sys.stdin.read(1)
            sequence = char
            if char == "\x1b":
                while select.select([sys.stdin], [], [], 0.01)[0]:
                    sequence += sys.stdin.read(1)
                    if sequence[-1].isalpha() or sequence[-1] == "~":
                        break
            key = decode_posix(sequence)
            if key:
                self.push(key)


def _demo() -> None:
    """Check that this terminal hands keys to a running program. Press keys; q or Ctrl+C ends it."""
    import time

    reader = KeyReader()
    if not reader.start():
        print(f"Keys cannot be read here: {reader.reason}.")
        print("The run board will not scroll in this terminal; use --plain instead, or start the run from a console window.")
        return
    print("Reading keys. Press the arrows, page up and page down, home, end. q ends this test.")
    try:
        while True:
            for key in reader.drain():
                print(f"  got: {key}")
                if key == "quit":
                    return
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        reader.stop()
        print("done.")


if __name__ == "__main__":
    _demo()


__all__ = ["KeyReader", "decode_posix", "decode_windows", "POSIX_CODES", "WINDOWS_CODES"]
