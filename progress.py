from __future__ import annotations

import logging
import sys
import time


class Progress:
    def __init__(
        self,
        label: str,
        total: int,
        logger: logging.Logger,
        *,
        min_interval: float = 10.0,
        width: int = 24,
    ) -> None:
        self.label = label
        self.total = max(total, 0)
        self.logger = logger
        self.min_interval = min_interval
        self.width = width
        self.count = 0
        self._last_emit = 0.0
        self._started = False
        self._tty = sys.stderr.isatty()

    def start(self) -> None:
        if self.total <= 0 or self._started:
            return
        self._started = True
        self._last_emit = time.monotonic()
        self._emit(force=True)

    def advance(self, step: int = 1) -> None:
        if self.total <= 0:
            return
        if not self._started:
            self.start()
        self.count = min(self.count + step, self.total)
        now = time.monotonic()
        if self.count >= self.total or (now - self._last_emit) >= self.min_interval:
            self._last_emit = now
            self._emit(force=self.count >= self.total)

    def finish(self) -> None:
        if self.total <= 0:
            return
        if not self._started:
            self.start()
        if self.count < self.total:
            self.count = self.total
            self._emit(force=True)
        if self._tty:
            sys.stderr.write("\n")
            sys.stderr.flush()

    def _emit(self, *, force: bool) -> None:
        if not force and not self.logger.isEnabledFor(logging.INFO):
            return
        percent = (self.count / self.total) * 100 if self.total else 100.0
        if self._tty:
            filled = round(self.width * self.count / self.total)
            bar = "#" * filled + "-" * (self.width - filled)
            sys.stderr.write(
                f"\r{self.label}: [{bar}] {self.count}/{self.total} ({percent:5.1f}%)",
            )
            sys.stderr.flush()
            return
        self.logger.info("%s: %d/%d (%.1f%%)", self.label, self.count, self.total, percent)
