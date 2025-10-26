import os
import json
import yaml
import pandas as pd
import datetime
import xml.etree.ElementTree as ET

# ========= CONFIG =========
DATA_FILE = "templates/client-data.xlsx"
OUTPUT_DIR = "schema-files"
SITE_BASE = "https://example.com"  # <-- CHANGE THIS to your live domain
SITEMAP_FILE = "ai-sitemap.xml"
# ==========================

def ensure_output_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_client_data(file_path):
    return pd.read_excel(file_path)

def save_json(data, path):
    if not data:
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def save_yaml(data, path):
    if not data:
        return
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True)

def save_md(content, path):
    if not content.strip():
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def save_llm(content, path):
    if not content.strip():
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def generate_files_from_row(row):
    """Generate JSON, YAML, MD, and LLM files for a single row in Excel"""
    base_name = row.get("slug") or row.get("name") or f"client_{row.name}"
    base_path = os.path.join(OUTPUT_DIR, base_name)
    os.makedirs(base_path, exist_ok=True)

    # Filter out empty/NaN/blank values
    row_dict = {k: v for k, v in row.to_dict().items() if pd.notna(v) and str(v).strip()}
    if not row_dict:
        # nothing useful to save for this row
        return

    # JSON
    save_json(row_dict, os.path.join(base_path, f"{base_name}.json"))

    # YAML
    save_yaml(row_dict, os.path.join(base_path, f"{base_name}.yaml"))

    # Markdown
    md_content = f"# {row.get('name', base_name)}\n\n"
    for col, val in row_dict.items():
        md_content += f"**{col}:** {val}\n\n"
    save_md(md_content, os.path.join(base_path, f"{base_name}.md"))

    # LLM text file
    llm_content = f"LLM Data for {row.get('name', base_name)}\n\n"
    for col, val in row_dict.items():
        llm_content += f"{col}: {val}\n"
    save_llm(llm_content, os.path.join(base_path, f"{base_name}.llm"))

def generate_all_files():
    ensure_output_dir()
    df = load_client_data(DATA_FILE)
    for _, row in df.iterrows():
        generate_files_from_row(row)

def generate_sitemap(root_dir=OUTPUT_DIR, output_file=SITEMAP_FILE):
    """Scan generated files and build sitemap including only non-empty files"""
    urlset = ET.Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")

    for dirpath, _, filenames in os.walk(root_dir):
        for fname in filenames:
            if not fname.endswith((".json", ".yaml", ".yml", ".md", ".llm")):
                continue

            path = os.path.join(dirpath, fname)
            if not os.path.isfile(path) or os.path.getsize(path) == 0:
                continue

            rel_path = os.path.relpath(path, root_dir).replace("\\", "/")
            url = f"{SITE_BASE}/{rel_path}"

            url_el = ET.SubElement(urlset, "url")
            ET.SubElement(url_el, "loc").text = url
            ET.SubElement(url_el, "lastmod").text = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    tree = ET.ElementTree(urlset)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"Sitemap written to {output_file}")

def main():
    print("Generating structured files from Excel...")
    generate_all_files()
    print("Building sitemap...")
    generate_sitemap()
    print("Done!")

if __name__ == "__main__":
    main()
