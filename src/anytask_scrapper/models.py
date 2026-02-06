"""Project data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Task:
    """Course task."""

    task_id: int
    title: str
    description: str = ""
    deadline: datetime | None = None
    max_score: float | None = None
    score: float | None = None
    status: str = ""
    section: str = ""
    edit_url: str = ""
    submit_url: str = ""


@dataclass
class Course:
    """Course with tasks."""

    course_id: int
    title: str = ""
    teachers: list[str] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)


@dataclass
class QueueEntry:
    """One queue row."""

    student_name: str
    student_url: str
    task_title: str
    update_time: str
    mark: str
    status_color: str
    status_name: str
    responsible_name: str
    responsible_url: str
    has_issue_access: bool
    issue_url: str


@dataclass
class FileAttachment:
    """Comment attachment."""

    filename: str
    download_url: str
    is_notebook: bool = False


@dataclass
class Comment:
    """Submission comment."""

    author_name: str
    author_url: str
    timestamp: datetime | None
    content_html: str
    files: list[FileAttachment] = field(default_factory=list)
    links: list[str] = field(default_factory=list)
    is_after_deadline: bool = False
    is_system_event: bool = False


@dataclass
class Submission:
    """Submission details."""

    issue_id: int
    task_title: str
    student_name: str = ""
    student_url: str = ""
    reviewer_name: str = ""
    reviewer_url: str = ""
    status: str = ""
    grade: str = ""
    max_score: str = ""
    deadline: str = ""
    comments: list[Comment] = field(default_factory=list)


@dataclass
class QueueFilters:
    """Queue filter options."""

    students: list[tuple[str, str]] = field(default_factory=list)
    tasks: list[tuple[str, str]] = field(default_factory=list)
    reviewers: list[tuple[str, str]] = field(default_factory=list)
    statuses: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class ReviewQueue:
    """Queue payload."""

    course_id: int
    entries: list[QueueEntry] = field(default_factory=list)
    submissions: dict[str, Submission] = field(default_factory=dict)
