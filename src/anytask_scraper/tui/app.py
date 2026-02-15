"""Main TUI application for anytask-scraper."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from textual import work
from textual.app import App
from textual.binding import Binding

from anytask_scraper.client import AnytaskClient
from anytask_scraper.models import Course, Gradebook, ReviewQueue

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".config" / "anytask-scraper"
COURSES_FILE = CONFIG_DIR / "courses.json"
SESSION_FILE = ".anytask_session.json"

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
    gradebook_cache: dict[int, Gradebook] = {}

    def __init__(self) -> None:
        super().__init__()
        self._last_ctrl_c: float = 0.0

    def on_mount(self) -> None:
        settings = self._load_settings()
        if settings.get("auto_login_session", False):
            session_path = settings.get("session_file", SESSION_FILE)
            if isinstance(session_path, str):
                session = Path(session_path)
                if session.exists():
                    self._auto_login(str(session))
                    return
        from anytask_scraper.tui.screens.login import LoginScreen

        self.push_screen(LoginScreen())

    def on_unmount(self) -> None:
        if self.client is not None:
            if self.session_path:
                try:
                    self.client.save_session(self.session_path)
                except Exception:
                    logger.debug("Failed to save session on unmount", exc_info=True)
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
            logger.debug("Failed to save course IDs", exc_info=True)

    def load_course_ids(self) -> list[int]:
        """Load saved course IDs from config file."""
        try:
            if not COURSES_FILE.exists():
                return []
            raw = json.loads(COURSES_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return [int(x) for x in raw if isinstance(x, int)]
        except Exception:
            logger.debug("Failed to load course IDs", exc_info=True)
        return []

    def remove_course_id(self, course_id: int) -> None:
        """Remove a course ID from persistence and memory."""
        self.courses.pop(course_id, None)
        self.queue_cache.pop(course_id, None)
        self.gradebook_cache.pop(course_id, None)
        self.save_course_ids()

    def _load_settings(self) -> dict[str, object]:
        """Load settings from .anytask_scraper_settings.json."""
        settings_path = Path(".anytask_scraper_settings.json")
        try:
            if settings_path.exists():
                data = json.loads(settings_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            logger.debug("Failed to load settings", exc_info=True)
        return {}

    @work(thread=True)
    def _auto_login(self, session_path: str) -> None:
        """Auto-login using saved session file."""
        logger.info("Attempting auto-login from %s", session_path)
        try:
            from anytask_scraper.client import AnytaskClient

            client = AnytaskClient()
            success = client.load_session(session_path)
            if success:
                self.client = client
                self.session_path = session_path
                logger.info("Auto-login successful")

                def _push_main() -> None:
                    from anytask_scraper.tui.screens.main import MainScreen

                    self.push_screen(MainScreen())

                self.call_from_thread(_push_main)
                return
        except Exception:
            logger.debug("Auto-login failed", exc_info=True)

        def _push_login() -> None:
            from anytask_scraper.tui.screens.login import LoginScreen

            self.push_screen(LoginScreen())

        self.call_from_thread(_push_login)
