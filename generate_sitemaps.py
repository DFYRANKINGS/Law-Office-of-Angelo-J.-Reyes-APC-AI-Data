# generate_sitemaps.py — Optimized for AI + SEO visibility via GitHub Raw

import os
from pathlib import Path
from datetime import datetime
import glob

def get_site_url():
    # Serve files via GitHub Raw — publicly crawlable by search engines & AI bots
    return "https://raw.githubusercontent.com/DFYRANKINGS/Urban-Luxury-Outdoors-AI-Data/main"

def find_generated_files():
    """Find all generated .json, .yaml, .md, .llm in schema-files/"""
    patterns = [
        "schema-files/**/*.json",
        "schema-files/**/*.yaml",
        "schema-files/**/*.yml",
        "schema-files/**/*.md",
        "schema-files/**/*.llm"
    ]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern, recursive=True))
    return sorted(set(files))  # dedupe

def generate_sitemap_xml(site_url, files):
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S+00:00")
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]

    for file_path in files:
        public_path = file_path.replace("\\", "/")  # Windows-safe
        full_url = f"{site_url}/{public_path}"
        
        xml_lines.append("  <url>")
        xml_lines.append(f"    <loc>{full_url}</loc>")
        xml_lines.append(f"    <lastmod>{now}</lastmod>")
        xml_lines.append("  </url>")

    xml_lines.append("</urlset>")
    return "\n".join(xml_lines)

def main():
    site_url = get_site_url()
    print(f"🌍 Base URL for sitemap: {site_url}")

    files = find_generated_files()
    print(f"📄 Found {len(files)} files for sitemap:")

    for f in files:
        print(f"   - {f}")

    sitemap_content = generate_sitemap_xml(site_url, files)

    with open("ai-sitemap.xml", "w", encoding="utf-8") as f:
        f.write(sitemap_content)

    print("✅ ai-sitemap.xml generated successfully.")
    print("🌐 Test a file: https://raw.githubusercontent.com/DFYRANKINGS/Urban-Luxury-Outdoors-AI-Data/main/schema-files/organization/main-data.json")

if __name__ == "__main__":
    main()
