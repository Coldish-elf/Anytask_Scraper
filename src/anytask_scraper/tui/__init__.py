"""Anytask Scraper TUI."""

from __future__ import annotations


def run() -> None:
    """Launch the TUI application."""
    from anytask_scraper.tui.app import AnytaskApp

    app = AnytaskApp()
    app.run()
