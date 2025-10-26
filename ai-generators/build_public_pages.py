# build_public_pages.py
import sys
import os
import yaml
import json
import re
from datetime import datetime

# -------------------------
# Utilities
# -------------------------
def escape_html(text):
    if not isinstance(text, str):
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def slugify(text):
    """Generate URL-friendly slug from text"""
    if not text:
        return "item"
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', str(text))
    text = re.sub(r'[\s]+', '-', text.strip().lower())
    return text or "item"

def load_data(filepath):
    if not os.path.exists(filepath):
        print(f"🔍 File not found: {filepath}")
        return []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                print(f"⚠️ File is empty: {filepath}")
                return []

            if filepath.endswith(('.yaml', '.yml')):
                data = yaml.safe_load(content) or []
                return data if isinstance(data, list) else [data]

            elif filepath.endswith('.json'):
                data = json.loads(content) or []
                return data if isinstance(data, list) else [data]

    except Exception as e:
        print(f"❌ Failed to load {filepath}: {e}")
        return []

    print(f"⚠️ Unsupported file type: {filepath}")
    return []

def generate_nav():
    return """
    <nav style="background: #2c3e50; padding: 1rem; margin-bottom: 2rem;">
        <ul style="list-style: none; display: flex; gap: 2rem; margin: 0; padding: 0; flex-wrap: wrap; justify-content: center;">
            <li><a href="index.html" style="color: white; text-decoration: none;">Home</a></li>
            <li><a href="about.html" style="color: white; text-decoration: none;">About</a></li>
            <li><a href="services.html" style="color: white; text-decoration: none;">Services</a></li>
            <li><a href="testimonials.html" style="color: white; text-decoration: none;">Testimonials</a></li>
            <li><a href="faqs.html" style="color: white; text-decoration: none;">FAQs</a></li>
            <li><a href="help.html" style="color: white; text-decoration: none;">Help</a></li>
            <li><a href="contact.html" style="color: white; text-decoration: none;">Contact</a></li>
        </ul>
    </nav>
    """

def generate_page(title, content):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{escape_html(title)}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.7; }}
        h1, h2, h3 {{ color: #2c3e50; }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        img {{ max-width: 100%; height: auto; }}
        .page-header {{ background: #ecf0f1; padding: 2rem; border-radius: 8px; margin-bottom: 2rem; text-align: center; }}
        .card {{ border: 1px solid #eee; padding: 1.5rem; border-radius: 8px; margin: 2rem 0; }}
        .badge {{ background: #3498db; color: white; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.9em; }}
    </style>
</head>
<body>
    {generate_nav()}
    <div class="page-header">
        <h1>{escape_html(title)}</h1>
    </div>
    {content}
    <footer style="margin-top: 4rem; padding-top: 2rem; border-top: 1px solid #eee; text-align: center; color: #7f8c8d;">
        <p>© {datetime.now().year} — Auto-generated from structured data. Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
    </footer>
</body>
</html>"""

# -------------------------
# Page generators
# -------------------------
def generate_contact_page():
    locations_dir = "schemas/locations"  # ✅ lowercase
    print(f"🔍 Checking contact data in: {locations_dir}")
    if not os.path.exists(locations_dir):
        print(f"❌ Locations directory not found: {locations_dir} — skipping contact.html")
        return False

    items = []
    for file in os.listdir(locations_dir):
        if file.endswith((".json", ".yaml", ".yml")):
            filepath = os.path.join(locations_dir, file)
            loc_data = load_data(filepath)
            if not loc_data:
                continue
            for loc in (loc_data if isinstance(loc_data, list) else [loc_data]):
                name = loc.get('name') or loc.get('location_name') or 'Location'
                address = loc.get('address') or ''
                phone = loc.get('phone') or ''
                email = loc.get('email') or ''
                hours = loc.get('hours') or ''
                map_url = loc.get('map_embed_url') or loc.get('google_maps_url') or ''

                item_html = f"""
                <div class="card">
                    <h3>{escape_html(name)}</h3>
                    {f'<p><strong>Address:</strong> {escape_html(address)}</p>' if address else ''}
                    {f'<p><strong>Phone:</strong> {escape_html(phone)}</p>' if phone else ''}
                    {f'<p><strong>Email:</strong> <a href="mailto:{email}">{escape_html(email)}</a></p>' if email else ''}
                    {f'<p><strong>Hours:</strong> {escape_html(hours)}</p>' if hours else ''}
                """
                if map_url:
                    item_html += f'''
                    <div style="margin-top: 1rem;">
                        <iframe src="{escape_html(map_url)}" width="100%" height="300" style="border:0; border-radius: 8px;" allowfullscreen loading="lazy"></iframe>
                    </div>
                    '''
                item_html += "</div>"
                items.append(item_html)

    if not items:
        print("⚠️ No valid locations found — skipping contact.html")
        return False

    with open("contact.html", "w", encoding="utf-8") as f:
        f.write(generate_page("Contact Us", "".join(items)))
    print(f"✅ contact.html generated ({len(items)} locations)")
    return True

def generate_services_page():
    services_dir = "schemas/services"  # ✅ lowercase
    print(f"🔍 Checking services data in: {services_dir}")
    if not os.path.exists(services_dir):
        print(f"❌ Services directory not found: {services_dir} — skipping services.html")
        return False

    items = []
    for file in os.listdir(services_dir):
        if file.endswith((".json", ".yaml", ".yml")):
            filepath = os.path.join(services_dir, file)
            svc_data = load_data(filepath)
            if not svc_data:
                continue
            for svc in (svc_data if isinstance(svc_data, list) else [svc_data]):
                title = svc.get('title') or svc.get('service_name') or 'Unnamed Service'
                description = svc.get('description') or ''
                price = svc.get('price') or svc.get('price_range') or 'Contact for pricing'
                slug = svc.get('slug') or slugify(title)
                featured = svc.get('featured', False)
                badge = '<span class="badge">Featured</span>' if featured else ''
                items.append(f"""
                <div class="card" id="{escape_html(slug)}">
                    <h2>{escape_html(title)} {badge}</h2>
                    <p>{escape_html(description)}</p>
                    <p><strong>Starting at:</strong> {escape_html(price)}</p>
                    <a href="#{slug}" style="display: inline-block; margin-top: 1rem;">🔗 Permalink</a>
                </div>
                """)

    if not items:
        print("⚠️ No valid services found — skipping services.html")
        return False

    with open("services.html", "w", encoding="utf-8") as f:
        f.write(generate_page("Our Services", "".join(items)))
    print(f"✅ services.html generated ({len(items)} services)")
    return True

def generate_testimonials_page():
    reviews_dir = "schemas/reviews"  # ✅ lowercase
    print(f"🔍 Checking testimonials data in: {reviews_dir}")
    if not os.path.exists(reviews_dir):
        print(f"❌ Reviews directory not found: {reviews_dir} — skipping testimonials.html")
        return False

    items = []
    for file in os.listdir(reviews_dir):
        if file.endswith((".json", ".yaml", ".yml")):
            filepath = os.path.join(reviews_dir, file)
            rev_data = load_data(filepath)
            if not rev_data:
                continue
            for rev in (rev_data if isinstance(rev_data, list) else [rev_data]):
                author = rev.get('customer_name') or rev.get('author') or 'Anonymous'
                entity = rev.get('entity_name') or ''  # standardized field
                quote = rev.get('review_body') or rev.get('quote') or rev.get('review_title') or 'No review text provided.'
                rating = int(rev.get('rating', 5))
                date = rev.get('date') or ''
                star_display = '★' * rating + '☆' * (5 - rating)
                items.append(f"""
                <blockquote class="card" style="font-style: italic;">
                    <p>“{escape_html(quote)}”</p>
                    <footer style="margin-top: 1rem; font-style: normal;">
                        — {escape_html(author)}{f', {escape_html(entity)}' if entity else ''}
                        {f'<br/><small>{escape_html(date)}</small>' if date else ''}
                    </footer>
                    <div style="margin-top: 0.5rem; color: #f39c12;">{star_display}</div>
                </blockquote>
                """)

    if not items:
        print("⚠️ No valid testimonials found — skipping testimonials.html")
        return False

    with open("testimonials.html", "w", encoding="utf-8") as f:
        f.write(generate_page("Testimonials", "".join(items)))
    print(f"✅ testimonials.html generated ({len(items)} testimonials)")
    return True

def generate_index_page():
    """Generate directory + welcome page — DYNAMIC REPO URL"""
    links = [
        ("About Us", "about.html"),
        ("Our Services", "services.html"),
        ("Testimonials", "testimonials.html"),
        ("FAQs", "faqs.html"),
        ("Help Center", "help.html"),
        ("Contact Us", "contact.html"),
        ("Browse All Schema Files", "#files"),
    ]
    quick_links = "\n".join(
        f'<li style="margin: 0.5rem 0;"><a href="{url}" style="font-size: 1.1em; font-weight: 500;">{escape_html(name)}</a></li>'
        for name, url in links
    )

    file_links = []
    repo_slug = os.getenv('GITHUB_REPOSITORY')
    if not repo_slug:
        print("❌ ERROR: GITHUB_REPOSITORY environment variable not set!")
        print("   Make sure you're running this in GitHub Actions.")
        sys.exit(1)

    base_url = f"https://raw.githubusercontent.com/{repo_slug}/main"
    print(f"🌐 Base URL for schema files: {base_url}")

    for root, dirs, files in os.walk("schemas"):
        for file in files:
            if file.endswith((".json", ".yaml", ".yml", ".md", ".llm")):
                filepath = os.path.join(root, file).replace("\\", "/")
                full_url = f"{base_url}/{filepath}"
                display_path = filepath.replace("schemas/", "")
                file_links.append(f'<li><a href="{full_url}" target="_blank">{escape_html(display_path)}</a></li>')

    content = f"""
    <p>Welcome to our AI-optimized data hub. Below are quick links to key sections, or browse all machine-readable files.</p>
    <h2>🚀 Quick Navigation</h2>
    <ul style="list-style: none; padding: 0;">
        {quick_links}
    </ul>
    <h2 id="files">📁 All Schema Files</h2>
    <ul>
        {''.join(sorted(file_links))}
    </ul>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(generate_page("Welcome", content))
    print("✅ index.html generated")
    return True

def generate_about_page():
    org_dir = "schemas/organization"  # ✅ lowercase
    print(f"🔍 Scanning {org_dir} for organization data...")

    if not os.path.exists(org_dir):
        print(f"❌ Directory not found: {org_dir} — skipping about.html")
        return False

    cand = [f for f in os.listdir(org_dir) if f.endswith(('.json', '.yaml', '.yml'))]
    if not cand:
        print(f"❌ No JSON/YAML files found in {org_dir} — skipping about.html")
        return False

    filepath = os.path.join(org_dir, cand[0])
    print(f"📄 Using: {os.path.basename(filepath)}")

    orgs = load_data(filepath)
    if not orgs:
        print(f"❌ Failed to load data — skipping about.html")
        return False

    org = orgs[0] if isinstance(orgs, list) else orgs

    content_parts = []
    logo_url = org.get('logo_url') or org.get('logo')
    if logo_url:
        content_parts.append(f'<img src="{escape_html(logo_url)}" alt="{escape_html(org.get("name", "Company"))}" style="max-height: 120px; margin-bottom: 2rem;">')

    if org.get('description'):
        content_parts.append(f"<p>{escape_html(org.get('description'))}</p>")
    if org.get('mission'):
        content_parts.append(f"<h2>Our Mission</h2><p>{escape_html(org.get('mission'))}</p>")
    if org.get('vision'):
        content_parts.append(f"<h2>Our Vision</h2><p>{escape_html(org.get('vision'))}</p>")
    if org.get('tagline') or org.get('slogan'):
        content_parts.append(f"<h2>Our Promise</h2><p>{escape_html(org.get('tagline') or org.get('slogan'))}</p>")

    if not content_parts:
        print("⚠️ No usable fields found in org data — skipping about.html")
        return False

    with open("about.html", "w", encoding="utf-8") as f:
        f.write(generate_page("About Us", "\n".join(content_parts)))

    print("✅ about.html generated successfully")
    return True

def generate_faq_page():
    faq_dir = "schemas/faqs"  # ✅ lowercase
    print(f"🔍 Checking FAQs in: {faq_dir}")
    if not os.path.exists(faq_dir):
        print(f"❌ FAQ directory not found: {faq_dir} — skipping faqs.html")
        return False

    items = []
    for file in os.listdir(faq_dir):
        if file.endswith((".json", ".yaml", ".yml")):
            filepath = os.path.join(faq_dir, file)
            faq_data = load_data(filepath)
            if not faq_data:
                continue
            for item in (faq_data if isinstance(faq_data, list) else [faq_data]):
                question = (item.get('question') or '').strip()
                answer = (item.get('answer') or '').strip()
                if not question:
                    continue
                items.append(f"""
                <div class="card">
                    <h3 style="margin: 0 0 0.5rem 0;">{escape_html(question)}</h3>
                    <p>{escape_html(answer)}</p>
                </div>
                """)

    if not items:
        print("⚠️ No valid FAQs found — skipping faqs.html")
        return False

    with open("faqs.html", "w", encoding="utf-8") as f:
        f.write(generate_page("Frequently Asked Questions", "".join(items)))
    print(f"✅ faqs.html generated ({len(items)} FAQs)")
    return True

def generate_help_articles_page():
    help_dir = "schemas/help-articles"  # ✅ lowercase + hyphen
    print(f"🔍 Looking for help articles in: {help_dir}")
    if not os.path.exists(help_dir):
        print(f"❌ Folder not found: {help_dir}")
        return False

    files_found = [f for f in os.listdir(help_dir) if f.endswith(".md")]
    print(f"📄 Found {len(files_found)} .md files: {files_found[:5]}")

    if not files_found:
        print("⚠️ No .md files found — skipping help.html")
        return False

    articles = []
    for file in files_found:
        filepath = os.path.join(help_dir, file)
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        title = None
        body_lines = []
        in_frontmatter = False
        frontmatter_done = False

        for line in content.splitlines():
            if line.strip() == "---" and not frontmatter_done:
                if not in_frontmatter:
                    in_frontmatter = True
                else:
                    in_frontmatter = False
                    frontmatter_done = True
                continue

            if in_frontmatter and not frontmatter_done:
                if line.lower().startswith("title:"):
                    title = line.split(":", 1)[1].strip()
            else:
                body_lines.append(line)

        if not title:
            title = file.replace(".md", "").replace("-", " ").title()

        html_lines = []
        for line in body_lines:
            if line.startswith("## "):
                html_lines.append(f"<h2>{escape_html(line[3:])}</h2>")
            elif line.startswith("# "):
                html_lines.append(f"<h1>{escape_html(line[2:])}</h1>")
            elif line.startswith(("- ", "* ")):
                html_lines.append(f"<p>• {escape_html(line[2:])}</p>")
            elif line.strip() == "":
                html_lines.append("<br/>")
            else:
                html_lines.append(f"<p>{escape_html(line)}</p>")

        article_html = f"""
        <div class="card">
            <h2>{escape_html(title)}</h2>
            {''.join(html_lines)}
        </div>
        """
        articles.append(article_html)

    with open("help.html", "w", encoding="utf-8") as f:
        f.write(generate_page("Help Center", "".join(articles)))
    print(f"✅ help.html generated ({len(articles)} articles)")
    return True

# -------------------------
# Entry point
# -------------------------
def find_repo_root():
    """Find a directory that contains 'schemas' by walking up from script dir."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cur = script_dir
    for _ in range(4):  # check script_dir and up to 3 parents
        if os.path.isdir(os.path.join(cur, "schemas")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return script_dir  # fallback

if __name__ == "__main__":
    print("🚀 STARTING build_public_pages.py — GENERIC VERSION FOR ANY REPO")

    REPO_ROOT = find_repo_root()
    os.chdir(REPO_ROOT)
    print(f"✅ WORKING DIRECTORY SET TO: {REPO_ROOT}")

    # Verify schemas exists
    if not os.path.exists("schemas"):
        print("❌ FATAL: schemas/ folder not found at repo root")
        sys.exit(1)
    else:
        print(f"📁 schemas/ contents: {os.listdir('schemas')[:10]}")

    # Create .nojekyll — required for GitHub Pages
    open(".nojekyll", "w").close()
    print("✅ Created .nojekyll file for GitHub Pages")

    # Force rebuild — delete old pages
    html_files = ["index.html", "about.html", "services.html", "testimonials.html", "faqs.html", "help.html", "contact.html"]
    for f in html_files:
        if os.path.exists(f):
            os.remove(f)
            print(f"🗑️ Deleted old {f} — forcing rebuild")

    # Generate all pages
    page_generators = [
        ("index.html", generate_index_page),
        ("about.html", generate_about_page),
        ("services.html", generate_services_page),
        ("testimonials.html", generate_testimonials_page),
        ("faqs.html", generate_faq_page),
        ("help.html", generate_help_articles_page),
        ("contact.html", generate_contact_page),
    ]

    any_success = False
    for filename, generator in page_generators:
        try:
            success = generator()
            if success:
                print(f"✅ {filename} generated successfully")
                any_success = True
        except Exception as e:
            print(f"❌ {filename} generation failed: {e}")

    if not any_success:
        print("⚠️ No pages generated — check your schemas/* folders and filenames")
    else:
        print("\n🎉 BUILD COMPLETE — site ready for GitHub Pages deployment")
