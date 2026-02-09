"""Unified main screen for anytask-scraper TUI - tabbed layout."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from rich.text import Text
from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Input,
    Label,
    OptionList,
    RadioButton,
    RadioSet,
    Select,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets.option_list import Option

from anytask_scraper.models import (
    Course,
    QueueEntry,
    ReviewQueue,
    Submission,
    Task,
)
from anytask_scraper.parser import (
    extract_csrf_from_queue_page,
    extract_issue_id_from_breadcrumb,
    parse_course_page,
    parse_submission_page,
    strip_html,
)
from anytask_scraper.storage import (
    save_course_csv,
    save_course_json,
    save_course_markdown,
    save_queue_csv,
    save_queue_json,
    save_queue_markdown,
    save_submissions_csv,
)
from anytask_scraper.tui.widgets.filter_bar import QueueFilterBar, TaskFilterBar

_STATUS_STYLES: dict[str, str] = {
    "Зачтено": "bold green",
    "На проверке": "bold yellow",
    "Не зачтено": "bold red",
    "Новый": "dim",
}

_QUEUE_STATUS_COLORS: dict[str, str] = {
    "success": "bold green",
    "warning": "bold yellow",
    "danger": "bold red",
    "info": "bold cyan",
    "default": "dim",
    "primary": "bold blue",
}


def _styled_status(status: str) -> Text:
    style = _STATUS_STYLES.get(status, "")
    return Text(status or "-", style=style)


def _styled_deadline(deadline: datetime | None) -> Text:
    if deadline is None:
        return Text("-", style="dim")
    label = deadline.strftime("%d.%m.%Y")
    now = datetime.now()
    if deadline < now:
        return Text(label, style="dim strike")
    if deadline < now + timedelta(days=3):
        return Text(label, style="bold yellow")
    return Text(label)


def _format_score(task: Task) -> str:
    parts: list[str] = []
    if task.score is not None:
        parts.append(str(task.score))
    if task.max_score is not None:
        parts.append(f"/{task.max_score}")
    return " ".join(parts) if parts else "-"


class MainScreen(Screen[None]):
    """Main screen: left course pane + right TabbedContent (Tasks|Queue|Export)."""

    BINDINGS = [
        Binding("tab", "cycle_focus", "Next", show=False),
        Binding("shift+tab", "cycle_focus_back", "Prev", show=False),
        Binding("1", "tab_tasks", "Tasks", show=False),
        Binding("2", "tab_queue", "Queue", show=False),
        Binding("3", "tab_export", "Export", show=False),
        Binding("a", "add_course", "Add", show=True),
        Binding("x", "remove_course", "Remove", show=True),
        Binding("h", "focus_left", show=False),
        Binding("l", "focus_right", show=False),
        Binding("ctrl+up", "focus_filter", show=False),
        Binding("ctrl+down", "focus_table", show=False),
        Binding("ctrl+right", "filter_next", show=False),
        Binding("ctrl+left", "filter_prev", show=False),
        Binding("slash", "focus_filter", "/ Filter", show=True),
        Binding("r", "reset_filters", "Reset", show=True),
        Binding("u", "undo_filters", "Undo", show=True),
        Binding("question_mark", "toggle_help", "? Help", show=True),
        Binding("escape", "dismiss_overlay", "Back", show=False),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._focus_left_pane = True
        self.all_tasks: list[Task] = []
        self.filtered_tasks: list[Task] = []
        self.is_teacher_view = False
        self._selected_course_id: int | None = None
        # Queue state
        self.all_queue_entries: list[QueueEntry] = []
        self.filtered_queue_entries: list[QueueEntry] = []
        self._queue_loaded_for: int | None = None
        # Filter undo stacks
        self._task_filter_undo: dict[str, Any] | None = None
        self._queue_filter_undo: dict[str, Any] | None = None
        self._queue_sort_column: int | None = None
        self._queue_sort_reverse = False
        # Help panel visible
        self._help_visible = False

    def compose(self) -> ComposeResult:
        client = getattr(self.app, "client", None)
        user = ""
        if client and hasattr(client, "username") and client.username:
            user = client.username

        yield Static(
            f"ANYTASK{('  ' + user) if user else ''}",
            id="header",
        )

        with Horizontal(id="body"):
            with Vertical(id="left-pane"):
                yield Static("Courses", id="left-title")
                yield OptionList(id="course-list")
                with Container(id="course-add-bar"):
                    yield Input(
                        placeholder="Course ID",
                        type="integer",
                        id="course-id-input",
                    )

            with (
                Vertical(id="right-pane"),
                TabbedContent("Tasks", "Queue", "Export", id="main-tabs"),
            ):
                with TabPane("Tasks", id="tasks-tab"):
                    yield TaskFilterBar(classes="filter-bar", id="task-filter-bar")
                    with Vertical(id="task-area"):
                        yield DataTable(id="task-table")
                        with Container(id="detail-pane"):
                            yield VerticalScroll(
                                Label("[dim]Select a task[/dim]"),
                                id="detail-scroll",
                            )

                with TabPane("Queue", id="queue-tab"):
                    yield QueueFilterBar(classes="filter-bar", id="queue-filter-bar")
                    yield Label(
                        "Select a teacher course to view queue",
                        id="queue-info-label",
                    )
                    with Horizontal(id="queue-body"):
                        yield DataTable(id="queue-table")
                        with Container(id="queue-detail-pane"):
                            yield VerticalScroll(
                                Label("[dim]Select a queue entry[/dim]"),
                                id="queue-detail-scroll",
                            )

                with TabPane("Export", id="export-tab"), Vertical(id="export-area"):
                    with Container(classes="option-group"):
                        yield Label("Export Type:", classes="option-label")
                        with RadioSet(id="export-type-set"):
                            yield RadioButton(
                                "Tasks", id="tasks-export-radio", value=True
                            )
                            yield RadioButton("Queue", id="queue-export-radio")
                            yield RadioButton("Submissions", id="subs-export-radio")
                    with Container(classes="option-group"):
                        yield Label("Format:", classes="option-label")
                        with RadioSet(id="format-set"):
                            yield RadioButton("JSON", id="json-radio", value=True)
                            yield RadioButton("Markdown", id="md-radio")
                            yield RadioButton("CSV", id="csv-radio")
                    with Container(classes="option-group", id="export-filter-group"):
                        yield Label("Filter (optional):", classes="option-label")
                        yield Select[str](
                            [],
                            allow_blank=True,
                            value=Select.BLANK,
                            prompt="Task",
                            id="export-filter-task",
                        )
                        yield Select[str](
                            [],
                            allow_blank=True,
                            value=Select.BLANK,
                            prompt="Status",
                            id="export-filter-status",
                        )
                        yield Select[str](
                            [],
                            allow_blank=True,
                            value=Select.BLANK,
                            prompt="Reviewer",
                            id="export-filter-reviewer",
                        )
                    with Container(classes="option-group"):
                        yield Label("Output Directory:", classes="option-label")
                        yield Input(value="./output", id="output-dir-input")
                    with Container(classes="button-row"):
                        yield Button("Export", variant="primary", id="export-btn")
                    yield Label("", id="export-status-label")

        yield Static("", id="help-panel")
        yield Static("", id="status-line")
        yield Footer()

    def on_mount(self) -> None:
        # Task table
        table = self.query_one("#task-table", DataTable)
        table.cursor_type = "row"
        table.zebra_stripes = True

        # Queue table
        qtable = self.query_one("#queue-table", DataTable)
        qtable.cursor_type = "row"
        qtable.zebra_stripes = True
        qtable.add_columns(
            "#", "Student", "Task", "Status", "Reviewer", "Updated", "Grade"
        )

        self.query_one("#course-list", OptionList).focus()

        saved_ids = self.app.load_course_ids()  # type: ignore[attr-defined]
        for cid in saved_ids:
            if cid not in self.app.courses:  # type: ignore[attr-defined]
                self._fetch_course(cid)

    #  Inline status line

    def _show_status(
        self, message: str, kind: str = "info", timeout: float = 4
    ) -> None:
        """Show an inline message in the status line."""
        line = self.query_one("#status-line", Static)
        style_map = {
            "error": "[bold red]",
            "warning": "[bold yellow]",
            "success": "[bold green]",
            "info": "[dim]",
        }
        prefix = style_map.get(kind, "[dim]")
        close = prefix.replace("[", "[/")
        line.update(f"{prefix}{message}{close}")
        if timeout > 0:
            self.set_timer(timeout, self._clear_status)

    def _clear_status(self) -> None:
        self.query_one("#status-line", Static).update("")

    #  Help panel

    def action_toggle_help(self) -> None:
        panel = self.query_one("#help-panel", Static)
        self._help_visible = not self._help_visible
        if self._help_visible:
            panel.update(
                "[bold]Navigation[/bold]\n"
                "  Tab / Shift+Tab   cycle focus\n"
                "  h / l             left / right pane\n"
                "  j / k             up / down\n"
                "  1 / 2 / 3         switch tabs\n"
                "\n"
                "[bold]Filters[/bold]\n"
                "  /                 focus filter\n"
                "  Ctrl+\u2190/\u2192          cycle filter fields\n"
                "  Ctrl+\u2191            jump to filters\n"
                "  Ctrl+\u2193            jump to table\n"
                "  r                 reset filters\n"
                "  u                 undo reset\n"
                "\n"
                "[bold]Actions[/bold]\n"
                "  a                 add course\n"
                "  x                 remove course\n"
                "  Enter             select / open\n"
                "  Esc               back / dismiss\n"
                "  Ctrl+Q            quit\n"
                "  Ctrl+C \u00d72         quit"
            )
            panel.add_class("visible")
        else:
            panel.update("")
            panel.remove_class("visible")

    #  Tab switching

    def action_tab_tasks(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "tasks-tab"
        self.query_one("#task-table", DataTable).focus()

    def action_tab_queue(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "queue-tab"
        self.query_one("#queue-table", DataTable).focus()

    def action_tab_export(self) -> None:
        self.query_one("#main-tabs", TabbedContent).active = "export-tab"
        self.query_one("#format-set", RadioSet).focus()

    @on(TabbedContent.TabActivated, "#main-tabs")
    def _tab_activated(self, event: TabbedContent.TabActivated) -> None:
        if event.pane.id == "queue-tab":
            self._maybe_load_queue()

    #  Focus cycling

    def _get_focus_order(self) -> list[str]:
        """Return IDs of focusable zones for current tab."""
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        zones = ["#course-list"]
        if active == "tasks-tab":
            zones += ["#task-filter-bar", "#task-table"]
        elif active == "queue-tab":
            zones += ["#queue-filter-bar", "#queue-table"]
        elif active == "export-tab":
            zones += ["#format-set", "#output-dir-input"]
        return zones

    def action_cycle_focus(self) -> None:
        focused = self.focused
        if focused is not None:
            tabs = self.query_one("#main-tabs", TabbedContent)
            active = tabs.active
            # If in filter bar, try cycling within it first
            if active == "tasks-tab":
                task_bar = self.query_one("#task-filter-bar", TaskFilterBar)
                if focused in task_bar.walk_children():
                    if task_bar.focus_next_filter():
                        return
                    # Last filter element -- go to table
                    self.query_one("#task-table", DataTable).focus()
                    return
            elif active == "queue-tab":
                queue_bar = self.query_one("#queue-filter-bar", QueueFilterBar)
                if focused in queue_bar.walk_children():
                    if queue_bar.focus_next_filter():
                        return
                    self.query_one("#queue-table", DataTable).focus()
                    return

        # Default zone cycling
        zones = self._get_focus_order()
        current = self._find_current_zone(zones)
        next_idx = (current + 1) % len(zones)
        self._focus_zone(zones[next_idx])

    def action_cycle_focus_back(self) -> None:
        focused = self.focused
        if focused is not None:
            tabs = self.query_one("#main-tabs", TabbedContent)
            active = tabs.active
            # If in filter bar, try cycling backward within it first
            if active == "tasks-tab":
                task_bar = self.query_one("#task-filter-bar", TaskFilterBar)
                if focused in task_bar.walk_children():
                    if task_bar.focus_prev_filter():
                        return
                    # First filter element -- go to course list
                    self.query_one("#course-list", OptionList).focus()
                    return
            elif active == "queue-tab":
                queue_bar = self.query_one("#queue-filter-bar", QueueFilterBar)
                if focused in queue_bar.walk_children():
                    if queue_bar.focus_prev_filter():
                        return
                    self.query_one("#course-list", OptionList).focus()
                    return

        # Default zone cycling
        zones = self._get_focus_order()
        current = self._find_current_zone(zones)
        prev_idx = (current - 1) % len(zones)
        self._focus_zone(zones[prev_idx])

    def _find_current_zone(self, zones: list[str]) -> int:
        focused = self.focused
        if focused is None:
            return -1
        for i, zone_id in enumerate(zones):
            try:
                widget = self.query_one(zone_id)
                if widget is focused or focused in widget.walk_children():
                    return i
            except Exception:
                continue
        return -1

    def _focus_zone(self, zone_id: str) -> None:
        if zone_id == "#task-filter-bar":
            self.query_one("#task-filter-bar", TaskFilterBar).focus_text()
            self._focus_left_pane = False
        elif zone_id == "#queue-filter-bar":
            self.query_one("#queue-filter-bar", QueueFilterBar).focus_text()
            self._focus_left_pane = False
        elif zone_id == "#course-list":
            self.query_one("#course-list", OptionList).focus()
            self._focus_left_pane = True
        elif zone_id == "#task-table":
            self.query_one("#task-table", DataTable).focus()
            self._focus_left_pane = False
        elif zone_id == "#queue-table":
            self.query_one("#queue-table", DataTable).focus()
            self._focus_left_pane = False
        elif zone_id == "#format-set":
            self.query_one("#format-set", RadioSet).focus()
            self._focus_left_pane = False
        elif zone_id == "#output-dir-input":
            self.query_one("#output-dir-input", Input).focus()
            self._focus_left_pane = False

    def action_focus_left(self) -> None:
        self._focus_left_pane = True
        self.query_one("#course-list", OptionList).focus()

    def action_focus_right(self) -> None:
        self._focus_left_pane = False
        self.action_focus_table()

    def action_focus_filter(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        if active == "tasks-tab":
            self.query_one("#task-filter-bar", TaskFilterBar).focus_text()
        elif active == "queue-tab":
            self.query_one("#queue-filter-bar", QueueFilterBar).focus_text()

    def action_focus_table(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        if active == "tasks-tab":
            self.query_one("#task-table", DataTable).focus()
        elif active == "queue-tab":
            self.query_one("#queue-table", DataTable).focus()
        elif active == "export-tab":
            self.query_one("#output-dir-input", Input).focus()

    def action_filter_next(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        if active == "tasks-tab":
            self.query_one("#task-filter-bar", TaskFilterBar).focus_next_filter()
        elif active == "queue-tab":
            self.query_one("#queue-filter-bar", QueueFilterBar).focus_next_filter()

    def action_filter_prev(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        if active == "tasks-tab":
            self.query_one("#task-filter-bar", TaskFilterBar).focus_prev_filter()
        elif active == "queue-tab":
            self.query_one("#queue-filter-bar", QueueFilterBar).focus_prev_filter()

    #  Key mappings (j/k)

    def on_key(self, event: object) -> None:
        from textual.events import Key

        if not isinstance(event, Key):
            return

        focused = self.focused
        if focused is None:
            return

        if isinstance(focused, (OptionList, DataTable)):
            if event.key == "j":
                event.prevent_default()
                focused.action_cursor_down()
            elif event.key == "k":
                event.prevent_default()
                focused.action_cursor_up()

    #  Filter reset / undo

    def action_reset_filters(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        if active == "tasks-tab":
            task_bar = self.query_one("#task-filter-bar", TaskFilterBar)
            self._task_filter_undo = task_bar.save_state()
            task_bar.reset()
            self._show_status("Filters reset (u to undo)", kind="info", timeout=3)
        elif active == "queue-tab":
            queue_bar = self.query_one("#queue-filter-bar", QueueFilterBar)
            self._queue_filter_undo = queue_bar.save_state()
            queue_bar.reset()
            self._show_status("Filters reset (u to undo)", kind="info", timeout=3)

    def action_undo_filters(self) -> None:
        tabs = self.query_one("#main-tabs", TabbedContent)
        active = tabs.active
        if active == "tasks-tab" and self._task_filter_undo is not None:
            task_bar = self.query_one("#task-filter-bar", TaskFilterBar)
            task_bar.restore_state(self._task_filter_undo)
            self._task_filter_undo = None
            self._show_status("Filters restored", kind="success", timeout=3)
        elif active == "queue-tab" and self._queue_filter_undo is not None:
            queue_bar = self.query_one("#queue-filter-bar", QueueFilterBar)
            queue_bar.restore_state(self._queue_filter_undo)
            self._queue_filter_undo = None
            self._show_status("Filters restored", kind="success", timeout=3)
        else:
            self._show_status("Nothing to undo", kind="warning", timeout=2)

    #  Add course

    def action_add_course(self) -> None:
        bar = self.query_one("#course-add-bar")
        if "visible" in bar.classes:
            bar.remove_class("visible")
            self.query_one("#course-list", OptionList).focus()
        else:
            bar.add_class("visible")
            inp = self.query_one("#course-id-input", Input)
            inp.value = ""
            inp.focus()

    @on(Input.Submitted, "#course-id-input")
    def _submit_course_id(self) -> None:
        inp = self.query_one("#course-id-input", Input)
        try:
            course_id = int(inp.value.strip())
        except ValueError:
            self._show_status("Enter a valid course ID", kind="error")
            return

        if course_id in self.app.courses:  # type: ignore[attr-defined]
            self._show_status(f"Course {course_id} already loaded", kind="warning")
            return

        inp.value = ""
        self.query_one("#course-add-bar").remove_class("visible")
        self._show_status(f"Loading course {course_id}...")
        self._fetch_course(course_id)

    #  Remove course

    def action_remove_course(self) -> None:
        if self._selected_course_id is None:
            self._show_status("No course selected", kind="warning")
            return
        cid = self._selected_course_id
        self.app.remove_course_id(cid)  # type: ignore[attr-defined]

        option_list = self.query_one("#course-list", OptionList)
        option_list.clear_options()
        for course in self.app.courses.values():  # type: ignore[attr-defined]
            title = course.title or f"Course {course.course_id}"
            option_list.add_option(Option(title, id=str(course.course_id)))

        self._selected_course_id = None
        self.all_tasks = []
        self.filtered_tasks = []
        self._rebuild_task_table()
        self._clear_detail()
        self.all_queue_entries = []
        self.filtered_queue_entries = []
        self._rebuild_queue_table()
        self._clear_queue_detail()
        self._queue_loaded_for = None
        self.query_one("#queue-info-label", Label).update(
            "Select a teacher course to view queue"
        )
        self._show_status(f"Removed course {cid}", kind="success")

    #  Dismiss overlays on Escape

    def action_dismiss_overlay(self) -> None:
        add_bar = self.query_one("#course-add-bar")
        if "visible" in add_bar.classes:
            add_bar.remove_class("visible")
            self.query_one("#course-list", OptionList).focus()
            return
        help_panel = self.query_one("#help-panel", Static)
        if self._help_visible:
            self._help_visible = False
            help_panel.update("")
            help_panel.remove_class("visible")

    #  Course selection

    @on(OptionList.OptionSelected, "#course-list")
    def _course_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if option_id is None:
            return
        course_id = int(option_id)
        course = self.app.courses.get(course_id)  # type: ignore[attr-defined]
        if course is None:
            return

        self._selected_course_id = course_id
        self.app.current_course = course  # type: ignore[attr-defined]
        self.all_tasks = list(course.tasks)
        self.is_teacher_view = any(t.section for t in self.all_tasks)

        self.filtered_tasks = list(self.all_tasks)
        self._update_task_filter_options()
        self._setup_task_table_columns()
        self._rebuild_task_table()
        self._clear_detail()

        self._queue_loaded_for = None
        self.all_queue_entries = []
        self.filtered_queue_entries = []
        self._rebuild_queue_table()
        self._clear_queue_detail()

        if self.is_teacher_view:
            self.query_one("#queue-info-label", Label).update(
                "Switch to Queue tab to load"
            )
        else:
            self.query_one("#queue-info-label", Label).update(
                "Queue available for teacher courses only"
            )

        self._update_export_filters()

        tabs = self.query_one("#main-tabs", TabbedContent)
        if tabs.active == "queue-tab":
            self._maybe_load_queue()

    #  Task filter handling

    @on(TaskFilterBar.Changed)
    def _handle_task_filter(self, event: TaskFilterBar.Changed) -> None:
        needle = event.text.lower()
        self.filtered_tasks = [
            t
            for t in self.all_tasks
            if (not needle or needle in t.title.lower())
            and (not event.status or t.status == event.status)
            and (not event.section or t.section == event.section)
        ]
        self._rebuild_task_table()

    def _update_task_filter_options(self) -> None:
        statuses = sorted({t.status for t in self.all_tasks if t.status})
        sections = sorted({t.section for t in self.all_tasks if t.section})
        self.query_one("#task-filter-bar", TaskFilterBar).update_options(
            statuses, sections
        )

    #  Task selection

    @on(DataTable.RowHighlighted, "#task-table")
    def _task_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key.value is None:
            return
        try:
            idx = int(event.row_key.value) - 1
        except (ValueError, TypeError):
            return
        if 0 <= idx < len(self.filtered_tasks):
            self._show_detail(self.filtered_tasks[idx])

    @on(DataTable.RowSelected, "#task-table")
    def _task_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value is None:
            return
        try:
            idx = int(event.row_key.value) - 1
        except (ValueError, TypeError):
            return
        if 0 <= idx < len(self.filtered_tasks):
            self._show_detail(self.filtered_tasks[idx])

    #  Queue filter handling

    @on(QueueFilterBar.Changed)
    def _handle_queue_filter(self, event: QueueFilterBar.Changed) -> None:
        needle = event.text.lower()
        self.filtered_queue_entries = [
            e
            for e in self.all_queue_entries
            if (
                not needle
                or needle in e.student_name.lower()
                or needle in e.task_title.lower()
            )
            and (not event.student or e.student_name == event.student)
            and (not event.task or e.task_title == event.task)
            and (not event.status or e.status_name == event.status)
            and (not event.reviewer or e.responsible_name == event.reviewer)
        ]
        self._rebuild_queue_table()

    def _update_queue_filter_options(self) -> None:
        students = sorted(
            {e.student_name for e in self.all_queue_entries if e.student_name}
        )
        tasks = sorted({e.task_title for e in self.all_queue_entries if e.task_title})
        statuses = sorted(
            {e.status_name for e in self.all_queue_entries if e.status_name}
        )
        reviewers = sorted(
            {e.responsible_name for e in self.all_queue_entries if e.responsible_name}
        )
        self.query_one("#queue-filter-bar", QueueFilterBar).update_options(
            students, tasks, statuses, reviewers
        )

    #  Queue row highlight → auto-load preview

    @on(DataTable.RowHighlighted, "#queue-table")
    def _queue_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        if event.row_key.value is None:
            return
        issue_url = event.row_key.value
        entry = next(
            (e for e in self.all_queue_entries if e.issue_url == issue_url),
            None,
        )
        if entry and entry.has_issue_access and entry.issue_url:
            self._load_queue_preview(entry)
        elif entry:
            self._show_queue_preview_info(entry)

    @on(DataTable.RowSelected, "#queue-table")
    def _queue_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.row_key.value is None:
            return
        issue_url = event.row_key.value
        entry = next(
            (e for e in self.all_queue_entries if e.issue_url == issue_url),
            None,
        )
        if entry and entry.has_issue_access and entry.issue_url:
            self._fetch_and_show_submission(entry)

    def _show_queue_preview_info(self, entry: QueueEntry) -> None:
        """Show basic queue entry info when no issue access."""
        scroll = self.query_one("#queue-detail-scroll", VerticalScroll)
        scroll.remove_children()
        scroll.mount(
            Label(
                f"[bold]{entry.task_title}[/bold]",
                classes="detail-heading",
            )
        )
        scroll.mount(Label(f"Student: {entry.student_name}", classes="detail-text"))
        scroll.mount(Label(f"Status: {entry.status_name}", classes="detail-text"))
        scroll.mount(
            Label(
                f"Reviewer: {entry.responsible_name or '-'}",
                classes="detail-text",
            )
        )
        scroll.mount(Label(f"Updated: {entry.update_time}", classes="detail-text"))
        scroll.mount(Label(f"Grade: {entry.mark or '-'}", classes="detail-text"))

    @work(thread=True)
    def _load_queue_preview(self, entry: QueueEntry) -> None:
        """Auto-load submission preview for queue detail pane."""
        try:
            # Check cache first
            if self._selected_course_id is not None:
                cache = self.app.queue_cache.get(  # type: ignore[attr-defined]
                    self._selected_course_id
                )
                if cache and entry.issue_url in cache.submissions:
                    sub = cache.submissions[entry.issue_url]
                    self.app.call_from_thread(self._render_queue_preview, sub)
                    return

            client = self.app.client  # type: ignore[attr-defined]
            if not client:
                return

            # Show loading state
            self.app.call_from_thread(self._show_queue_preview_loading, entry)

            html = client.fetch_submission_page(entry.issue_url)
            issue_id = extract_issue_id_from_breadcrumb(html)
            if issue_id == 0:
                self.app.call_from_thread(self._show_queue_preview_info, entry)
                return

            sub = parse_submission_page(html, issue_id)

            # Cache it
            if self._selected_course_id is not None:
                cache = self.app.queue_cache.get(  # type: ignore[attr-defined]
                    self._selected_course_id
                )
                if cache:
                    cache.submissions[entry.issue_url] = sub

            self.app.call_from_thread(self._render_queue_preview, sub)
        except Exception:
            self.app.call_from_thread(self._show_queue_preview_info, entry)

    def _show_queue_preview_loading(self, entry: QueueEntry) -> None:
        scroll = self.query_one("#queue-detail-scroll", VerticalScroll)
        scroll.remove_children()
        scroll.mount(
            Label(
                f"[bold]{entry.task_title}[/bold]",
                classes="detail-heading",
            )
        )
        scroll.mount(Label(f"Student: {entry.student_name}", classes="detail-text"))
        scroll.mount(Label("[dim]Loading...[/dim]", classes="detail-text"))

    def _render_queue_preview(self, sub: Submission) -> None:
        """Render submission preview in the queue detail pane."""
        scroll = self.query_one("#queue-detail-scroll", VerticalScroll)
        scroll.remove_children()

        scroll.mount(Label(f"[bold]{sub.task_title}[/bold]", classes="detail-heading"))
        scroll.mount(Label(f"Student: {sub.student_name}", classes="detail-text"))
        scroll.mount(
            Label(
                f"Reviewer: {sub.reviewer_name or '-'}",
                classes="detail-text",
            )
        )
        scroll.mount(
            Label(
                f"Status: {sub.status}  |  Grade: {sub.grade}/{sub.max_score}",
                classes="detail-text",
            )
        )
        if sub.deadline:
            scroll.mount(Label(f"Deadline: {sub.deadline}", classes="detail-text"))

        if sub.comments:
            scroll.mount(
                Label(
                    f"\n[bold]Comments ({len(sub.comments)})[/bold]",
                    classes="detail-heading",
                )
            )
            for comment in sub.comments:
                ts = (
                    comment.timestamp.strftime("%d.%m.%Y %H:%M")
                    if comment.timestamp
                    else "-"
                )
                after = (
                    " [bold red](LATE)[/bold red]" if comment.is_after_deadline else ""
                )
                scroll.mount(
                    Label(
                        f"[bold]{comment.author_name}[/bold] [dim]{ts}[/dim]{after}",
                        classes="detail-text",
                    )
                )
                if comment.content_html:
                    text = strip_html(comment.content_html)
                    if text:
                        scroll.mount(Label(text, classes="detail-text"))
                if comment.files:
                    fnames = ", ".join(f.filename for f in comment.files)
                    scroll.mount(
                        Label(
                            f"[dim]Files: {fnames}[/dim]",
                            classes="detail-text",
                        )
                    )

        scroll.mount(
            Label(
                "\n[dim]Press Enter for full view[/dim]",
                classes="detail-text",
            )
        )

    def _clear_queue_detail(self) -> None:
        scroll = self.query_one("#queue-detail-scroll", VerticalScroll)
        scroll.remove_children()
        scroll.mount(Label("[dim]Select a queue entry[/dim]"))

    #  Queue column sorting

    @on(DataTable.HeaderSelected, "#queue-table")
    def _queue_header_selected(self, event: DataTable.HeaderSelected) -> None:
        col_idx = event.column_index
        if self._queue_sort_column == col_idx:
            self._queue_sort_reverse = not self._queue_sort_reverse
        else:
            self._queue_sort_column = col_idx
            self._queue_sort_reverse = False
        self._sort_and_rebuild_queue()

    def _sort_and_rebuild_queue(self) -> None:
        col = self._queue_sort_column
        if col is None:
            return
        key_map: dict[int, Any] = {
            0: lambda e: 0,
            1: lambda e: e.student_name.lower(),
            2: lambda e: e.task_title.lower(),
            3: lambda e: e.status_name.lower(),
            4: lambda e: e.responsible_name.lower(),
            5: lambda e: e.update_time,
            6: lambda e: e.mark,
        }
        key_fn = key_map.get(col)
        if key_fn:
            self.filtered_queue_entries.sort(
                key=key_fn, reverse=self._queue_sort_reverse
            )
            self._rebuild_queue_table()

    #  Export

    @on(RadioSet.Changed, "#export-type-set")
    def _export_type_changed(self, event: RadioSet.Changed) -> None:
        self._update_export_filters()

    def _update_export_filters(self) -> None:
        try:
            radioset = self.query_one("#export-type-set", RadioSet)
        except Exception:
            return
        btn = radioset.pressed_button
        if not btn:
            return

        export_type = btn.id or ""
        task_select = self.query_one("#export-filter-task", Select)
        status_select = self.query_one("#export-filter-status", Select)
        reviewer_select = self.query_one("#export-filter-reviewer", Select)

        task_select.set_options([])
        status_select.set_options([])
        reviewer_select.set_options([])

        if export_type == "tasks-export-radio":
            statuses = sorted({t.status for t in self.all_tasks if t.status})
            status_select.set_options([(s, s) for s in statuses])
            reviewer_select.disabled = True
            task_select.disabled = True
            status_select.disabled = False
        elif export_type in ("queue-export-radio", "subs-export-radio"):
            tasks = sorted(
                {e.task_title for e in self.all_queue_entries if e.task_title}
            )
            statuses = sorted(
                {e.status_name for e in self.all_queue_entries if e.status_name}
            )
            reviewers = sorted(
                {
                    e.responsible_name
                    for e in self.all_queue_entries
                    if e.responsible_name
                }
            )
            task_select.set_options([(t, t) for t in tasks])
            status_select.set_options([(s, s) for s in statuses])
            reviewer_select.set_options([(r, r) for r in reviewers])
            task_select.disabled = False
            status_select.disabled = False
            reviewer_select.disabled = False

    @on(Button.Pressed, "#export-btn")
    def _handle_export(self) -> None:
        if self._selected_course_id is None:
            self._set_export_status("Select a course first", "error")
            return

        format_set = self.query_one("#format-set", RadioSet)
        fmt_btn = format_set.pressed_button
        if not fmt_btn:
            self._set_export_status("Select a format", "error")
            return

        fmt_map = {"json-radio": "json", "md-radio": "markdown", "csv-radio": "csv"}
        fmt = fmt_map.get(fmt_btn.id or "", "json")

        type_set = self.query_one("#export-type-set", RadioSet)
        type_btn = type_set.pressed_button
        export_type = type_btn.id if type_btn else "tasks-export-radio"

        task_val = self.query_one("#export-filter-task", Select).value
        status_val = self.query_one("#export-filter-status", Select).value
        reviewer_val = self.query_one("#export-filter-reviewer", Select).value
        filters = {
            "task": "" if task_val is Select.BLANK else str(task_val),
            "status": "" if status_val is Select.BLANK else str(status_val),
            "reviewer": "" if reviewer_val is Select.BLANK else str(reviewer_val),
        }

        output_dir = (
            self.query_one("#output-dir-input", Input).value.strip() or "./output"
        )
        output_path = Path(output_dir).expanduser().resolve()

        self._set_export_status(f"Exporting to {output_path}...", "info")
        self._do_export(fmt, output_path, export_type or "tasks-export-radio", filters)

    def _set_export_status(self, message: str, kind: str = "info") -> None:
        label = self.query_one("#export-status-label", Label)
        label.update(message)
        label.remove_class("error", "success", "info")
        label.add_class(kind)

    @work(thread=True)
    def _do_export(
        self,
        fmt: str,
        output_path: Path,
        export_type: str = "tasks-export-radio",
        filters: dict[str, str] | None = None,
    ) -> None:
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            filters = filters or {}
            course_id = self._selected_course_id or 0

            if export_type == "tasks-export-radio":
                course = self.app.current_course  # type: ignore[attr-defined]
                if not course:
                    self.app.call_from_thread(
                        self._set_export_status, "No course selected", "error"
                    )
                    return

                tasks = list(course.tasks)
                if filters.get("status"):
                    tasks = [t for t in tasks if t.status == filters["status"]]

                filtered_course = Course(
                    course_id=course.course_id,
                    title=course.title,
                    teachers=list(course.teachers),
                    tasks=tasks,
                )

                if fmt == "json":
                    saved = save_course_json(filtered_course, output_path)
                elif fmt == "csv":
                    saved = save_course_csv(filtered_course, output_path)
                else:
                    saved = save_course_markdown(filtered_course, output_path)

            elif export_type == "queue-export-radio":
                entries = list(self.all_queue_entries)
                if filters.get("task"):
                    entries = [e for e in entries if e.task_title == filters["task"]]
                if filters.get("status"):
                    entries = [e for e in entries if e.status_name == filters["status"]]
                if filters.get("reviewer"):
                    entries = [
                        e for e in entries if e.responsible_name == filters["reviewer"]
                    ]

                queue = ReviewQueue(course_id=course_id, entries=entries)

                if fmt == "json":
                    saved = save_queue_json(queue, output_path)
                elif fmt == "csv":
                    saved = save_queue_csv(queue, output_path)
                else:
                    saved = save_queue_markdown(queue, output_path)

            elif export_type == "subs-export-radio":
                cache = self.app.queue_cache.get(course_id)  # type: ignore[attr-defined]
                if not cache or not cache.submissions:
                    self.app.call_from_thread(
                        self._set_export_status,
                        "No submissions loaded. Open queue entries first.",
                        "error",
                    )
                    return

                subs = list(cache.submissions.values())
                if filters.get("task"):
                    subs = [s for s in subs if s.task_title == filters["task"]]
                if filters.get("status"):
                    subs = [s for s in subs if s.status == filters["status"]]
                if filters.get("reviewer"):
                    subs = [s for s in subs if s.reviewer_name == filters["reviewer"]]

                if fmt == "csv":
                    saved = save_submissions_csv(subs, course_id, output_path)
                elif fmt == "json":
                    import json as json_mod
                    from dataclasses import asdict

                    saved = output_path / f"submissions_{course_id}.json"
                    saved.write_text(
                        json_mod.dumps(
                            [asdict(s) for s in subs],
                            indent=2,
                            default=str,
                            ensure_ascii=False,
                        )
                    )
                else:
                    queue = ReviewQueue(
                        course_id=course_id,
                        submissions={s.student_url or str(s.issue_id): s for s in subs},
                    )
                    saved = save_queue_markdown(queue, output_path)
            else:
                self.app.call_from_thread(
                    self._set_export_status, "Unknown export type", "error"
                )
                return

            self.app.call_from_thread(
                self._set_export_status,
                f"Saved: {saved.name if hasattr(saved, 'name') else saved}",
                "success",
            )
        except Exception as e:
            self.app.call_from_thread(
                self._set_export_status,
                f"Export failed: {e}",
                "error",
            )

    #  Data fetching

    @work(thread=True)
    def _fetch_course(self, course_id: int) -> None:
        try:
            client = self.app.client  # type: ignore[attr-defined]
            if not client:
                self.app.call_from_thread(self._show_status, "No client", kind="error")
                return

            html = client.fetch_course_page(course_id)
            course = parse_course_page(html, course_id)

            self.app.courses[course_id] = course  # type: ignore[attr-defined]
            self.app.call_from_thread(
                self.app.save_course_ids  # type: ignore[attr-defined]
            )
            self.app.call_from_thread(self._add_course_option, course)
            self.app.call_from_thread(
                self._show_status,
                f"Loaded: {course.title or course_id}",
                kind="success",
            )
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code == 403:
                msg = f"Course {course_id}: closed or no access"
            elif code == 404:
                msg = f"Course {course_id}: not found"
            else:
                msg = f"Course {course_id}: HTTP {code}"
            self.app.call_from_thread(self._show_status, msg, kind="error")
            self.app.call_from_thread(
                self.app.remove_course_id,  # type: ignore[attr-defined]
                course_id,
            )
        except Exception as e:
            self.app.call_from_thread(
                self._show_status,
                f"Failed to load {course_id}: {e}",
                kind="error",
            )
            self.app.call_from_thread(
                self.app.remove_course_id,  # type: ignore[attr-defined]
                course_id,
            )

    def _add_course_option(self, course: Course) -> None:
        option_list = self.query_one("#course-list", OptionList)
        title = course.title or f"Course {course.course_id}"
        option_list.add_option(Option(title, id=str(course.course_id)))

    #  Queue fetching

    def _maybe_load_queue(self) -> None:
        self._enable_queue_tab()
        if self._selected_course_id is None:
            return
        if not self.is_teacher_view:
            self.query_one("#queue-info-label", Label).update(
                "Queue available for teacher courses only"
            )
            return
        if self._queue_loaded_for == self._selected_course_id:
            return

        cache = self.app.queue_cache  # type: ignore[attr-defined]
        if self._selected_course_id in cache:
            queue = cache[self._selected_course_id]
            self.all_queue_entries = list(queue.entries)
            self.filtered_queue_entries = list(queue.entries)
            self._queue_loaded_for = self._selected_course_id
            self._update_queue_filter_options()
            self._rebuild_queue_table()
            self.query_one("#queue-info-label", Label).update(
                f"{len(queue.entries)} entries"
            )
            return

        self.query_one("#queue-info-label", Label).update("Loading queue...")
        self._fetch_queue(self._selected_course_id)

    @work(thread=True)
    def _fetch_queue(self, course_id: int) -> None:
        try:
            client = self.app.client  # type: ignore[attr-defined]
            if not client:
                self.app.call_from_thread(self._show_status, "No client", kind="error")
                return

            queue_html = client.fetch_queue_page(course_id)
            csrf = extract_csrf_from_queue_page(queue_html)

            raw = client.fetch_all_queue_entries(course_id, csrf)
            entries = [
                QueueEntry(
                    student_name=str(r.get("student_name", "")),
                    student_url=str(r.get("student_url", "")),
                    task_title=str(r.get("task_title", "")),
                    update_time=str(r.get("update_time", "")),
                    mark=str(r.get("mark", "")),
                    status_color=str(r.get("status_color", "default")),
                    status_name=str(r.get("status_name", "")),
                    responsible_name=str(r.get("responsible_name", "")),
                    responsible_url=str(r.get("responsible_url", "")),
                    has_issue_access=bool(r.get("has_issue_access", False)),
                    issue_url=str(r.get("issue_url", "")),
                )
                for r in raw
            ]

            queue = ReviewQueue(course_id=course_id, entries=entries)
            self.app.queue_cache[course_id] = queue  # type: ignore[attr-defined]

            self.all_queue_entries = entries
            self.filtered_queue_entries = list(entries)
            self._queue_loaded_for = course_id

            self.app.call_from_thread(self._update_queue_filter_options)
            self.app.call_from_thread(self._rebuild_queue_table)
            self.app.call_from_thread(
                self._update_queue_info, f"{len(entries)} entries"
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                self.app.call_from_thread(self._disable_queue_tab)
                self.app.call_from_thread(
                    self._update_queue_info, "No permission to view queue"
                )
            else:
                self.app.call_from_thread(
                    self._show_status,
                    f"Queue error: HTTP {e.response.status_code}",
                    kind="error",
                )
                self.app.call_from_thread(
                    self._update_queue_info, f"Error: HTTP {e.response.status_code}"
                )
        except Exception as e:
            self.app.call_from_thread(
                self._show_status,
                f"Queue error: {e}",
                kind="error",
            )
            self.app.call_from_thread(self._update_queue_info, f"Error: {e}")

    def _update_queue_info(self, text: str) -> None:
        self.query_one("#queue-info-label", Label).update(text)

    def _disable_queue_tab(self) -> None:
        self.query_one("#queue-filter-bar", QueueFilterBar).disabled = True
        self.query_one("#queue-table", DataTable).disabled = True
        self.query_one("#queue-info-label", Label).update("No permission to view queue")

    def _enable_queue_tab(self) -> None:
        self.query_one("#queue-filter-bar", QueueFilterBar).disabled = False
        self.query_one("#queue-table", DataTable).disabled = False

    @work(thread=True)
    def _fetch_and_show_submission(self, entry: QueueEntry) -> None:
        try:
            if self._selected_course_id is not None:
                cache = self.app.queue_cache.get(  # type: ignore[attr-defined]
                    self._selected_course_id
                )
                if cache and entry.issue_url in cache.submissions:
                    sub = cache.submissions[entry.issue_url]
                    self.app.call_from_thread(self._push_submission_screen, sub)
                    return

            client = self.app.client  # type: ignore[attr-defined]
            if not client:
                return

            html = client.fetch_submission_page(entry.issue_url)
            issue_id = extract_issue_id_from_breadcrumb(html)
            if issue_id == 0:
                self.app.call_from_thread(
                    self._show_status,
                    "Could not find issue ID",
                    kind="warning",
                )
                return

            sub = parse_submission_page(html, issue_id)

            if self._selected_course_id is not None:
                cache = self.app.queue_cache.get(  # type: ignore[attr-defined]
                    self._selected_course_id
                )
                if cache:
                    cache.submissions[entry.issue_url] = sub

            self.app.call_from_thread(self._push_submission_screen, sub)
        except Exception as e:
            self.app.call_from_thread(
                self._show_status,
                f"Submission error: {e}",
                kind="error",
            )

    def _push_submission_screen(self, sub: Submission) -> None:
        from anytask_scraper.tui.screens.submission import (
            SubmissionScreen,
        )

        self.app.push_screen(SubmissionScreen(sub))

    #  Task table helpers

    def _setup_task_table_columns(self) -> None:
        table = self.query_one("#task-table", DataTable)
        table.clear(columns=True)
        if self.is_teacher_view:
            table.add_columns("#", "Title", "Section", "Max", "Deadline")
        else:
            table.add_columns("#", "Title", "Score", "Status", "Deadline")

    def _rebuild_task_table(self) -> None:
        table = self.query_one("#task-table", DataTable)
        if not table.columns:
            self._setup_task_table_columns()
        table.clear()

        for idx, task in enumerate(self.filtered_tasks, 1):
            if self.is_teacher_view:
                table.add_row(
                    str(idx),
                    Text(task.title),
                    Text(task.section or "-", style="dim"),
                    str(task.max_score) if task.max_score is not None else "-",
                    _styled_deadline(task.deadline),
                    key=str(idx),
                )
            else:
                table.add_row(
                    str(idx),
                    Text(task.title),
                    _format_score(task),
                    _styled_status(task.status),
                    _styled_deadline(task.deadline),
                    key=str(idx),
                )

    #  Queue table helpers

    def _rebuild_queue_table(self) -> None:
        table = self.query_one("#queue-table", DataTable)
        table.clear()

        for idx, entry in enumerate(self.filtered_queue_entries, 1):
            style = _QUEUE_STATUS_COLORS.get(entry.status_color, "")
            table.add_row(
                str(idx),
                entry.student_name,
                entry.task_title,
                Text(entry.status_name, style=style),
                entry.responsible_name,
                entry.update_time,
                entry.mark,
                key=entry.issue_url or str(idx),
            )

    #  Detail panel (tasks)

    def _clear_detail(self) -> None:
        scroll = self.query_one("#detail-scroll", VerticalScroll)
        scroll.remove_children()
        scroll.mount(Label("[dim]Select a task[/dim]"))

    def _show_detail(self, task: Task) -> None:
        scroll = self.query_one("#detail-scroll", VerticalScroll)
        scroll.remove_children()

        scroll.mount(Label(f"[bold]{task.title}[/bold]", classes="detail-heading"))

        if not self.is_teacher_view:
            score = _format_score(task)
            status_style = _STATUS_STYLES.get(task.status, "")
            status_txt = task.status or "-"
            scroll.mount(
                Label(
                    f"Score: {score}  Status: [{status_style}]{status_txt}[/{status_style}]",
                    classes="detail-text",
                )
            )
        else:
            parts: list[str] = []
            if task.max_score is not None:
                parts.append(f"Max: {task.max_score}")
            if task.section:
                parts.append(f"Group: {task.section}")
            if parts:
                scroll.mount(Label("  ".join(parts), classes="detail-text"))

        if task.deadline:
            now = datetime.now()
            dl = task.deadline.strftime("%H:%M %d.%m.%Y")
            if task.deadline < now:
                dl_text = f"[dim strike]{dl}[/dim strike] (passed)"
            elif task.deadline < now + timedelta(days=3):
                dl_text = f"[bold yellow]{dl}[/bold yellow] (soon)"
            else:
                dl_text = dl
            scroll.mount(Label(f"Deadline: {dl_text}", classes="detail-text"))

        if task.description:
            desc = strip_html(task.description)
            scroll.mount(Label(desc, classes="detail-text"))
