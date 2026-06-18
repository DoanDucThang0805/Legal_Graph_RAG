"""Create flat competition submission zip archives."""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def make_submission_zip(results_path: str | Path, zip_path: str | Path) -> Path:
    """Create a zip containing only results.json at the archive root."""

    source_path = Path(results_path)
    output_path = Path(zip_path)

    if not source_path.is_file():
        raise FileNotFoundError(f"results file does not exist: {source_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output_path, mode="w", compression=ZIP_DEFLATED) as archive:
        archive.write(source_path, arcname="results.json")

    return output_path
