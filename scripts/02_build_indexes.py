"""Thin entrypoint for Phase 2 index builds.

Script này chỉ parse CLI, preflight dữ liệu đầu vào, rồi gọi business logic trong
backend modules. Không tự chạy dense index nếu người dùng không truyền --only.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LOGGER = logging.getLogger(__name__)

ONLY_CHOICES = ("bm25", "dense", "vector", "exact", "exact-duckdb", "all-no-dense")


@dataclass(frozen=True)
class IndexPaths:
    processed_dir: Path
    legal_article_chunks: Path
    phapdien_articles_index: Path
    anle_units: Path
    legal_articles: Path
    exact_duckdb: Path
    exact_legacy_json: Path


@dataclass(frozen=True)
class IndexBuilders:
    build_bm25: Callable[..., object]
    build_vector: Callable[..., object]
    build_exact_duckdb: Callable[..., object]
    build_exact_json: Callable[..., object]
    embedder_factory: Callable[..., object]
    prepare_index_corpus: Callable[..., object]


def main(argv: Sequence[str] | None = None, *, builders: IndexBuilders | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.only is None:
        parser.print_help()
        return 2

    _configure_logging(args.log_level)
    paths = build_index_paths(Path(args.processed_dir) if args.processed_dir else None)
    selected = _normalize_only(args.only)
    active_builders = builders or load_builders(
        selected=selected,
        write_legacy_json=args.write_legacy_json,
        prepare_index_corpus=args.prepare_index_corpus,
    )

    if args.prepare_index_corpus:
        LOGGER.info("Preparing derived index corpus before build")
        active_builders.prepare_index_corpus()

    if selected in {"bm25", "all-no-dense"}:
        validate_required_files(
            [paths.legal_article_chunks, paths.phapdien_articles_index, paths.anle_units],
            purpose="BM25 index",
        )
        LOGGER.info("Building BM25 indexes")
        active_builders.build_bm25(recreate=args.recreate)

    if selected == "dense":
        validate_required_files(
            [paths.legal_article_chunks, paths.phapdien_articles_index, paths.anle_units],
            purpose="dense/vector index",
        )
        if args.recreate and args.resume:
            LOGGER.warning("Using --recreate with resume=True; existing collections may be recreated before resume checks.")
        LOGGER.info("Building dense/vector indexes")
        embedder_kwargs = {
            "batch_size": args.batch_size,
            "max_length": args.max_length,
        }
        if args.device:
            embedder_kwargs["device"] = args.device
        embedder = active_builders.embedder_factory(**embedder_kwargs)
        active_builders.build_vector(
            recreate=args.recreate,
            resume=args.resume,
            max_rows=args.max_rows,
            embedder=embedder,
        )

    if selected in {"exact", "all-no-dense"}:
        validate_required_files([paths.legal_articles], purpose="exact index")
        LOGGER.info("Building DuckDB exact index")
        active_builders.build_exact_duckdb(
            paths.legal_articles,
            paths.exact_duckdb,
            recreate=args.recreate,
        )
        if args.write_legacy_json:
            LOGGER.info("Building legacy JSON exact index")
            active_builders.build_exact_json(paths.legal_articles, paths.exact_legacy_json)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build Phase 2 indexes. Pass --only explicitly; dense/vector never runs by default.",
    )
    parser.add_argument("--only", choices=ONLY_CHOICES, help="Index group to build. Required to avoid accidental full dense runs.")
    parser.add_argument("--processed-dir", help="Override processed data directory. Defaults to config processed data dir.")
    parser.add_argument("--prepare-index-corpus", action="store_true", help="Regenerate derived index corpus before building.")
    parser.add_argument("--write-legacy-json", action="store_true", help="Also write legacy exact_index.json. Off by default.")
    parser.add_argument("--device", default=None, help="Dense embedder device, e.g. cuda/cpu. Defaults to embedder auto mode.")
    parser.add_argument("--batch-size", type=int, default=8, help="Dense embedding batch size.")
    parser.add_argument("--max-length", type=int, default=512, help="Dense embedding max token length.")
    parser.add_argument("--max-rows", type=int, default=None, help="Optional dense smoke-test row cap.")
    parser.add_argument("--recreate", action="store_true", help="Recreate target indexes/collections before build.")
    parser.add_argument("--resume", dest="resume", action="store_true", default=True, help="Resume dense build by skipping existing points.")
    parser.add_argument("--no-resume", dest="resume", action="store_false", help="Disable dense resume.")
    parser.add_argument("--log-level", default="INFO", help="Python logging level.")
    return parser


def build_index_paths(processed_dir_override: Path | None = None) -> IndexPaths:
    processed_dir = processed_dir_override or _default_processed_dir()
    return IndexPaths(
        processed_dir=processed_dir,
        legal_article_chunks=processed_dir / "legal_article_chunks.parquet",
        phapdien_articles_index=processed_dir / "phapdien_articles_index.parquet",
        anle_units=processed_dir / "anle_units.parquet",
        legal_articles=processed_dir / "legal_articles.parquet",
        exact_duckdb=processed_dir / "exact_index.duckdb",
        exact_legacy_json=processed_dir / "exact_index.json",
    )


def validate_required_files(paths: Sequence[Path], *, purpose: str) -> None:
    missing = [path for path in paths if not path.exists()]
    if not missing:
        return

    missing_text = "\n".join(f"- {path}" for path in missing)
    raise FileNotFoundError(
        f"Missing required input file(s) for {purpose}:\n{missing_text}\n"
        "Run prepare_index_corpus() or the corresponding corpus preparation script before building indexes."
    )


def load_builders(
    *,
    selected: str,
    write_legacy_json: bool,
    prepare_index_corpus: bool,
) -> IndexBuilders:
    build_bm25 = _unavailable_builder("BM25 builder was not loaded for this mode")
    build_vector = _unavailable_builder("Dense/vector builder was not loaded for this mode")
    build_exact_duckdb = _unavailable_builder("Exact DuckDB builder was not loaded for this mode")
    build_exact_json = _unavailable_builder("Legacy JSON exact builder was not loaded")
    embedder_factory = _unavailable_builder("Dense embedder was not loaded for this mode")
    prepare_corpus = _unavailable_builder("prepare_index_corpus was not loaded")

    if selected in {"bm25", "all-no-dense"}:
        from backend.indexing.build_bm25_index import build_all_bm25_indexes

        build_bm25 = build_all_bm25_indexes

    if selected == "dense":
        from backend.indexing.build_vector_index import build_all_vector_indexes
        from backend.infrastructure.embedding_models.vnlegal_lal import VNLegalLALEmbedder

        build_vector = build_all_vector_indexes
        embedder_factory = VNLegalLALEmbedder

    if selected in {"exact", "all-no-dense"}:
        from backend.indexing.exact_index_store import build_exact_duckdb_index

        build_exact_duckdb = build_exact_duckdb_index
        if write_legacy_json:
            from backend.indexing.build_exact_index import build_exact_index

            build_exact_json = build_exact_index

    if prepare_index_corpus:
        from backend.knowledge_processing.prepare_index_corpus import prepare_index_corpus as prepare_corpus

    return IndexBuilders(
        build_bm25=build_bm25,
        build_vector=build_vector,
        build_exact_duckdb=build_exact_duckdb,
        build_exact_json=build_exact_json,
        embedder_factory=embedder_factory,
        prepare_index_corpus=prepare_corpus,
    )


def _unavailable_builder(message: str) -> Callable[..., object]:
    def _raise_unavailable(*args: object, **kwargs: object) -> object:
        raise RuntimeError(message)

    return _raise_unavailable


def _normalize_only(value: str) -> str:
    if value == "vector":
        return "dense"
    if value == "exact-duckdb":
        return "exact"
    return value


def _default_processed_dir() -> Path:
    try:
        from backend.config import path_config
    except ImportError:
        return Path("data") / "processed"

    for name in ("PROCESSED_DATA_DIR", "PROCESSED_DIR"):
        value = getattr(path_config, name, None)
        if value is not None:
            return Path(value)
    return Path("data") / "processed"


def _configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


if __name__ == "__main__":
    raise SystemExit(main())
