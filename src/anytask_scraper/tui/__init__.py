"""Anytask Scraper TUI."""

from __future__ import annotations


def run(debug: bool = False) -> None:
    """Launch the TUI application."""
    if debug:
        import logging

        from anytask_scraper._logging import setup_logging

        setup_logging(level=logging.DEBUG)

    from anytask_scraper.tui.app import AnytaskApp

    app = AnytaskApp()
    app.run()
