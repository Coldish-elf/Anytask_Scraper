"""Export parameter selector widget."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Label, OptionList
from textual.widgets.option_list import Option

from anytask_scraper.tui.export_params import ExportParam


class ParameterSelector(Vertical):
    """A toggleable parameter list with names and descriptions."""

    class Changed(Message):
        """Fired when parameter selection changes."""

        def __init__(self, included: list[str]) -> None:
            super().__init__()
            self.included = included

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._params: list[ExportParam] = []

    def compose(self) -> ComposeResult:
        yield Label("Parameters", classes="export-section-title")
        yield Label("Toggle with Enter/Space", classes="export-filter-desc")
        yield OptionList(id="param-option-list")

    def set_params(self, params: list[ExportParam]) -> None:
        """Replace the parameter list and rebuild the OptionList."""
        self._params = [ExportParam(p.name, p.description, p.selected) for p in params]
        self._rebuild()

    def _rebuild(self) -> None:
        option_list = self.query_one("#param-option-list", OptionList)
        option_list.clear_options()
        for i, p in enumerate(self._params):
            check = "[x]" if p.selected else "[ ]"
            label = Text()
            label.append(f"{check}  {p.name}\n")
            label.append(f"     {p.description}", style="dim")
            option_list.add_option(Option(label, id=str(i)))

    def get_included(self) -> list[str]:
        """Return names of selected parameters."""
        return [p.name for p in self._params if p.selected]

    @on(OptionList.OptionSelected, "#param-option-list")
    def _toggle_param(self, event: OptionList.OptionSelected) -> None:
        if event.option_id is None:
            return
        idx = int(event.option_id)
        if 0 <= idx < len(self._params):
            self._params[idx].selected = not self._params[idx].selected
            self._rebuild()
            option_list = self.query_one("#param-option-list", OptionList)
            option_list.highlighted = idx
            self.post_message(self.Changed(self.get_included()))
