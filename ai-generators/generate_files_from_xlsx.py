# ai-generators/generate_files_from_xlsx.py
import os
import sys
import re
import json
import math
import argparse
from datetime import datetime, date
from typing import Any, Dict

import pandas as pd
import numpy as np

# -----------------------------
# Utilities
# -----------------------------
def slugify(text: Any) -> str:
    """Generate clean, URL-friendly slug from text (stable across runs)."""
    if text is None:
        return "untitled"
    s = str(text).strip().lower()
    # remove accents
    try:
        import unicodedata
        s = ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))
    except Exception:
        pass
    s = re.sub(r'[^a-z0-9\s-]', '', s)
    s = re.sub(r'\s+', '-', s).strip('-')
    return s or "untitled"

def json_default(o):
    """Make pandas / numpy / datetime objects JSON-serializable."""
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    # pandas Timestamp/NaT
    if isinstance(o, pd.Timestamp):
        if pd.isna(o):
            return None
        return o.isoformat()
    # numpy scalars
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        if np.isnan(o) or np.isinf(o):
            return None
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    return str(o)

def write_json(path: str, data: Dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=json_default)
    print(f"✅ Generated: {path}")

def write_md(path: str, title: str, slug: str, body: str, extras: Dict[str, Any] = None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    extras = extras or {}
    with open(path, "w", encoding="utf-8") as f:
        f.write("---\n")
        f.write(f"title: {title}\n")
        f.write(f"slug: {slug}\n")
        for k, v in extras.items():
            # keep front matter simple strings/arrays
            if isinstance(v, (list, tuple)):
                f.write(f"{k}: [{', '.join(map(lambda x: str(x), v))}]\n")
            elif v is not None and v != "":
                f.write(f"{k}: {v}\n")
        f.write("---\n\n")
        f.write(body or "")
    print(f"✅ Generated: {path}")

def clean_headers(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def is_empty_value(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return True
    if isinstance(v, (pd.Timestamp,)) and pd.isna(v):
        return True
    s = str(v).strip()
    return s == "" or s.lower() in {"nan", "none", "null", "n/a"}

def row_is_meaningful(row: pd.Series, min_fields: int = 2) -> bool:
    """Consider a row meaningful if it has >= min_fields non-empty (after cleaning)."""
    non_empty = 0
    for v in row.to_dict().values():
        if not is_empty_value(v):
            non_empty += 1
        if non_empty >= min_fields:
            return True
    return False

def coerce_bool(val: Any) -> bool:
    s = str(val).strip().lower()
    return s in {"1", "true", "yes", "y", "on", "t"}

# -----------------------------
# Processors (each returns count)
# -----------------------------
def process_entity_info(df: pd.DataFrame, out_dir: str) -> int:
    """
    Treat entity_info as SINGLE authoritative org row.
    Pick the first meaningful row and write one file: {slug(entity_name)}.json
    """
    df = clean_headers(df)
    if df.empty:
        print("⚠️ 'entity_info' empty — skipping")
        return 0

    # Choose first meaningful row
    chosen = None
    for _, r in df.iterrows():
        if row_is_meaningful(r, min_fields=2):
            chosen = r
            break
    if chosen is None:
        print("⚠️ No meaningful row found in 'entity_info' — skipping")
        return 0

    entity_name = str(chosen.get("entity_name", "")).strip() or "Organization"
    slug = slugify(entity_name)
    path = os.path.join(out_dir, f"{slug}.json")

    # Normalize a few likely columns
    data = {}
    for col, val in chosen.items():
        if is_empty_value(val):
            continue
        data[str(col)] = val

    # aliases
    if "name" not in data:
        data["name"] = entity_name

    write_json(path, data)
    return 1

def process_services(df: pd.DataFrame, out_dir: str) -> int:
    df = clean_headers(df)
    count = 0
    for _, r in df.iterrows():
        # require at least a name-ish field
        service_name = str(r.get("service_name", "") or r.get("title", "") or r.get("name", "")).strip()
        if not service_name and not row_is_meaningful(r, 2):
            continue
        slug = str(r.get("slug", "")).strip() or slugify(service_name) or f"service"
        path = os.path.join(out_dir, f"{slug}.json")

        item = {
            "name": service_name or slug,
        }
        # common fields
        for k in [
            "description", "price_range", "priceRange", "category", "keywords",
            "license_number", "bar_number", "npi_number", "certification_body",
            "service_area_radius_miles"
        ]:
            v = r.get(k)
            if not is_empty_value(v):
                item[k] = v

        # normalize common names
        if "price_range" in item and "priceRange" not in item:
            item["priceRange"] = item.pop("price_range")

        # featured
        feat = r.get("featured")
        if not is_empty_value(feat):
            item["featured"] = coerce_bool(feat)

        write_json(path, item)
        count += 1
    return count

def process_products(df: pd.DataFrame, out_dir: str) -> int:
    df = clean_headers(df)
    count = 0
    for _, r in df.iterrows():
        name = str(r.get("name", "")).strip()
        if not name and not row_is_meaningful(r, 2):
            continue
        slug = str(r.get("slug", "")).strip() or slugify(name) or "product"
        path = os.path.join(out_dir, f"{slug}.json")

        item = {"name": name or slug}
        for k in ["short_description", "description", "price", "features", "sku", "brand", "offers_price_currency"]:
            v = r.get(k)
            if not is_empty_value(v):
                item[k] = v

        write_json(path, item)
        count += 1
    return count

def process_faqs(df: pd.DataFrame, out_dir: str) -> int:
    df = clean_headers(df)
    count = 0
    for _, r in df.iterrows():
        q = str(r.get("question", "")).strip()
        a = str(r.get("answer", "")).strip()
        if not q and not row_is_meaningful(r, 2):
            continue
        slug = str(r.get("slug", "")).strip() or slugify(q) or "faq"
        path = os.path.join(out_dir, f"{slug}.json")

        item = {"question": q or slug, "answer": a}
        write_json(path, item)
        count += 1
    return count

def process_help_articles(df: pd.DataFrame, out_dir: str) -> int:
    df = clean_headers(df)
    count = 0
    for _, r in df.iterrows():
        title = str(r.get("title", "")).strip()
        body = str(r.get("article", "")).strip()
        if not title and not row_is_meaningful(r, 2):
            continue
        slug = str(r.get("slug", "")).strip() or slugify(title) or "article"
        path = os.path.join(out_dir, f"{slug}.md")

        extras = {}
        for k in ["article_type", "keywords", "url", "published_date"]:
            v = r.get(k)
            if not is_empty_value(v):
                # convert timestamps to iso string
                if isinstance(v, (pd.Timestamp, datetime, date)):
                    v = json_default(v)
                extras[k] = v
        write_md(path, title or slug, slug, body, extras=extras)
        count += 1
    return count

def process_reviews(df: pd.DataFrame, out_dir: str) -> int:
    df = clean_headers(df)
    count = 0
    for _, r in df.iterrows():
        if not row_is_meaningful(r, 2):
            continue
        customer = str(r.get("customer_name", "")).strip()
        title = str(r.get("review_title", "")).strip()
        dateval = r.get("date")
        date_part = ""
        if not is_empty_value(dateval):
            date_part = slugify(json_default(dateval))
        # make a stable slug from name+title+date
        base = "-".join(filter(None, [customer, title, date_part])) or "review"
        slug = slugify(base)
        path = os.path.join(out_dir, f"{slug}.json")

        item = {}
        for k, v in r.items():
            if is_empty_value(v):
                continue
            item[str(k)] = v

        write_json(path, item)
        count += 1
    return count

def process_locations(df: pd.DataFrame, out_dir: str) -> int:
    df = clean_headers(df)
    count = 0
    for _, r in df.iterrows():
        # require at least an address or a name
        nm = str(r.get("name", "") or r.get("location_name", "") or r.get("entity_name", "")).strip()
        addr = str(r.get("address", "") or r.get("address_street", "")).strip()
        if not (nm or addr) and not row_is_meaningful(r, 2):
            continue

        slug = str(r.get("slug", "")).strip()
        if not slug:
            # Prefer something stable from name or address_city/state
            city = str(r.get("address_city", "")).strip()
            state = str(r.get("address_state", "")).strip()
            base = nm or f"{city}-{state}" or "location"
            slug = slugify(base)

        path = os.path.join(out_dir, f"{slug}.json")

        item = {}
        for k, v in r.items():
            if is_empty_value(v):
                continue
            item[str(k)] = v

        write_json(path, item)
        count += 1
    return count

def process_team(df: pd.DataFrame, out_dir: str) -> int:
    df = clean_headers(df)
    count = 0
    for _, r in df.iterrows():
        name = str(r.get("member_name", "") or r.get("name", "")).strip()
        if not name and not row_is_meaningful(r, 2):
            continue
        slug = str(r.get("slug", "")).strip() or slugify(name) or "member"
        path = os.path.join(out_dir, f"{slug}.json")

        item = {"name": name or slug}
        for k, v in r.items():
            if is_empty_value(v):
                continue
            if k in {"member_name"}:
                continue
            item[str(k)] = v

        write_json(path, item)
        count += 1
    return count

def process_awards(df: pd.DataFrame, out_dir: str) -> int:
    df = clean_headers(df)
    count = 0
    for _, r in df.iterrows():
        title = str(r.get("title", "") or r.get("award", "")).strip()
        if not title and not row_is_meaningful(r, 2):
            continue
        slug = str(r.get("slug", "")).strip() or slugify(title) or "award"
        path = os.path.join(out_dir, f"{slug}.json")

        item = {}
        for k, v in r.items():
            if is_empty_value(v):
                continue
            item[str(k)] = v

        write_json(path, item)
        count += 1
    return count

def process_press(df: pd.DataFrame, out_dir: str) -> int:
    df = clean_headers(df)
    count = 0
    for _, r in df.iterrows():
        title = str(r.get("title", "")).strip()
        url = str(r.get("url", "")).strip()
        if not (title or url) and not row_is_meaningful(r, 2):
            continue
        slug = str(r.get("slug", "")).strip() or slugify(title or url) or "press"
        path = os.path.join(out_dir, f"{slug}.json")

        item = {}
        for k, v in r.items():
            if is_empty_value(v):
                continue
            item[str(k)] = v

        write_json(path, item)
        count += 1
    return count

def process_case_studies(df: pd.DataFrame, out_dir: str) -> int:
    df = clean_headers(df)
    count = 0
    for _, r in df.iterrows():
        title = str(r.get("title", "")).strip()
        if not title and not row_is_meaningful(r, 2):
            continue
        slug = str(r.get("slug", "")).strip() or slugify(title) or "case-study"
        path = os.path.join(out_dir, f"{slug}.json")

        item = {}
        for k, v in r.items():
            if is_empty_value(v):
                continue
            item[str(k)] = v

        write_json(path, item)
        count += 1
    return count

# -----------------------------
# Main
# -----------------------------
SHEET_DIR_MAP = {
    "entity_info": "schemas/organization",
    "Services": "schemas/services",
    "Products": "schemas/products",
    "FAQs": "schemas/faqs",
    "Help Articles": "schemas/help-articles",
    "Reviews": "schemas/reviews",
    "Locations": "schemas/locations",
    "Team": "schemas/team",
    "Awards & Certifications": "schemas/awards",
    # Accept both spellings for press/news
    "Press/News Mentions": "schemas/press",
    "PressNews Mentions": "schemas/press",
    "Case Studies": "schemas/case-studies",
}

PROCESSORS = {
    "entity_info": process_entity_info,
    "Services": process_services,
    "Products": process_products,
    "FAQs": process_faqs,
    "Help Articles": process_help_articles,
    "Reviews": process_reviews,
    "Locations": process_locations,
    "Team": process_team,
    "Awards & Certifications": process_awards,
    "Press/News Mentions": process_press,
    "PressNews Mentions": process_press,
    "Case Studies": process_case_studies,
}

def main(input_file: str = "templates/AI-Visibility-Master-Template.xlsx"):
    print(f"📂 Opening Excel file: {input_file}")

    if not os.path.exists(input_file):
        print(f"❌ FATAL: Excel file not found at {input_file}")
        sys.exit(1)

    try:
        xlsx = pd.ExcelFile(input_file)
    except Exception as e:
        print(f"❌ Failed to load Excel file: {e}")
        sys.exit(1)

    print(f"📄 Available sheets in workbook: {xlsx.sheet_names}")

    total_written = 0
    for sheet_name in xlsx.sheet_names:
        if sheet_name not in SHEET_DIR_MAP:
            print(f"⚠️ Skipping unsupported sheet: {sheet_name}")
            continue

        print(f"\n📄 Processing sheet: {sheet_name}")
        try:
            df = xlsx.parse(sheet_name)
        except Exception as e:
            print(f"❌ Failed parsing '{sheet_name}': {e}")
            continue

        df = clean_headers(df)
        if df.empty:
            print(f"⚠️ Sheet '{sheet_name}' is empty — skipping")
            continue

        out_dir = SHEET_DIR_MAP[sheet_name]
        os.makedirs(out_dir, exist_ok=True)
        print(f"📁 Output directory: {out_dir}")

        processor = PROCESSORS[sheet_name]
        try:
            count = processor(df, out_dir)
            print(f"📊 Total processed in '{sheet_name}': {count} items")
            total_written += count
        except Exception as e:
            print(f"❌ Error while processing '{sheet_name}': {e}")

    if total_written == 0:
        print("\n⚠️ No files were generated. Check that your sheets have meaningful rows.")
    else:
        print(f"\n🎉 Generation complete. Total files written: {total_written}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate schema files from Excel.")
    parser.add_argument("--input", type=str, default="templates/AI-Visibility-Master-Template.xlsx",
                        help="Path to input Excel file")
    args = parser.parse_args()
    main(args.input)
