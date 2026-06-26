"""Syosetu scraper using official API + Jina Reader for text."""

import requests
import time
from config import SYOSETU_API

JINA_READER = "https://r.jina.ai/"


def search_completed(novel_type="er", min_length=50000, limit=100, page=1, genre=None):
    """Search for completed novels on syosetu.

    Args:
        novel_type: "er" for short stories, "re" for serial novels
    """
    params = {
        "out": "json",
        "of": "t-n-w-s-g-k-e-gp-f-l",
        "type": novel_type,
        "order": "favnovelcnt",
        "lim": min(limit, 500),
        "st": (page - 1) * 500 + 1,
        "minlen": min_length,
        "notr15": 1,
        "notbl": 1,
        "notgl": 1,
        "stop": 1,
    }
    if genre:
        params["biggenre"] = genre

    resp = requests.get(SYOSETU_API, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if not data or len(data) <= 1:
        return []

    return {"total": data[0].get("allcount", 0), "novels": data[1:]}


def get_chapter_count(ncode):
    """Get number of chapters from the API."""
    resp = requests.get(
        SYOSETU_API,
        params={"out": "json", "ncode": ncode.lower()},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if len(data) > 1:
        novel = data[1]
        # novel_type: 1=serial, 2=short
        if novel.get("novel_type") == 2:
            return 1  # short story = 1 chapter
        return novel.get("general_all_no", 1)
    return 1


def fetch_chapter_text(ncode, chapter_num):
    """Fetch text of a single chapter via Jina Reader."""
    ncode_lower = ncode.lower()
    url = f"https://ncode.syosetu.com/{ncode_lower}/{chapter_num}/"

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

    # Check for 403 warning
    if "returned error 403" in text or "returned error" in text:
        return None

    return text if text and len(text) > 50 else None


def get_novel_text(ncode):
    """Fetch full text of a novel, returning list of chapter texts."""
    chapter_count = get_chapter_count(ncode)
    print(f"  Novel has {chapter_count} chapters")

    texts = []
    for i in range(1, chapter_count + 1):
        print(f"  Fetching chapter {i}/{chapter_count}...")
        text = fetch_chapter_text(ncode, i)
        if text:
            texts.append(text)
        else:
            print(f"  WARNING: Chapter {i} failed, stopping")
            break
        time.sleep(1.5)  # rate limit for Jina Reader

    return texts


def filter_not_published(novels):
    """Filter out novels that are likely published/signed."""
    publish_keywords = [
        "書籍化", "出版", "文庫", "コミカライズ", "漫画化",
        "アニメ化", "ドラマ化", "映画化", "商業", "担当編集",
        "KADOKAWA", "集英社", "講談社", "小学館", "スクウェア・エニックス",
        "MF文庫J", "電撃文庫", "ファミ通文庫", "MF文庫", "GA文庫",
        "HJ文庫", "富士見ファンタジア", "角川スニーカー",
        "bookwalker", "amazon.co.jp/dp", "発売", "巻発売",
        "第１巻", "第2巻", "第３巻", "第4巻", "第5巻",
        "アース・スターノベル", "オーバーラップ", "TOブックス",
        "ノベルアップ", "ヒーロー文庫", "一二三書房",
    ]

    filtered = []
    seen_ncodes = set()
    for novel in novels:
        ncode = novel.get("ncode", "")
        if ncode in seen_ncodes:
            continue
        seen_ncodes.add(ncode)

        text = (novel.get("story", "") + " " + novel.get("keyword", "") + " " + novel.get("title", "")).lower()
        if not any(kw.lower() in text for kw in publish_keywords):
            filtered.append(novel)

    return filtered


if __name__ == "__main__":
    # Test
    print("Testing chapter count...")
    count = get_chapter_count("n6251hf")
    print(f"n6251hf has {count} chapters")

    print("\nFetching chapter 1...")
    text = fetch_chapter_text("n6251hf", 1)
    if text:
        print(f"Got {len(text)} chars")
        print(text[:200] + "...")
    else:
        print("Failed")
