"""Persistence helpers."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from anytask_scrapper.models import Course, ReviewQueue, Submission, Task
from anytask_scrapper.parser import format_student_folder, strip_html


def save_course_json(course: Course, output_dir: Path | str = ".") -> Path:
    """Save course to JSON."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"course_{course.course_id}.json"
    path.write_text(
        json.dumps(asdict(course), indent=2, default=str, ensure_ascii=False)
    )
    return path


def save_course_markdown(course: Course, output_dir: Path | str = ".") -> Path:
    """Save course to Markdown."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"course_{course.course_id}.md"

    lines: list[str] = []
    lines.append(f"# {course.title}")
    lines.append("")
    if course.teachers:
        lines.append(f"**Teachers:** {', '.join(course.teachers)}")
        lines.append("")

    has_sections = any(t.section for t in course.tasks)

    if has_sections:
        _md_teacher_tasks(course.tasks, lines)
    else:
        _md_student_tasks(course.tasks, lines)

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _md_deadline(task: Task) -> str:
    if task.deadline is None:
        return "—"
    return task.deadline.strftime("%H:%M %d-%m-%Y")


def _md_student_tasks(tasks: list[Task], lines: list[str]) -> None:
    lines.append("| # | Title | Score | Status | Deadline |")
    lines.append("|---|-------|------:|--------|----------|")
    for i, task in enumerate(tasks, 1):
        score = str(task.score) if task.score is not None else "—"
        lines.append(
            f"| {i} | {task.title} | {score} | {task.status} | {_md_deadline(task)} |"
        )

    lines.append("")
    for task in tasks:
        if task.description:
            lines.append(f"### {task.title}")
            lines.append("")
            lines.append(strip_html(task.description))
            lines.append("")


def _md_teacher_tasks(tasks: list[Task], lines: list[str]) -> None:
    sections: dict[str, list[Task]] = {}
    for task in tasks:
        sections.setdefault(task.section or "Unsorted", []).append(task)

    for section_name, section_tasks in sections.items():
        lines.append(f"## {section_name}")
        lines.append("")
        lines.append("| # | Title | Max Score | Deadline |")
        lines.append("|---|-------|----------:|----------|")
        for i, task in enumerate(section_tasks, 1):
            max_score = str(task.max_score) if task.max_score is not None else "—"
            lines.append(f"| {i} | {task.title} | {max_score} | {_md_deadline(task)} |")
        lines.append("")


def save_queue_json(queue: ReviewQueue, output_dir: Path | str = ".") -> Path:
    """Save queue to JSON."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"queue_{queue.course_id}.json"
    path.write_text(
        json.dumps(asdict(queue), indent=2, default=str, ensure_ascii=False)
    )
    return path


def save_queue_markdown(queue: ReviewQueue, output_dir: Path | str = ".") -> Path:
    """Save queue to Markdown."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"queue_{queue.course_id}.md"

    lines: list[str] = []
    lines.append(f"# Review Queue — Course {queue.course_id}")
    lines.append("")

    if queue.entries:
        lines.append("| # | Student | Task | Status | Reviewer | Updated | Grade |")
        lines.append("|---|---------|------|--------|----------|---------|-------|")
        for i, e in enumerate(queue.entries, 1):
            lines.append(
                f"| {i} | {e.student_name} | {e.task_title} | "
                f"{e.status_name} | {e.responsible_name} | {e.update_time} | {e.mark} |"
            )
        lines.append("")

    if queue.submissions:
        lines.append("## Submissions")
        lines.append("")
        for _url, sub in queue.submissions.items():
            lines.append(f"### Issue {sub.issue_id}: {sub.task_title}")
            lines.append(f"**Student:** {sub.student_name}  ")
            lines.append(f"**Reviewer:** {sub.reviewer_name or '—'}  ")
            lines.append(f"**Status:** {sub.status}  ")
            lines.append(f"**Grade:** {sub.grade}/{sub.max_score}  ")
            lines.append(f"**Deadline:** {sub.deadline}")
            lines.append("")
            for j, c in enumerate(sub.comments, 1):
                ts = str(c.timestamp) if c.timestamp else "—"
                after = " [AFTER DEADLINE]" if c.is_after_deadline else ""
                lines.append(f"**{j}. {c.author_name}** ({ts}){after}")
                if c.content_html:
                    lines.append(f"> {strip_html(c.content_html)}")
                if c.files:
                    for f in c.files:
                        lines.append(f"  - File: {f.filename}")
                if c.links:
                    for link in c.links:
                        lines.append(f"  - Link: {link}")
                lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def download_submission_files(
    client: object,
    submission: Submission,
    base_dir: Path | str,
) -> dict[str, Path]:
    """Download files from submission comments."""
    from anytask_scrapper.client import AnytaskClient

    assert isinstance(client, AnytaskClient)
    base_dir = Path(base_dir)
    folder_name = (
        format_student_folder(submission.student_name)
        if submission.student_name
        else str(submission.issue_id)
    )
    student_dir = base_dir / folder_name
    student_dir.mkdir(parents=True, exist_ok=True)

    downloaded: dict[str, Path] = {}

    for comment in submission.comments:
        for file_att in comment.files:
            dest = student_dir / file_att.filename
            try:
                client.download_file(file_att.download_url, str(dest))
                downloaded[file_att.filename] = dest
            except Exception:
                pass

        for link in comment.links:
            if "colab.research.google.com" not in link:
                continue
            nb_name = f"colab_{submission.issue_id}.ipynb"
            dest = student_dir / nb_name
            ok = client.download_colab_notebook(link, str(dest))
            if ok:
                downloaded[link] = dest
            else:
                url_file = student_dir / f"colab_{submission.issue_id}.url.txt"
                url_file.write_text(link)
                downloaded[link] = url_file

    return downloaded
