"""Composite filter bar widgets for Tasks and Queue tabs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Select


class TaskFilterBar(Widget):
    """Filter bar for the Tasks tab: text search + status + section selects."""

    @dataclass
    class Changed(Message):
        """Emitted when any filter value changes."""

        text: str
        status: str
        section: str

    @dataclass
    class Reset(Message):
        """Emitted when the filter bar is reset to defaults."""

    def __init__(
        self,
        statuses: list[str] | None = None,
        sections: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._statuses = statuses or []
        self._sections = sections or []

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search tasks...", id="task-filter-text")
        yield Select[str](
            [(s, s) for s in self._statuses],
            allow_blank=True,
            value=Select.BLANK,
            prompt="Status",
            id="task-filter-status",
        )
        yield Select[str](
            [(s, s) for s in self._sections],
            allow_blank=True,
            value=Select.BLANK,
            prompt="Section",
            id="task-filter-section",
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._emit_changed()

    def on_select_changed(self, event: Select.Changed) -> None:
        event.stop()
        self._emit_changed()

    def _emit_changed(self) -> None:
        text = self.query_one("#task-filter-text", Input).value.strip()
        status_val = self.query_one("#task-filter-status", Select).value
        section_val = self.query_one("#task-filter-section", Select).value

        status = "" if status_val is Select.BLANK else str(status_val)
        section = "" if section_val is Select.BLANK else str(section_val)

        self.post_message(self.Changed(text=text, status=status, section=section))

    def reset(self) -> None:
        """Clear text input and reset all selects to blank, then emit Changed and Reset."""
        self.query_one("#task-filter-text", Input).value = ""
        self.query_one("#task-filter-status", Select).value = Select.BLANK
        self.query_one("#task-filter-section", Select).value = Select.BLANK
        self._emit_changed()
        self.post_message(self.Reset())

    def save_state(self) -> dict[str, Any]:
        """Return current filter values as a dict for undo functionality."""
        return {
            "text": self.query_one("#task-filter-text", Input).value,
            "status": self.query_one("#task-filter-status", Select).value,
            "section": self.query_one("#task-filter-section", Select).value,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore filter values from a previously saved dict, then emit Changed."""
        self.query_one("#task-filter-text", Input).value = state.get("text", "")
        self.query_one("#task-filter-status", Select).value = state.get(
            "status", Select.BLANK
        )
        self.query_one("#task-filter-section", Select).value = state.get(
            "section", Select.BLANK
        )
        self._emit_changed()

    def focus_text(self) -> None:
        """Focus the text search input."""
        self.query_one("#task-filter-text", Input).focus()

    def focus_next_filter(self) -> bool:
        """Cycle forward. Returns False if already on last element."""
        focusable = [
            self.query_one("#task-filter-text", Input),
            self.query_one("#task-filter-status", Select),
            self.query_one("#task-filter-section", Select),
        ]
        for i, widget in enumerate(focusable):
            if widget.has_focus:
                if i == len(focusable) - 1:
                    return False
                focusable[i + 1].focus()
                return True
        focusable[0].focus()
        return True

    def focus_prev_filter(self) -> bool:
        """Cycle backward. Returns False if already on first element."""
        focusable = [
            self.query_one("#task-filter-text", Input),
            self.query_one("#task-filter-status", Select),
            self.query_one("#task-filter-section", Select),
        ]
        for i, widget in enumerate(focusable):
            if widget.has_focus:
                if i == 0:
                    return False
                focusable[i - 1].focus()
                return True
        focusable[-1].focus()
        return True

    def update_options(
        self,
        statuses: list[str],
        sections: list[str],
    ) -> None:
        """Repopulate select options when course changes."""
        self._statuses = statuses
        self._sections = sections

        status_select = self.query_one("#task-filter-status", Select)
        status_select.set_options([(s, s) for s in statuses])

        section_select = self.query_one("#task-filter-section", Select)
        section_select.set_options([(s, s) for s in sections])

        self.query_one("#task-filter-text", Input).value = ""


class QueueFilterBar(Widget):
    """Filter bar for the Queue tab: text + student + task + status selects."""

    @dataclass
    class Changed(Message):
        """Emitted when any filter value changes."""

        text: str
        student: str
        task: str
        status: str
        reviewer: str

    @dataclass
    class Reset(Message):
        """Emitted when the filter bar is reset to defaults."""

    def __init__(
        self,
        students: list[str] | None = None,
        tasks: list[str] | None = None,
        statuses: list[str] | None = None,
        reviewers: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._students = students or []
        self._tasks = tasks or []
        self._statuses = statuses or []
        self._reviewers = reviewers or []

    def compose(self) -> ComposeResult:
        yield Input(placeholder="Search queue...", id="queue-filter-text")
        yield Select[str](
            [(s, s) for s in self._students],
            allow_blank=True,
            value=Select.BLANK,
            prompt="Student",
            id="queue-filter-student",
        )
        yield Select[str](
            [(t, t) for t in self._tasks],
            allow_blank=True,
            value=Select.BLANK,
            prompt="Task",
            id="queue-filter-task",
        )
        yield Select[str](
            [(s, s) for s in self._statuses],
            allow_blank=True,
            value=Select.BLANK,
            prompt="Status",
            id="queue-filter-status",
        )
        yield Select[str](
            [(r, r) for r in self._reviewers],
            allow_blank=True,
            value=Select.BLANK,
            prompt="Reviewer",
            id="queue-filter-reviewer",
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        event.stop()
        self._emit_changed()

    def on_select_changed(self, event: Select.Changed) -> None:
        event.stop()
        self._emit_changed()

    def _emit_changed(self) -> None:
        text = self.query_one("#queue-filter-text", Input).value.strip()
        student_val = self.query_one("#queue-filter-student", Select).value
        task_val = self.query_one("#queue-filter-task", Select).value
        status_val = self.query_one("#queue-filter-status", Select).value
        reviewer_val = self.query_one("#queue-filter-reviewer", Select).value

        student = "" if student_val is Select.BLANK else str(student_val)
        task = "" if task_val is Select.BLANK else str(task_val)
        status = "" if status_val is Select.BLANK else str(status_val)
        reviewer = "" if reviewer_val is Select.BLANK else str(reviewer_val)

        self.post_message(
            self.Changed(
                text=text, student=student, task=task, status=status, reviewer=reviewer
            )
        )

    def reset(self) -> None:
        """Clear text input and reset all selects to blank, then emit Changed and Reset."""
        self.query_one("#queue-filter-text", Input).value = ""
        self.query_one("#queue-filter-student", Select).value = Select.BLANK
        self.query_one("#queue-filter-task", Select).value = Select.BLANK
        self.query_one("#queue-filter-status", Select).value = Select.BLANK
        self.query_one("#queue-filter-reviewer", Select).value = Select.BLANK
        self._emit_changed()
        self.post_message(self.Reset())

    def save_state(self) -> dict[str, Any]:
        """Return current filter values as a dict for undo functionality."""
        return {
            "text": self.query_one("#queue-filter-text", Input).value,
            "student": self.query_one("#queue-filter-student", Select).value,
            "task": self.query_one("#queue-filter-task", Select).value,
            "status": self.query_one("#queue-filter-status", Select).value,
            "reviewer": self.query_one("#queue-filter-reviewer", Select).value,
        }

    def restore_state(self, state: dict[str, Any]) -> None:
        """Restore filter values from a previously saved dict, then emit Changed."""
        self.query_one("#queue-filter-text", Input).value = state.get("text", "")
        self.query_one("#queue-filter-student", Select).value = state.get(
            "student", Select.BLANK
        )
        self.query_one("#queue-filter-task", Select).value = state.get(
            "task", Select.BLANK
        )
        self.query_one("#queue-filter-status", Select).value = state.get(
            "status", Select.BLANK
        )
        self.query_one("#queue-filter-reviewer", Select).value = state.get(
            "reviewer", Select.BLANK
        )
        self._emit_changed()

    def focus_text(self) -> None:
        """Focus the text search input."""
        self.query_one("#queue-filter-text", Input).focus()

    def focus_next_filter(self) -> bool:
        """Cycle forward. Returns False if already on last element."""
        focusable = [
            self.query_one("#queue-filter-text", Input),
            self.query_one("#queue-filter-student", Select),
            self.query_one("#queue-filter-task", Select),
            self.query_one("#queue-filter-status", Select),
            self.query_one("#queue-filter-reviewer", Select),
        ]
        for i, widget in enumerate(focusable):
            if widget.has_focus:
                if i == len(focusable) - 1:
                    return False
                focusable[i + 1].focus()
                return True
        focusable[0].focus()
        return True

    def focus_prev_filter(self) -> bool:
        """Cycle backward. Returns False if already on first element."""
        focusable = [
            self.query_one("#queue-filter-text", Input),
            self.query_one("#queue-filter-student", Select),
            self.query_one("#queue-filter-task", Select),
            self.query_one("#queue-filter-status", Select),
            self.query_one("#queue-filter-reviewer", Select),
        ]
        for i, widget in enumerate(focusable):
            if widget.has_focus:
                if i == 0:
                    return False
                focusable[i - 1].focus()
                return True
        focusable[-1].focus()
        return True

    def update_options(
        self,
        students: list[str],
        tasks: list[str],
        statuses: list[str],
        reviewers: list[str] | None = None,
    ) -> None:
        """Repopulate select options when queue data changes."""
        self._students = students
        self._tasks = tasks
        self._statuses = statuses
        if reviewers is not None:
            self._reviewers = reviewers

        self.query_one("#queue-filter-student", Select).set_options(
            [(s, s) for s in students]
        )
        self.query_one("#queue-filter-task", Select).set_options(
            [(t, t) for t in tasks]
        )
        self.query_one("#queue-filter-status", Select).set_options(
            [(s, s) for s in statuses]
        )
        if reviewers is not None:
            self.query_one("#queue-filter-reviewer", Select).set_options(
                [(r, r) for r in reviewers]
            )
        self.query_one("#queue-filter-text", Input).value = ""
