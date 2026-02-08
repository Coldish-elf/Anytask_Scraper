"""Main TUI application for anytask-scraper."""

from __future__ import annotations

import contextlib
import json
import time
from pathlib import Path

from textual.app import App
from textual.binding import Binding

from anytask_scraper.client import AnytaskClient
from anytask_scraper.models import Course, ReviewQueue

CONFIG_DIR = Path.home() / ".config" / "anytask-scraper"
COURSES_FILE = CONFIG_DIR / "courses.json"

_DOUBLE_PRESS_MS = 500


class AnytaskApp(App[None]):
    """Anytask Scraper TUI application."""

    TITLE = "Anytask Scraper"
    CSS_PATH = "app.tcss"

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit", show=True, priority=True),
        Binding("ctrl+c", "ctrl_c", "Ctrl+C x2 Quit", show=False, priority=True),
    ]

    client: AnytaskClient | None = None
    courses: dict[int, Course] = {}
    current_course: Course | None = None
    session_path: str = ""
    queue_cache: dict[int, ReviewQueue] = {}

    def __init__(self) -> None:
        super().__init__()
        self._last_ctrl_c: float = 0.0

    def on_mount(self) -> None:
        from anytask_scraper.tui.screens.login import LoginScreen

        self.push_screen(LoginScreen())

    def on_unmount(self) -> None:
        if self.client is not None:
            if self.session_path:
                with contextlib.suppress(Exception):
                    self.client.save_session(self.session_path)
            self.client.close()

    def action_ctrl_c(self) -> None:
        """Double Ctrl+C to quit."""
        now = time.monotonic()
        elapsed_ms = (now - self._last_ctrl_c) * 1000
        if elapsed_ms < _DOUBLE_PRESS_MS:
            self.exit()
        else:
            self._last_ctrl_c = now
            self.notify("Press Ctrl+C again to quit", timeout=2)

    def save_course_ids(self) -> None:
        """Persist course IDs to config file."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            ids = list(self.courses.keys())
            COURSES_FILE.write_text(json.dumps(ids, indent=2), encoding="utf-8")
        except Exception:
            pass

    def load_course_ids(self) -> list[int]:
        """Load saved course IDs from config file."""
        try:
            if not COURSES_FILE.exists():
                return []
            raw = json.loads(COURSES_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return [int(x) for x in raw if isinstance(x, int)]
        except Exception:
            pass
        return []

    def remove_course_id(self, course_id: int) -> None:
        """Remove a course ID from persistence and memory."""
        self.courses.pop(course_id, None)
        self.queue_cache.pop(course_id, None)
        self.save_course_ids()
