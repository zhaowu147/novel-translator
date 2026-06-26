"""Kakuyomu scraper using Jina Reader for text."""

import requests
import time
import re

JINA_READER = "https://r.jina.ai/"


def search_completed(min_bookmarks=500, limit=50):
    """Search for popular completed works on Kakuyomu via Jina Reader."""
    # Fetch ranking page
    url = "https://kakuyomu.jp/rankings/completions/weekly"
    resp = requests.get(
        JINA_READER + url,
        headers={"Accept": "text/plain"},
        timeout=30,
    )

    if resp.status_code != 200:
        print("  Kakuyomu: Failed to fetch ranking")
        return []

    text = resp.text
    if "Markdown Content:" in text:
        text = text.split("Markdown Content:", 1)[1].strip()

    # Extract work IDs from links
    works = []
    seen = set()
    for match in re.finditer(r'kakuyomu\.jp/works/(\d+)', text):
        work_id = match.group(1)
        if work_id not in seen:
            seen.add(work_id)
            works.append(work_id)

    # Get details for each work
    results = []
    for work_id in works[:limit]:
        detail = _get_work_detail(work_id)
        if detail:
            results.append(detail)
        time.sleep(1)

    return results


def _get_work_detail(work_id):
    """Get work details from Kakuyomu via Jina Reader."""
    url = f"https://kakuyomu.jp/works/{work_id}"
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

    # Extract title (first heading)
    title_match = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else ""

    # Extract synopsis
    synopsis = ""
    lines = text.split('\n')
    for line in lines[1:30]:
        line = line.strip()
        if line and not line.startswith('#') and len(line) > 20 and 'エピソード' not in line:
            synopsis = line
            break

    # Extract episode count
    ep_match = re.search(r'(\d+)\s*エピソード', text)
    episode_count = int(ep_match.group(1)) if ep_match else 0

    if not title:
        return None

    # Clean title - remove site name suffix
    title = re.sub(r'\s*[-–—]\s*カクヨム\s*$', '', title)
    title = re.sub(r'\s*[-–—]\s*Kakuyomu\s*$', '', title, flags=re.IGNORECASE)

    return {
        "id": work_id,
        "title": title,
        "author": "",
        "bookmarks": 0,
        "synopsis": synopsis[:200],
        "url": f"https://kakuyomu.jp/works/{work_id}",
        "episodeCount": episode_count,
    }


def get_chapter_count(work_id):
    """Get number of chapters from Kakuyomu."""
    url = f"https://r.jina.ai/https://kakuyomu.jp/works/{work_id}"
    resp = requests.get(
        url,
        headers={"Accept": "text/plain", "X-Timeout": "60"},
        timeout=120,
    )
    if resp.status_code != 200:
        return 0

    text = resp.text
    # Look for "全XX話" pattern
    match = re.search(r'全(\d+)話', text)
    if match:
        return int(match.group(1))

    # Count episode links
    episodes = re.findall(r'/works/\d+/episodes/(\d+)', text)
    return len(set(episodes)) if episodes else 0


def fetch_chapter_text(work_id, chapter_num):
    """Fetch text of a single chapter via Jina Reader."""
    url = f"https://kakuyomu.jp/works/{work_id}/episodes/{chapter_num}"

    resp = requests.get(
        JINA_READER + url,
        headers={"Accept": "text/plain"},
        timeout=60,
    )

    if resp.status_code != 200:
        return None

    text = resp.text.strip()

    # Remove Jina Reader header
    if "Markdown Content:" in text:
        text = text.split("Markdown Content:", 1)[1].strip()

    # Remove common navigation/footer text
    text = re.sub(r'カクヨム.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r'エピソードを評価.*$', '', text, flags=re.MULTILINE)

    return text if text and len(text) > 50 else None


def get_novel_text(work_id, max_chapters=10):
    """Fetch full text of a Kakuyomu novel."""
    # Get total chapter count
    chapter_count = get_chapter_count(work_id)
    print(f"  Kakuyomu novel has {chapter_count} chapters")

    if chapter_count == 0:
        return []

    # Try to get all episode IDs by fetching page multiple times
    all_episode_ids = set()
    for attempt in range(3):
        url = f"https://r.jina.ai/https://kakuyomu.jp/works/{work_id}"
        resp = requests.get(url, headers={"Accept": "text/plain", "X-Timeout": "60"}, timeout=120)
        if resp.status_code == 200:
            text = resp.text
            if "Markdown Content:" in text:
                text = text.split("Markdown Content:", 1)[1]
            eps = re.findall(r'episodes/(\d+)', text)
            all_episode_ids.update(eps)
        time.sleep(2)

    if not all_episode_ids:
        print("  WARNING: Could not find any episode IDs")
        return []

    episode_ids = sorted(all_episode_ids)[:max_chapters]
    print(f"  Found {len(episode_ids)} episode IDs (of {chapter_count} total)")

    texts = []
    for i, ep_id in enumerate(episode_ids):
        print(f"  Fetching chapter {i+1}/{len(episode_ids)}...")
        url = f"https://r.jina.ai/https://kakuyomu.jp/works/{work_id}/episodes/{ep_id}"
        resp = requests.get(url, headers={"Accept": "text/plain"}, timeout=60)
        if resp.status_code == 200:
            text = resp.text.strip()
            if "Markdown Content:" in text:
                text = text.split("Markdown Content:", 1)[1].strip()
            text = re.sub(r'カクヨム.*$', '', text, flags=re.MULTILINE)
            text = re.sub(r'エピソードを評価.*$', '', text, flags=re.MULTILINE)
            if text and len(text) > 50:
                texts.append(text)
            else:
                print(f"  WARNING: Chapter {i+1} too short, skipping")
        else:
            print(f"  WARNING: Chapter {i+1} failed")
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
        "KADOKAWAグループ", "角川", "KADOKAWA FANLIKE",
    ]

    filtered = []
    for novel in novels:
        # Check all available text fields
        text = " ".join([
            novel.get("synopsis", ""),
            novel.get("title", ""),
            novel.get("author", ""),
        ]).lower()
        if not any(kw.lower() in text for kw in publish_keywords):
            filtered.append(novel)
        else:
            print(f"  Filtered out (published): {novel.get('title', '')[:50]}")

    return filtered
