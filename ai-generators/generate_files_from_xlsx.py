# ai-generators/generate_files_from_xlsx.py
import os
import re
import json
import sys
from pathlib import Path
from hashlib import md5

import pandas as pd

# ---------------------------
# Helpers
# ---------------------------
def slugify(text):
    """Generate clean, URL-friendly slug from text."""
    if text is None:
        return "untitled"
    text = str(text)
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text.strip().lower())
    return text or "untitled"

def coerce_json_value(v):
    """Make values JSON-serializable and stable."""
    if pd.isna(v):
        return None
    # Convert numpy types gracefully
    if hasattr(v, "item"):
        try:
            return v.item()
        except Exception:
            pass
    if isinstance(v, (list, tuple)):
        return [coerce_json_value(x) for x in v]
    if isinstance(v, dict):
        return {str(k): coerce_json_value(v) for k,v in v.items()}
    return v

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase, trim, and normalize column names."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df

def row_to_dict(row) -> dict:
    """
    Return a plain dict for a row that may be a pandas Series or already a dict.
    """
    if isinstance(row, dict):
        base = row
    else:
        # pandas Series
        base = row.to_dict()
    out = {}
    for k, v in base.items():
        if pd.isna(v):
            continue
        out[str(k)] = coerce_json_value(v)
    return out

def first_nonempty(row_dict: dict, keys):
    """Return the first non-empty string from a list of keys in row_dict."""
    for k in keys:
        if k in row_dict and row_dict[k] not in (None, ""):
            s = str(row_dict[k]).strip()
            if s:
                return s
    return None

def stable_key(row, candidates):
    """
    Return a stable, deterministic key for a row that may be a pandas Series or a dict.
    Prefer explicit ID/slug-like fields; otherwise hash the normalized payload.
    """
    rd = row_to_dict(row)

    # Try candidates in order
    cand = first_nonempty(rd, candidates)
    if cand:
        return slugify(cand)

    # If no candidate available, try secondary fallbacks commonly present
    fallback = first_nonempty(rd, [
        "entity_name", "name", "title", "question", "member_name",
        "service_name", "product_name"
    ])
    if fallback:
        return slugify(fallback)

    # As a last resort, hash the sorted payload for deterministic key
    payload = {k: str(rd[k]) for k in sorted(rd.keys()) if rd[k] is not None}
    digest = md5(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    return f"item-{digest}"

def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def write_markdown(path: Path, title: str, slug: str, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        f.write("---\n")
        if title:
            f.write(f"title: {title}\n")
        f.write(f"slug: {slug}\n")
        f.write("---\n\n")
        f.write(content or "")

# ---------------------------
# Sheet configuration
# ---------------------------
SHEET_CONFIG = {
    # sheet_name: {dir, key_candidates, type}
    "entity_info": {
        "dir": "schemas/organization",
        "key_candidates": ["slug", "entity_name", "name", "title"],
        "type": "json",
    },
    "Services": {
        "dir": "schemas/services",
        "key_candidates": ["slug", "service_name", "name", "title"],
        "type": "json",
    },
    "Products": {
        "dir": "schemas/products",
        "key_candidates": ["slug", "product_name", "name", "title"],
        "type": "json",
    },
    "FAQs": {
        "dir": "schemas/faqs",
        "key_candidates": ["slug", "question"],
        "type": "json",
    },
    "Help Articles": {
        "dir": "schemas/help-articles",
        "key_candidates": ["slug", "title"],
        "type": "markdown",
    },
    "Reviews": {
        "dir": "schemas/reviews",
        "key_candidates": ["slug", "review_id", "title", "customer_name", "author"],
        "type": "json",
    },
    "Locations": {
        "dir": "schemas/locations",
        "key_candidates": ["slug", "location_id", "location_name", "entity_name", "name"],
        "type": "json",
    },
    "Team": {
        "dir": "schemas/team",
        "key_candidates": ["slug", "member_name", "name", "title"],
        "type": "json",
    },
    "Awards & Certifications": {
        "dir": "schemas/awards",
        "key_candidates": ["slug", "title", "name", "award_name"],
        "type": "json",
    },
    # Some workbooks use "Press/News Mentions" or "PressNews Mentions"
    "Press/News Mentions": {
        "dir": "schemas/press",
        "key_candidates": ["slug", "title", "name"],
        "type": "json",
    },
    "PressNews Mentions": {
        "dir": "schemas/press",
        "key_candidates": ["slug", "title", "name"],
        "type": "json",
    },
    "Case Studies": {
        "dir": "schemas/case-studies",
        "key_candidates": ["slug", "case_id", "title", "name"],
        "type": "json",
    },
}

# ---------------------------
# Processing per sheet
# ---------------------------
def process_entity_info(df: pd.DataFrame, out_dir: Path):
    processed = 0
    for _, row in df.iterrows():
        rd = row_to_dict(row)
        key = stable_key(row, SHEET_CONFIG["entity_info"]["key_candidates"])
        path = out_dir / f"{key}.json"

        # Normalize a few typical fields
        data = {}
        for col, val in rd.items():
            data[col] = val

        write_json(path, data)
        print(f"✅ Generated: {path}")
        processed += 1
    return processed

def process_services(df: pd.DataFrame, out_dir: Path):
    processed = 0
    for _, row in df.iterrows():
        rd = row_to_dict(row)
        key = stable_key(row, SHEET_CONFIG["Services"]["key_candidates"])
        path = out_dir / f"{key}.json"

        item = {
            "name": rd.get("service_name") or rd.get("name") or rd.get("title") or key.replace("-", " ").title(),
        }
        if rd.get("description"):   item["description"] = rd["description"]
        if rd.get("price_range"):   item["priceRange"]  = rd["price_range"]
        if rd.get("license_number"): item["license"]    = rd["license_number"]
        if rd.get("bar_number"):     item["barNumber"]  = rd["bar_number"]
        if rd.get("npi_number"):     item["npiNumber"]  = rd["npi_number"]
        if rd.get("certification_body"): item["certification"] = rd["certification_body"]

        write_json(path, item)
        print(f"✅ Generated: {path}")
        processed += 1
    return processed

def process_products(df: pd.DataFrame, out_dir: Path):
    processed = 0
    for _, row in df.iterrows():
        rd = row_to_dict(row)
        key = stable_key(row, SHEET_CONFIG["Products"]["key_candidates"])
        path = out_dir / f"{key}.json"
        write_json(path, rd)
        print(f"✅ Generated: {path}")
        processed += 1
    return processed

def process_faqs(df: pd.DataFrame, out_dir: Path):
    processed = 0
    for _, row in df.iterrows():
        rd = row_to_dict(row)
        key = stable_key(row, SHEET_CONFIG["FAQs"]["key_candidates"])  # usually slug or question
        path = out_dir / f"{key}.json"

        item = {
            "question": rd.get("question") or key.replace("-", " ").title(),
            "answer": rd.get("answer") or "",
        }
        write_json(path, item)
        print(f"✅ Generated: {path}")
        processed += 1
    return processed

def process_help_articles(df: pd.DataFrame, out_dir: Path):
    processed = 0
    for _, row in df.iterrows():
        rd = row_to_dict(row)
        # Prefer explicit slug; else title → slug
        slug = rd.get("slug") or rd.get("title") or None
        key = slugify(slug) if slug else stable_key(row, SHEET_CONFIG["Help Articles"]["key_candidates"])
        path = out_dir / f"{key}.md"

        title = rd.get("title") or key.replace("-", " ").title()
        content = rd.get("article") or rd.get("content") or rd.get("body") or ""

        write_markdown(path, title, key, content)
        print(f"✅ Generated: {path}")
        processed += 1
    return processed

def process_reviews(df: pd.DataFrame, out_dir: Path):
    processed = 0
    for _, row in df.iterrows():
        rd = row_to_dict(row)
        key = stable_key(row, SHEET_CONFIG["Reviews"]["key_candidates"])
        path = out_dir / f"{key}.json"
        write_json(path, rd)
        print(f"✅ Generated: {path}")
        processed += 1
    return processed

def process_locations(df: pd.DataFrame, out_dir: Path):
    processed = 0
    for _, row in df.iterrows():
        rd = row_to_dict(row)
        key = stable_key(row, SHEET_CONFIG["Locations"]["key_candidates"])
        path = out_dir / f"{key}.json"
        write_json(path, rd)
        print(f"✅ Generated: {path}")
        processed += 1
    return processed

def process_team(df: pd.DataFrame, out_dir: Path):
    processed = 0
    for _, row in df.iterrows():
        rd = row_to_dict(row)
        key = stable_key(row, SHEET_CONFIG["Team"]["key_candidates"])
        path = out_dir / f"{key}.json"

        item = {
            "name": rd.get("member_name") or rd.get("name") or rd.get("title") or key.replace("-", " ").title(),
            "role": rd.get("role") or "",
            "description": rd.get("bio") or rd.get("description") or "",
        }
        if rd.get("license_number"): item["license"]    = rd["license_number"]
        if rd.get("bar_number"):     item["barNumber"]  = rd["bar_number"]
        if rd.get("npi_number"):     item["npiNumber"]  = rd["npi_number"]

        write_json(path, item)
        print(f"✅ Generated: {path}")
        processed += 1
    return processed

def process_awards(df: pd.DataFrame, out_dir: Path):
    processed = 0
    for _, row in df.iterrows():
        rd = row_to_dict(row)
        key = stable_key(row, SHEET_CONFIG["Awards & Certifications"]["key_candidates"])
        path = out_dir / f"{key}.json"
        write_json(path, rd)
        print(f"✅ Generated: {path}")
        processed += 1
    return processed

def process_press(df: pd.DataFrame, out_dir: Path):
    processed = 0
    for _, row in df.iterrows():
        rd = row_to_dict(row)
        # Works for either sheet label
        key = stable_key(row, ["slug", "title", "name", "press_id"])
        path = out_dir / f"{key}.json"
        write_json(path, rd)
        print(f"✅ Generated: {path}")
        processed += 1
    return processed

def process_case_studies(df: pd.DataFrame, out_dir: Path):
    processed = 0
    for _, row in df.iterrows():
        rd = row_to_dict(row)
        key = stable_key(row, SHEET_CONFIG["Case Studies"]["key_candidates"])
        path = out_dir / f"{key}.json"
        write_json(path, rd)
        print(f"✅ Generated: {path}")
        processed += 1
    return processed

# ---------------------------
# Main
# ---------------------------
def main(input_file="templates/AI-Visibility-Master-Template.xlsx"):
    print("Processing detected XLSX files...")
    print(f"📄 Processing: {input_file}")

    if not os.path.exists(input_file):
        print(f"❌ FATAL: Excel file not found at {input_file}")
        sys.exit(1)

    print(f"📂 Opening Excel file: {input_file}")
    try:
        xlsx = pd.ExcelFile(input_file)
    except Exception as e:
        print(f"❌ Failed to load Excel file: {e}")
        sys.exit(1)

    print(f"📄 Available sheets in workbook: {xlsx.sheet_names}")

    total = 0
    for sheet_name in xlsx.sheet_names:
        if sheet_name not in SHEET_CONFIG:
            print(f"⚠️ Skipping unsupported sheet: {sheet_name}")
            continue

        cfg = SHEET_CONFIG[sheet_name]
        out_dir = Path(cfg["dir"])
        out_dir.mkdir(parents=True, exist_ok=True)

        print(f"\n📄 Processing sheet: {sheet_name}")
        try:
            df = xlsx.parse(sheet_name)
        except Exception as e:
            print(f"❌ Failed to parse sheet '{sheet_name}': {e}")
            continue

        df = normalize_columns(df)
        print(f"🧹 Cleaned column names: {list(df.columns)}")

        if df.empty:
            print(f"⚠️ Sheet '{sheet_name}' is empty — skipping")
            continue

        # Route to the proper handler
        if sheet_name == "entity_info":
            count = process_entity_info(df, out_dir)
        elif sheet_name == "Services":
            count = process_services(df, out_dir)
        elif sheet_name == "Products":
            count = process_products(df, out_dir)
        elif sheet_name == "FAQs":
            count = process_faqs(df, out_dir)
        elif sheet_name == "Help Articles":
            count = process_help_articles(df, out_dir)
        elif sheet_name == "Reviews":
            count = process_reviews(df, out_dir)
        elif sheet_name == "Locations":
            count = process_locations(df, out_dir)
        elif sheet_name == "Team":
            count = process_team(df, out_dir)
        elif sheet_name in ("Press/News Mentions", "PressNews Mentions"):
            count = process_press(df, out_dir)
        elif sheet_name == "Awards & Certifications":
            count = process_awards(df, out_dir)
        elif sheet_name == "Case Studies":
            count = process_case_studies(df, out_dir)
        else:
            print(f"⚠️ No handler for sheet '{sheet_name}' — skipping")
            count = 0

        print(f"📊 Total processed in '{sheet_name}': {count} items")
        total += count

    print(f"\n🎉 All files generated successfully. Total items: {total}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Generate schema files from Excel (overwrite existing, no duplicates).")
    parser.add_argument("--input", type=str, default="templates/AI-Visibility-Master-Template.xlsx",
                        help="Path to input Excel file")
    args = parser.parse_args()
    main(args.input)
