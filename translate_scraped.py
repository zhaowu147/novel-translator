"""Translate scraped Kakuyomu novels using concurrent agents."""

import sys
import io
import os
import json
import time
import glob
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from translator import call_api, review_text
from prompts import JA_TO_AR_PROMPT, DIRECT_JA_TO_AR_PROMPT, REVIEW_PROMPT
from config import TRANSLATIONS_DIR

SCRAPED_DIR = "G:/kakuyomu-scraper/output"
WORKERS = 5  # Concurrent translation agents


def get_novel_dirs():
    """List all novel directories with chapter counts."""
    novels = []
    for d in sorted(os.listdir(SCRAPED_DIR)):
        novel_path = os.path.join(SCRAPED_DIR, d)
        if not os.path.isdir(novel_path):
            continue
        chapters = sorted(glob.glob(os.path.join(novel_path, "*.txt")))
        if chapters:
            novels.append({"id": d, "path": novel_path, "chapters": chapters})
    return novels


def translate_chapter(chapter_path, chapter_num):
    """Translate a single chapter with review."""
    with open(chapter_path, 'r', encoding='utf-8') as f:
        text = f.read()

    if not text.strip():
        return None, "Empty chapter"

    print(f"    [Agent] Ch{chapter_num}: translating JA→AR...")

    # Try two-step: JA→EN→AR
    en_prompt = """Translate Japanese light novel text to English.
Rules: Output ONLY the translation. Maintain literary style. Preserve paragraph breaks.
Text: """ + text[:6000]  # Limit input size

    en = call_api(en_prompt)
    if en:
        # Review EN translation
        en_review = review_text(text[:2000], en[:2000], "Japanese", "English")
        if not en_review.get("clean", True):
            print(f"    [Agent] Ch{chapter_num}: EN review issues: {en_review.get('issues', [])}")

        # EN→AR
        ar_prompt = JA_TO_AR_PROMPT.format(text=en)
        ar = call_api(ar_prompt)
        if ar:
            # Review AR translation
            ar_review = review_text(en[:2000], ar[:2000], "English", "Arabic")
            if not ar_review.get("clean", True):
                print(f"    [Agent] Ch{chapter_num}: AR review issues: {ar_review.get('issues', [])}")
            return ar, None

    # Fallback: direct JA→AR
    print(f"    [Agent] Ch{chapter_num}: trying direct JA→AR...")
    ar_prompt = DIRECT_JA_TO_AR_PROMPT.format(text=text[:6000])
    ar = call_api(ar_prompt)
    if ar:
        review = review_text(text[:2000], ar[:2000], "Japanese", "Arabic")
        if not review.get("clean", True):
            print(f"    [Agent] Ch{chapter_num}: review issues: {review.get('issues', [])}")
        return ar, None

    return None, "All translation methods failed"


def translate_novel(novel_info):
    """Translate all chapters of a novel concurrently."""
    novel_id = novel_info["id"]
    chapters = novel_info["chapters"]
    out_dir = os.path.join(TRANSLATIONS_DIR, novel_id)
    os.makedirs(out_dir, exist_ok=True)

    print(f"\n=== Translating: {novel_id} ({len(chapters)} chapters) ===")

    results = [None] * len(chapters)

    def translate_one(args):
        i, chapter_path = args
        ch_num = i + 1
        result, error = translate_chapter(chapter_path, ch_num)
        return i, result, error

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(translate_one, (i, ch)): i
                   for i, ch in enumerate(chapters)}
        for future in as_completed(futures):
            i, result, error = future.result()
            if result:
                filename = os.path.basename(chapters[i]).replace('.txt', '_ar.txt')
                with open(os.path.join(out_dir, filename), 'w', encoding='utf-8') as f:
                    f.write(result)
                results[i] = True
                print(f"    Ch{i+1}: OK ({len(result)} chars)")
            else:
                print(f"    Ch{i+1}: FAILED - {error}")

    ok_count = sum(1 for r in results if r)
    print(f"  Done: {ok_count}/{len(chapters)} chapters translated")
    return ok_count


def main():
    novels = get_novel_dirs()
    print(f"Found {len(novels)} novels to translate")
    for n in novels:
        print(f"  {n['id'][:40]}: {len(n['chapters'])} chapters")

    print(f"\nStarting translation with {WORKERS} concurrent agents...\n")

    total_ok = 0
    total_chapters = 0
    for novel in novels:
        ok = translate_novel(novel)
        total_ok += ok
        total_chapters += len(novel["chapters"])

    print(f"\n=== DONE ===")
    print(f"Total: {total_ok}/{total_chapters} chapters translated")
    print(f"Output: {TRANSLATIONS_DIR}")


if __name__ == "__main__":
    main()
