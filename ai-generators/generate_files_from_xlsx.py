import os
import json
import yaml
import pandas as pd
import argparse
from datetime import datetime

# ===== CONFIG =====
DEFAULT_DATA_FILE = "templates/client-data.xlsx"
OUTPUT_DIR = "schema-files"

# Map Google Sheet tab names → output folder names
SHEET_TO_FOLDER = {
    "core_info": "organization",
    "Services": "services",
    "Products": "products",
    "FAQs": "faqs",
    "Help Articles": "help-articles",
    "Reviews": "reviews",
    "Locations": "locations",
    "Team": "team",
    "Awards & Certifications": "awards",
    "PressNews Mentions": "press",
    "Case Studies": "case-studies",
}
# ===================

def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def sanitize_value(val):
    """Convert any non-JSON-safe value into string or None"""
    if pd.isna(val):  # Covers NaN, NaT, None
        return None
    elif isinstance(val, (pd.Timestamp, datetime)):
        return val.isoformat()
    elif isinstance(val, pd.Timedelta):
        return str(val)
    elif hasattr(val, 'to_pydatetime'):  # Some pandas datetime types
        return val.to_pydatetime().isoformat()
    elif isinstance(val, (list, dict)):
        # Recursively sanitize nested structures (unlikely in your data, but safe)
        if isinstance(val, list):
            return [sanitize_value(x) for x in val]
        else:
            return {k: sanitize_value(v) for k, v in val.items()}
    else:
        # Fallback: convert everything else to string if needed later
        return val

def save_json(data, path):
    if not data:
        print(f"⚠️ No data to save for {path}")
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # Deep sanitize every value
    clean_data = {k: sanitize_value(v) for k, v in data.items()}

    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean_data, f, indent=2, ensure_ascii=False)
    print(f"✅ SAVED: {path}")

def save_yaml(data, path):
    if not data:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    # Sanitize for YAML too (though YAML is more forgiving)
    clean_data = {k: sanitize_value(v) for k, v in data.items()}

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(clean_data, f, allow_unicode=True)
    print(f"✅ SAVED: {path}")

def process_sheet_to_file(sheet_name, df_sheet):
    """Process one sheet → save as main-data.json/.yaml in mapped folder"""
    if df_sheet.empty:
        print(f"⚠️ Sheet '{sheet_name}' is empty — skipping")
        return

    # Take first row only → convert to clean dict
    row_dict = df_sheet.iloc[0].to_dict()

    # Get target folder name
    folder_name = SHEET_TO_FOLDER.get(sheet_name, sheet_name.lower().replace(" ", "-"))
    target_dir = os.path.join(OUTPUT_DIR, folder_name)
    base_path = os.path.join(target_dir, "main-data")

    # Save both formats
    save_json(row_dict, base_path + ".json")
    save_yaml(row_dict, base_path + ".yaml")

def generate_all_files(input_file):
    ensure_output_dir()
    print(f"📄 Processing: {input_file}")
    
    # Load all sheets from XLSX
    xls = pd.read_excel(input_file, sheet_name=None)  # Returns dict: sheet_name → DataFrame
    print(f"📄 Sheets found: {list(xls.keys())}")

    for sheet_name, df_sheet in xls.items():
        print(f"\n--- PROCESSING: {sheet_name} ---")
        process_sheet_to_file(sheet_name, df_sheet)

def main():
    parser = argparse.ArgumentParser(description="Generate schema files from XLSX tabs")
    parser.add_argument("--input", "-i", default=DEFAULT_DATA_FILE,
                        help="Path to input .xlsx file")
    args = parser.parse_args()

    print("⚙️ Starting processing...")
    generate_all_files(args.input)
    print("🎉 SUCCESS: All schema files generated!")

if __name__ == "__main__":
    main()
