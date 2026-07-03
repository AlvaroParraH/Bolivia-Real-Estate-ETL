from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import perf_counter

from c21_scraper import DEFAULT_URLS, export_json, listings_to_dataframe, scrape_listings


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data"


def default_output_path(output_format: str) -> Path:
    return DEFAULT_OUTPUT_DIR / f"c21_listings.{output_format}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape Century 21 Bolivia listings")
    parser.add_argument("--url", default=DEFAULT_URLS, help="Search results page or pages to scrape")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of listings to collect")
    parser.add_argument(
        "--skip-map-details",
        action="store_true",
        help="Skip per-listing map page visits (much faster and lower memory usage)",
    )
    parser.add_argument("--output", help="Write results to a file instead of stdout")
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Output format when --output is provided",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    started_at = datetime.now()
    started_perf = perf_counter()
    print(f"Script started at {started_at.strftime('%Y-%m-%d %H:%M:%S')}")

    listings = scrape_listings(
        url=args.url,
        limit=args.limit,
        enrich_map_details=not args.skip_map_details,
    )
    dataframe = listings_to_dataframe(listings)
    output_path = Path(args.output) if args.output else default_output_path(args.format)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "csv":
        # Use UTF-8 BOM so spreadsheet tools reliably detect Unicode accents.
        dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")
    else:
        export_json(listings, str(output_path))

    ended_at = datetime.now()
    elapsed_seconds = perf_counter() - started_perf
    print(f"Script finished at {ended_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total runtime: {elapsed_seconds:.2f} seconds")
    print(f"Wrote {len(dataframe)} listings to {output_path}")


if __name__ == "__main__":
    main()
