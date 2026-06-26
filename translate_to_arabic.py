# -*- coding: utf-8 -*-
"""Translate scraped Japanese novels to Arabic.
Merged version: Arabic system prompt + retry/validation/resume."""

import sys, io, os, json, time, re
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from translator import call_api

SCRAPED_DIR = 'G:/kakuyomu-scraper/output'
OUTPUT_DIR = 'G:/阿拉伯语'
MAX_WORKERS = 5
MAX_TOKENS = 8192

# Arabic system prompt (from MTLS-Arabic-Translation)
SYSTEM_PROMPT = """أنت مترجم ياباني-عربي محترف. مهمتك هي ترجمة النص الياباني التالي إلى العربية.

قواعد الترجمة:
1. اتجاه النص: من اليمين إلى اليسار (RTL)
2. استخدم علامات الترقيم العربية (، ؛ ؟)
3. استخدم اقتباسات «» للحوار
4. الأرقام: استخدم الأرقام الغربية (1, 2, 3)
5. أسماء الشخصيات: نقل صوتي من اليابانية إلى العربية
6. حافظ على نبرة وأسلوب الشخصيات
7. استخدم الفصحى في السرد، والعامية في الحوار حسب الشخصية
8. تجنب التكرار والביטויات الاصطناعية
9. اجعل الترجمة طبيعية تبدو كأنها مكتوبة أصلاً بالعربية
10. حافظ على فقرات النص الأصلية
11. ترجم جميع المحتوى دون اختصار أو حذف
12. لا تضع أي نص ياباني في الإخراج"""

_ja_pattern = re.compile(r'[぀-ゟ゠-ヿ]{5,}')


def _is_valid_arabic(text):
    """Check if text is actually translated (not still Japanese)."""
    ja_chars = sum(len(m) for m in _ja_pattern.findall(text))
    return ja_chars < 100


def translate_text(text, max_tokens=2000):
    """Translate Japanese text to Arabic using system prompt."""
    if not text or len(text.strip()) < 10:
        return None
    return call_api(text[:6000], max_tokens=max_tokens, system=SYSTEM_PROMPT)


def translate_text_with_retry(text, max_tokens=2000):
    """Translate with retry if output is still Japanese."""
    if not text or len(text.strip()) < 10:
        return None
    for attempt in range(3):
        result = call_api(text[:6000], max_tokens=max_tokens, system=SYSTEM_PROMPT)
        if not result:
            continue
        if _is_valid_arabic(result):
            return result
        if attempt >= 1:
            return result  # Accept on 2nd attempt
        time.sleep(1)
    return None


def translate_novel_info(novel_folder, out_dir):
    """Translate novel info/synopsis."""
    info_path = os.path.join(novel_folder, 'info.json')
    with open(info_path, encoding='utf-8') as f:
        info = json.load(f)

    print('  Translating info...', flush=True)

    title_ar = translate_text(info['title'])
    time.sleep(0.3)
    catchphrase_ar = translate_text(info.get('catchphrase', ''))
    time.sleep(0.3)
    intro_ar = translate_text(info.get('introduction', ''), max_tokens=4000)
    time.sleep(0.3)

    info_ar = {
        'title_original': info['title'],
        'title_ar': title_ar or info['title'],
        'author': info['author'],
        'genre': info['genre'],
        'catchphrase_original': info.get('catchphrase', ''),
        'catchphrase_ar': catchphrase_ar or '',
        'introduction_original': info.get('introduction', ''),
        'introduction_ar': intro_ar or '',
        'tags': info.get('tags', []),
        'source_url': info.get('source_url', ''),
    }

    with open(os.path.join(out_dir, 'info_ar.json'), 'w', encoding='utf-8') as f:
        json.dump(info_ar, f, ensure_ascii=False, indent=2)

    print(f'  Title: {info_ar["title_ar"][:50]}', flush=True)
    return info_ar


def translate_chapter_file(ch_path):
    """Translate a single chapter file."""
    with open(ch_path, encoding='utf-8') as f:
        text = f.read()

    lines = text.split('\n')
    header = lines[0] if lines[0].startswith('#') else ''
    body = '\n'.join(l for l in lines if not l.startswith('#')).strip()

    if len(body) < 30:
        return None, 'Too short'

    # Translate chapter title
    title_ar = None
    if header.startswith('# '):
        title_ar = translate_text(header[2:].strip())
        time.sleep(0.3)

    # Translate body with validation retry
    body_ar = translate_text_with_retry(body, max_tokens=MAX_TOKENS)

    if not body_ar:
        return None, 'Translation failed'

    if title_ar:
        result = f'# {title_ar}\n\n{body_ar}'
    else:
        result = body_ar

    return result, None


def main():
    novels = sorted(os.listdir(SCRAPED_DIR))

    if not novels:
        print('No novels found', flush=True)
        return

    print(f'Found {len(novels)} novels', flush=True)
    print(f'Output: {OUTPUT_DIR}', flush=True)
    print(flush=True)

    for novel_name in novels:
        novel_path = os.path.join(SCRAPED_DIR, novel_name)
        if not os.path.isdir(novel_path):
            continue

        info_path = os.path.join(novel_path, 'info.json')
        if not os.path.exists(info_path):
            continue

        print(f'=== {novel_name[:50]} ===', flush=True)

        out_dir = os.path.join(OUTPUT_DIR, novel_name)
        os.makedirs(out_dir, exist_ok=True)

        # 1. Translate info (skip if exists)
        info_ar_path = os.path.join(out_dir, 'info_ar.json')
        if not os.path.exists(info_ar_path):
            translate_novel_info(novel_path, out_dir)
        else:
            print('  Info already translated', flush=True)

        # 2. Get chapters, skip already translated
        chapter_files = sorted([f for f in os.listdir(novel_path)
                               if f.endswith('.txt') and '_' in f])

        existing = set()
        for f in os.listdir(out_dir):
            if f.endswith('_ar.txt'):
                existing.add(f.replace('_ar.txt', '.txt'))

        pending = [f for f in chapter_files if f not in existing]

        if not pending:
            print(f'  All {len(chapter_files)} chapters already translated', flush=True)
            continue

        print(f'  Chapters: {len(chapter_files)} total, {len(pending)} pending', flush=True)
        print(f'  Workers: {MAX_WORKERS}', flush=True)

        translated = 0
        failed = 0

        def do_chapter(fname):
            ch_path = os.path.join(novel_path, fname)
            result, error = translate_chapter_file(ch_path)
            return fname, result, error

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {executor.submit(do_chapter, f): f for f in pending}
            for future in as_completed(futures):
                fname, result, error = future.result()
                num = fname.split('_')[0]
                try:
                    if result:
                        out_name = fname.replace('.txt', '_ar.txt')
                        with open(os.path.join(out_dir, out_name), 'w', encoding='utf-8') as f:
                            f.write(result)
                        translated += 1
                        print(f'    {num}: OK ({len(result)} chars)', flush=True)
                    else:
                        failed += 1
                        print(f'    {num}: FAILED - {error}', flush=True)
                except Exception as e:
                    failed += 1
                    print(f'    {num}: ERROR - {e}', flush=True)

        print(f'  Done: {translated} translated, {failed} failed', flush=True)
        print(flush=True)


if __name__ == '__main__':
    main()
