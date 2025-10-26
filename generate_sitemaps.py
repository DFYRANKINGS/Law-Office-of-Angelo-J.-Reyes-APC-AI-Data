# generate_sitemaps.py
import os
import re
import glob
import json
import subprocess
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, ElementTree
from urllib.parse import quote

# ---------------------------
# Repo & URL helpers
# ---------------------------
def _run(cmd):
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8").strip()
    except Exception:
        return ""

def get_repo_slug():
    """
    Returns 'owner/repo' using (in order):
    - GITHUB_REPOSITORY env
    - git remote origin url
    """
    env_repo = os.getenv("GITHUB_REPOSITORY")
    if env_repo and "/" in env_repo:
        return env_repo

    origin = _run(["git", "config", "--get", "remote.origin.url"])
    # Supports: git@github.com:owner/repo.git  OR  https://github.com/owner/repo.git
    m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/\.]+)", origin or "")
    if m:
        return f"{m.group('owner')}/{m.group('repo')}"

    # Last resort: try reading .git/config directly
    try:
        with open(".git/config", "r", encoding="utf-8") as f:
            cfg = f.read()
        m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/\.]+)", cfg)
        if m:
            return f"{m.group('owner')}/{m.group('repo')}"
    except Exception:
        pass

    raise RuntimeError("Unable to determine owner/repo. Set GITHUB_REPOSITORY or add a git remote origin.")

def get_branch_name():
    """
    Returns a branch/ref name using (in order):
    - GITHUB_REF_NAME env (Actions)
    - current git branch
    - 'main' fallback
    """
    ref = os.getenv("GITHUB_REF_NAME")
    if ref:
        return ref
    ref = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    return ref if ref and ref != "HEAD" else "main"

def get_raw_base_url(repo_slug: str, ref: str) -> str:
    # raw URLs for files inside the repo (json/yaml/md/etc.)
    return f"https://raw.githubusercontent.com/{repo_slug}/{quote(ref)})"

def get_pages_base_url(repo_slug: str) -> str:
    """
    GitHub Pages for project sites: https://<owner>.github.io/<repo>
    (For org/user pages, you'd host in <owner>.github.io repo directly.)
    """
    owner, repo = repo_slug.split("/", 1)
    return f"https://{owner}.github.io/{repo}"

# ---------------------------
# File discovery
# ---------------------------
def find_generated_files(patterns=None, roots=("schemas",), include_exts=None):
    """
    Returns a list of repo-relative paths matching given patterns.
    """
    if patterns is None:
        patterns = [
            "schemas/**/*.json", "schemas/**/*.yaml", "schemas/**/*.yml",
            "schemas/**/*.md", "schemas/**/*.llm",
        ]
    paths = set()
    for pat in patterns:
        for p in glob.glob(pat, recursive=True):
            # ensure it exists and is file
            if os.path.isfile(p):
                # normalize to forward slashes
                paths.add(p.replace("\\", "/"))
    # optional extension filter
    if include_exts:
        paths = {p for p in paths if any(p.lower().endswith(ext) for ext in include_exts)}
    return sorted(paths)

def find_public_pages():
    """Public HTML pages we want in the standard sitemap."""
    candidates = [
        "index.html", "about.html", "services.html",
        "testimonials.html", "faqs.html", "help.html", "contact.html",
    ]
    return [c for c in candidates if os.path.exists(c)]

# ---------------------------
# Sitemap writers
# ---------------------------
def write_sitemap(urls, out_file):
    urlset = Element("urlset", attrib={
        "xmlns": "http://www.sitemaps.org/schemas/sitemap/0.9"
    })
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    for u in urls:
        url_el = SubElement(urlset, "url")
        loc = SubElement(url_el, "loc")
        loc.text = u
        lastmod = SubElement(url_el, "lastmod")
        lastmod.text = now
        # (Optional) You can add changefreq/priority if desired
        # SubElement(url_el, "changefreq").text = "weekly"
        # SubElement(url_el, "priority").text = "0.5"
    ElementTree(urlset).write(out_file, encoding="utf-8", xml_declaration=True)
    print(f"📝 Wrote {out_file} with {len(urls)} URLs")

# ---------------------------
# Main
# ---------------------------
def main():
    import argparse
    ap = argparse.ArgumentParser(description="Generate sitemaps for GitHub-hosted data & pages.")
    ap.add_argument("--repo", help="Override 'owner/repo' (default: auto-detect)")
    ap.add_argument("--ref", help="Override branch/ref (default: auto-detect)")
    ap.add_argument("--raw-base", help="Override raw base URL")
    ap.add_argument("--pages-base", help="Override GitHub Pages base URL")
    ap.add_argument("--skip-ai", action="store_true", help="Skip ai-sitemap.xml")
    ap.add_argument("--skip-pages", action="store_true", help="Skip sitemap.xml (HTML pages)")
    args = ap.parse_args()

    repo_slug = args.repo or get_repo_slug()
    ref = args.ref or get_branch_name()

    raw_base = args.raw_base or f"https://raw.githubusercontent.com/{repo_slug}/{ref}"
    pages_base = args.pages_base or get_pages_base_url(repo_slug)

    print(f"📦 repo: {repo_slug}")
    print(f"🌿 ref : {ref}")
    print(f"📡 raw : {raw_base}")
    print(f"🌐 pages: {pages_base}")

    # AI sitemap → raw machine-readable files
    if not args.skip_ai:
        data_files = find_generated_files()
        ai_urls = [f"{raw_base}/{p}" for p in data_files]
        write_sitemap(ai_urls, "ai-sitemap.xml")

    # Standard sitemap → public HTML pages
    if not args.skip_pages:
        html_pages = find_public_pages()
        page_urls = [f"{pages_base}/{p}" for p in html_pages]
        write_sitemap(page_urls, "sitemap.xml")

    print("✅ Done.")

if __name__ == "__main__":
    main()
