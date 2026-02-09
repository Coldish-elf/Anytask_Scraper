"""Full-screen submission detail view."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Label, Static

from anytask_scraper.models import Submission
from anytask_scraper.parser import strip_html


class SubmissionScreen(Screen[None]):
    """Full-screen view for a single submission with all comments."""

    BINDINGS = [
        Binding("escape", "go_back", "Back", show=True),
        Binding("j", "scroll_down", "Down", show=False),
        Binding("k", "scroll_up", "Up", show=False),
    ]

    def __init__(self, submission: Submission) -> None:
        super().__init__()
        self.submission = submission

    def compose(self) -> ComposeResult:
        sub = self.submission

        yield Static(
            f"Issue {sub.issue_id}: {sub.task_title}",
            id="sub-header",
        )

        with Vertical(id="sub-metadata"):
            yield Label(
                f"Student: [bold]{sub.student_name}[/bold]",
                classes="meta-line",
            )
            yield Label(
                f"Reviewer: [bold]{sub.reviewer_name or '-'}[/bold]",
                classes="meta-line",
            )
            status_line = (
                f"Status: {sub.status}  |  Grade: {sub.grade}/{sub.max_score}"
                f"  |  Deadline: {sub.deadline}"
            )
            yield Label(status_line, classes="meta-line")

        with VerticalScroll(id="sub-scroll"):
            if not sub.comments:
                yield Label("No comments", classes="no-comments")
            else:
                yield Label(
                    f"[bold]Comments ({len(sub.comments)})[/bold]",
                    classes="detail-heading",
                )
                for comment in sub.comments:
                    card = Container(classes="comment-card")
                    if comment.is_after_deadline:
                        card.add_class("-after-deadline")

                    ts = (
                        comment.timestamp.strftime("%d.%m.%Y %H:%M")
                        if comment.timestamp
                        else "-"
                    )
                    after_tag = (
                        " [bold red](LATE)[/bold red]"
                        if comment.is_after_deadline
                        else ""
                    )

                    header_label = Label(
                        f"[bold]{comment.author_name}[/bold]  [dim]{ts}[/dim]{after_tag}",
                        classes="comment-header",
                    )
                    card.compose_add_child(header_label)

                    if comment.content_html:
                        text = strip_html(comment.content_html)
                        if text:
                            card.compose_add_child(Label(text, classes="comment-body"))

                    if comment.files:
                        files_str = "\n".join(f"  {f.filename}" for f in comment.files)
                        card.compose_add_child(
                            Label(
                                f"[dim]Files:\n{files_str}[/dim]",
                                classes="comment-files",
                            )
                        )

                    if comment.links:
                        links_str = "\n".join(f"  {lnk}" for lnk in comment.links)
                        card.compose_add_child(
                            Label(
                                f"[dim]Links:\n{links_str}[/dim]",
                                classes="comment-links",
                            )
                        )

                    yield card

        yield Footer()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_scroll_down(self) -> None:
        self.query_one("#sub-scroll", VerticalScroll).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#sub-scroll", VerticalScroll).scroll_up()
