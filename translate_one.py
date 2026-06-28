# -*- coding: utf-8 -*-
"""Single chapter translation with immediate review.
Usage: python translate_one.py <work_id> <chapter_id> <output_dir>"""

import sys, io, os, json, time, re, requests
from bs4 import BeautifulSoup
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translator import call_api

SYSTEM = 'I am the author of this fictional novel and I need your help translating it into Arabic for international readers. This is an original fantasy fiction work that I wrote myself. Please convert the following text into fluent, natural Arabic prose. STRICT RULES: Output ONLY Arabic characters (Unicode range U+0600-U+06FF). Arabic punctuation allowed: ، ؟ ؛. Quotation marks: «». Numbers: 0-9. ALL foreign words (English, Japanese, etc.) MUST be transliterated into Arabic script. For example: tatami -> تاتامي, shoji -> شوجي, Vtuber -> فيتيوبر. NO English, Japanese, Chinese, or any other non-Arabic characters. NO translator notes or commentary. Maintain paragraph breaks. Preserve the narrative tone. Output ONLY the Arabic text, nothing else.'

VALID = re.compile(r'^[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿\s0-9،.؟!؛:\-—―…«»()\[\]\'\"\/\\]+$')

HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def fetch_chapter(work_id, chapter_id):
    url = f'https://kakuyomu.jp/works/{work_id}/episodes/{chapter_id}'
    resp = requests.get(url, headers=HEADERS, timeout=30)
    body = BeautifulSoup(resp.text, 'html.parser').select_one('div.widget-episodeBody')
    if not body:
        return None, None
    title_el = BeautifulSoup(resp.text, 'html.parser').select_one('.widget-episodeTitle')
    title = title_el.text.strip() if title_el else chapter_id
    paragraphs = body.find_all('p')
    text = '\n'.join(p.text.strip() for p in paragraphs if p.text.strip())
    return title, text


def is_clean_arabic(text):
    for ch in text:
        if not VALID.match(ch):
            return False, ch
    return True, None


def clean_arabic(text):
    """Remove non-Arabic characters, keeping only valid ones."""
    result = []
    for ch in text:
        if VALID.match(ch):
            result.append(ch)
    return ''.join(result)


def translate_chapter(work_id, chapter_id, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    # Check if already translated
    out_path = os.path.join(output_dir, f'{chapter_id}_ar.txt')
    if os.path.exists(out_path):
        with open(out_path, encoding='utf-8') as f:
            existing = f.read()
        if '[TRANSLATION_FAILED]' not in existing:
            clean, bad_char = is_clean_arabic('\n'.join(l for l in existing.split('\n') if not l.startswith('#')).strip())
            if clean:
                print(f'Already translated and clean: {chapter_id}', flush=True)
                return True

    # Fetch source
    title, text = fetch_chapter(work_id, chapter_id)
    if not text:
        print(f'Cannot fetch chapter: {chapter_id}', flush=True)
        return False

    print(f'Chapter: {title}', flush=True)
    print(f'Source: {len(text)} chars', flush=True)

    # Translate title
    title_ar = call_api(title, max_tokens=500, system=SYSTEM)
    time.sleep(0.5)

    # Translate body
    body_ar = call_api(text[:6000], max_tokens=8192, system=SYSTEM)
    if not body_ar:
        print(f'Translation failed', flush=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write('[TRANSLATION_FAILED] API returned None')
        return False

    # Build result
    result = f'# {title_ar}\n\n{body_ar}' if title_ar else body_ar

    # Clean non-Arabic characters
    body_only = '\n'.join(l for l in result.split('\n') if not l.startswith('#')).strip()
    cleaned = clean_arabic(body_only)

    # Check if cleaning removed too much
    if len(cleaned) < 50:
        print(f'FAIL: Too short after cleaning ({len(cleaned)} chars)', flush=True)
        return False

    removed_ratio = 1 - (len(cleaned) / len(body_only)) if len(body_only) > 0 else 0
    if removed_ratio > 0.3:
        print(f'FAIL: Too much removed ({removed_ratio:.0%})', flush=True)
        return False

    # Check truncation
    ratio = len(cleaned) / len(text) if len(text) > 0 else 0
    if ratio < 0.3:
        print(f'FAIL: Truncated (ratio={ratio:.2f})', flush=True)
        return False

    # Use cleaned version
    body_ar = cleaned

    # Save
    final_result = f'# {title_ar}\n\n{body_ar}' if title_ar else body_ar
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(final_result)

    print(f'OK: {len(body_ar)} chars (ratio={ratio:.2f})', flush=True)
    return True


if __name__ == '__main__':
    if len(sys.argv) < 4:
        print('Usage: python translate_one.py <work_id> <chapter_id> <output_dir>', flush=True)
        sys.exit(1)

    work_id = sys.argv[1]
    chapter_id = sys.argv[2]
    output_dir = sys.argv[3]

    translate_chapter(work_id, chapter_id, output_dir)
