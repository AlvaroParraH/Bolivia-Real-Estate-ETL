from __future__ import annotations

import csv
import html
import json
import random
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import pandas as pd
from playwright.sync_api import sync_playwright


DEFAULT_URL = (
    "https://remax.bo/search/venta/casa/"
)
DEFAULT_URLS = (DEFAULT_URL,)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/149.0.0.0 Safari/537.36"
)
DEFAULT_MIN_DELAY_MS = 200
DEFAULT_MAX_DELAY_MS = 600
DEFAULT_NAVIGATION_RETRIES = 3
DEFAULT_NAVIGATION_RETRY_WAIT_MS = 1500
DEFAULT_BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}

NUMBER_RE = re.compile(r"[\d.,]+")
SEARCH_CITY_RE = re.compile(r"/search/(?:[^/]+/)*([^/?#]+)")


@dataclass(slots=True)
class Listing:
    city: str
    property_id: str
    property_type: str
    transaction_type: str
    title: str
    location: str
    land_m2: int | None
    construction_m2: int | None
    bedrooms: int | None
    bathrooms: int | None
    price_text: str
    price_amount: int | None
    url: str
    thumbnail_url: str | None
    agency_name: str | None


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return html.unescape(" ".join(value.split()))


def _parse_int(value: str | int | float | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else None


def _parse_price(value: str | None) -> int | None:
    if not value:
        return None
    match = NUMBER_RE.search(value.replace("\xa0", " "))
    if not match:
        return None
    numeric = match.group(0).replace(",", "")
    try:
        return int(float(numeric))
    except ValueError:
        return None


def _build_page_url(base_url: str, page_number: int) -> str:
    parsed = urlparse(base_url)
    query = parse_qs(parsed.query)
    query["page"] = [str(page_number)]
    updated_query = urlencode(query, doseq=True)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            parsed.params,
            updated_query,
            parsed.fragment,
        )
    )


def _page_number_from_url(url: str) -> int:
    parsed = urlparse(url)
    page_values = parse_qs(parsed.query).get("page", [])
    if not page_values:
        return 1
    try:
        return int(page_values[0])
    except (TypeError, ValueError):
        return 1


def _discover_pagination_urls(page: object, current_url: str, max_pages: int) -> list[str]:
    discovered: list[str] = page.evaluate(
        r"""
        ({ currentUrl }) => {
            const current = new URL(currentUrl);
            const anchors = Array.from(document.querySelectorAll('a[href]'));
            const urls = anchors
                .map((a) => {
                    try {
                        return new URL(a.getAttribute('href') || a.href, currentUrl).toString();
                    } catch (_) {
                        return null;
                    }
                })
                .filter((href) => href && href.includes('page='));

            return Array.from(new Set(urls));
        }
        """,
        {"currentUrl": current_url},
    )

    page_urls = [current_url]
    for candidate in discovered:
        parsed_candidate = urlparse(candidate)
        parsed_current = urlparse(current_url)
        if parsed_candidate.netloc != parsed_current.netloc:
            continue
        if parsed_candidate.path.rstrip("/") != parsed_current.path.rstrip("/"):
            continue
        page_urls.append(candidate)

    unique_sorted = sorted(set(page_urls), key=_page_number_from_url)
    return unique_sorted[:max_pages]


def _log_pagination_urls(
    log_file: str | Path | None,
    *,
    run_id: str,
    city: str,
    base_url: str,
    fallback_mode: bool,
    page_urls: Sequence[str],
) -> None:
    if not log_file:
        return

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(
            f"{run_id}\tpagination_debug\tcity={city}\tfallback={str(fallback_mode).lower()}\tbase_url={base_url}\tpages={len(page_urls)}\n"
        )
        for idx, page_url in enumerate(page_urls, start=1):
            handle.write(f"{run_id}\tpagination_url\tcity={city}\tindex={idx}\turl={page_url}\n")


def _infer_city_label(base_url: str) -> str:
    match = SEARCH_CITY_RE.search(base_url)
    if not match:
        return "unknown"
    return match.group(1).replace("_", "-").lower()


def _random_delay(page: object) -> None:
    delay_ms = random.randint(DEFAULT_MIN_DELAY_MS, DEFAULT_MAX_DELAY_MS)
    page.wait_for_timeout(delay_ms)


def _safe_goto(page: object, page_url: str) -> bool:
    for attempt in range(1, DEFAULT_NAVIGATION_RETRIES + 1):
        try:
            page.goto(page_url, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
            return True
        except Exception:
            if attempt == DEFAULT_NAVIGATION_RETRIES:
                return False
            page.wait_for_timeout(DEFAULT_NAVIGATION_RETRY_WAIT_MS * attempt)

    return False


def _normalize_urls(urls: str | Sequence[str]) -> list[str]:
    if isinstance(urls, str):
        return [urls]
    return [url for url in urls if url]


def _get_listings_data(page: object) -> dict[str, object] | None:
    data = page.evaluate(
        r"""
        () => {
          const root = document.querySelector('[data-page]');
          if (!root) return null;

          try {
            const payload = JSON.parse(root.getAttribute('data-page') || '{}');
            return payload?.props?.listingsData ?? null;
          } catch (_) {
            return null;
          }
        }
        """
    )
    return data if isinstance(data, dict) else None


def _extract_records_from_listings_data(
    listings_data: dict[str, object],
    limit: int | None = None,
) -> list[dict[str, str | int | float | None]]:
    raw_rows = listings_data.get("data")
    if not isinstance(raw_rows, list):
        return []

    rows = raw_rows[:limit] if limit is not None else raw_rows
    extracted: list[dict[str, str | int | float | None]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        listing_information = row.get("listing_information") if isinstance(row.get("listing_information"), dict) else {}
        subtype_property = (
            listing_information.get("subtype_property")
            if isinstance(listing_information.get("subtype_property"), dict)
            else {}
        )
        transaction_type = row.get("transaction_type") if isinstance(row.get("transaction_type"), dict) else {}
        default_image = row.get("default_imagen") if isinstance(row.get("default_imagen"), dict) else {}
        location = row.get("location") if isinstance(row.get("location"), dict) else {}
        zone = location.get("zone") if isinstance(location.get("zone"), dict) else {}
        city = location.get("city") if isinstance(location.get("city"), dict) else {}
        agent = row.get("agent") if isinstance(row.get("agent"), dict) else {}
        user = agent.get("user") if isinstance(agent.get("user"), dict) else {}
        office = agent.get("office") if isinstance(agent.get("office"), dict) else {}
        price = row.get("price") if isinstance(row.get("price"), dict) else {}

        slug = _clean_text(str(row.get("slug") or ""))
        property_type = _clean_text(str(subtype_property.get("name") or ""))
        location_text = ", ".join(part for part in [_clean_text(str(zone.get("name") or "")), _clean_text(str(city.get("name") or ""))] if part)
        price_in_dollars = price.get("price_in_dollars")
        price_amount = float(price_in_dollars) if isinstance(price_in_dollars, (int, float)) else None
        price_text = f"USD {price_amount:.2f}" if price_amount is not None else ""

        extracted.append(
            {
                "property_id": slug or _clean_text(str(row.get("key") or row.get("id") or "")),
                "property_type": property_type,
                "transaction_type": _clean_text(str(transaction_type.get("name") or "")),
                "title": property_type,
                "location": location_text,
                "land_m2": listing_information.get("land_m2"),
                "construction_m2": listing_information.get("construction_area_m"),
                "bedrooms": listing_information.get("number_bedrooms"),
                "bathrooms": listing_information.get("number_bathrooms"),
                "price_text": price_text,
                "price_amount": price_amount,
                "url": f"https://remax.bo/propiedad/{slug}" if slug else "",
                "thumbnail_url": _clean_text(str(default_image.get("url") or "")) or None,
                "agency_name": _clean_text(str(office.get("name") or "")),
            }
        )

    return extracted


def _records_to_listings(
    records: list[dict[str, str | int | None]],
    seen_ids: set[str],
    city: str,
) -> list[Listing]:
    listings: list[Listing] = []

    for record in records:
        property_id = _clean_text(record.get("property_id"))
        if not property_id or property_id in seen_ids:
            continue
        seen_ids.add(property_id)

        listings.append(
            Listing(
                city=city,
                property_id=property_id,
                property_type=_clean_text(record.get("property_type")),
                transaction_type=_clean_text(record.get("transaction_type")),
                title=_clean_text(record.get("title")),
                location=_clean_text(record.get("location")),
                land_m2=_parse_int(record.get("land_m2")),
                construction_m2=_parse_int(record.get("construction_m2")),
                bedrooms=_parse_int(record.get("bedrooms")),
                bathrooms=_parse_int(record.get("bathrooms")),
                price_text=_clean_text(record.get("price_text")),
                price_amount=(
                    int(float(record.get("price_amount")))
                    if record.get("price_amount") is not None
                    else _parse_price(record.get("price_text"))
                ),
                url=_clean_text(record.get("url")),
                thumbnail_url=_clean_text(record.get("thumbnail_url")) or None,
                agency_name=_clean_text(record.get("agency_name")) or None,
            )
        )

    return listings


def scrape_listings(
    url: str | Sequence[str] = DEFAULT_URLS,
    limit: int | None = None,
    max_pages: int = 10,
    pagination_log_file: str | Path | None = None,
    pagination_log_run_id: str = "run",
) -> list[Listing]:
    listings: list[Listing] = []
    seen_ids: set[str] = set()
    base_urls = _normalize_urls(url)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 1600},
            user_agent=DEFAULT_USER_AGENT,
            locale="es-BO",
            timezone_id="America/La_Paz",
            extra_http_headers={"Accept-Language": "es-BO,es;q=0.9,en;q=0.8"},
        )

        context.route(
            "**/*",
            lambda route, request: route.abort()
            if request.resource_type in DEFAULT_BLOCKED_RESOURCE_TYPES
            else route.continue_(),
        )

        page = context.new_page()
        page.set_default_timeout(30000)

        for base_url in base_urls:
            city = _infer_city_label(base_url)
            city_start_count = len(listings)

            if not _safe_goto(page, base_url):
                print(f"Could not load base URL for city '{city}': {base_url}")
                continue

            first_page_data = _get_listings_data(page)
            fallback_mode = first_page_data is None
            if first_page_data is not None:
                raw_last_page = first_page_data.get("last_page")
                try:
                    last_page = max(1, int(raw_last_page))
                except (TypeError, ValueError):
                    last_page = 1
                pagination_urls = [_build_page_url(base_url, page_number) for page_number in range(1, min(last_page, max_pages) + 1)]
            else:
                pagination_urls = [_build_page_url(base_url, page_number) for page_number in range(1, max_pages + 1)]

            _log_pagination_urls(
                pagination_log_file,
                run_id=pagination_log_run_id,
                city=city,
                base_url=base_url,
                fallback_mode=fallback_mode,
                page_urls=pagination_urls,
            )

            for page_url in pagination_urls:
                if page.url != page_url and not _safe_goto(page, page_url):
                    break
                _random_delay(page)

                if not page.locator('a.sr-only[href*="/propiedad/"]').count():
                    break

                remaining = None if limit is None else max(limit - len(listings), 0)
                if remaining == 0:
                    break

                listings_data = _get_listings_data(page)
                if listings_data is None:
                    break

                records = _extract_records_from_listings_data(listings_data, remaining)
                page_listings = _records_to_listings(records, seen_ids, city)
                if not page_listings:
                    break

                listings.extend(page_listings)
                if limit is not None and len(listings) >= limit:
                    break

            city_count = len(listings) - city_start_count
            print(f"Processed city '{city}': scraped {city_count} records")

        browser.close()

    return listings


def export_json(listings: list[Listing], output_path: str) -> None:
    Path(output_path).write_text(
        json.dumps([asdict(listing) for listing in listings], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def export_csv(listings: list[Listing], output_path: str) -> None:
    rows = [asdict(listing) for listing in listings]
    fieldnames = list(rows[0].keys()) if rows else [field.name for field in Listing.__dataclass_fields__.values()]

    with Path(output_path).open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def listings_to_dataframe(listings: list[Listing]) -> pd.DataFrame:
    return pd.DataFrame([asdict(listing) for listing in listings])
