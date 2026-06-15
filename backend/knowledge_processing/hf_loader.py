"""Generic helpers for loading Hugging Face datasets into Polars."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import polars as pl
from datasets import Dataset, DatasetDict, IterableDataset, load_dataset

logger = logging.getLogger(__name__)


def load_hf_dataset_to_polars(
    dataset_name: str,
    config_name: str | None = None,
    split: str = "train",
    **load_kwargs: Any,
) -> pl.DataFrame:
    """Load one Hugging Face dataset split and convert it to a Polars DataFrame."""

    if not dataset_name.strip():
        raise ValueError("dataset_name must not be empty")
    if not split.strip():
        raise ValueError("split must not be empty")

    try:
        logger.info(
            "Loading Hugging Face dataset: dataset=%s config=%s split=%s",
            dataset_name,
            config_name,
            split,
        )
        dataset = load_dataset(dataset_name, config_name, split=split, **load_kwargs)
    except Exception as exc:
        logger.exception(
            "Failed to load Hugging Face dataset: dataset=%s config=%s split=%s",
            dataset_name,
            config_name,
            split,
        )
        raise RuntimeError(
            f"Failed to load Hugging Face dataset "
            f"{dataset_name!r} config={config_name!r} split={split!r}"
        ) from exc

    return _dataset_to_polars(dataset)


def save_parquet(df: pl.DataFrame, output_path: str | Path) -> None:
    """Save a Polars DataFrame to parquet and create the parent directory."""

    path = Path(output_path)
    if not path.name:
        raise ValueError("output_path must include a file name")

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(path)
        logger.info("Saved parquet: path=%s rows=%s columns=%s", path, df.height, df.width)
    except Exception as exc:
        logger.exception("Failed to save parquet: path=%s", path)
        raise RuntimeError(f"Failed to save parquet to {path}") from exc


def _dataset_to_polars(dataset: Any) -> pl.DataFrame:
    """Convert supported Hugging Face dataset objects to Polars."""

    if isinstance(dataset, DatasetDict):
        raise TypeError("Expected a dataset split, but got DatasetDict")

    if isinstance(dataset, IterableDataset):
        raise TypeError("IterableDataset is not supported; provide a materialized split")

    if isinstance(dataset, Dataset):
        # Chuyển qua Arrow table để giữ schema ổn định hơn so với list(dict).
        return pl.from_arrow(dataset.data.table)

    try:
        return pl.DataFrame(dataset)
    except Exception as exc:
        raise TypeError(f"Unsupported dataset type: {type(dataset)!r}") from exc
