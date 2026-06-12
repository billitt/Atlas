"""Shared pytest fixtures for Atlas boundary tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from memory.episodic import EpisodicMemory


@pytest.fixture
def episodic_db(tmp_path: Path) -> EpisodicMemory:
    """Isolated episodic memory backed by a temporary SQLite file."""
    return EpisodicMemory(db_path=str(tmp_path / "test_episodic.db"))
