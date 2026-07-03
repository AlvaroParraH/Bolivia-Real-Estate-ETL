from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path
from time import perf_counter

from remax_scraper import DEFAULT_URLS, export_json, listings_to_dataframe, scrape_listings


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data"
DEFAULT_LOG_FILE = PROJECT_ROOT / "logs" / "processed_files.log"
CITY_RE = re.compile(r"/search/(?:[^/]+/)*([^/?#]+)")


def _resolve_output_target(output_arg: str | None) -> tuple[Path, str]:
    if not output_arg:
        return DEFAULT_OUTPUT_DIR, "remax_house_listings"

    output_path = Path(output_arg)
    if output_path.suffix:
        return output_path.parent, output_path.stem

    return output_path, "remax_house_listings"


def _slugify_city(city: str) -> str:
    slug = city.strip().lower().replace(" ", "-")
    slug = "".join(ch for ch in slug if ch.isalnum() or ch in "-_")
    return slug or "unknown"


def _normalize_urls(urls: str | tuple[str, ...]) -> list[str]:
    if isinstance(urls, str):
        return [urls]
    return [url for url in urls if url]


def _city_from_url(url: str) -> str:
    match = CITY_RE.search(url)
    if not match:
        return "unknown"
    return match.group(1).replace("_", "-").lower()


def _log_processed_file(
    log_file: Path,
    *,
    run_timestamp: str,
    city: str,
    row_count: int,
    output_path: Path,
) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(
            f"{run_timestamp}\tcity={city}\trows={row_count}\tfile={output_path}\n"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scrape RE/MAX Bolivia listings")
    parser.add_argument("--url", default=DEFAULT_URLS, help="Search results page or pages to scrape")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of listings to collect")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Maximum number of paginated result pages to scrape per URL",
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

    urls = _normalize_urls(args.url)
    output_dir, base_name = _resolve_output_target(args.output)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_dir.mkdir(parents=True, exist_ok=True)
    remaining_limit = args.limit
    written_files: list[Path] = []
    total_rows_written = 0

    for base_url in urls:
        if remaining_limit is not None and remaining_limit <= 0:
            break

        city_listings = scrape_listings(
            url=base_url,
            limit=remaining_limit,
            max_pages=args.max_pages,
            pagination_log_file=DEFAULT_LOG_FILE,
            pagination_log_run_id=timestamp,
        )

        if not city_listings:
            print(f"No listings found for city URL: {base_url}")
            continue

        city_frame = listings_to_dataframe(city_listings)
        city_name = str(city_frame["city"].iloc[0]) if "city" in city_frame.columns else _city_from_url(base_url)
        city_slug = _slugify_city(city_name)
        output_path = output_dir / f"{base_name}_{city_slug}_{timestamp}.{args.format}"

        if args.format == "csv":
            city_frame.to_csv(output_path, index=False, encoding="utf-8-sig")
        else:
            export_json(city_listings, str(output_path))

        _log_processed_file(
            DEFAULT_LOG_FILE,
            run_timestamp=timestamp,
            city=city_name,
            row_count=len(city_frame),
            output_path=output_path,
        )

        print(f"Wrote city file: {output_path} ({len(city_frame)} rows)")
        written_files.append(output_path)
        total_rows_written += len(city_frame)

        if remaining_limit is not None:
            remaining_limit -= len(city_frame)

    ended_at = datetime.now()
    elapsed_seconds = perf_counter() - started_perf
    print(f"Script finished at {ended_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total runtime: {elapsed_seconds:.2f} seconds")
    if not written_files:
        print("No listings found. No files were written.")
        return

    print(f"Wrote {total_rows_written} listings across {len(written_files)} file(s):")
    for file_path in sorted(written_files):
        print(f"- {file_path}")
    print(f"Processed-files log updated at {DEFAULT_LOG_FILE}")


if __name__ == "__main__":
    main()
