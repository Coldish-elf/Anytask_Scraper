"""Export parameter definitions for different export types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ExportParam:
    """One selectable export parameter (column)."""

    name: str
    description: str
    selected: bool = True


TASKS_STUDENT_PARAMS = [
    ExportParam("#", "Row number"),
    ExportParam("Title", "Task title"),
    ExportParam("Score", "Points received"),
    ExportParam("Status", "Submission status"),
    ExportParam("Deadline", "Due date"),
]

TASKS_TEACHER_PARAMS = [
    ExportParam("#", "Row number"),
    ExportParam("Title", "Task title"),
    ExportParam("Section", "Task section/group"),
    ExportParam("Max Score", "Maximum points"),
    ExportParam("Deadline", "Due date"),
]

QUEUE_PARAMS = [
    ExportParam("#", "Row number"),
    ExportParam("Student", "Student name"),
    ExportParam("Task", "Task title"),
    ExportParam("Status", "Review status"),
    ExportParam("Reviewer", "Assigned reviewer"),
    ExportParam("Updated", "Last update time"),
    ExportParam("Grade", "Current grade"),
]

SUBMISSIONS_PARAMS = [
    ExportParam("Issue ID", "Submission issue number"),
    ExportParam("Task", "Task title"),
    ExportParam("Student", "Student name"),
    ExportParam("Reviewer", "Assigned reviewer"),
    ExportParam("Status", "Review status"),
    ExportParam("Grade", "Current grade"),
    ExportParam("Max Score", "Maximum points"),
    ExportParam("Deadline", "Due date"),
    ExportParam("Comments", "Number of comments"),
]


def gradebook_params(task_titles: list[str]) -> list[ExportParam]:
    """Build gradebook parameters with dynamic task columns."""
    params = [
        ExportParam("Group", "Student group"),
        ExportParam("Student", "Last name First name"),
    ]
    for title in task_titles:
        params.append(ExportParam(title, f"Task: {title}"))
    params.append(ExportParam("Total", "Total score"))
    return params
