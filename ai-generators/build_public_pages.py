# ai-generators/build_public_pages.py
import sys
import os
import yaml
import json
import re
from datetime import datetime

# =========================
# Utilities
# =========================
def escape_html(text):
    if not isinstance(text, str):
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def slugify(text):
    if not text:
        return "item"
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', str(text))
    text = re.sub(r'[\s]+', '-', text.strip().lower())
    return text or "item"

def load_data(filepath):
    if not filepath or not os.path.exists(filepath):
        if filepath:
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

def _first_nonempty(*vals):
    for v in vals:
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, (int, float)):
            return str(v)
        if isinstance(v, dict) and "@value" in v and isinstance(v["@value"], str) and v["@value"].strip():
            return v["@value"].strip()
    return ""

def _as_list(val):
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    if isinstance(val, str) and val.strip():
        return [s.strip() for s in val.split(",") if s.strip()]
    return []

def _title_from_filename(path):
    base = os.path.splitext(os.path.basename(path))[0]
    return base.replace("-", " ").replace("_", " ").strip().title()

def _is_placeholder_title(text):
    if not isinstance(text, str) or not text.strip():
        return True
    t = text.strip().lower()
    return (
        t in {"service", "unnamed service", "untitled", "n/a", "na", "tbd"}
        or bool(re.fullmatch(r"(service|item|entry)\s*\d+", t))
    )

def _guess_description(obj):
    return _first_nonempty(
        obj.get("description"),
        obj.get("summary"),
        obj.get("details"),
        obj.get("body"),
        obj.get("content"),
        obj.get("answer"),
        obj.get("copy"),
    )

def _guess_price(obj):
    return _first_nonempty(
        obj.get("price"),
        obj.get("price_range"),
        obj.get("starting_price"),
        obj.get("min_price"),
        obj.get("cost"),
        obj.get("fee"),
    ) or "Contact for pricing"

def _bullet_points(obj):
    feats = _as_list(obj.get("features") or obj.get("benefits") or obj.get("highlights"))
    specs = _as_list(obj.get("specialties") or obj.get("capabilities"))
    areas = _as_list(obj.get("service_areas") or obj.get("areas") or obj.get("locations_served"))
    bullets = []
    for f in feats[:3]: bullets.append(f)
    if not bullets:
        for s in specs[:3]: bullets.append(s)
    if areas:
        bullets.append("Service areas: " + ", ".join(areas[:5]))
    seen, out = set(), []
    for b in bullets:
        if b.lower() not in seen:
            out.append(b); seen.add(b.lower())
    return out[:4]

# =========================
# Contact helpers
# =========================
FIELD_ALIASES = {
    "entity_name": ["entity_name", "organization", "org_name", "company", "name"],
    "contact_person": ["contact_person", "contact", "contact_name", "primary_contact", "attention"],
    "email": ["email", "contact_email", "email_address", "mail"],
    "phone": ["phone", "telephone", "tel", "phone_number", "contact_number"],
    "address_street": ["address_street", "streetAddress", "street", "address1", "address_line_1", "address_line"],
    "address_city": ["address_city", "city", "addressLocality"],
    "address_state": ["address_state", "state", "addressRegion", "province"],
    "address_postal_code": ["address_postal_code", "postalCode", "zip", "zipCode", "postcode"],
    "hours": ["hours", "openingHours", "opening_hours", "business_hours"],
    "map_embed_url": ["map_embed_url", "map", "map_iframe"],
    "google_maps_url": ["google_maps_url", "maps_url", "map_url"],
    "latitude": ["geo_latitude", "latitude", "lat"],
    "longitude": ["geo_longitude", "longitude", "lng", "lon"],
    "website": ["website", "url", "homepage"],
    "sameAs": ["sameAs", "same_as", "social", "social_links"],
}

def _alias_get(d: dict, canon_key: str):
    if not isinstance(d, dict):
        return None
    if canon_key in d and (d[canon_key] or d[canon_key] == 0):
        return d[canon_key]
    for k in FIELD_ALIASES.get(canon_key, []):
        if k in d and (d[k] or d[k] == 0):
            return d[k]
    if canon_key in ("latitude", "longitude"):
        geo = d.get("geo") or {}
        if isinstance(geo, dict):
            return geo.get(canon_key)
    if canon_key in ("phone", "email"):
        cp = d.get("contactPoint") or d.get("contact_point")
        if isinstance(cp, dict):
            if canon_key == "phone":
                return _first_nonempty(cp.get("telephone"), cp.get("phone"))
            else:
                return _first_nonempty(cp.get("email"))
    return None

def _format_address_from_components(loc: dict):
    line1 = _first_nonempty(_alias_get(loc, "address_street"))
    line2 = _first_nonempty(loc.get("address2"), loc.get("address_line_2"), loc.get("suite"))
    city  = _first_nonempty(_alias_get(loc, "address_city"))
    state = _first_nonempty(_alias_get(loc, "address_state"))
    zipc  = _first_nonempty(_alias_get(loc, "address_postal_code"))
    parts = [line1, line2, ", ".join([p for p in [city, state] if p]) if city or state else None, zipc]
    return " ".join([p for p in parts if p]).strip()

def _format_address(addr, loc):
    if isinstance(addr, str) and addr.strip():
        return addr.strip()
    if isinstance(addr, dict):
        line1 = _first_nonempty(addr.get("streetAddress"), addr.get("address1"), addr.get("addressLine1"))
        line2 = _first_nonempty(addr.get("address2"), addr.get("addressLine2"), addr.get("suite"))
        city  = _first_nonempty(addr.get("addressLocality"), addr.get("city"))
        state = _first_nonempty(addr.get("addressRegion"), addr.get("state"))
        zipc  = _first_nonempty(addr.get("postalCode"), addr.get("zip"), addr.get("zipCode"))
        parts = [line1, line2, ", ".join([p for p in [city, state] if p]) if city or state else None, zipc]
        return " ".join([p for p in parts if p]).strip()
    return _format_address_from_components(loc)

def _extract_hours(loc):
    hours = _first_nonempty(_alias_get(loc, "hours"))
    if hours:
        return hours
    spec = loc.get("openingHoursSpecification") or loc.get("opening_hours_specification")
    if isinstance(spec, list) and spec:
        rows = []
        for r in spec:
            if not isinstance(r, dict):
                continue
            day = _first_nonempty(r.get("dayOfWeek"), r.get("day"), r.get("weekday"))
            if isinstance(day, list) and day:
                day = day[0]
            if isinstance(day, str) and "/" in day:
                day = day.rsplit("/", 1)[-1]
            opens  = _first_nonempty(r.get("opens"), r.get("openingTime"))
            closes = _first_nonempty(r.get("closes"), r.get("closingTime"))
            if day and (opens or closes):
                rows.append(f"{day}: {opens or '—'} – {closes or '—'}")
        if rows:
            return "; ".join(rows)
    return ""

def _map_embed_src(loc, address):
    lat = _alias_get(loc, "latitude")
    lng = _alias_get(loc, "longitude")
    if isinstance(lat, (int, float)) and isinstance(lng, (int, float)):
        return f"https://www.google.com/maps?q={lat},{lng}&z=15&output=embed"
    map_url = _first_nonempty(_alias_get(loc, "map_embed_url"))
    gmaps   = _first_nonempty(_alias_get(loc, "google_maps_url"))
    if map_url: return map_url
    if gmaps:   return gmaps
    if address:
        from urllib.parse import quote_plus
        return f"https://www.google.com/maps?q={quote_plus(address)}&output=embed"
    return ""

def _normalize_records(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        if isinstance(payload.get("locations"), list):
            return payload["locations"]
        return [payload]
    return []

# =========================
# Branding / meta
# =========================
def _load_first_yaml_json(path_glob):
    import glob
    for p in glob.glob(path_glob):
        if os.path.isfile(p) and p.lower().endswith((".json", ".yaml", ".yml")):
            data = load_data(p)
            if data:
                return data[0] if isinstance(data, list) else data
    return None

def _discover_entity_name_from_other_schemas():
    probes = [
        "schemas/organization/*.*",
        "schemas/organizations/*.*",
        "schemas/company/*.*",
        "schemas/entity/*.*",
        "schemas/business/*.*",
        "schemas/reviews/*.*",
        "schemas/services/*.*",
        "schemas/locations/*.*",
    ]
    for pat in probes:
        obj = _load_first_yaml_json(pat)
        if not obj or not isinstance(obj, dict):
            continue
        candidate = _first_nonempty(
            obj.get("entity_name"),
            obj.get("name"),
            obj.get("legal_name"),
            obj.get("brand"),
            obj.get("company"),
            obj.get("organization"),
            obj.get("site_title"),
        )
        if candidate:
            return candidate
    return None

def load_org_meta():
    meta = {"name": None, "favicon": None, "logo": None}
    candidate_dirs = ["schemas/organization", "schemas/organizations", "schemas/company", "schemas/entity", "schemas/business"]
    import glob
    org_file = None
    for d in candidate_dirs:
        if os.path.isdir(d):
            cand = [p for p in glob.glob(os.path.join(d, "*.*")) if p.lower().endswith((".json",".yaml",".yml"))]
            if cand:
                org_file = cand[0]
                break
    org = None
    if org_file:
        data = load_data(org_file)
        org = data[0] if isinstance(data, list) else data
    if isinstance(org, dict):
        meta["name"] = _first_nonempty(org.get("entity_name"), org.get("name"), org.get("legal_name"), org.get("brand"), org.get("site_title"))
        meta["logo"] = _first_nonempty(org.get("logo_url"), org.get("logo"))
        meta["favicon"] = _first_nonempty(org.get("favicon"), org.get("favicon_url"))
    if not meta["name"]:
        meta["name"] = _discover_entity_name_from_other_schemas()
    if not meta["name"]:
        repo_slug = os.getenv("GITHUB_REPOSITORY") or ""
        meta["name"] = repo_slug.split("/", 1)[-1].replace("-", " ").title() if repo_slug else "Site"
    return meta

# =========================
# HTML shells (nav + footer)
# =========================
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

def generate_footer():
    return f"""
    <footer style="margin-top: 4rem; padding-top: 2rem; border-top: 1px solid #eee; color: #7f8c8d;">
        <div style="text-align:center; margin-bottom:1rem;">
            <a href="index.html">Home</a> ·
            <a href="about.html">About</a> ·
            <a href="services.html">Services</a> ·
            <a href="testimonials.html">Testimonials</a> ·
            <a href="faqs.html">FAQs</a> ·
            <a href="help.html">Help</a> ·
            <a href="contact.html">Contact</a>
        </div>
        <p style="text-align:center;">© {datetime.now().year} — Auto-generated from structured data. Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
    </footer>
    """

def generate_page(title, content):
    org = load_org_meta()
    site_name = org.get("name") or "Site"
    page_title = f"{escape_html(site_name)} — {escape_html(title)}" if title else escape_html(site_name)
    favicon_href = org.get("favicon") or "favicon.ico"
    theme_color = "#2c3e50"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{page_title}</title>
    <meta name="application-name" content="{escape_html(site_name)}">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="theme-color" content="{theme_color}">
    <link rel="icon" href="{escape_html(favicon_href)}">
    <link rel="icon" type="image/png" sizes="32x32" href="icons/favicon-32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="icons/favicon-16.png">
    <link rel="apple-touch-icon" sizes="180x180" href="icons/apple-touch-icon.png">
    <link rel="manifest" href="site.webmanifest">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.7; }}
        h1, h2, h3 {{ color: #2c3e50; }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        img {{ max-width: 100%; height: auto; }}
        .page-header {{ background: #ecf0f1; padding: 2rem; border-radius: 8px; margin-bottom: 2rem; text-align: center; }}
        .card {{ border: 1px solid #eee; padding: 1.5rem; border-radius: 8px; margin: 2rem 0; }}
        .badge {{ background: #3498db; color: white; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.9em; }}
        .toc {{ position: sticky; top: 0; background: #fff; padding: 1rem; border: 1px solid #eee; border-radius: 8px; margin-bottom: 1.5rem; }}
        .toc h2 {{ margin-top: 0; }}
        .toc ul {{ margin: 0; padding-left: 1.25rem; }}
    </style>
</head>
<body>
    {generate_nav()}
    <div class="page-header">
        <h1>{escape_html(title or site_name)}</h1>
    </div>
    {content}
    {generate_footer()}
</body>
</html>"""

# =========================
# Pages
# =========================
def generate_contact_page():
    """
    Builds contact.html from schemas/locations/*.{json,yaml,yml}
    Renders a top 'Quick Contact' card, then deduped location card(s).
    Deduping key = (entity, person, phone, email, address, map_src) normalized.
    """
    locations_dir = "schemas/locations"
    print(f"🔍 Checking contact data in: {locations_dir}")
    if not os.path.exists(locations_dir):
        # Still create the page to avoid 404s
        with open("contact.html", "w", encoding="utf-8") as f:
            f.write(generate_page("Contact Us", "<p>No contact locations found yet.</p>"))
        print("⚠️ contact.html created with placeholder (no data; folder missing).")
        return True

    def _extract_contact(loc):
        phone = _first_nonempty(_alias_get(loc, "phone"))
        email = _first_nonempty(_alias_get(loc, "email"))
        return phone, email

    def _extract_site_and_social(loc):
        website = _first_nonempty(_alias_get(loc, "website"))
        socials = _as_list(_alias_get(loc, "sameAs"))
        return website, socials

    def _norm(s: str) -> str:
        return (s or "").strip().lower()

    def _norm_phone(s: str) -> str:
        return re.sub(r"\D+", "", s or "")

    items = []
    files_seen = records_seen = rendered = 0

    # Quick Contact fields (prefer person over entity if available)
    quick_label = ""
    quick_phone = ""
    quick_email = ""

    # Signatures we've already rendered
    seen = set()

    for fname in sorted(os.listdir(locations_dir)):
        if not fname.lower().endswith((".json", ".yaml", ".yml")):
            continue
        files_seen += 1
        path = os.path.join(locations_dir, fname)
        data = load_data(path)
        if not data:
            continue

        for loc in _normalize_records(data):
            if not isinstance(loc, dict):
                continue
            records_seen += 1

            entity = _first_nonempty(_alias_get(loc, "entity_name"), loc.get("location_name")) or "Location"
            person = _first_nonempty(_alias_get(loc, "contact_person"))
            phone, email = _extract_contact(loc)
            addr   = _format_address(loc.get("address"), loc)
            hours  = _extract_hours(loc)
            site, socials = _extract_site_and_social(loc)
            map_src = _map_embed_src(loc, addr)

            # Build dedupe signature
            sig = (
                _norm(entity),
                _norm(person),
                _norm_phone(phone),
                _norm(email),
                _norm(addr),
                _norm(map_src),
            )
            if sig in seen:
                continue
            seen.add(sig)

            # Prime quick contact once, preferring a person label
            if not quick_label:
                quick_label = person or entity
            if not quick_phone and phone:
                quick_phone = phone
            if not quick_email and email:
                quick_email = email

            block = f"<div class='card'>"
            block += f"<h3>{escape_html(entity)}</h3><p>"
            if person:
                block += f"<strong>Contact:</strong> {escape_html(person)}<br>"
            if addr:
                block += f"<strong>Address:</strong> {escape_html(addr)}<br>"
            if phone:
                block += f"<strong>Phone:</strong> <a href='tel:{escape_html(phone)}'>{escape_html(phone)}</a><br>"
            if email:
                block += f"<strong>Email:</strong> <a href='mailto:{escape_html(email)}'>{escape_html(email)}</a><br>"
            if hours:
                block += f"<strong>Hours:</strong> {escape_html(hours)}<br>"
            if site:
                block += f"<strong>Website:</strong> <a href='{escape_html(site)}' target='_blank' rel='nofollow'>{escape_html(site)}</a><br>"
            block += "</p>"

            if socials:
                block += "<p><strong>Find us:</strong> " + " • ".join(
                    f"<a href='{escape_html(s)}' target='_blank' rel='nofollow'>{escape_html(s)}</a>" for s in socials[:8]
                ) + "</p>"

            if map_src:
                block += f"""
                <div style="margin-top: 1rem;">
                    <iframe src="{escape_html(map_src)}" width="100%" height="320"
                            style="border:0; border-radius: 8px;" allowfullscreen loading="lazy"></iframe>
                </div>
                """

            block += "</div>"
            items.append(block)
            rendered += 1

    # Always create the page (avoid 404s)
    intro = "<p>We’d love to hear from you. Reach out using the details below or visit us at our offices.</p>"
    if quick_label or quick_phone or quick_email:
        intro += "<div class='card'><h2>Quick Contact</h2>"
        if quick_label:
            intro += f"<p><strong>{escape_html(quick_label)}</strong></p>"
        if quick_phone:
            intro += f"<p><strong>Phone:</strong> <a href='tel:{escape_html(quick_phone)}'>{escape_html(quick_phone)}</a></p>"
        if quick_email:
            intro += f"<p><strong>Email:</strong> <a href='mailto:{escape_html(quick_email)}'>{escape_html(quick_email)}</a></p>"
        intro += "</div>"

    content = (intro + "".join(items)) if items else (intro + "<p>No contact locations found yet.</p>")
    with open("contact.html", "w", encoding="utf-8") as f:
        f.write(generate_page("Contact Us", content))

    print(f"✅ contact.html generated — {rendered} unique location card(s) from {files_seen} file(s), {records_seen} record(s) scanned (deduped: {records_seen - rendered})")
    return True

def generate_services_page():
    services_dir = "schemas/services"
    print(f"🔍 Checking services data in: {services_dir}")
    if not os.path.exists(services_dir):
        with open("services.html", "w", encoding="utf-8") as f:
            f.write(generate_page("Our Services", "<p>No services found yet.</p>"))
        print("⚠️ services.html created with placeholder (no data).")
        return True

    def _guess_title(obj, filename):
        candidate = _first_nonempty(
            obj.get("title"),
            obj.get("service_name"),
            obj.get("name"),
            obj.get("headline"),
            obj.get("service"),
            obj.get("offering"),
            obj.get("product_name"),
            obj.get("category"),
            obj.get("subtype"),
            obj.get("type"),
            obj.get("label"),
        )
        if _is_placeholder_title(candidate):
            kws = _as_list(obj.get("keywords"))
            if kws:
                candidate = " / ".join(kws[:2]).title()
        if _is_placeholder_title(candidate):
            candidate = _title_from_filename(filename)
        return candidate or "Service"

    items = []
    files_processed = placeholders_fixed = 0

    for file in sorted(os.listdir(services_dir)):
        if not file.endswith((".json", ".yaml", ".yml")):
            continue
        filepath = os.path.join(services_dir, file)
        data = load_data(filepath)
        if not data:
            continue
        files_processed += 1

        records = data if isinstance(data, list) else [data]
        expanded = []
        for rec in records:
            if isinstance(rec, dict) and isinstance(rec.get("services"), list):
                expanded.extend(rec["services"])
            else:
                expanded.append(rec)

        for svc in expanded:
            if not isinstance(svc, dict):
                continue

            title_before = _first_nonempty(svc.get("title"), svc.get("service_name"), svc.get("name"))
            title = _guess_title(svc, filepath)
            if _is_placeholder_title(title_before) and not _is_placeholder_title(title):
                placeholders_fixed += 1

            description = _guess_description(svc) or ""
            price = _guess_price(svc)
            featured = bool(svc.get("featured") or svc.get("is_featured"))
            slug = svc.get("slug") or slugify(title)
            badge = '<span class="badge">Featured</span>' if featured else ''
            bullets = _bullet_points(svc)
            bullet_html = "<ul>" + "".join(f"<li>{escape_html(b)}</li>" for b in bullets) + "</ul>" if bullets else ""

            items.append(f"""
            <div class="card" id="{escape_html(slug)}">
                <h2>{escape_html(title)} {badge}</h2>
                {'<p>' + escape_html(description) + '</p>' if description else ''}
                {bullet_html}
                <p><strong>Starting at:</strong> {escape_html(price)}</p>
                <a href="#{slug}" style="display: inline-block; margin-top: 1rem;">🔗 Permalink</a>
            </div>
            """)

    if not items:
        with open("services.html", "w", encoding="utf-8") as f:
            f.write(generate_page("Our Services", "<p>No services found yet.</p>"))
        print("⚠️ services.html created with placeholder (no service items).")
        return True

    with open("services.html", "w", encoding="utf-8") as f:
        f.write(generate_page("Our Services", "".join(items)))

    if placeholders_fixed:
        print(f"✨ Polished {placeholders_fixed} placeholder service title(s).")
    print(f"✅ services.html generated ({len(items)} services from {files_processed} file(s))")
    return True

def generate_testimonials_page():
    reviews_dir = "schemas/reviews"
    print(f"🔍 Checking testimonials data in: {reviews_dir}")
    if not os.path.exists(reviews_dir):
        with open("testimonials.html", "w", encoding="utf-8") as f:
            f.write(generate_page("Testimonials", "<p>No testimonials found yet.</p>"))
        print("⚠️ testimonials.html created with placeholder (no data).")
        return True

    items = []; total = 0
    for file in os.listdir(reviews_dir):
        if file.endswith((".json", ".yaml", ".yml")):
            filepath = os.path.join(reviews_dir, file)
            rev_data = load_data(filepath)
            if not rev_data:
                continue
            for rev in (rev_data if isinstance(rev_data, list) else [rev_data]):
                if not isinstance(rev, dict): continue
                author = _first_nonempty(rev.get('customer_name'), rev.get('author')) or 'Anonymous'
                entity = rev.get('entity_name') or ''
                quote = _first_nonempty(rev.get('review_body'), rev.get('quote'), rev.get('review_title')) or 'No review text provided.'
                try:
                    rating = int(float(str(rev.get('rating', 5))))
                except Exception:
                    rating = 5
                date = _first_nonempty(rev.get('date'))
                stars = '★' * max(0, min(5, rating)) + '☆' * (5 - max(0, min(5, rating)))
                items.append(f"""
                <blockquote class="card" style="font-style: italic;">
                    <p>“{escape_html(quote)}”</p>
                    <footer style="margin-top: 1rem; font-style: normal;">
                        — {escape_html(author)}{f', {escape_html(entity)}' if entity else ''}
                        {f'<br/><small>{escape_html(date)}</small>' if date else ''}
                    </footer>
                    <div style="margin-top: 0.5rem; color: #f39c12;">{stars}</div>
                </blockquote>
                """)
                total += 1

    if not items:
        with open("testimonials.html", "w", encoding="utf-8") as f:
            f.write(generate_page("Testimonials", "<p>No testimonials found yet.</p>"))
        print("⚠️ testimonials.html created with placeholder (no items).")
        return True

    with open("testimonials.html", "w", encoding="utf-8") as f:
        f.write(generate_page("Testimonials", "".join(items)))
    print(f"✅ testimonials.html generated ({total} testimonials)")
    return True

def generate_index_page():
    org = load_org_meta()
    site_name = org.get("name") or "Site"
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
        return False

    base_url = f"https://raw.githubusercontent.com/{repo_slug}/main"
    print(f"🌐 Base URL for schema files: {base_url}")

    for root, _, files in os.walk("schemas"):
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
        f.write(generate_page(f"Welcome to {site_name}", content))
    print("✅ index.html generated")
    return True

def generate_about_page():
    """
    Rich About page that MERGES all org records and surfaces full sameAs/socials.
    """

    # --- helpers ---
    def _load_all_orgs():
        candidate_dirs = [
            "schemas/organization", "schemas/organizations",
            "schemas/company", "schemas/entity", "schemas/business",
        ]
        orgs = []
        for d in candidate_dirs:
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if not fn.lower().endswith((".json", ".yaml", ".yml")):
                    continue
                recs = load_data(os.path.join(d, fn))
                if isinstance(recs, list):
                    orgs.extend([r for r in recs if isinstance(r, dict)])
                elif isinstance(recs, dict):
                    orgs.append(recs)
        return orgs

    def _merge_orgs(orgs):
        """Pick best non-empty value per field across all orgs; merge lists like sameAs."""
        merged = {}
        list_keys = {"sameAs", "same_as", "social", "social_links"}
        # fields we might want to pick best single value
        scalar_order = [
            "entity_name", "name", "legal_name", "brand", "site_title",
            "description", "mission", "vision",
            "logo_url", "logo",
            "website", "main_website_url", "url",
            "phone", "email",
        ]
        # take the first non-empty for scalars
        for key in scalar_order:
            for org in orgs:
                v = org.get(key)
                if _first_nonempty(v):
                    merged[key] = _first_nonempty(v)
                    break

        # merge all social-like keys into a single list (dedup)
        socials = []
        for org in orgs:
            for lk in list_keys:
                socials.extend(_as_list(org.get(lk)))
        # de-dup while preserving order
        seen, dedup = set(), []
        for s in socials:
            if s and s not in seen:
                dedup.append(s)
                seen.add(s)
        if dedup:
            merged["sameAs_merged"] = dedup
        return merged

    def _gather_titles_from_dir(root_dir, key_list=None, nested_list_key=None, max_items=None):
        titles = []
        if not os.path.isdir(root_dir):
            return titles
        for fn in sorted(os.listdir(root_dir)):
            if not fn.lower().endswith((".json", ".yaml", ".yml")):
                continue
            for rec in (load_data(os.path.join(root_dir, fn)) or []):
                if not isinstance(rec, dict):
                    continue
                if nested_list_key and isinstance(rec.get(nested_list_key), list):
                    for sub in rec[nested_list_key]:
                        if isinstance(sub, dict):
                            t = _first_nonempty(*(sub.get(k) for k in (key_list or [])))
                            if _is_placeholder_title(t):
                                t = None
                            titles.append(t or _title_from_filename(fn))
                else:
                    t = _first_nonempty(*(rec.get(k) for k in (key_list or [])))
                    if _is_placeholder_title(t):
                        t = None
                    titles.append(t or _title_from_filename(fn))
        # de-dup
        seen, out = set(), []
        for t in titles:
            if t and t.lower() not in seen:
                out.append(t)
                seen.add(t.lower())
        return out[:max_items] if max_items else out

    def _count_records(root_dir):
        if not os.path.isdir(root_dir):
            return 0
        count = 0
        for fn in os.listdir(root_dir):
            if not fn.lower().endswith((".json", ".yaml", ".yml", ".md", ".llm")):
                continue
            if fn.lower().endswith((".json", ".yaml", ".yml")):
                recs = load_data(os.path.join(root_dir, fn))
                if isinstance(recs, list):
                    count += len(recs)
                else:
                    count += 1
            else:
                count += 1
        return count

    # --- Load & merge org data (this is the key fix) ---
    all_orgs = _load_all_orgs()
    merged = _merge_orgs(all_orgs) if all_orgs else {}

    site_name = _first_nonempty(
        merged.get("entity_name"),
        merged.get("name"),
        merged.get("legal_name"),
        merged.get("brand"),
        merged.get("site_title"),
        load_org_meta().get("name"),
        "Our Firm"
    )
    logo_url = _first_nonempty(merged.get("logo_url"), merged.get("logo"))
    # include main_website_url as a strong candidate
    website  = _first_nonempty(merged.get("website"), merged.get("main_website_url"), merged.get("url"))
    desc     = _first_nonempty(merged.get("description")) or f"{site_name} is a results-driven law firm focused on client advocacy and outstanding outcomes."
    mission  = _first_nonempty(merged.get("mission"))
    vision   = _first_nonempty(merged.get("vision"))
    phone    = _first_nonempty(merged.get("phone"))
    email    = _first_nonempty(merged.get("email"))

    # merged sameAs list
    sameas   = merged.get("sameAs_merged", [])

    # roll-ups
    service_titles = _gather_titles_from_dir("schemas/services",
                                             key_list=["title","service_name","name","headline","category","type","label"],
                                             nested_list_key="services",
                                             max_items=12)
    services_count = _count_records("schemas/services")
    faqs_count  = _count_records("schemas/faqs")
    help_count  = _count_records("schemas/help-articles")
    team_count  = _count_records("schemas/team")
    loc_count   = _count_records("schemas/locations")
    awards_count= _count_records("schemas/awards")
    press_count = _count_records("schemas/press")
    cases_count = _count_records("schemas/case-studies")

    # reviews summary
    reviews_dir = "schemas/reviews"
    review_count, ratings = 0, []
    if os.path.isdir(reviews_dir):
        for fn in os.listdir(reviews_dir):
            if not fn.lower().endswith((".json", ".yaml", ".yml")): 
                continue
            for rec in (load_data(os.path.join(reviews_dir, fn)) or []):
                if isinstance(rec, dict):
                    review_count += 1
                    try:
                        r = float(rec.get("rating"))
                        if r > 0: ratings.append(r)
                    except Exception:
                        pass
    avg_rating = (sum(ratings) / len(ratings)) if ratings else None

    # service areas + primary address
    service_areas = set()
    address_str = ""
    if os.path.isdir("schemas/locations"):
        for fn in os.listdir("schemas/locations"):
            if not fn.lower().endswith((".json", ".yaml", ".yml")):
                continue
            for loc in (load_data(os.path.join("schemas/locations", fn)) or []):
                if not isinstance(loc, dict): 
                    continue
                for area in _as_list(loc.get("service_areas") or loc.get("areas") or loc.get("locations_served")):
                    service_areas.add(area)
                if not address_str:
                    address_str = _format_address(loc.get("address"), loc)

    # --- Build page ---
    toc = """
    <nav class="card" aria-label="Page sections" style="margin-top:1rem">
      <strong>On this page:</strong>
      <ul style="margin:0.5rem 0 0; padding-left:1.2rem;">
        <li><a href="#overview">Overview</a></li>
        <li><a href="#practice-areas">Practice Areas</a></li>
        <li><a href="#facts">Key Facts</a></li>
        <li><a href="#locations">Locations & Hours</a></li>
        <li><a href="#team">Team</a></li>
        <li><a href="#reviews">Reviews</a></li>
        <li><a href="#press-awards">Press & Awards</a></li>
        <li><a href="#resources">Helpful Resources</a></li>
        <li><a href="#profiles">Social & Profiles</a></li>
        <li><a href="#contact">Contact</a></li>
      </ul>
    </nav>
    """

    parts = []
    if logo_url:
        parts.append(f'<img src="{escape_html(logo_url)}" alt="{escape_html(site_name)}" style="max-height:120px;margin-bottom:1.25rem;border-radius:8px">')

    parts.append(f'<section id="overview" class="card"><h2>Overview</h2><p>{escape_html(desc)}</p>')
    if mission:
        parts.append(f"<h3>Our Mission</h3><p>{escape_html(mission)}</p>")
    if vision:
        parts.append(f"<h3>Our Vision</h3><p>{escape_html(vision)}</p>")
    parts.append("</section>")

    if service_titles:
        areas_list = "".join(f"<li>{escape_html(t)}</li>" for t in service_titles)
        parts.append(f"""
        <section id="practice-areas" class="card">
          <h2>Practice Areas</h2>
          <ul>{areas_list}</ul>
          <p><a href="services.html">Browse all services ({services_count}) →</a></p>
        </section>
        """)

    facts = []
    facts.append(f"<strong>Services:</strong> {services_count}")
    facts.append(f"<strong>FAQs:</strong> {faqs_count}")
    facts.append(f"<strong>Help Articles:</strong> {help_count}")
    facts.append(f"<strong>Team Members:</strong> {team_count}")
    facts.append(f"<strong>Locations:</strong> {loc_count}")
    if review_count:
        if avg_rating is not None:
            stars = "★" * int(round(avg_rating)) + "☆" * (5 - int(round(avg_rating)))
            facts.append(f"<strong>Reviews:</strong> {review_count} (avg {avg_rating:.1f}) {stars}")
        else:
            facts.append(f"<strong>Reviews:</strong> {review_count}")
    if awards_count: facts.append(f"<strong>Awards/Certifications:</strong> {awards_count}")
    if press_count:  facts.append(f"<strong>Press Mentions:</strong> {press_count}")
    if cases_count:  facts.append(f"<strong>Case Studies:</strong> {cases_count}")
    if service_areas:
        facts.append(f"<strong>Service Areas:</strong> {escape_html(', '.join(sorted(list(service_areas))[:12]))}")

    parts.append('<section id="facts" class="card"><h2>Key Facts</h2><ul>' + "".join(f"<li>{row}</li>" for row in facts) + "</ul></section>")

    if address_str or loc_count:
        hours_text = ""
        if os.path.isdir("schemas/locations"):
            for fn in os.listdir("schemas/locations"):
                if not fn.lower().endswith((".json", ".yaml", ".yml")): continue
                for loc in (load_data(os.path.join("schemas/locations", fn)) or []):
                    if isinstance(loc, dict):
                        hours_text = _extract_hours(loc)
                        break
                if hours_text: break

        parts.append(f"""
        <section id="locations" class="card">
          <h2>Locations & Hours</h2>
          {'<p><strong>Primary Address:</strong> ' + escape_html(address_str) + '</p>' if address_str else ''}
          {('<p><strong>Hours:</strong> ' + escape_html(hours_text) + '</p>') if hours_text else ''}
          <p><a href="contact.html">All contact details & map →</a></p>
        </section>
        """)

    if team_count:
        parts.append(f"""
        <section id="team" class="card">
          <h2>Team</h2>
          <p><em>Total team members:</em> {team_count}</p>
        </section>
        """)

    if review_count:
        parts.append(f"""
        <section id="reviews" class="card">
          <h2>Reviews</h2>
          <p><a href="testimonials.html">Read testimonials →</a></p>
        </section>
        """)

    if press_count or awards_count:
        parts.append(f"""
        <section id="press-awards" class="card">
          <h2>Press & Awards</h2>
          <ul>
            {'<li><a href="press.html">Press mentions</a></li>' if press_count else ''}
            {'<li><a href="awards.html">Awards & certifications</a></li>' if awards_count else ''}
          </ul>
        </section>
        """)

    if faqs_count or help_count:
        parts.append(f"""
        <section id="resources" class="card">
          <h2>Helpful Resources</h2>
          <ul>
            {'<li><a href="faqs.html">Frequently Asked Questions</a></li>' if faqs_count else ''}
            {'<li><a href="help.html">Help Center Articles</a></li>' if help_count else ''}
          </ul>
        </section>
        """)

    # PROFILES from merged sameAs + website
    if sameas or website:
        links = []
        if website:
            links.append(f'<li><a href="{escape_html(website)}" target="_blank" rel="nofollow">Website</a></li>')
        for s in sameas[:48]:
            links.append(f'<li><a href="{escape_html(s)}" target="_blank" rel="nofollow">{escape_html(s)}</a></li>')
        parts.append(f"""
        <section id="profiles" class="card">
          <h2>Social & Profiles</h2>
          <ul>{''.join(links)}</ul>
        </section>
        """)

    contact_bits = []
    if phone: contact_bits.append(f"<strong>Phone:</strong> <a href='tel:{escape_html(phone)}'>{escape_html(phone)}</a>")
    if email: contact_bits.append(f"<strong>Email:</strong> <a href='mailto:{escape_html(email)}'>{escape_html(email)}</a>")
    parts.append(f"""
    <section id="contact" class="card">
      <h2>Ready to Talk?</h2>
      <p>{' &nbsp;•&nbsp; '.join(contact_bits) if contact_bits else ''}</p>
      <p><a href="contact.html">Contact us →</a></p>
    </section>
    """)

    # Organization JSON-LD (now with merged sameAs)
    json_ld = {
        "@context": "https://schema.org",
        "@type": "LegalService",
        "name": site_name,
        **({"url": website} if website else {}),
        **({"logo": logo_url} if logo_url else {}),
        **({"telephone": phone} if phone else {}),
        **({"email": email} if email else {}),
        **({"sameAs": sameas} if sameas else {}),
    }
    if address_str:
        json_ld["address"] = {"@type": "PostalAddress", "streetAddress": address_str}

    content = (
        toc +
        "\n".join(parts) +
        f'\n<script type="application/ld+json">{json.dumps(json_ld)}</script>\n'
    )

    with open("about.html", "w", encoding="utf-8") as f:
        f.write(generate_page(site_name, content))

    print("✅ about.html generated (merged org + full sameAs)")
    return True

# ---------- Helpers for TOC + Categorization ----------
def _guess_category_from_text(text: str) -> str:
    t = (text or "").lower()
    maps = [
        ("dui", "DUI & DMV"),
        ("dmv", "DUI & DMV"),
        ("personal injury", "Personal Injury"),
        ("injury", "Personal Injury"),
        ("car accident", "Personal Injury"),
        ("property damage", "Property Damage"),
        ("felony", "Felony"),
        ("misdemeanor", "Misdemeanor"),
        ("federal", "Federal"),
        ("state", "State"),
        ("trial", "Trial"),
        ("appeal", "Appeals"),
        ("domestic violence", "Domestic Violence"),
        ("drug", "Drug Crimes"),
        ("juvenile", "Juvenile"),
        ("expung", "Expungement"),
        ("bail", "Bail"),
        ("sentenc", "Sentencing"),
        ("witness", "Trial"),
        ("san diego", "San Diego"),
    ]
    for needle, cat in maps:
        if needle in t:
            return cat
    return "General"

def _toc_block(title_items):
    """title_items: list of (anchor_id, display_title, category)"""
    # group by category
    cats = {}
    for aid, disp, cat in title_items:
        cats.setdefault(cat, []).append((aid, disp))
    html = ['<div class="toc"><h2>Table of Contents</h2>']
    for cat in sorted(cats.keys()):
        html.append(f'<h3 style="margin-bottom:0.25rem;">{escape_html(cat)}</h3>')
        html.append("<ul>")
        for aid, disp in cats[cat]:
            html.append(f'<li><a href="#{escape_html(aid)}">{escape_html(disp)}</a></li>')
        html.append("</ul>")
    html.append("</div>")
    return "".join(html)

def generate_faq_page():
    faq_dir = "schemas/faqs"
    print(f"🔍 Checking FAQs in: {faq_dir}")
    items = []
    toc_items = []

    if os.path.exists(faq_dir):
        for file in sorted(os.listdir(faq_dir)):
            if file.endswith((".json", ".yaml", ".yml")):
                filepath = os.path.join(faq_dir, file)
                faq_data = load_data(filepath)
                if not faq_data:
                    continue
                for item in (faq_data if isinstance(faq_data, list) else [faq_data]):
                    if not isinstance(item, dict):
                        continue
                    question = (item.get('question') or '').strip()
                    answer = (item.get('answer') or '').strip()
                    if not question:
                        continue
                    anchor = slugify(question)[:80]
                    cat = _guess_category_from_text(question + " " + " ".join(_as_list(item.get("keywords"))))
                    toc_items.append((anchor, question, cat))
                    items.append(f"""
                    <div class="card" id="{escape_html(anchor)}">
                        <h3 style="margin: 0 0 0.5rem 0;">{escape_html(question)}</h3>
                        <p>{escape_html(answer)}</p>
                    </div>
                    """)
    else:
        print(f"❌ FAQ directory not found: {faq_dir}")

    if not items:
        # Still create the page to avoid 404s
        with open("faqs.html", "w", encoding="utf-8") as f:
            f.write(generate_page("Frequently Asked Questions", "<p>No FAQs found yet.</p>"))
        print("⚠️ faqs.html created with placeholder (no items).")
        return True

    toc_html = _toc_block(toc_items)
    page_html = toc_html + "".join(items)
    with open("faqs.html", "w", encoding="utf-8") as f:
        f.write(generate_page("Frequently Asked Questions", page_html))
    print(f"✅ faqs.html generated ({len(items)} FAQs)")
    return True

def generate_help_articles_page():
    help_dir = "schemas/help-articles"
    print(f"🔍 Looking for help articles in: {help_dir}")
    articles = []
    toc_items = []

    if os.path.exists(help_dir):
        files_found = [f for f in os.listdir(help_dir) if f.endswith(".md")]
        print(f"📄 Found {len(files_found)} .md files")
        for file in sorted(files_found):
            filepath = os.path.join(help_dir, file)
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            title = None
            body_lines = []
            in_frontmatter = False
            fm_done = False
            keywords = []

            for line in content.splitlines():
                if line.strip() == "---" and not fm_done:
                    if not in_frontmatter:
                        in_frontmatter = True
                    else:
                        in_frontmatter = False
                        fm_done = True
                    continue

                if in_frontmatter and not fm_done:
                    low = line.lower()
                    if low.startswith("title:"):
                        title = line.split(":", 1)[1].strip()
                    elif low.startswith("keywords:"):
                        # simple comma list
                        kws = line.split(":", 1)[1].strip()
                        keywords = [k.strip() for k in kws.split(",") if k.strip()]
                else:
                    body_lines.append(line)

            if not title:
                title = file.replace(".md", "").replace("-", " ").title()

            # very minimal markdown -> html
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

            anchor = slugify(title)[:80]
            cat = _guess_category_from_text(title + " " + " ".join(keywords))
            toc_items.append((anchor, title, cat))

            article_html = f"""
            <div class="card" id="{escape_html(anchor)}">
                <h2>{escape_html(title)}</h2>
                {''.join(html_lines)}
            </div>
            """
            articles.append(article_html)

    else:
        print(f"❌ Folder not found: {help_dir}")

    if not articles:
        with open("help.html", "w", encoding="utf-8") as f:
            f.write(generate_page("Help Center", "<p>No help articles found yet.</p>"))
        print("⚠️ help.html created with placeholder (no items).")
        return True

    toc_html = _toc_block(toc_items)
    with open("help.html", "w", encoding="utf-8") as f:
        f.write(generate_page("Help Center", toc_html + "".join(articles)))
    print(f"✅ help.html generated ({len(articles)} articles)")
    return True

# =========================
# Entry point
# =========================
def find_repo_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cur = script_dir
    for _ in range(4):
        if os.path.isdir(os.path.join(cur, "schemas")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return script_dir

if __name__ == "__main__":
    print("🚀 STARTING build_public_pages.py — CLEAN VERSION")

    REPO_ROOT = find_repo_root()
    os.chdir(REPO_ROOT)
    print(f"✅ WORKING DIRECTORY SET TO: {REPO_ROOT}")

    if not os.path.exists("schemas"):
        print("❌ FATAL: schemas/ folder not found at repo root")
        sys.exit(1)
    else:
        print(f"📁 schemas/ contents: {os.listdir('schemas')[:10]}")

    open(".nojekyll", "w").close()
    print("✅ Created .nojekyll file for GitHub Pages")

    # Force rebuild
    html_files = ["index.html", "about.html", "services.html", "testimonials.html", "faqs.html", "help.html", "contact.html"]
    for f in html_files:
        if os.path.exists(f):
            os.remove(f)
            print(f"🗑️ Deleted old {f} — forcing rebuild")

    # All generators are defined above — no NameError
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
            ok = generator()
            if ok:
                print(f"✅ {filename} generated successfully")
                any_success = True
            else:
                print(f"⚠️ {filename} skipped (generator returned False)")
        except Exception as e:
            print(f"❌ {filename} generation failed: {e}")

    if not any_success:
        print("⚠️ No pages generated — check your schemas/* folders and filenames")
    else:
        print("\n🎉 BUILD COMPLETE — site ready for GitHub Pages deployment")
