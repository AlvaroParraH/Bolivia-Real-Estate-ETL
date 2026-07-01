from __future__ import annotations

import csv
import html
import json
import random
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from collections.abc import Sequence

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

        page = context.new_page()
        page.set_default_timeout(30000)

        for base_url in base_urls:
            city = _infer_city_label(base_url)

            for page_number in range(1, max_pages + 1):
                page_url = _build_page_url(base_url, page_number)
                page.goto(page_url, wait_until="domcontentloaded")
                try:
                    page.wait_for_load_state("networkidle", timeout=5000)
                except Exception:
                    pass
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

                listings.extend(page_listings)
                if limit is not None and len(listings) >= limit:
                    break

            if limit is not None and len(listings) >= limit:
                break

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

    with Path(output_path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def listings_to_dataframe(listings: list[Listing]) -> pd.DataFrame:
    return pd.DataFrame([asdict(listing) for listing in listings])