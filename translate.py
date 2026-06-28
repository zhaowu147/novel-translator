# -*- coding: utf-8 -*-
"""Translation layer: one novel at a time, 5 workers, no validation."""

import sys, io, os, json, time
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from translator import call_api
from config import MIMO_API_KEY, MIMO_API_URL, MIMO_MODEL

MAX_WORKERS = 3
MAX_TOKENS = 8192

SYSTEM_PROMPT = """I am the author of this fictional novel and I need your help translating it into Arabic for international readers. This is an original fantasy fiction work that I wrote myself. Please convert the following text into fluent, natural Arabic prose.

Rules:
1. Write in Modern Standard Arabic (Fusha)
2. Use Arabic punctuation: ، ؟ ؛
3. Use «» for dialogue
4. Keep character names in their romanized form
5. Use Western numerals (1, 2, 3)
6. Maintain paragraph structure
7. Preserve the narrative tone and emotional depth
8. Output ONLY the Arabic text, nothing else"""


def get_novel_info(work_id):
    """Fetch novel metadata from kakuyomu."""
    import requests
    from bs4 import BeautifulSoup
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    resp = requests.get(f'https://kakuyomu.jp/works/{work_id}', headers=headers, timeout=30)
    data = json.loads(BeautifulSoup(resp.text, 'html.parser').find('script', id='__NEXT_DATA__').string)
    apollo = data['props']['pageProps']['__APOLLO_STATE__']
    work = apollo.get(f'Work:{work_id}', {})
    toc = {k: v for k, v in apollo.items() if k.startswith('TableOfContentsChapter:')}
    ordered = []
    for _, t in sorted(toc.items()):
        for ref in t.get('episodeUnions', []):
            ep = apollo.get(ref['__ref'])
            if ep:
                ordered.append({'id': ep['id'], 'title': ep['title']})
    return work, ordered


def translate_chapter(work_id, chapter):
    """Translate one chapter. Returns (chapter_id, result_text, error_msg)."""
    ch_id = chapter['id']
    ch_title = chapter['title']
    url = f'https://kakuyomu.jp/works/{work_id}/episodes/{ch_id}'

    import requests
    from bs4 import BeautifulSoup
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    resp = requests.get(url, headers=headers, timeout=30)
    body = BeautifulSoup(resp.text, 'html.parser').select_one('div.widget-episodeBody')
    if not body:
        return ch_id, None, 'No content found'

    paragraphs = body.find_all('p')
    text = '\n'.join(p.text.strip() for p in paragraphs if p.text.strip())
    if len(text) < 30:
        return ch_id, None, 'Too short'

    title_ar = call_api(ch_title, max_tokens=500, system=SYSTEM_PROMPT)
    time.sleep(0.3)
    body_ar = call_api(text[:6000], max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT)

    if not body_ar:
        return ch_id, None, 'API returned None'

    result = f'# {title_ar}\n\n{body_ar}' if title_ar else body_ar
    return ch_id, result, None


def translate_novel(work_id, output_dir, resume=True):
    """Translate one novel. Returns summary dict."""
    os.makedirs(output_dir, exist_ok=True)

    # Get novel info
    work, chapters = get_novel_info(work_id)
    title = work.get('title', f'work_{work_id}')
    print(f'Novel: {title}', flush=True)
    print(f'Total chapters: {len(chapters)}', flush=True)

    # Save info
    info_path = os.path.join(output_dir, 'info.json')
    if not os.path.exists(info_path):
        with open(info_path, 'w', encoding='utf-8') as f:
            json.dump({'work_id': work_id, 'title': title, 'chapters': chapters}, f, ensure_ascii=False, indent=2)

    # Filter already translated (skip failed ones too)
    if resume:
        existing = set()
        for f in os.listdir(output_dir):
            if f.endswith('_ar.txt'):
                fpath = os.path.join(output_dir, f)
                with open(fpath, encoding='utf-8') as fh:
                    content = fh.read()
                if '[TRANSLATION_FAILED]' not in content:
                    existing.add(f.replace('_ar.txt', ''))
        pending = [ch for ch in chapters if ch['id'] not in existing]
    else:
        pending = chapters

    if not pending:
        print('All chapters already translated', flush=True)
        return {'title': title, 'total': len(chapters), 'translated': 0, 'failed': 0, 'skipped': len(chapters)}

    print(f'Pending: {len(pending)} chapters', flush=True)
    print(f'Workers: {MAX_WORKERS}', flush=True)
    print(flush=True)

    translated = 0
    failed = 0
    failed_chapters = []

    def do_chapter(ch):
        return translate_chapter(work_id, ch)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(do_chapter, ch): ch for ch in pending}
        for future in as_completed(futures):
            ch_id, result, error = future.result()
            ch = futures[future]
            num = chapters.index(ch) + 1
            if result:
                out_path = os.path.join(output_dir, f'{ch_id}_ar.txt')
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(result)
                translated += 1
                print(f'  ({num}/{len(chapters)}) OK ({len(result)} chars)', flush=True)
            else:
                # Save error marker
                out_path = os.path.join(output_dir, f'{ch_id}_ar.txt')
                with open(out_path, 'w', encoding='utf-8') as f:
                    f.write(f'[TRANSLATION_FAILED] {error}')
                failed += 1
                failed_chapters.append({'id': ch_id, 'title': ch['title'], 'error': error})
                print(f'  ({num}/{len(chapters)}) FAILED - {error}', flush=True)

    summary = {
        'title': title,
        'total': len(chapters),
        'translated': translated,
        'failed': failed,
        'failed_chapters': failed_chapters,
    }

    print(flush=True)
    print(f'=== DONE ===', flush=True)
    print(f'Total: {len(chapters)}', flush=True)
    print(f'Translated: {translated}', flush=True)
    print(f'Failed: {failed}', flush=True)
    if failed_chapters:
        print(f'Failed chapters:', flush=True)
        for fc in failed_chapters:
            print(f'  - {fc["title"]} ({fc["error"]})', flush=True)

    return summary


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('work_id', help='Kakuyomu work ID')
    parser.add_argument('output_dir', help='Output directory')
    parser.add_argument('--no-resume', action='store_true', help='Re-translate all')
    args = parser.parse_args()

    translate_novel(args.work_id, args.output_dir, resume=not args.no_resume)
