from __future__ import annotations

import json
import random
import re
from dataclasses import asdict, dataclass
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import pandas as pd


DEFAULT_LISTINGS_URL = "https://firmacasas.com/propiedades"
DEFAULT_FILTER_API_URL = "https://firmacasas.com/api/properties/property/filter-properties/"
DEFAULT_CITIES_API_URL = "https://firmacasas.com/api/parameter/city/cities/"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/149.0.0.0 Safari/537.36"
)
DEFAULT_REQUEST_RETRIES = 3
DEFAULT_REQUEST_TIMEOUT = 30
DEFAULT_MIN_DELAY_MS = 150
DEFAULT_MAX_DELAY_MS = 450
DEFAULT_CATEGORY_IDS = (1,)
DEFAULT_TYPE_IDS = (2,)

PROPERTY_CATEGORY_LABELS = {
    1: "Casa",
    2: "Oficina",
    3: "Departamento",
    4: "Local comercial",
    5: "Galpón",
    6: "Terreno industrial",
    7: "Casa comercial",
    8: "Edificio",
    9: "Quinta",
    10: "Terreno",
}

PROPERTY_TYPE_LABELS = {
    0: "Alquiler",
    1: "Anticretico",
    2: "Venta",
}

CURRENCY_LABELS = {
    0: "USD",
    1: "Bs.",
}

NUMBER_RE = re.compile(r"[\d.,]+")


@dataclass(slots=True)
class Listing:
    city: str
    property_id: str
    listing_id: int
    property_category: str
    transaction_type: str
    title: str
    location: str
    address: str
    land_m2: float | None
    construction_m2: float | None
    bedrooms: int | None
    bathrooms: int | None
    parking_spaces: int | None
    price_text: str
    price_amount: float | None
    currency: str | None
    url: str
    thumbnail_url: str | None
    agent_name: str | None
    agent_phone: str | None


def _clean_text(value: str | None) -> str:
    if not value:
        return ""
    return unescape(" ".join(value.split()))


def _parse_float(value: str | int | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return None
    try:
        return float(cleaned)
    except ValueError:
        match = NUMBER_RE.search(cleaned)
        if not match:
            return None
        try:
            return float(match.group(0).replace(",", ""))
        except ValueError:
            return None


def _parse_int(value: str | int | float | None) -> int | None:
    number = _parse_float(value)
    if number is None:
        return None
    return int(number)


def _format_price(price: str | int | float | None, currency_type: int | None) -> str:
    amount = _parse_float(price)
    if amount is None:
        return ""
    currency = CURRENCY_LABELS.get(currency_type, "")
    return f"{currency} {amount:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _random_delay() -> None:
    delay_ms = random.randint(DEFAULT_MIN_DELAY_MS, DEFAULT_MAX_DELAY_MS)
    if delay_ms <= 0:
        return
    import time

    time.sleep(delay_ms / 1000)


def _request_json(url: str, *, payload: dict | None = None) -> dict | list:
    data = None
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    last_error: Exception | None = None
    for attempt in range(1, DEFAULT_REQUEST_RETRIES + 1):
        request = Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
        try:
            with urlopen(request, timeout=DEFAULT_REQUEST_TIMEOUT) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if attempt == DEFAULT_REQUEST_RETRIES:
                break
            _random_delay()

    raise RuntimeError(f"Failed to fetch JSON from {url}: {last_error}")


def _build_filter_payload(
    *,
    city_ids: list[int] | None = None,
    property_category_ids: list[int] | None = None,
    property_type_ids: list[int] | None = None,
    bedrooms: int | None = None,
    bathrooms: int | None = None,
    parking_spaces: int | None = None,
) -> dict:
    return {
        "agent": None,
        "area_max": 0,
        "area_min": 0,
        "city": city_ids or None,
        "bathrooms": [bathrooms] if bathrooms is not None else None,
        "features": None,
        "bedrooms": [bedrooms] if bedrooms is not None else None,
        "num_parking": [parking_spaces] if parking_spaces is not None else None,
        "price_max": 0,
        "price_min": 0,
        "property_category": property_category_ids or None,
        "property_code": "",
        "property_type": property_type_ids or None,
        "zones": None,
        "current_user": None,
    }


def fetch_cities() -> list[dict]:
    data = _request_json(DEFAULT_CITIES_API_URL)
    if not isinstance(data, list):
        raise RuntimeError("Unexpected cities payload from Firmacasas API")
    return data


def _extract_city_name(record: dict) -> str:
    zone = record.get("zone") or {}
    city = zone.get("city") or {}
    city_name = _clean_text(city.get("name"))
    return city_name or "Unknown"


def _build_listing_url(listing_id: int) -> str:
    return f"https://firmacasas.com/propiedad/{listing_id}"


def _record_to_listing(record: dict) -> Listing:
    listing_id = int(record["id"])
    currency_type = _parse_int(record.get("currency_type"))
    city_name = _extract_city_name(record)
    zone_name = _clean_text((record.get("zone") or {}).get("name"))
    location = f"{city_name} - {zone_name}" if zone_name else city_name
    price_text = _format_price(record.get("price"), currency_type)

    return Listing(
        city=city_name,
        property_id=_clean_text(record.get("code")) or str(listing_id),
        listing_id=listing_id,
        property_category=PROPERTY_CATEGORY_LABELS.get(_parse_int(record.get("property_category")) or -1, "Unknown"),
        transaction_type=PROPERTY_TYPE_LABELS.get(_parse_int(record.get("property_type")) or -1, "Unknown"),
        title=_clean_text(record.get("property_title")),
        location=location,
        address=_clean_text(record.get("address")),
        land_m2=_parse_float(record.get("total_area")),
        construction_m2=_parse_float(record.get("built_surface")),
        bedrooms=_parse_int(record.get("bedrooms")),
        bathrooms=_parse_int(record.get("bathrooms")),
        parking_spaces=_parse_int(record.get("num_parking")),
        price_text=price_text,
        price_amount=_parse_float(record.get("price")),
        currency=CURRENCY_LABELS.get(currency_type),
        url=_build_listing_url(listing_id),
        thumbnail_url=_clean_text(record.get("banner")) or None,
        agent_name=_clean_text((record.get("created_by") or {}).get("full_name")) or None,
        agent_phone=_clean_text((record.get("created_by") or {}).get("phone")) or None,
    )


def scrape_listings(
    *,
    city_ids: list[int] | None = None,
    property_category_ids: list[int] | None = None,
    property_type_ids: list[int] | None = None,
    bedrooms: int | None = None,
    bathrooms: int | None = None,
    parking_spaces: int | None = None,
    limit: int | None = None,
) -> list[Listing]:
    payload = _build_filter_payload(
        city_ids=city_ids,
        property_category_ids=property_category_ids or list(DEFAULT_CATEGORY_IDS),
        property_type_ids=property_type_ids or list(DEFAULT_TYPE_IDS),
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        parking_spaces=parking_spaces,
    )

    page_number = 1
    listings: list[Listing] = []

    while True:
        query = urlencode({"page": page_number})
        page_url = f"{DEFAULT_FILTER_API_URL}?{query}"
        response = _request_json(page_url, payload=payload)
        if not isinstance(response, dict):
            raise RuntimeError("Unexpected listings payload from Firmacasas API")

        records = response.get("results") or []
        if not records:
            break

        for record in records:
            listings.append(_record_to_listing(record))
            if limit is not None and len(listings) >= limit:
                return listings[:limit]

        if not response.get("next"):
            break

        page_number += 1
        _random_delay()

    return listings


def listings_to_dataframe(listings: list[Listing]) -> pd.DataFrame:
    return pd.DataFrame(asdict(listing) for listing in listings)


def export_json(listings: list[Listing], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump([asdict(listing) for listing in listings], handle, ensure_ascii=False, indent=2)