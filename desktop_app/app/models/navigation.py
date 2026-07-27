from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkspaceRoute:
    """A stable destination inside one of the app's product workspaces."""

    workspace: str
    section: str
    entity_id: str | None = None
    action: str | None = None
