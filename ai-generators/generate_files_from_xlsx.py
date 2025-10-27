import os
import pandas as pd
import json
import re
import sys
from pathlib import Path
from hashlib import md5

# ---------------------------
# Helpers
# ---------------------------
MANIFEST_PATH = Path("ai-generated-manifest.txt")

def slugify(text):
    if text is None:
        return "untitled"
    text = str(text)
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', text)
    text = re.sub(r'[\s]+', '-', text.strip().lower())
    return text or "untitled"

def stable_key(row, candidates):
    """Return the first non-empty candidate as a stable key; else hash of the row."""
    for c in candidates:
        if c in row and pd.notna(row[c]) and str(row[c]).strip():
            return str(row[c]).strip()
    # last resort: deterministic hash of the row (order-independent)
    payload = {k:str(row[k]) for k in sorted(row.index) if pd.notna(row[k])}
    return md5(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:12]

def write_text_atomic(text: str, path: Path, manifest: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)  # atomic move (overwrite if exists)
    manifest.append(str(path))

def write_json_atomic(obj: dict, path: Path, manifest: list):
    write_text_atomic(json.dumps(obj, ensure_ascii=False, indent=2), path, manifest)

def clean_previous_outputs():
    if MANIFEST_PATH.exists():
        lines = MANIFEST_PATH.read_text(encoding="utf-8").splitlines()
        for line in lines:
            p = Path(line.strip())
            try:
                if p.is_file():
                    p.unlink()
            except Exception:
                pass
        MANIFEST_PATH.unlink(missing_ok=True)

def save_manifest(paths: list[str]):
    MANIFEST_PATH.write_text("\n".join(paths), encoding="utf-8")

# ---------------------------
# Main generator
# ---------------------------
def main(input_file="templates/AI-Visibility-Master-Template.xlsx"):
    print(f"📂 Opening Excel file: {input_file}")

    if not os.path.exists(input_file):
        print(f"❌ FATAL: Excel file not found at {input_file}")
        sys.exit(1)
    print(f"✅ Excel file confirmed at: {input_file}")

    try:
        xlsx = pd.ExcelFile(input_file)
        print(f"📄 Available sheets in workbook: {xlsx.sheet_names}")
    except Exception as e:
        print(f"❌ Failed to load Excel file: {e}")
        sys.exit(1)

    # Only remove files we generated last time
    clean_previous_outputs()
    manifest: list[str] = []

    sheet_config = {
        "entity_info": "schemas/organization",
        "Services": "schemas/services",
        "Products": "schemas/products",
        "FAQs": "schemas/faqs",
        "Help Articles": "schemas/help-articles",
        "Reviews": "schemas/reviews",
        "Locations": "schemas/locations",
        "Team": "schemas/team",
        "Awards & Certifications": "schemas/awards",
        "Press/News Mentions": "schemas/press",
        "Case Studies": "schemas/case-studies",
    }

    for sheet_name in xlsx.sheet_names:
        if sheet_name not in sheet_config:
            print(f"⚠️ Skipping unsupported sheet: {sheet_name}")
            continue

        print(f"\n📄 Processing sheet: {sheet_name}")
        df = xlsx.parse(sheet_name)
        df.columns = df.columns.str.strip()
        print(f"🧹 Cleaned column names: {list(df.columns)}")

        if df.empty:
            print(f"⚠️ Sheet '{sheet_name}' is empty — skipping")
            continue

        out_dir = Path(sheet_config[sheet_name])
        out_dir.mkdir(parents=True, exist_ok=True)
        print(f"📁 Output directory: {out_dir}")

        seen_keys = set()
        processed_count = 0

        for idx, row in df.iterrows():
            # Skip completely empty rows
            if row.dropna().empty:
                continue

            # Normalize row as dict of primitives/strings for JSON
            norm = {}
            for col in df.columns:
                val = row[col]
                if pd.isna(val):
                    continue
                if hasattr(val, "item"):
                    val = val.item()
                norm[col] = val

            # ---------- HELP ARTICLES (markdown) ----------
            if sheet_name == "Help Articles":
                title = str(norm.get("title", "")).strip()
                slug = str(norm.get("slug", "")).strip() or slugify(title or f"article-{idx+1}")
                body = str(norm.get("article", "")).strip()

                # de-dupe per run
                key = slug
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                path = out_dir / f"{slug}.md"
                fm = ["---"]
                if title:
                    fm.append(f"title: {title}")
                fm.append(f"slug: {slug}")
                fm.append("---\n")
                md = "\n".join(fm) + body
                write_text_atomic(md, path, manifest)
                print(f"✅ Generated: {path}")
                processed_count += 1
                continue

            # ---------- FAQs ----------
            if sheet_name == "FAQs":
                # Prefer explicit ids/slug; fall back to question text
                key = stable_key(norm, ["faq_id", "slug", "question"])
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                # Slug: prefer provided slug else from question or key
                s = str(norm.get("slug", "")).strip() or slugify(norm.get("question", key))
                path = out_dir / f"{s}.json"

                item = {
                    "question": str(norm.get("question", "")).strip() or f"Untitled FAQ {idx+1}",
                    "answer": str(norm.get("answer", "")).strip(),
                }
                write_json_atomic(item, path, manifest)
                print(f"✅ Generated: {path}")
                processed_count += 1
                continue

            # ---------- Services ----------
            if sheet_name == "Services":
                key = stable_key(norm, ["service_id", "slug", "service_name", "name"])
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                slug_val = str(norm.get("slug", "")).strip() or slugify(norm.get("service_name", norm.get("name", key)))
                path = out_dir / f"{slug_val}.json"

                item = {
                    "name": str(norm.get("service_name", norm.get("name", f"Service {idx+1}"))).strip(),
                    "description": str(norm.get("description", "")).strip(),
                    "priceRange": str(norm.get("price_range", "")).strip(),
                }
                if str(norm.get("license_number", "")).strip():
                    item["license"] = str(norm["license_number"]).strip()
                if str(norm.get("bar_number", "")).strip():
                    item["barNumber"] = str(norm["bar_number"]).strip()
                if str(norm.get("npi_number", "")).strip():
                    item["npiNumber"] = str(norm["npi_number"]).strip()
                if str(norm.get("certification_body", "")).strip():
                    item["certification"] = str(norm["certification_body"]).strip()

                write_json_atomic(item, path, manifest)
                print(f"✅ Generated: {path}")
                processed_count += 1
                continue

            # ---------- Team ----------
            if sheet_name == "Team":
                key = stable_key(norm, ["team_id", "member_id", "slug", "member_name", "name"])
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                slug_val = str(norm.get("slug", "")).strip() or slugify(norm.get("member_name", norm.get("name", key)))
                path = out_dir / f"{slug_val}.json"

                item = {
                    "name": str(norm.get("member_name", norm.get("name", f"Member {idx+1}"))).strip(),
                    "role": str(norm.get("role", "")).strip(),
                    "description": str(norm.get("bio", "")).strip(),
                }
                if str(norm.get("license_number", "")).strip():
                    item["license"] = str(norm["license_number"]).strip()
                if str(norm.get("bar_number", "")).strip():
                    item["barNumber"] = str(norm["bar_number"]).strip()
                if str(norm.get("npi_number", "")).strip():
                    item["npiNumber"] = str(norm["npi_number"]).strip()

                write_json_atomic(item, path, manifest)
                print(f"✅ Generated: {path}")
                processed_count += 1
                continue

            # ---------- Generic handler for other sheets ----------
            # Choose a stable key in priority order per sheet type
            key_candidates = {
                "Products": ["product_id", "slug", "name", "title"],
                "Reviews": ["review_id", "slug", "customer_name", "name", "title"],
                "Locations": ["location_id", "slug", "location_name", "entity_name", "name"],
                "Awards & Certifications": ["award_id", "slug", "name", "title"],
                "Press/News Mentions": ["press_id", "slug", "title", "name"],
                "Case Studies": ["case_id", "slug", "title", "name"],
                "entity_info": ["entity_id", "slug", "entity_name", "name", "title"],
            }
            kc = key_candidates.get(sheet_name, ["slug", "name", "title"])
            key = stable_key(norm, kc)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            slug_val = str(norm.get("slug", "")).strip() or slugify(norm.get("name", norm.get("title", key)))
            # For Locations you may prefer id-prefix to ensure uniqueness across similarly named branches
            if sheet_name == "Locations" and "location_id" in norm and str(norm["location_id"]).strip():
                slug_val = f"{str(norm['location_id']).strip()}-{slugify(norm.get('location_name', norm.get('entity_name', slug_val)))}"

            path = out_dir / f"{slug_val}.json"
            write_json_atomic(norm, path, manifest)
            print(f"✅ Generated: {path}")
            processed_count += 1

        print(f"📊 Total processed in '{sheet_name}': {processed_count} items")

    save_manifest(manifest)
    print("\n🎉 All files generated successfully (idempotent).")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Generate schema files from Excel (idempotent).')
    parser.add_argument('--input', type=str, default='templates/AI-Visibility-Master-Template.xlsx',
                        help='Path to input Excel file')
    args = parser.parse_args()
    main(args.input)
