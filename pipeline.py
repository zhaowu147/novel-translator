"""
Novel translation pipeline: Scrape → Translate → Publish chapters.

Usage:
    python pipeline.py discover              # Find novels
    python pipeline.py translate [limit]     # Translate novels
    python pipeline.py publish [limit]       # Publish chapters
    python pipeline.py run [limit] [max_ch]  # Full pipeline
    python pipeline.py test                  # Test API
"""

import sys
import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper_syosetu import (
    search_completed as syosetu_search,
    get_novel_text as syosetu_text,
    filter_not_published as syosetu_filter,
)
from scraper_kakuyomu import (
    search_completed as kakuyomu_search,
    get_novel_text as kakuyomu_text,
    filter_not_published as kakuyomu_filter,
)
from scraper_alphapolis import (
    search_completed as alphapolis_search,
    get_novel_text as alphapolis_text,
    filter_not_published as alphapolis_filter,
)
from translator import translate_long_text, call_api as translate, test_api
from publisher import publish_post, format_chapter, get_post_title
from config import TRANSLATIONS_DIR, MIN_NOVELS_BEFORE_PUBLISH

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

# Max concurrent translation agents
MAX_TRANSLATION_AGENTS = 3  # Conservative to avoid rate limits


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"discovered": [], "translated": [], "published": [], "failed": []}


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def discover(limit=50):
    """Step 1: Discover novels from multiple sources."""
    state = load_state()
    known_ids = {n.get("id") or n.get("ncode") for n in state["discovered"]}

    print("=== Discovering novels from multiple sources ===")

    all_novels = []

    # Source 1: Kakuyomu
    print("  Checking Kakuyomu...")
    try:
        kakuyomu_novels = kakuyomu_search(limit=limit)
        for n in kakuyomu_novels:
            n["source"] = "kakuyomu"
            n["ncode"] = n["id"]
        all_novels.extend(kakuyomu_novels)
        print(f"  Kakuyomu: {len(kakuyomu_novels)} novels")
    except Exception as e:
        print(f"  Kakuyomu failed: {e}")
    time.sleep(1)

    # Source 2: AlphaPolis
    print("  Checking AlphaPolis...")
    try:
        alphapolis_novels = alphapolis_search(limit=limit)
        for n in alphapolis_novels:
            n["source"] = "alphapolis"
            n["ncode"] = n["id"]
        all_novels.extend(alphapolis_novels)
        print(f"  AlphaPolis: {len(alphapolis_novels)} novels")
    except Exception as e:
        print(f"  AlphaPolis failed: {e}")

    # Filter published/signed works by source
    filtered = []
    for novel in all_novels:
        source = novel.get("source", "unknown")
        if source == "kakuyomu":
            if kakuyomu_filter([novel]):
                filtered.append(novel)
        elif source == "alphapolis":
            if alphapolis_filter([novel]):
                filtered.append(novel)
        else:
            if syosetu_filter([novel]):
                filtered.append(novel)

    new_novels = [n for n in filtered if n.get("ncode") not in known_ids]

    for novel in new_novels:
        state["discovered"].append({
            "ncode": novel.get("ncode"),
            "source": novel.get("source", "unknown"),
            "title": novel.get("title"),
            "author": novel.get("author", novel.get("writer", "")),
            "bookmarks": novel.get("bookmarks", novel.get("fav_novel_cnt", 0)),
            "synopsis": novel.get("synopsis", novel.get("story", "")),
        })

    save_state(state)
    print(f"\nFound {len(new_novels)} new novels (total: {len(state['discovered'])})")
    return new_novels


def translate_novel(ncode, title, source="syosetu", max_chapters=10):
    """Translate a novel's chapters."""
    print(f"\n--- Translating: {title} ({ncode}, source: {source}) ---")

    if source == "kakuyomu":
        chapters = kakuyomu_text(ncode, max_chapters)
    elif source == "alphapolis":
        chapters = alphapolis_text(ncode, max_chapters)
    else:
        chapters = syosetu_text(ncode)
        if chapters and len(chapters) > max_chapters:
            chapters = chapters[:max_chapters]
    if not chapters:
        print("  ERROR: Could not fetch text")
        return None

    if len(chapters) > max_chapters:
        print(f"  Limiting to first {max_chapters} of {len(chapters)} chapters")
        chapters = chapters[:max_chapters]

    # Translate book title to Arabic
    print("  Translating title...")
    from prompts import JA_TO_AR_PROMPT
    title_ar = translate(JA_TO_AR_PROMPT.format(text=title)) or title
    time.sleep(0.5)

    # Translate each chapter
    chapters_ar = []
    for i, chapter in enumerate(chapters):
        print(f"  Chapter {i+1}/{len(chapters)}...")
        translated = translate_long_text(chapter)
        if translated:
            chapters_ar.append(translated)
        else:
            print(f"  WARNING: Chapter {i+1} failed")
        time.sleep(0.5)

    if not chapters_ar:
        return None

    return {
        "title_ar": title_ar,
        "total_chapters": len(chapters),
        "chapters_ar": chapters_ar,
    }


def run_translate(limit=1, max_chapters=10, workers=8):
    """Step 2: Translate discovered novels with multiple concurrent agents."""
    state = load_state()
    translated_ncodes = {n["ncode"] for n in state["translated"]}
    failed_ncodes = {n["ncode"] for n in state["failed"]}

    pending = [
        n for n in state["discovered"]
        if n["ncode"] not in translated_ncodes and n["ncode"] not in failed_ncodes
    ]

    if not pending:
        print("Nothing to translate.")
        return

    to_translate = pending[:limit]
    print(f"=== Translating {len(to_translate)} novels ({workers} agents) ===")

    def translate_one(novel):
        ncode = novel["ncode"]
        try:
            result = translate_novel(
                ncode, novel["title"],
                source=novel.get("source", "syosetu"),
                max_chapters=max_chapters,
            )
            # Save to G drive organized by novel name
            if result:
                novel_dir = os.path.join(TRANSLATIONS_DIR, novel["title"])
                os.makedirs(novel_dir, exist_ok=True)
                with open(os.path.join(novel_dir, "full.json"), "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                for j, ch in enumerate(result.get("chapters_ar", []), 1):
                    with open(os.path.join(novel_dir, f"chapter_{j:03d}.txt"), "w", encoding="utf-8") as f:
                        f.write(ch)
            return ncode, novel, result, None
        except Exception as e:
            return ncode, novel, None, str(e)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(translate_one, n): n for n in to_translate}
        for future in as_completed(futures):
            ncode, novel, result, error = future.result()
            if result:
                out_file = os.path.join(OUTPUT_DIR, f"{ncode}.json")
                os.makedirs(OUTPUT_DIR, exist_ok=True)
                with open(out_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                state["translated"].append({
                    "ncode": ncode,
                    "title": novel["title"],
                    "title_ar": result["title_ar"],
                    "file": out_file,
                })
                save_state(state)
                print(f"  Saved: {novel['title'][:30]}")
            elif error:
                print(f"  ERROR ({novel['title'][:30]}): {error}")
                state["failed"].append({"ncode": ncode, "title": novel["title"], "error": error})
                save_state(state)
            else:
                state["failed"].append({"ncode": ncode, "title": novel["title"]})
                save_state(state)


def run_publish(limit=5):
    """Step 3: Publish chapters as individual posts."""
    state = load_state()
    translated_count = len(state["translated"])
    if translated_count < MIN_NOVELS_BEFORE_PUBLISH:
        print(f"Need at least {MIN_NOVELS_BEFORE_PUBLISH} novels translated before publishing (currently: {translated_count})")
        return

    published_ncodes = {n["ncode"] for n in state["published"]}

    pending = [n for n in state["translated"] if n["ncode"] not in published_ncodes]
    if not pending:
        print("Nothing to publish.")
        return

    for novel in pending[:limit]:
        ncode = novel["ncode"]
        print(f"\nPublishing: {novel['title_ar']}")

        with open(novel["file"], "r", encoding="utf-8") as f:
            data = json.load(f)

        title_ar = data["title_ar"]
        chapters_ar = data["chapters_ar"]
        total = data["total_chapters"]

        # Use novel title as label (for grouping chapters in Blogger)
        labels = [title_ar, "روايات"]

        # Publish each chapter as a separate post
        chapters_ok = 0
        chapters_fail = 0
        for i, chapter_text in enumerate(chapters_ar, 1):
            post_title = get_post_title(title_ar, i)
            content = format_chapter(title_ar, i, chapter_text, total)

            try:
                result = publish_post(
                    title=post_title,
                    content=content,
                    labels=labels,
                )
                print(f"  Ch{i}: {result.get('url', 'ok')}")
                chapters_ok += 1
            except Exception as e:
                print(f"  Ch{i} ERROR: {e}")
                chapters_fail += 1

            time.sleep(1)  # rate limit between posts

        state["published"].append({
            "ncode": ncode,
            "title": novel["title"],
            "chapters_published": chapters_ok,
            "chapters_failed": chapters_fail,
        })
        save_state(state)
        print(f"  Done: {chapters_ok}/{len(chapters_ar)} chapters published, {chapters_fail} failed")


def run_full(limit_novels=5, max_chapters=10, workers=3):
    """Full pipeline."""
    print("=== FULL PIPELINE ===\n")
    discover()
    print("\n" + "=" * 50)
    run_translate(limit=limit_novels, max_chapters=max_chapters, workers=workers)
    print("\n" + "=" * 50)
    run_publish(limit=limit_novels)
    print("\n=== DONE ===")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    cmd = sys.argv[1]
    if cmd == "discover":
        discover()
    elif cmd == "translate":
        run_translate(limit=int(sys.argv[2]) if len(sys.argv) > 2 else 1,
                      max_chapters=int(sys.argv[3]) if len(sys.argv) > 3 else 10,
                      workers=int(sys.argv[4]) if len(sys.argv) > 4 else MAX_TRANSLATION_AGENTS)
    elif cmd == "publish":
        run_publish(limit=int(sys.argv[2]) if len(sys.argv) > 2 else 5)  # Default 5
    elif cmd == "run":
        run_full(limit_novels=int(sys.argv[2]) if len(sys.argv) > 2 else 5,
                 max_chapters=int(sys.argv[3]) if len(sys.argv) > 3 else 10)
    elif cmd == "test":
        test_api()
    else:
        print(f"Unknown: {cmd}\n{__doc__}")


if __name__ == "__main__":
    main()
