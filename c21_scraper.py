from __future__ import annotations

import csv
import html
import json
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from collections.abc import Sequence
from urllib.parse import parse_qs, urlparse

import pandas as pd
from playwright.sync_api import sync_playwright


DEFAULT_URL = (
    "https://c21.com.bo/v/resultados/"
    "tipo_casa-o-casa-en-condominio/operacion_venta/en-pais_bolivia/en-estado_la-paz"
)

DEFAULT_URL_SANTA_CRUZ = (
    "https://c21.com.bo/v/resultados/"
    "tipo_casa-o-casa-en-condominio/operacion_venta/en-pais_bolivia/en-estado_santa-cruz"
)

DEFAULT_URL_COCHABAMBA = (
    "https://c21.com.bo/v/resultados/"
    "tipo_casa-o-casa-en-condominio/operacion_venta/en-pais_bolivia/en-estado_cochabamba"
)

DEFAULT_URL_BENI = (
    "https://c21.com.bo/v/resultados/"
    "tipo_casa-o-casa-en-condominio/operacion_venta/en-pais_bolivia/en-estado_beni"
)

DEFAULT_URL_CHUQUISACA = (
    "https://c21.com.bo/v/resultados/"
    "tipo_casa-o-casa-en-condominio/operacion_venta/en-pais_bolivia/en-estado_chuquisaca"
)

DEFAULT_URL_ORURO = (
    "https://c21.com.bo/v/resultados/"
    "tipo_casa-o-casa-en-condominio/operacion_venta/en-pais_bolivia/en-estado_oruro"
)

DEFAULT_URL_POTOSI = (
    "https://c21.com.bo/v/resultados/"
    "tipo_casa-o-casa-en-condominio/operacion_venta/en-pais_bolivia/en-estado_potosi"
)

DEFAULT_URL_TARIJA = (
    "https://c21.com.bo/v/resultados/"
    "tipo_casa-o-casa-en-condominio/operacion_venta/en-pais_bolivia/en-estado_tarija"
)

DEFAULT_URLS = (
    DEFAULT_URL,
    DEFAULT_URL_SANTA_CRUZ,
    DEFAULT_URL_COCHABAMBA,
    DEFAULT_URL_BENI,
    DEFAULT_URL_CHUQUISACA,
    DEFAULT_URL_ORURO,
    DEFAULT_URL_POTOSI,
    DEFAULT_URL_TARIJA,
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/149.0.0.0 Safari/537.36"
)
DEFAULT_MIN_DELAY_MS = 1200
DEFAULT_MAX_DELAY_MS = 2600
DEFAULT_NAVIGATION_RETRIES = 3
DEFAULT_NAVIGATION_RETRY_WAIT_MS = 1500
DEFAULT_BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}

NUMBER_RE = re.compile(r"[\d.,]+")
CITY_RE = re.compile(r"en-estado_([^/]+)")


@dataclass(slots=True)
class Listing:
    city: str
    property_id: str
    property_type: str
    title: str
    location: str
    land_m2: int | None
    construction_m2: int | None
    bedrooms: int | None
    bathrooms: int | None
    parking_spaces: int | None
    price_text: str
    price_amount: int | None
    url: str
    thumbnail_url: str | None
    map_google_url: str | None
    map_latitude: float | None
    map_longitude: float | None


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return html.unescape(" ".join(value.split()))


def _parse_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    digits = re.sub(r"[^\d]", "", value)
    return int(digits) if digits else None


def _parse_price(value: str | None) -> int | None:
    if not value:
        return None
    match = NUMBER_RE.search(value.replace("\xa0", " "))
    if not match:
        return None
    numeric = match.group(0).replace(".", "").replace(",", "")
    return int(numeric) if numeric else None


def _parse_float(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value.strip())
    except ValueError:
        return None


def _parse_google_maps_coordinates(google_maps_url: str | None) -> tuple[float | None, float | None]:
    if not google_maps_url:
        return None, None

    normalized = html.unescape(google_maps_url).strip()
    parsed = urlparse(normalized)
    query = parse_qs(parsed.query)

    daddr = query.get("daddr", [""])[0]
    if daddr and "," in daddr:
        lat_text, lng_text = (part.strip() for part in daddr.split(",", maxsplit=1))
        lat, lng = _parse_float(lat_text), _parse_float(lng_text)
        if lat is not None and lng is not None:
            return lat, lng

    ll = query.get("ll", [""])[0]
    if ll and "," in ll:
        lat_text, lng_text = (part.strip() for part in ll.split(",", maxsplit=1))
        lat, lng = _parse_float(lat_text), _parse_float(lng_text)
        if lat is not None and lng is not None:
            return lat, lng

    path_match = re.search(r"@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)", normalized)
    if path_match:
        return _parse_float(path_match.group(1)), _parse_float(path_match.group(2))

    return None, None


def _build_page_url(base_url: str, page_number: int) -> str:
    if page_number <= 1:
        return base_url.rstrip("/")
    return f"{base_url.rstrip('/')}/pagina_{page_number}"


def _infer_city_label(base_url: str) -> str:
    match = CITY_RE.search(base_url)
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


def _close_extra_pages(context: object, keep_pages: Sequence[object]) -> None:
    keep_ids = {id(page) for page in keep_pages}
    for extra_page in list(context.pages):
        if id(extra_page) in keep_ids:
            continue
        try:
            extra_page.close()
        except Exception:
            pass


def _extract_records(page: object, limit: int | None = None) -> list[dict[str, str | int | None]]:
    return page.locator('a.btnVerDetalle[href*="/propiedad/"]').evaluate_all(
        """
        (buttons, limit) => buttons.slice(0, limit ?? buttons.length).map((button) => {
          const card = button.closest('div.flex-grow-1');
          const titleLink = card?.querySelector('a.stretched-link[href*="/propiedad/"]');
          const typeNode = card?.querySelector('div.text-info.fw-bold');
          const locationNode = card?.querySelector('h2');
          const detailNodes = card ? Array.from(card.querySelectorAll('h3')) : [];
          const priceNode = card?.querySelector('h5');
          const imageNode = card?.querySelector('img');

          const detailsText = detailNodes.map((node) => node.textContent?.trim() || '');
          const landConstruction = detailsText[0] || '';
          const stats = detailsText[1] || '';

          const landMatch = landConstruction.match(/([\d.,]+)\s*m²\s*Terreno/i);
          const constructionMatch = landConstruction.match(/([\d.,]+)\s*m²\s*Construcción/i);
          const bedroomMatch = stats.match(/(\d+)\s*Rec\.?/i);
          const bathroomMatch = stats.match(/(\d+)\s*Bañ/i);
          const parkingMatch = stats.match(/(\d+)\s*Estac\.?/i);

          const href = titleLink?.href || button.href;
          const idMatch = href.match(/\/propiedad\/(\d+)_/);

          return {
            property_id: idMatch?.[1] || '',
            property_type: typeNode?.textContent || '',
            title: titleLink?.textContent || '',
            location: locationNode?.textContent || '',
            land_m2: landMatch ? Number(landMatch[1].replace(/[^\d]/g, '')) : null,
            construction_m2: constructionMatch ? Number(constructionMatch[1].replace(/[^\d]/g, '')) : null,
            bedrooms: bedroomMatch ? Number(bedroomMatch[1]) : null,
            bathrooms: bathroomMatch ? Number(bathroomMatch[1]) : null,
            parking_spaces: parkingMatch ? Number(parkingMatch[1]) : null,
            price_text: priceNode?.textContent || '',
            url: href,
            thumbnail_url: imageNode?.src || null,
          };
        })
        """,
        limit,
    )


def _extract_map_details(page: object, property_url: str) -> dict[str, str | float | None]:
    details: dict[str, str | float | None] = {
        "map_google_url": None,
        "map_latitude": None,
        "map_longitude": None,
    }

    if not property_url or not _safe_goto(page, property_url):
        return details

    page.wait_for_timeout(800)

    page.evaluate(
        r"""
        () => {
          window.__c21OpenedUrls = [];
          window.open = function (...args) {
            try {
              window.__c21OpenedUrls.push(args[0] || '');
            } catch (_) {}
                        // Avoid opening extra tabs/popups; we only need the URL.
                        return null;
          };
        }
        """
    )

    open_map_button = page.get_by_role("button", name=re.compile(r"open\s*map", re.IGNORECASE)).first

    if open_map_button.count() == 0:
        # Some listings require opening the map section before the Open Map button appears.
        map_tab_button = page.get_by_role("button", name=re.compile(r"^mapa$", re.IGNORECASE)).first
        if map_tab_button.count() > 0:
            try:
                map_tab_button.click(timeout=5000)
                page.wait_for_timeout(600)
            except Exception:
                pass

        open_map_button = page.get_by_role("button", name=re.compile(r"open\s*map", re.IGNORECASE)).first

    if open_map_button.count() == 0:
        return details

    try:
        open_map_button.click(timeout=5000)
        page.wait_for_timeout(1000)
    except Exception:
        return details

    candidate_url = page.evaluate(
        r"""
        () => {
          const opened = Array.isArray(window.__c21OpenedUrls) ? window.__c21OpenedUrls : [];
          const openedUrl = opened.find((url) => /google\.|maps\./i.test(url || ''));
          if (openedUrl) return openedUrl;

          const links = Array.from(document.querySelectorAll('a[href]')).map((a) => a.href || '');
          return links.find((url) => /google\.|maps\./i.test(url || '')) || null;
        }
        """
    )

    clean_url = _clean_text(candidate_url) or None
    lat, lng = _parse_google_maps_coordinates(clean_url)

    details["map_google_url"] = clean_url
    details["map_latitude"] = lat
    details["map_longitude"] = lng
    return details


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
                title=_clean_text(record.get("title")),
                location=_clean_text(record.get("location")),
                land_m2=_parse_int(record.get("land_m2")),
                construction_m2=_parse_int(record.get("construction_m2")),
                bedrooms=_parse_int(record.get("bedrooms")),
                bathrooms=_parse_int(record.get("bathrooms")),
                parking_spaces=_parse_int(record.get("parking_spaces")),
                price_text=_clean_text(record.get("price_text")),
                price_amount=_parse_price(record.get("price_text")),
                url=_clean_text(record.get("url")),
                thumbnail_url=_clean_text(record.get("thumbnail_url")) or None,
                map_google_url=None,
                map_latitude=None,
                map_longitude=None,
            )
        )

    return listings


def _normalize_urls(urls: str | Sequence[str]) -> list[str]:
    if isinstance(urls, str):
        return [urls]
    return [url for url in urls if url]


def scrape_listings(
    url: str | Sequence[str] = DEFAULT_URLS,
    limit: int | None = None,
    max_pages: int = 10,
    enrich_map_details: bool = True,
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
        detail_page = context.new_page()
        page.set_default_timeout(30000)
        detail_page.set_default_timeout(30000)

        for base_url in base_urls:
            city = _infer_city_label(base_url)
            city_start_count = len(listings)

            for page_number in range(1, max_pages + 1):
                page_url = _build_page_url(base_url, page_number)
                if not _safe_goto(page, page_url):
                    break
                _random_delay(page)

                if not page.locator('a.btnVerDetalle[href*="/propiedad/"]').count():
                    break

                remaining = None if limit is None else max(limit - len(listings), 0)
                if remaining == 0:
                    break

                records = _extract_records(page, remaining)
                page_listings = _records_to_listings(records, seen_ids, city)
                if not page_listings:
                    break

                if enrich_map_details:
                    for listing in page_listings:
                        map_details = _extract_map_details(detail_page, listing.url)
                        listing.map_google_url = map_details["map_google_url"]
                        listing.map_latitude = map_details["map_latitude"]
                        listing.map_longitude = map_details["map_longitude"]
                        _close_extra_pages(context, (page, detail_page))

                listings.extend(page_listings)
                if limit is not None and len(listings) >= limit:
                    break

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