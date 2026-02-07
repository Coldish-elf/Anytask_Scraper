"""Terminal renderers."""

from __future__ import annotations

from datetime import datetime, timedelta

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from anytask_scraper.models import Course, ReviewQueue, Submission, Task
from anytask_scraper.parser import strip_html

_STATUS_STYLES: dict[str, str] = {
    "Зачтено": "bold green",
    "Новый": "dim",
    "На проверке": "bold yellow",
    "Не зачтено": "bold red",
}


def _status_text(status: str) -> Text:
    style = _STATUS_STYLES.get(status, "")
    return Text(status, style=style)


def _deadline_text(deadline: datetime | None) -> Text:
    if deadline is None:
        return Text("—", style="dim")
    now = datetime.now()
    label = deadline.strftime("%H:%M %d-%m-%Y")
    if deadline < now:
        return Text(label, style="dim strike")
    if deadline < now + timedelta(days=3):
        return Text(label, style="bold yellow")
    return Text(label)


def _score_text(task: Task) -> str:
    parts: list[str] = []
    if task.score is not None:
        parts.append(str(task.score))
    if task.max_score is not None:
        parts.append(f"/ {task.max_score}")
    return " ".join(parts) if parts else "—"


def display_course(course: Course, console: Console | None = None) -> None:
    """Render course view."""
    if console is None:
        console = Console()

    teachers_line = ", ".join(course.teachers) if course.teachers else "—"
    header = f"[bold]{course.title}[/bold]\nTeachers: {teachers_line}"
    console.print(Panel(header, title=f"Course {course.course_id}", border_style="blue"))

    if not course.tasks:
        console.print("[dim]No tasks found.[/dim]")
        return

    has_sections = any(t.section for t in course.tasks)

    if has_sections:
        _display_teacher_tasks(course.tasks, console)
    else:
        _display_student_tasks(course.tasks, console)


def _display_student_tasks(tasks: list[Task], console: Console) -> None:
    table = Table(show_header=True, header_style="bold cyan", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", min_width=20)
    table.add_column("Score", justify="right", width=8)
    table.add_column("Status", width=14)
    table.add_column("Deadline", width=18)

    for i, task in enumerate(tasks, 1):
        table.add_row(
            str(i),
            task.title,
            _score_text(task),
            _status_text(task.status),
            _deadline_text(task.deadline),
        )

    console.print(table)


def _display_teacher_tasks(tasks: list[Task], console: Console) -> None:
    sections: dict[str, list[Task]] = {}
    for task in tasks:
        sections.setdefault(task.section or "Unsorted", []).append(task)

    for section_name, section_tasks in sections.items():
        console.print(f"\n[bold magenta]{section_name}[/bold magenta]")

        table = Table(show_header=True, header_style="bold cyan", show_lines=False)
        table.add_column("#", style="dim", width=4)
        table.add_column("Title", min_width=20)
        table.add_column("Max Score", justify="right", width=10)
        table.add_column("Deadline", width=18)

        for i, task in enumerate(section_tasks, 1):
            max_score = str(task.max_score) if task.max_score is not None else "—"
            table.add_row(
                str(i),
                task.title,
                max_score,
                _deadline_text(task.deadline),
            )

        console.print(table)


def display_task_detail(task: Task, console: Console | None = None) -> None:
    """Render task details."""
    if console is None:
        console = Console()

    desc = strip_html(task.description) if task.description else "[dim]No description[/dim]"
    console.print(Panel(desc, title=task.title, border_style="green"))


_QUEUE_STATUS_COLORS: dict[str, str] = {
    "success": "green",
    "warning": "yellow",
    "danger": "red",
    "info": "cyan",
    "default": "dim",
    "primary": "blue",
}


def display_queue(queue: ReviewQueue, console: Console | None = None) -> None:
    """Render review queue."""
    if console is None:
        console = Console()

    console.print(
        Panel(
            f"[bold]{len(queue.entries)} entries[/bold]",
            title=f"Review Queue — Course {queue.course_id}",
            border_style="blue",
        )
    )

    if not queue.entries:
        console.print("[dim]No queue entries found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold cyan", show_lines=False)
    table.add_column("#", style="dim", width=4)
    table.add_column("Student", min_width=15)
    table.add_column("Task", min_width=10)
    table.add_column("Status", width=16)
    table.add_column("Reviewer", min_width=12)
    table.add_column("Updated", width=18)
    table.add_column("Grade", justify="right", width=8)

    for i, entry in enumerate(queue.entries, 1):
        color = _QUEUE_STATUS_COLORS.get(entry.status_color, "")
        status_text = Text(entry.status_name, style=f"bold {color}" if color else "")
        table.add_row(
            str(i),
            entry.student_name,
            entry.task_title,
            status_text,
            entry.responsible_name,
            entry.update_time,
            entry.mark,
        )

    console.print(table)


def display_submission(submission: Submission, console: Console | None = None) -> None:
    """Render submission thread."""
    if console is None:
        console = Console()

    header_lines = [
        f"[bold]Issue {submission.issue_id}: {submission.task_title}[/bold]",
        f"Student: {submission.student_name}",
        f"Reviewer: {submission.reviewer_name or '—'}",
        f"Status: {submission.status}  |  Grade: {submission.grade}/{submission.max_score}",
        f"Deadline: {submission.deadline}",
    ]
    console.print(Panel("\n".join(header_lines), border_style="green"))

    for i, comment in enumerate(submission.comments, 1):
        ts = str(comment.timestamp) if comment.timestamp else "—"
        after = " [bold red][AFTER DEADLINE][/bold red]" if comment.is_after_deadline else ""
        console.print(f"\n  [bold]{i}. {comment.author_name}[/bold] [dim]{ts}[/dim]{after}")
        if comment.content_html:
            text = strip_html(comment.content_html)
            if text:
                console.print(f"     {text}")
        if comment.files:
            for f in comment.files:
                icon = "[NB]" if f.is_notebook else "[FILE]"
                console.print(f"     {icon} {f.filename}")
        if comment.links:
            for link in comment.links:
                console.print(f"     [LINK] {link}")
