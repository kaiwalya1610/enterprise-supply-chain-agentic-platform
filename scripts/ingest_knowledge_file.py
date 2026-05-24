from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.knowledge_ingestion import ingest_file, report_to_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest a file into retrieval, structured, and graph knowledge stores.")
    parser.add_argument("path", type=Path, help="File to ingest. Supported types: .md, .txt, .csv")
    parser.add_argument(
        "--mode",
        choices=["auto", "embedding", "structured", "graph", "hybrid"],
        default="auto",
        help="Override automatic storage-target classification.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Classify and report planned writes without mutating stores.")
    parser.add_argument(
        "--no-copy",
        action="store_true",
        help="Use the source file in place instead of copying it into dataset-managed folders.",
    )
    parser.add_argument(
        "--skip-chroma",
        action="store_true",
        help="Skip embedding/upserting chunks into Chroma.",
    )
    parser.add_argument(
        "--skip-graph",
        action="store_true",
        help="Skip graph extraction and graph JSON merge.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = ingest_file(
        args.path,
        mode=args.mode,
        copy_into_dataset=not args.no_copy,
        rebuild_chroma=not args.skip_chroma,
        update_graph=not args.skip_graph,
        dry_run=args.dry_run,
    )
    print(report_to_json(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
