from __future__ import annotations

import argparse
import json
from pathlib import Path

from c21_scraper import DEFAULT_URLS, export_json, listings_to_dataframe, scrape_listings


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data"


def default_output_path(output_format: str) -> Path:
    return DEFAULT_OUTPUT_DIR / f"c21_listings.{output_format}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape Century 21 Bolivia listings")
    parser.add_argument("--url", default=DEFAULT_URLS, help="Search results page or pages to scrape")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of listings to collect")
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

    listings = scrape_listings(url=args.url, limit=args.limit)
    dataframe = listings_to_dataframe(listings)
    output_path = Path(args.output) if args.output else default_output_path(args.format)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.format == "csv":
        dataframe.to_csv(output_path, index=False)
    else:
        export_json(listings, str(output_path))

    print(f"Wrote {len(dataframe)} listings to {output_path}")


if __name__ == "__main__":
    main()
