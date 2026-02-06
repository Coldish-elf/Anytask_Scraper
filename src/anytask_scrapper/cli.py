"""CLI for anytask-scrapper."""

from __future__ import annotations

import argparse
import sys

from rich.console import Console

from anytask_scrapper.client import AnytaskClient, LoginError
from anytask_scrapper.display import display_course, display_queue, display_submission
from anytask_scrapper.models import QueueEntry, ReviewQueue
from anytask_scrapper.parser import (
    extract_csrf_from_queue_page,
    extract_issue_id_from_breadcrumb,
    parse_course_page,
    parse_submission_page,
)
from anytask_scrapper.storage import (
    download_submission_files,
    save_course_json,
    save_course_markdown,
    save_queue_json,
    save_queue_markdown,
)

console = Console()
err_console = Console(stderr=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape course data from anytask.org")
    parser.add_argument("--username", "-u", required=True)
    parser.add_argument("--password", "-p", required=True)

    subparsers = parser.add_subparsers(dest="command", required=True)

    course_p = subparsers.add_parser("course", help="Scrape course tasks")
    course_p.add_argument("--course", "-c", type=int, nargs="+", required=True, help="Course ID(s)")
    course_p.add_argument("--output", "-o", default=".", help="Output directory")
    course_p.add_argument(
        "--format",
        "-f",
        choices=["json", "markdown", "table"],
        default="json",
        help="Output format (default: json). 'table' displays only, no file saved.",
    )
    course_p.add_argument(
        "--show",
        action="store_true",
        help="Print a rich table to terminal after saving",
    )
    course_p.add_argument(
        "--fetch-descriptions",
        action="store_true",
        help="Fetch task descriptions for teacher view (requires extra requests)",
    )

    queue_p = subparsers.add_parser("queue", help="Scrape review queue")
    queue_p.add_argument("--course", "-c", type=int, required=True, help="Course ID")
    queue_p.add_argument("--output", "-o", default=".", help="Output directory")
    queue_p.add_argument(
        "--format",
        "-f",
        choices=["json", "markdown", "table"],
        default="json",
        help="Output format (default: json). 'table' displays only, no file saved.",
    )
    queue_p.add_argument(
        "--show",
        action="store_true",
        help="Print a rich table to terminal after saving",
    )
    queue_p.add_argument(
        "--deep",
        action="store_true",
        help="Fetch full submission details for each queue entry",
    )
    queue_p.add_argument(
        "--download-files",
        action="store_true",
        help="Download files from submissions (implies --deep)",
    )
    queue_p.add_argument("--filter-task", help="Filter by task title (substring match)")
    queue_p.add_argument("--filter-reviewer", help="Filter by reviewer name (substring match)")
    queue_p.add_argument("--filter-status", help="Filter by status name (substring match)")

    return parser


def _run_course(args: argparse.Namespace, client: AnytaskClient) -> None:
    for course_id in args.course:
        with console.status(f"[bold blue]Fetching course {course_id}…"):
            html = client.fetch_course_page(course_id)
            course = parse_course_page(html, course_id)

        if args.fetch_descriptions:
            tasks_needing_desc = [t for t in course.tasks if not t.description and t.edit_url]
            if tasks_needing_desc:
                with console.status(
                    f"[bold blue]Fetching {len(tasks_needing_desc)} task descriptions…"
                ):
                    for task in tasks_needing_desc:
                        try:
                            task.description = client.fetch_task_description(task.task_id)
                        except Exception as e:
                            err_console.print(
                                f"[yellow]Warning:[/yellow] "
                                f"Could not fetch description for '{task.title}': {e}"
                            )

        if args.format == "table":
            display_course(course, console)
        elif args.format == "json":
            path = save_course_json(course, args.output)
            console.print(
                f"[green][OK][/green] Course {course_id} "
                f"([bold]{course.title}[/bold]): "
                f"{len(course.tasks)} tasks -> {path}"
            )
        elif args.format == "markdown":
            path = save_course_markdown(course, args.output)
            console.print(
                f"[green][OK][/green] Course {course_id} "
                f"([bold]{course.title}[/bold]): "
                f"{len(course.tasks)} tasks -> {path}"
            )

        if args.show and args.format != "table":
            display_course(course, console)


def _parse_ajax_entry(row: dict[str, object]) -> QueueEntry:
    """Convert AJAX row to ``QueueEntry``."""
    return QueueEntry(
        student_name=str(row.get("student_name", "")),
        student_url=str(row.get("student_url", "")),
        task_title=str(row.get("task_title", "")),
        update_time=str(row.get("update_time", "")),
        mark=str(row.get("mark", "")),
        status_color=str(row.get("status_color", "")),
        status_name=str(row.get("status_name", "")),
        responsible_name=str(row.get("responsible_name", "")),
        responsible_url=str(row.get("responsible_url", "")),
        has_issue_access=bool(row.get("has_issue_access", False)),
        issue_url=str(row.get("issue_url", "")),
    )


def _run_queue(args: argparse.Namespace, client: AnytaskClient) -> None:
    course_id = args.course

    if args.download_files:
        args.deep = True

    with console.status("[bold blue]Fetching queue page…"):
        queue_html = client.fetch_queue_page(course_id)
        csrf = extract_csrf_from_queue_page(queue_html)
        if not csrf:
            err_console.print("[bold red]Error:[/bold red] Could not extract CSRF token")
            sys.exit(1)

    with console.status("[bold blue]Fetching queue entries…"):
        raw_entries = client.fetch_all_queue_entries(course_id, csrf)

    entries = [_parse_ajax_entry(row) for row in raw_entries]

    if args.filter_task:
        needle = args.filter_task.lower()
        entries = [e for e in entries if needle in e.task_title.lower()]
    if args.filter_reviewer:
        needle = args.filter_reviewer.lower()
        entries = [e for e in entries if needle in e.responsible_name.lower()]
    if args.filter_status:
        needle = args.filter_status.lower()
        entries = [e for e in entries if needle in e.status_name.lower()]

    queue = ReviewQueue(course_id=course_id, entries=entries)

    console.print(
        f"[green][OK][/green] Queue: {len(entries)} entries"
        + (f" (filtered from {len(raw_entries)})" if len(entries) != len(raw_entries) else "")
    )

    if args.deep:
        accessible = [e for e in entries if e.has_issue_access and e.issue_url]
        with console.status(f"[bold blue]Fetching {len(accessible)} submissions…"):
            for entry in accessible:
                try:
                    sub_html = client.fetch_submission_page(entry.issue_url)
                    issue_id = extract_issue_id_from_breadcrumb(sub_html)
                    if issue_id == 0:
                        continue
                    sub = parse_submission_page(sub_html, issue_id)
                    queue.submissions[entry.issue_url] = sub
                except Exception as e:
                    err_console.print(
                        f"[yellow]Warning:[/yellow] Could not fetch {entry.issue_url}: {e}"
                    )
        console.print(f"[green][OK][/green] Fetched {len(queue.submissions)} submissions")

    if args.download_files:
        total = 0
        with console.status("[bold blue]Downloading files…"):
            for sub in queue.submissions.values():
                downloaded = download_submission_files(client, sub, args.output)
                total += len(downloaded)
        console.print(f"[green][OK][/green] Downloaded {total} files -> {args.output}")

    if args.format == "table":
        display_queue(queue, console)
        if queue.submissions:
            for sub in queue.submissions.values():
                display_submission(sub, console)
    elif args.format == "json":
        path = save_queue_json(queue, args.output)
        console.print(f"[green][OK][/green] Saved -> {path}")
    elif args.format == "markdown":
        path = save_queue_markdown(queue, args.output)
        console.print(f"[green][OK][/green] Saved -> {path}")

    if args.show and args.format != "table":
        display_queue(queue, console)
        if queue.submissions:
            for sub in queue.submissions.values():
                display_submission(sub, console)


def main(argv: list[str] | None = None) -> None:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        with AnytaskClient(args.username, args.password) as client:
            with console.status("[bold blue]Logging in…"):
                try:
                    client.login()
                except LoginError as e:
                    err_console.print(f"[bold red]Login failed:[/bold red] {e}")
                    sys.exit(1)

            if args.command == "course":
                _run_course(args, client)
            elif args.command == "queue":
                _run_queue(args, client)

    except Exception as e:
        err_console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])
