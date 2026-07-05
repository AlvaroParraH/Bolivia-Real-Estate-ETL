from __future__ import annotations

import argparse
import os
import re
from datetime import datetime
from pathlib import Path
from time import perf_counter

from azure_blob_uploader import upload_files_to_azure_blob
from firmacasas_scraper import export_json, listings_to_dataframe, scrape_listings


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data"
DEFAULT_LOG_FILE = PROJECT_ROOT / "logs" / "processed_files.log"
DEFAULT_CATEGORY_IDS = (1,)
DEFAULT_TYPE_IDS = (2,)
NON_ALNUM_RE = re.compile(r"[^a-z0-9_-]+")


def _resolve_output_target(output_arg: str | None) -> tuple[Path, str]:
    if not output_arg:
        return DEFAULT_OUTPUT_DIR, "firmacasas_house_listings"

    output_path = Path(output_arg)
    if output_path.suffix:
        return output_path.parent, output_path.stem

    return output_path, "firmacasas_house_listings"


def _slugify_city(city: str) -> str:
    normalized = city.strip().lower().replace(" ", "-")
    slug = NON_ALNUM_RE.sub("", normalized)
    return slug or "unknown"


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
    parser = argparse.ArgumentParser(description="Scrape Firmacasas listings")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of listings to collect")
    parser.add_argument("--city-id", action="append", type=int, default=None, help="Optional Firmacasas city id filter. Repeat to include multiple cities")
    parser.add_argument("--output", help="Write results to a file instead of stdout")
    parser.add_argument(
        "--format",
        choices=("json", "csv"),
        default="json",
        help="Output format when --output is provided",
    )
    parser.add_argument(
        "--upload-azure",
        action="store_true",
        help="Upload generated files to Azure Blob Storage",
    )
    parser.add_argument(
        "--azure-container",
        default=None,
        help="Azure Blob container name (defaults to AZURE_STORAGE_CONTAINER env var)",
    )
    parser.add_argument(
        "--azure-prefix",
        default=None,
        help="Optional blob path prefix inside the container",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    started_at = datetime.now()
    started_perf = perf_counter()
    print(f"Script started at {started_at.strftime('%Y-%m-%d %H:%M:%S')}")

    output_dir, base_name = _resolve_output_target(args.output)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=True)

    listings = scrape_listings(
        city_ids=args.city_id,
        property_category_ids=list(DEFAULT_CATEGORY_IDS),
        property_type_ids=list(DEFAULT_TYPE_IDS),
        limit=args.limit,
    )

    if not listings:
        print("No listings found. No files were written.")
        return

    frame = listings_to_dataframe(listings)
    written_files: list[Path] = []
    total_rows_written = 0

    for city, city_frame in frame.groupby("city", dropna=False):
        city_name = str(city) if city else "unknown"
        city_slug = _slugify_city(city_name)
        output_path = output_dir / f"{base_name}_{city_slug}_{timestamp}.{args.format}"

        if args.format == "csv":
            city_frame.to_csv(output_path, index=False, encoding="utf-8-sig")
        else:
            city_listings = [listing for listing in listings if listing.city == city_name]
            export_json(city_listings, output_path)

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

    ended_at = datetime.now()
    elapsed_seconds = perf_counter() - started_perf
    print(f"Script finished at {ended_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total runtime: {elapsed_seconds:.2f} seconds")
    print(f"Wrote {total_rows_written} listings across {len(written_files)} file(s):")
    for file_path in sorted(written_files):
        print(f"- {file_path}")
    print(f"Processed-files log updated at {DEFAULT_LOG_FILE}")

    if args.upload_azure:
        container_name = args.azure_container or os.getenv("AZURE_STORAGE_CONTAINER", "")
        default_prefix = f"firmacasas/{timestamp}"
        blob_prefix = args.azure_prefix if args.azure_prefix is not None else default_prefix
        uploaded_urls = upload_files_to_azure_blob(
            file_paths=written_files,
            container_name=container_name,
            prefix=blob_prefix,
        )
        print(f"Uploaded {len(uploaded_urls)} file(s) to Azure Blob Storage:")
        for url in uploaded_urls:
            print(f"- {url}")


if __name__ == "__main__":
    main()