"""anytask_scrapper: Scrape course data from anytask.org."""

from anytask_scrapper.client import AnytaskClient, LoginError
from anytask_scrapper.display import display_course, display_queue, display_submission
from anytask_scrapper.models import (
    Comment,
    Course,
    FileAttachment,
    QueueEntry,
    QueueFilters,
    ReviewQueue,
    Submission,
    Task,
)
from anytask_scrapper.parser import (
    extract_csrf_from_queue_page,
    extract_issue_id_from_breadcrumb,
    format_student_folder,
    parse_course_page,
    parse_queue_filters,
    parse_submission_page,
    parse_task_edit_page,
    strip_html,
)
from anytask_scrapper.storage import (
    download_submission_files,
    save_course_json,
    save_course_markdown,
    save_queue_json,
    save_queue_markdown,
)

__all__ = [
    "AnytaskClient",
    "Comment",
    "Course",
    "FileAttachment",
    "LoginError",
    "QueueEntry",
    "QueueFilters",
    "ReviewQueue",
    "Submission",
    "Task",
    "display_course",
    "display_queue",
    "display_submission",
    "download_submission_files",
    "extract_csrf_from_queue_page",
    "extract_issue_id_from_breadcrumb",
    "format_student_folder",
    "parse_course_page",
    "parse_queue_filters",
    "parse_submission_page",
    "parse_task_edit_page",
    "save_course_json",
    "save_course_markdown",
    "save_queue_json",
    "save_queue_markdown",
    "strip_html",
]
