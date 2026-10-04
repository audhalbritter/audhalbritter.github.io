#!/usr/bin/env python3
"""Import WordPress posts into a Quarto blog.

Each post keeps its original date and gains an alias for the old URL
(for example /three-d-field-work/), so links keep working after the
domain moves. Images hosted on audhalbritter.com are downloaded next
to the post.
"""

import html
import json
import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POSTS = ROOT / "posts"
API = "https://audhalbritter.com/wp-json/wp/v2/"
UA = "Mozilla/5.0 (compatible; audhalbritter-site-import/1.0)"


def get_json(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode())


def fetch_all_posts() -> list[dict]:
    posts = []
    page = 1
    while True:
        batch = get_json(f"{API}posts?per_page=50&page={page}&_embed=1")
        if not batch:
            break
        posts.extend(batch)
        print(f"fetched page {page}: {len(batch)} posts")
        if len(batch) < 50:
            break
        page += 1
    return posts


def fetch_categories() -> dict[int, str]:
    cats = {}
    page = 1
    while True:
        batch = get_json(f"{API}categories?per_page=100&page={page}")
        if not batch:
            break
        for cat in batch:
            cats[cat["id"]] = html.unescape(cat["name"])
        if len(batch) < 100:
            break
        page += 1
    return cats


def strip_tags(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def yaml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def safe_filename(url: str) -> str:
    path = urllib.parse.urlparse(url).path
    name = urllib.parse.unquote(Path(path).name)
    name = re.sub(r"[^A-Za-z0-9._-]", "-", name)
    return name or "file"


def download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as exc:
        print("  image failed", url, exc)
        return False


def localize_media(content: str, media_dir: Path) -> str:
    content = content.replace("http://audhalbritter.com", "https://audhalbritter.com")
    content = re.sub(r"\s+srcset=\"[^\"]*\"", "", content)
    content = re.sub(r"\s+sizes=\"[^\"]*\"", "", content)
    urls = re.findall(
        r"https://audhalbritter\.com/wp-content/uploads/[^\"'\s>]+",
        content,
    )
    seen = {}
    for url in urls:
        clean = url.split("?")[0]
        ext = Path(urllib.parse.urlparse(clean).path).suffix.lower()
        if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf"}:
            continue
        filename = safe_filename(clean)
        dest = media_dir / filename
        n = 2
        while filename in seen and seen[filename] != clean:
            stem = Path(filename).stem
            filename = f"{stem}-{n}{ext}"
            dest = media_dir / filename
            n += 1
        if download(clean, dest):
            seen[filename] = clean
            content = content.replace(url, f"media/{filename}")
            content = content.replace(clean, f"media/{filename}")
    return content


def to_markdown(content: str) -> str:
    proc = subprocess.run(
        ["pandoc", "-f", "html", "-t", "gfm", "--wrap=none"],
        input=content.encode(),
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode()[:500])
    text = proc.stdout.decode()
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text + "\n"


def write_post(post: dict, categories: dict[int, str]) -> None:
    slug = post["slug"]
    folder = POSTS / slug
    media_dir = folder / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    title = strip_tags(post["title"]["rendered"])
    date = post["date"][:10]
    names = [categories[cid] for cid in post.get("categories", []) if cid in categories]
    names = [name for name in names if name.lower() != "uncategorized"]
    content = localize_media(post["content"]["rendered"], media_dir)
    body = to_markdown(content)
    lines = [
        "---",
        f"title: {yaml_quote(title)}",
        f"date: {date}",
        "aliases:",
        f"  - /{slug}/",
    ]
    if names:
        lines.append("categories:")
        for name in names:
            lines.append(f"  - {yaml_quote(name)}")
    description = strip_tags(post.get("excerpt", {}).get("rendered", ""))
    description = re.sub(r"\s+", " ", description).strip()
    if description.endswith("[…]"):
        description = description[:-3].strip()
    if description and len(description) > 40:
        lines.append(f"description: {yaml_quote(description[:280])}")
    lines.append("---")
    lines.append("")
    (folder / "index.qmd").write_text("\n".join(lines) + body, encoding="utf-8")
    # Drop the media folder if nothing was saved.
    if media_dir.exists() and not any(media_dir.iterdir()):
        media_dir.rmdir()


def main() -> None:
    categories = fetch_categories()
    posts = fetch_all_posts()
    print(f"{len(posts)} posts, {len(categories)} categories")
    failed = []
    for i, post in enumerate(posts, start=1):
        slug = post["slug"]
        try:
            write_post(post, categories)
        except Exception as exc:
            failed.append((slug, str(exc)))
            print("FAIL", slug, exc)
            continue
        if i % 10 == 0 or i == len(posts):
            print(f"{i}/{len(posts)} {slug}")
    print("done", len(posts) - len(failed), "imported;", len(failed), "failed")
    if failed:
        for slug, err in failed:
            print(" -", slug, err)


if __name__ == "__main__":
    main()
