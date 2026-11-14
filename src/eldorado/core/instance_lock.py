"""Only one live bot at a time (`eldorado app` or `eldorado bid run`).

Uses an OS file lock on logs/bot.lock. The OS releases it when the process ends, even after a
crash or a closed window, so a stale lock never blocks the next start.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from types import TracebackType
from typing import IO

from eldorado.core.exceptions import EldoradoError

DEFAULT_LOCK_PATH = Path("logs") / "bot.lock"


class BotAlreadyRunningError(EldoradoError):
    """Another bot already holds the lock."""


class BotLock:
    def __init__(self, path: Path = DEFAULT_LOCK_PATH) -> None:
        self.path = path
        self._fh: IO[str] | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = self.path.open("a+", encoding="utf-8")
        try:
            _lock(fh)
        except OSError:
            fh.close()
            raise BotAlreadyRunningError(
                "Another bot is already running (eldorado app or eldorado bid run in another "
                "window). Close it first: two bots would change the same prices twice."
            ) from None
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        self._fh = fh

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            _unlock(self._fh)
        finally:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> BotLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None,
                 tb: TracebackType | None) -> None:
        self.release()


if sys.platform == "win32":
    import msvcrt

    def _lock(fh: IO[str]) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock(fh: IO[str]) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock(fh: IO[str]) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock(fh: IO[str]) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
