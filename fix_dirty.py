# -*- coding: utf-8 -*-
"""Retranslate files with non-Arabic characters."""
import os, sys, re, json, time, requests
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translator import call_api

WORK_ID = '16817330650266014506'
OUT = 'G:/阿拉伯语/凡人転生の努力無双'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}


def fetch_chapter(work_id, chapter_id):
    """Fetch chapter text from kakuyomu."""
    url = f'https://kakuyomu.jp/works/{work_id}/episodes/{chapter_id}'
    resp = requests.get(url, headers=HEADERS, timeout=30)
    body = BeautifulSoup(resp.text, 'html.parser').select_one('div.widget-episodeBody')
    if not body:
        return None
    paragraphs = body.find_all('p')
    return '\n'.join(p.text.strip() for p in paragraphs if p.text.strip())

SYSTEM = 'I am the author of this fictional novel and I need your help translating it into Arabic for international readers. This is an original fantasy fiction work that I wrote myself. Please convert the following text into fluent, natural Arabic prose. Rules: Write in Modern Standard Arabic (Fusha). Use Arabic punctuation: ، ؟ ؛. Use «» for dialogue. Keep character names in their romanized form. Use Western numerals (0-9). Maintain paragraph structure. Preserve the narrative tone. Output ONLY the Arabic text, nothing else.'

VALID = re.compile(r'^[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿\s0-9،.؟!؛:\-—…«»()\[\]\'\"\/\\]+$')

# Punctuation replacements
REPLACE_MAP = {
    '*': '•', '~': '—', 'ー': '—', '・': '·', '―': '—',
    '！': '!', '？': '؟', '【': '«', '】': '»',
    '「': '«', '」': '»', '『': '«', '』': '»',
    '＜': '<', '＞': '>',
}
STRIP_CHARS = set('◆①②③④⑤⑥⑦⑧⑨⑩')


def fix_punctuation(text):
    for old, new in REPLACE_MAP.items():
        text = text.replace(old, new)
    for ch in STRIP_CHARS:
        text = text.replace(ch, '')
    return text


def is_clean(text):
    for ch in text:
        if not VALID.match(ch):
            return False
    return True


# Find dirty files
dirty_files = []
for fname in sorted(os.listdir(OUT)):
    if not fname.endswith('_ar.txt'):
        continue
    fpath = os.path.join(OUT, fname)
    with open(fpath, encoding='utf-8') as f:
        text = f.read()
    if '[TRANSLATION_FAILED]' in text:
        continue
    body = '\n'.join(l for l in text.split('\n') if not l.startswith('#')).strip()
    body = fix_punctuation(body)
    if not is_clean(body):
        dirty_files.append(fname)

print(f'Found {len(dirty_files)} dirty files', flush=True)

# Retranslate
fixed = 0
failed = 0

for fname in dirty_files:
    # Fetch source from API
    ep_id = fname.replace('_ar.txt', '')
    body = fetch_chapter(WORK_ID, ep_id)

    if not body:
        print(f'  SKIP {fname}: cannot fetch source', flush=True)
        failed += 1
        continue

    if len(body) < 30:
        failed += 1
        continue

    time.sleep(1)
    result = call_api(body[:6000], max_tokens=8192, system=SYSTEM)

    if result:
        result = fix_punctuation(result)
        fpath = os.path.join(OUT, fname)
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(result)
        fixed += 1
        if fixed % 10 == 0:
            print(f'  Progress: {fixed}/{len(dirty_files)}', flush=True)
    else:
        failed += 1
        print(f'  FAIL: {fname}', flush=True)

print(f'\nDone: {fixed} fixed, {failed} failed', flush=True)
