"""Translate chapters with concurrency."""

import sys
import io
import os
import glob
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from translator import call_api
from prompts import JA_TO_AR_PROMPT
from config import TRANSLATIONS_DIR

SCRAPED_DIR = "G:/kakuyomu-scraper/output"
MAX_WORKERS = 5


def translate_chapter(chapter_path):
    """Translate a single chapter."""
    with open(chapter_path, 'r', encoding='utf-8') as f:
        text = f.read()

    if not text.strip() or len(text) < 50:
        return None, "Too short"

    prompt = JA_TO_AR_PROMPT.format(text=text[:6000])
    result = call_api(prompt)
    if result:
        return result, None
    return None, "Translation failed"


def get_pending_chapters(novel_id):
    """Get list of untranslated chapters."""
    src_dir = os.path.join(SCRAPED_DIR, novel_id)
    dst_dir = os.path.join(TRANSLATIONS_DIR, novel_id)

    src_chs = sorted(glob.glob(os.path.join(src_dir, '*.txt')))

    translated_nums = set()
    if os.path.exists(dst_dir):
        for f in glob.glob(os.path.join(dst_dir, '*_ar.txt')):
            num = os.path.basename(f).split('_')[0]
            translated_nums.add(num)

    pending = []
    for ch in src_chs:
        num = os.path.basename(ch).split('_')[0]
        if num not in translated_nums:
            pending.append((num, ch))

    return pending


def main():
    batch_size = int(sys.argv[1]) if len(sys.argv) > 1 else 50

    novels = []
    for d in sorted(os.listdir(SCRAPED_DIR)):
        p = os.path.join(SCRAPED_DIR, d)
        if os.path.isdir(p):
            pending = get_pending_chapters(d)
            if pending:
                novels.append((d, pending))

    if not novels:
        print("All novels fully translated!")
        return

    novels.sort(key=lambda x: len(x[1]), reverse=True)
    novel_id, pending = novels[0]

    batch = pending[:batch_size]
    workers = min(MAX_WORKERS, len(batch))
    print(f"Translating: {novel_id[:50]}")
    print(f"Pending: {len(pending)}, batch: {batch_size}, workers: {workers}")

    out_dir = os.path.join(TRANSLATIONS_DIR, novel_id)
    os.makedirs(out_dir, exist_ok=True)

    translated = 0
    failed = 0

    def do_translate(item):
        num, ch_path = item
        result, error = translate_chapter(ch_path)
        return num, ch_path, result, error

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(do_translate, item): item for item in batch}
        for future in as_completed(futures):
            num, ch_path, result, error = future.result()
            try:
                if result:
                    filename = os.path.basename(ch_path).replace('.txt', '_ar.txt')
                    with open(os.path.join(out_dir, filename), 'w', encoding='utf-8') as f:
                        f.write(result)
                    translated += 1
                    print(f"  {num}: OK ({len(result)} chars)")
                else:
                    failed += 1
                    print(f"  {num}: FAILED - {error}")
            except Exception as e:
                failed += 1
                print(f"  {num}: ERROR - {e}")
                traceback.print_exc()

    print(f"\nDone: {translated} translated, {failed} failed")
    print(f"Remaining: {len(pending) - translated - failed} chapters")


if __name__ == "__main__":
    main()
