import argparse
import csv
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


BASE_URL = "http://www.phct.com.tn"
CATALOG_URL = f"{BASE_URL}/index.php/catalogue/medicament-humain/form/25/"
EXPORT_URL = f"{BASE_URL}/index.php/component/fabrik/list/31?Itemid=701&format=csv"

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "sources"
RAW_MEDICINES_CSV = OUTPUT_DIR / "pct_human_medicines_raw.csv"
REFERENCE_OPTIONS_CSV = OUTPUT_DIR / "pct_human_medicines_reference_options.csv"
RECENT_RICH_ROWS_CSV = OUTPUT_DIR / "pct_human_medicines_recent_rich_rows.csv"
SERVER_EXPORT_CSV = OUTPUT_DIR / "pct_human_medicines_server_export.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

SELECTS = {
    "medicine": "___libelle",
    "laboratory": "___code_labo",
    "therapeutic_class": "___code_classe",
    "dci": "___code_DCI1",
}

STRENGTH_RE = re.compile(
    r"(?ix)"
    r"\b\d+(?:[.,]\d+)?\s*"
    r"(?:mg|g|mcg|ug|ml|l|ui|iu|mui|%|mmol|mEq|gbq|kbq|mbq)"
    r"(?:\s*/\s*\d+(?:[.,]\d+)?\s*(?:mg|g|mcg|ug|ml|l|ui|iu|mui|%))?"
)


def now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch_text(session, url, timeout=60):
    response = session.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def clean_text(value):
    if value is None:
        return ""
    return re.sub(r"\s+", " ", html.unescape(str(value))).strip()


def parse_options(soup, select_id):
    select = soup.find("select", id=select_id)
    if not select:
        return []

    rows = []
    for option in select.find_all("option"):
        label = clean_text(option.get_text(" "))
        value = clean_text(option.get("value", ""))
        if not value and label.lower() in {"", "veuillez choisir"}:
            continue
        if not label and not value:
            continue
        rows.append(
            {
                "value": value,
                "label": label or value,
                "css_class": clean_text(" ".join(option.get("class", []))),
            }
        )
    return rows


def guess_brand(label):
    strength_match = STRENGTH_RE.search(label)
    if strength_match:
        before_strength = label[: strength_match.start()].strip()
        return before_strength or label.split()[0]
    return label.split()[0] if label.split() else ""


def guess_strength(label):
    match = STRENGTH_RE.search(label)
    return match.group(0).replace(" ", "") if match else ""


def write_raw_medicines(medicines, scraped_at):
    fieldnames = [
        "row_number",
        "medicine_label",
        "medicine_value",
        "brand_guess",
        "strength_guess",
        "source_url",
        "scraped_at_utc",
    ]
    with RAW_MEDICINES_CSV.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for index, row in enumerate(medicines, start=1):
            label = row["label"]
            writer.writerow(
                {
                    "row_number": index,
                    "medicine_label": label,
                    "medicine_value": row["value"],
                    "brand_guess": guess_brand(label),
                    "strength_guess": guess_strength(label),
                    "source_url": CATALOG_URL,
                    "scraped_at_utc": scraped_at,
                }
            )


def write_reference_options(reference_options, scraped_at):
    fieldnames = ["option_type", "value", "label", "css_class", "source_url", "scraped_at_utc"]
    with REFERENCE_OPTIONS_CSV.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for option_type, rows in reference_options.items():
            for row in rows:
                writer.writerow(
                    {
                        "option_type": option_type,
                        "value": row["value"],
                        "label": row["label"],
                        "css_class": row["css_class"],
                        "source_url": CATALOG_URL,
                        "scraped_at_utc": scraped_at,
                    }
                )


def extract_fabrik_list_config(page_html):
    match = re.search(
        r"var\s+list\s*=\s*new\s+FbList\('31',\s*(\{.*?\})\s*\);",
        page_html,
        flags=re.DOTALL,
    )
    if not match:
        return None
    return json.loads(match.group(1))


def flatten_rich_rows(config):
    if not config:
        return []

    rows = []
    for group in config.get("data", []):
        for row in group:
            data = row.get("data", {})
            flattened = {
                "fabrik_row_id": row.get("id", ""),
                "cursor": row.get("cursor", ""),
                "reported_total": row.get("total", ""),
            }
            for key, value in data.items():
                if key.startswith("fabrik_") or key in {"slug", "__pk_val"}:
                    continue
                clean_key = key.replace("produits___", "")
                flattened[clean_key] = clean_text(value)
            rows.append(flattened)
    return rows


def write_rich_rows(rows, scraped_at):
    if not rows:
        return

    fieldnames = []
    for row in rows:
        row["source_url"] = CATALOG_URL
        row["scraped_at_utc"] = scraped_at
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    with RECENT_RICH_ROWS_CSV.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def try_server_export(session):
    response = session.get(EXPORT_URL, headers=HEADERS, timeout=120)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    text = response.text.strip()

    if text.startswith("{"):
        payload = response.json()
        raise RuntimeError(f"PCT CSV export failed: {payload.get('err', payload)}")

    if "produits" not in text[:1000].lower() and "libelle" not in text[:1000].lower():
        raise RuntimeError("PCT CSV export did not look like a medicine table.")

    SERVER_EXPORT_CSV.write_text(response.text, encoding="utf-8-sig")
    return SERVER_EXPORT_CSV


def scrape_catalog(include_server_export=False):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    scraped_at = now_iso()

    with requests.Session() as session:
        page_html = fetch_text(session, CATALOG_URL)

        server_export_path = None
        if include_server_export:
            try:
                server_export_path = try_server_export(session)
            except Exception as exc:
                print(f"Server CSV export unavailable: {exc}", file=sys.stderr)

    soup = BeautifulSoup(page_html, "html.parser")
    parsed = {name: parse_options(soup, select_id) for name, select_id in SELECTS.items()}

    medicines = parsed.pop("medicine", [])
    if not medicines:
        raise RuntimeError("No medicines were found in the PCT catalogue dropdown.")

    write_raw_medicines(medicines, scraped_at)
    write_reference_options(parsed, scraped_at)

    recent_rows = flatten_rich_rows(extract_fabrik_list_config(page_html))
    write_rich_rows(recent_rows, scraped_at)

    return {
        "medicine_count": len(medicines),
        "reference_count": sum(len(rows) for rows in parsed.values()),
        "recent_rich_row_count": len(recent_rows),
        "server_export_path": str(server_export_path) if server_export_path else "",
    }


def main():
    parser = argparse.ArgumentParser(
        description="Collect raw human medicine data from the PCT catalogue."
    )
    parser.add_argument(
        "--try-server-export",
        action="store_true",
        help="Also try the Fabrik CSV export endpoint; the site may return a server-side error.",
    )
    args = parser.parse_args()

    summary = scrape_catalog(include_server_export=args.try_server_export)
    print(f"Saved {summary['medicine_count']} raw medicines to {RAW_MEDICINES_CSV}")
    print(f"Saved {summary['reference_count']} reference options to {REFERENCE_OPTIONS_CSV}")
    print(f"Saved {summary['recent_rich_row_count']} recent rich rows to {RECENT_RICH_ROWS_CSV}")
    if summary["server_export_path"]:
        print(f"Saved server CSV export to {summary['server_export_path']}")


if __name__ == "__main__":
    main()
