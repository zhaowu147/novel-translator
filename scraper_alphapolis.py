"""AlphaPolis scraper using Jina Reader for text."""

import requests
import time
import re

JINA_READER = "https://r.jina.ai/"


def search_completed(min_bookmarks=100, limit=50):
    """Search for popular works on AlphaPolis."""
    url = "https://www.alphapolis.co.jp/novel"
    resp = requests.get(
        JINA_READER + url,
        headers={"Accept": "text/plain"},
        timeout=30,
    )

    if resp.status_code != 200:
        print("  AlphaPolis: Failed to fetch novel list")
        return []

    text = resp.text
    if "Markdown Content:" in text:
        text = text.split("Markdown Content:", 1)[1]

    # Extract novel URLs
    novels = []
    seen = set()
    for match in re.finditer(r'alphapolis\.co\.jp/novel/(\d+)', text):
        novel_id = match.group(1)
        if novel_id not in seen:
            seen.add(novel_id)
            novels.append({"id": novel_id})

    # Get details for each novel
    results = []
    for novel in novels[:limit]:
        detail = _get_novel_detail(novel["id"])
        if detail:
            results.append(detail)
        time.sleep(1)

    return results


def _get_novel_detail(novel_id):
    """Get novel details from AlphaPolis."""
    url = f"https://www.alphapolis.co.jp/novel/{novel_id}"
    resp = requests.get(
        JINA_READER + url,
        headers={"Accept": "text/plain"},
        timeout=30,
    )

    if resp.status_code != 200:
        return None

    text = resp.text
    if "Markdown Content:" in text:
        text = text.split("Markdown Content:", 1)[1].strip()

    # Extract title
    title_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    # Extract synopsis (usually first paragraph after title)
    lines = text.split('\n')
    synopsis = ""
    for line in lines[1:20]:
        line = line.strip()
        if line and not line.startswith('#') and len(line) > 20:
            synopsis = line
            break

    # Extract episode count
    ep_match = re.search(r'(\d+)\s*エピソード', text)
    episode_count = int(ep_match.group(1)) if ep_match else 0

    if not title:
        return None

    return {
        "id": novel_id,
        "title": title,
        "author": "",
        "bookmarks": 0,
        "synopsis": synopsis[:200],
        "url": f"https://www.alphapolis.co.jp/novel/{novel_id}",
        "episodeCount": episode_count,
    }


def get_chapter_count(novel_id):
    """Get number of chapters."""
    detail = _get_novel_detail(novel_id)
    return detail["episodeCount"] if detail else 0


def fetch_chapter_text(novel_id, chapter_num):
    """Fetch text of a single chapter via Jina Reader."""
    url = f"https://www.alphapolis.co.jp/novel/{novel_id}/episode/{chapter_num}"

    resp = requests.get(
        JINA_READER + url,
        headers={"Accept": "text/plain"},
        timeout=60,
    )

    if resp.status_code != 200:
        return None

    text = resp.text.strip()
    if "Markdown Content:" in text:
        text = text.split("Markdown Content:", 1)[1].strip()

    # Clean up AlphaPolis boilerplate
    text = re.sub(r'アルファポリス.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'このエピソードを評価.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'著者について.*$', '', text, flags=re.MULTILINE)

    return text if text and len(text) > 50 else None


def get_novel_text(novel_id, max_chapters=10):
    """Fetch full text of an AlphaPolis novel."""
    chapter_count = get_chapter_count(novel_id)
    print(f"  AlphaPolis novel has {chapter_count} chapters")

    if chapter_count == 0:
        return []

    texts = []
    for i in range(1, min(chapter_count, max_chapters) + 1):
        print(f"  Fetching chapter {i}/{min(chapter_count, max_chapters)}...")
        text = fetch_chapter_text(novel_id, i)
        if text:
            texts.append(text)
        else:
            print(f"  WARNING: Chapter {i} failed, stopping")
            break
        time.sleep(1.5)

    return texts


def filter_not_published(novels):
    """Filter out published/signed works."""
    publish_keywords = [
        "書籍化", "出版", "文庫", "コミカライズ", "漫画化",
        "アニメ化", "ドラマ化", "映画化", "商業", "担当編集",
        "KADOKAWA", "集英社", "講談社", "小学館",
        "MF文庫J", "電撃文庫", "ファミ通文庫",
        "bookwalker", "amazon.co.jp/dp", "発売",
    ]

    filtered = []
    for novel in novels:
        text = (novel.get("synopsis", "") + " " + novel.get("title", "")).lower()
        if not any(kw.lower() in text for kw in publish_keywords):
            filtered.append(novel)

    return filtered
