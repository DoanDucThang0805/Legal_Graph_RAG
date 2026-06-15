"""Path defaults for the Legal Graph RAG project."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def get_project_root() -> Path:
    """Return the repository root based on this config module location."""

    return Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PathConfig:
    """Filesystem paths used by data loading, indexing, QA, and submission."""

    project_root: Path
    data_dir: Path
    raw_dir: Path
    processed_dir: Path
    output_dir: Path


def get_default_path_config() -> PathConfig:
    """Build default repository-relative paths."""

    project_root = get_project_root()
    data_dir = project_root / "data"
    return PathConfig(
        project_root=project_root,
        data_dir=data_dir,
        raw_dir=data_dir / "raw",
        processed_dir=data_dir / "processed",
        output_dir=data_dir / "outputs",
    )
