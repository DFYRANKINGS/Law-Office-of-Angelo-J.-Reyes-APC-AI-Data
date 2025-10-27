# ai-generators/generate_files_from_xlsx.py
import os
import sys
import re
import json
import hashlib
from datetime import datetime, date

import pandas as pd

# -----------------------
# Utilities
# -----------------------
def log(msg: str):
    print(msg, flush=True)

def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def slugify(text):
    """Generate clean, URL-friendly slug from text."""
    if text is None:
        return "untitled"
    text = str(text)
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text.strip().lower())
    return text or "untitled"

def safe_filename(name: str, ext: str):
    name = slugify(name)
    if not ext.startswith("."):
        ext = "." + ext
    return f"{name}{ext}"

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def is_empty_row(sr: pd.Series) -> bool:
    # Treat a row with all NaN or empty strings as empty
    if sr.dropna().empty:
        return True
    for v in sr.values:
        if isinstance(v, str) and v.strip():
            return False
        if not (isinstance(v, float) and pd.isna(v)):
            return False
    return True

def coerce_json_value(v):
    """Make values JSON-serializable and stable."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None

    # Pandas / numpy scalars -> native python
    if hasattr(v, "item"):
        try:
            v = v.item()
        except Exception:
            pass

    # Pandas Timestamp / Python datetime & date -> ISO string
    if isinstance(v, pd.Timestamp):
        # If it looks like a date-only value, keep it date-only
        if v.tz is None and v.hour == 0 and v.minute == 0 and v.second == 0 and v.microsecond == 0:
            return v.date().isoformat()
        return v.isoformat()
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()

    # Containers: recurse
    if isinstance(v, (list, tuple)):
        return [coerce_json_value(x) for x in v]
    if isinstance(v, dict):
        return {str(k): coerce_json_value(val) for k, val in v.items()}

    # Basic types (str, int, float, bool) are fine
    return v

def write_json(path: str, data: dict):
    # Coerce all values
    def _coerce(obj):
        if isinstance(obj, dict):
            return {str(k): _coerce(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_coerce(x) for x in obj]
        return coerce_json_value(obj)

    payload = _coerce(data)

    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log(f"✅ Generated: {path}")

def write_text(path: str, text: str):
    ensure_dir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    log(f"✅ Generated: {path}")

def stable_key(row: pd.Series, key_columns: list[str]) -> str:
    """
    Build a stable key based on the subset of columns that define identity.
    If none are present, hash the non-empty values for determinism.
    """
    norm = {}
    if isinstance(row, pd.Series):
        for c in key_columns:
            if c in row.index and pd.notna(row[c]) and str(row[c]).strip():
                norm[c] = str(row[c]).strip()
    else:
        # defensive fallback if a dict somehow gets passed
        for c in key_columns:
            v = row.get(c)
            if v is not None and not (isinstance(v, float) and pd.isna(v)) and str(v).strip():
                norm[c] = str(v).strip()

    if norm:
        parts = [norm[k] for k in sorted(norm.keys())]
        base = "-".join(slugify(p) for p in parts if p)
        return base or "item"

    # Fallback: hash a deterministic subset of row data
    if isinstance(row, pd.Series):
        payload = {k: str(row[k]) for k in sorted(row.index) if pd.notna(row[k])}
    else:
        payload = {k: str(row[k]) for k in sorted(row.keys()) if row.get(k) is not None}
    h = hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return f"item-{h}"

# -----------------------
# Sheet processors
# -----------------------
def process_entity_info(df: pd.DataFrame, out_dir: str) -> int:
    df = normalize_columns(df)
    ensure_dir(out_dir)
    count = 0
    for _, row in df.iterrows():
        if is_empty_row(row):
            continue
        # Prefer entity_name slug; if missing, compose stable key
        name = str(row.get("entity_name", "")).strip()
        filename = safe_filename(name or stable_key(row, ["entity_name", "Legal"]), ".json")
        path = os.path.join(out_dir, filename)

        item = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                continue
            item[col] = v

        write_json(path, item)
        count += 1
    return count

def process_services(df: pd.DataFrame, out_dir: str) -> int:
    df = normalize_columns(df)
    ensure_dir(out_dir)
    count = 0
    for _, row in df.iterrows():
        if is_empty_row(row):
            continue
        title = str(row.get("title", "")).strip() or str(row.get("service_name", "")).strip()
        slug = str(row.get("slug", "")).strip() or slugify(title or stable_key(row, ["service_id", "title", "service_name"]))
        path = os.path.join(out_dir, f"{slug}.json")

        item = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                continue
            item[col] = v

        write_json(path, item)
        count += 1
    return count

def process_products(df: pd.DataFrame, out_dir: str) -> int:
    df = normalize_columns(df)
    ensure_dir(out_dir)
    count = 0
    for _, row in df.iterrows():
        if is_empty_row(row):
            continue
        name = str(row.get("name", "")).strip()
        slug = str(row.get("slug", "")).strip() or slugify(name or stable_key(row, ["product_id", "name"]))
        path = os.path.join(out_dir, f"{slug}.json")

        item = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                continue
            item[col] = v

        write_json(path, item)
        count += 1
    return count

def process_faqs(df: pd.DataFrame, out_dir: str) -> int:
    df = normalize_columns(df)
    ensure_dir(out_dir)
    count = 0
    for _, row in df.iterrows():
        if is_empty_row(row):
            continue
        q = str(row.get("question", "")).strip()
        slug_val = str(row.get("slug", "")).strip()
        slug_final = slug_val or slugify(q or stable_key(row, ["question"]))
        path = os.path.join(out_dir, f"{slug_final}.json")

        item = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                continue
            item[col] = v

        write_json(path, item)
        count += 1
    return count

def process_help_articles(df: pd.DataFrame, out_dir: str) -> int:
    df = normalize_columns(df)
    ensure_dir(out_dir)
    count = 0
    for _, row in df.iterrows():
        if is_empty_row(row):
            continue
        title = str(row.get("title", "")).strip()
        slug_val = str(row.get("slug", "")).strip()
        slug_final = slug_val or slugify(title or stable_key(row, ["article_id", "title"]))
        body = str(row.get("article", "")).strip()

        fm_lines = ["---"]
        if title:
            fm_lines.append(f"title: {title}")
        fm_lines.append(f"slug: {slug_final}")
        if str(row.get("article_type", "")).strip():
            fm_lines.append(f"article_type: {str(row.get('article_type')).strip()}")
        if str(row.get("published_date", "")).strip():
            fm_lines.append(f"published_date: {coerce_json_value(row.get('published_date'))}")
        if str(row.get("url", "")).strip():
            fm_lines.append(f"url: {str(row.get('url')).strip()}")
        if str(row.get("keywords", "")).strip():
            fm_lines.append(f"keywords: {str(row.get('keywords')).strip()}")
        fm_lines.append("---\n")

        md = "\n".join(fm_lines) + (body or "")
        path = os.path.join(out_dir, f"{slug_final}.md")
        write_text(path, md)
        count += 1
    return count

def process_reviews(df: pd.DataFrame, out_dir: str) -> int:
    df = normalize_columns(df)
    ensure_dir(out_dir)
    count = 0
    for _, row in df.iterrows():
        if is_empty_row(row):
            continue
        # Build slug from customer_name + review_title as identity
        name = str(row.get("customer_name", "")).strip()
        title = str(row.get("review_title", "")).strip()
        slug_final = slugify(name or "") + ("-" if name and title else "") + slugify(title or "")
        if not slug_final or slug_final == "-":
            slug_final = slugify(stable_key(row, ["customer_name", "review_title", "date"]))
        path = os.path.join(out_dir, f"{slug_final}.json")

        item = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                continue
            item[col] = v

        write_json(path, item)
        count += 1
    return count

def process_locations(df: pd.DataFrame, out_dir: str) -> int:
    df = normalize_columns(df)
    ensure_dir(out_dir)
    count = 0
    for _, row in df.iterrows():
        if is_empty_row(row):
            continue
        nm = str(row.get("location_name", "")).strip() or str(row.get("entity_name", "")).strip()
        slug_final = str(row.get("slug", "")).strip() or slugify(nm or stable_key(row, ["location_id", "entity_name"]))
        path = os.path.join(out_dir, f"{slug_final}.json")

        item = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                continue
            item[col] = v

        write_json(path, item)
        count += 1
    return count

def process_team(df: pd.DataFrame, out_dir: str) -> int:
    df = normalize_columns(df)
    ensure_dir(out_dir)
    count = 0
    for _, row in df.iterrows():
        if is_empty_row(row):
            continue
        nm = str(row.get("member_name", "")).strip() or str(row.get("name", "")).strip()
        slug_final = str(row.get("slug", "")).strip() or slugify(nm or stable_key(row, ["member_id", "member_name", "name"]))
        path = os.path.join(out_dir, f"{slug_final}.json")

        item = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                continue
            item[col] = v

        write_json(path, item)
        count += 1
    return count

def process_awards(df: pd.DataFrame, out_dir: str) -> int:
    df = normalize_columns(df)
    ensure_dir(out_dir)
    count = 0
    for _, row in df.iterrows():
        if is_empty_row(row):
            continue
        nm = str(row.get("award_name", "")).strip() or str(row.get("title", "")).strip()
        slug_final = str(row.get("slug", "")).strip() or slugify(nm or stable_key(row, ["award_id", "award_name", "title"]))
        path = os.path.join(out_dir, f"{slug_final}.json")

        item = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                continue
            item[col] = v

        write_json(path, item)
        count += 1
    return count

def process_press(df: pd.DataFrame, out_dir: str) -> int:
    df = normalize_columns(df)
    ensure_dir(out_dir)
    count = 0
    for _, row in df.iterrows():
        if is_empty_row(row):
            continue
        nm = str(row.get("title", "")).strip()
        slug_final = str(row.get("slug", "")).strip() or slugify(nm or stable_key(row, ["press_id", "title"]))
        path = os.path.join(out_dir, f"{slug_final}.json")

        item = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                continue
            item[col] = v

        write_json(path, item)
        count += 1
    return count

def process_case_studies(df: pd.DataFrame, out_dir: str) -> int:
    df = normalize_columns(df)
    ensure_dir(out_dir)
    count = 0
    for _, row in df.iterrows():
        if is_empty_row(row):
            continue
        nm = str(row.get("title", "")).strip()
        slug_final = str(row.get("slug", "")).strip() or slugify(nm or stable_key(row, ["case_id", "title"]))
        path = os.path.join(out_dir, f"{slug_final}.json")

        item = {}
        for col in df.columns:
            v = row[col]
            if pd.isna(v):
                continue
            item[col] = v

        write_json(path, item)
        count += 1
    return count

# -----------------------
# Main
# -----------------------
def main(input_file="templates/AI-Visibility-Master-Template.xlsx"):
    log(f"📂 Opening Excel file: {input_file}")

    if not os.path.exists(input_file):
        log(f"❌ FATAL: Excel file not found at {input_file}")
        sys.exit(1)
    else:
        log(f"✅ Excel file confirmed at: {input_file}")

    try:
        xlsx = pd.ExcelFile(input_file)
        log(f"📄 Available sheets in workbook: {xlsx.sheet_names}")
    except Exception as e:
        log(f"❌ Failed to load Excel file: {e}")
        sys.exit(1)

    # Map sheet names to output dirs + processor function
    sheet_map = [
        ("entity_info",             "schemas/organization",      process_entity_info),
        ("Services",                "schemas/services",          process_services),
        ("Products",                "schemas/products",          process_products),
        ("FAQs",                    "schemas/faqs",              process_faqs),
        ("Help Articles",           "schemas/help-articles",     process_help_articles),
        ("Reviews",                 "schemas/reviews",           process_reviews),
        ("Locations",               "schemas/locations",         process_locations),
        ("Team",                    "schemas/team",              process_team),
        ("Awards & Certifications", "schemas/awards",            process_awards),
        ("PressNews Mentions",      "schemas/press",             process_press),
        ("Case Studies",            "schemas/case-studies",      process_case_studies),
    ]

    total = 0
    for sheet_name, out_dir, handler in sheet_map:
        if sheet_name not in xlsx.sheet_names:
            log(f"⚠️ Skipping missing sheet: {sheet_name}")
            continue

        log(f"\n📄 Processing sheet: {sheet_name}")
        df = xlsx.parse(sheet_name)
        df = normalize_columns(df)
        log(f"🧹 Cleaned column names: {list(df.columns)}")
        if df.empty:
            log(f"⚠️ Sheet '{sheet_name}' is empty — skipping")
            continue

        ensure_dir(out_dir)
        try:
            count = handler(df, out_dir)
            log(f"📊 Total processed in '{sheet_name}': {count} items")
            total += count
        except Exception as e:
            # Fail fast with clear context
            log(f"❌ Error while processing sheet '{sheet_name}': {e}")
            raise

    log(f"\n🎉 All files generated successfully. Total items: {total}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Generate schema files from Excel.')
    parser.add_argument('--input', type=str, default='templates/AI-Visibility-Master-Template.xlsx',
                        help='Path to input Excel file')
    args = parser.parse_args()
    main(args.input)
