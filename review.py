# -*- coding: utf-8 -*-
"""Review layer: check translation quality after translation is done.
Does not modify files. Outputs review_report.json."""

import sys, io, os, json, re, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from translator import call_api

REVIEW_PROMPT = """You are a translation quality reviewer. Check the following Arabic text and answer these questions:

1. Is this text primarily in Arabic? (not English, Japanese, or Chinese)
2. Does it appear to be a complete translation (not truncated mid-sentence)?
3. Is there any obvious garbage text, error messages, or non-Arabic content mixed in?

Reply with ONLY a JSON object:
{"arabic": true/false, "complete": true/false, "clean": true/false, "notes": "brief explanation if any issue found"}

Do NOT include any other text, just the JSON."""

REJECT_PATTERNS = [
    'high risk', 'copyrighted material', 'rejected', 'cannot provide',
    'not specified', 'I\'m Claude', 'I need to address', 'TRANSLATION_FAILED',
]

# Valid characters: Arabic + digits + Arabic punctuation + whitespace
VALID = re.compile(r'^[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿\s0-9،.؟!؛:\-—…«»()\[\]\'\"\/\\]+$')


def check_file(trans_path, src_path):
    """Check one translated file. Returns dict with check results.
    STRICT: only 100% Arabic content passes."""
    with open(trans_path, encoding='utf-8') as f:
        trans = f.read()

    # Skip error markers
    if '[TRANSLATION_FAILED]' in trans:
        return {'pass': False, 'reason': 'translation_failed', 'detail': trans.strip()}

    body = '\n'.join(l for l in trans.split('\n') if not l.startswith('#')).strip()

    # Check: empty
    if len(body) < 50:
        return {'pass': False, 'reason': 'too_short', 'detail': f'{len(body)} chars'}

    # Check: rejection messages
    body_lower = body.lower()
    for pattern in REJECT_PATTERNS:
        if pattern.lower() in body_lower:
            return {'pass': False, 'reason': 'api_rejection', 'detail': body[:100]}

    # STRICT: every character must be valid Arabic/punctuation/digit
    invalid_chars = set()
    for ch in body:
        if not VALID.match(ch):
            invalid_chars.add(ch)
    if invalid_chars:
        sample = ''.join(list(invalid_chars)[:10])
        return {'pass': False, 'reason': 'non_arabic_chars', 'detail': f'{len(invalid_chars)} invalid: [{sample}]'}

    # Check: truncation (compare with source)
    if src_path and os.path.exists(src_path):
        with open(src_path, encoding='utf-8') as f:
            src = f.read()
        src_body = '\n'.join(l for l in src.split('\n') if not l.startswith('#')).strip()
        if len(src_body) > 100:
            ratio = len(body) / len(src_body)
            if ratio < 0.3:
                return {'pass': False, 'reason': 'truncated', 'detail': f'src={len(src_body)} trans={len(body)} ratio={ratio:.2f}'}

    # Check: truncation (compare with source)
    if src_path and os.path.exists(src_path):
        with open(src_path, encoding='utf-8') as f:
            src = f.read()
        src_body = '\n'.join(l for l in src.split('\n') if not l.startswith('#')).strip()
        if len(src_body) > 100:
            ratio = len(body) / len(src_body)
            if ratio < 0.3:
                return {'pass': False, 'reason': 'truncated', 'detail': f'src={len(src_body)} trans={len(body)} ratio={ratio:.2f}'}

    # Pass
    return {'pass': True, 'reason': None, 'detail': None}


def review_novel(src_dir, trans_dir):
    """Review all chapters of a novel. Returns review report."""
    meta_path = os.path.join(src_dir, 'metadata.json')
    if not os.path.exists(meta_path):
        # Try info.json
        meta_path = os.path.join(trans_dir, 'info.json')

    if os.path.exists(meta_path):
        with open(meta_path, encoding='utf-8') as f:
            meta = json.load(f)
    else:
        meta = {}

    title = meta.get('title', os.path.basename(src_dir))

    # Build source file map
    src_files = {}
    if os.path.isdir(src_dir):
        for f in os.listdir(src_dir):
            if f.endswith('.txt') and '_' in f:
                ep_id = f.replace('.txt', '').split('_', 1)[1]
                src_files[ep_id] = os.path.join(src_dir, f)

    # Review each translated file
    results = []
    passed = 0
    failed = 0

    for fname in sorted(os.listdir(trans_dir)):
        if not fname.endswith('_ar.txt'):
            continue

        ep_id = fname.replace('_ar.txt', '')
        trans_path = os.path.join(trans_dir, fname)
        src_path = src_files.get(ep_id)

        check = check_file(trans_path, src_path)
        check['chapter_id'] = ep_id
        check['file'] = fname

        if check['pass']:
            passed += 1
        else:
            failed += 1

        results.append(check)

    report = {
        'title': title,
        'total': len(results),
        'passed': passed,
        'failed': failed,
        'issues': [r for r in results if not r['pass']],
    }

    # Print summary
    print(f'=== {title[:40]} ===', flush=True)
    print(f'Total: {len(results)}, Passed: {passed}, Failed: {failed}', flush=True)
    if failed > 0:
        print(f'Issues:', flush=True)
        for issue in report['issues']:
            print(f'  [{issue["reason"]}] {issue["file"]}: {issue["detail"][:60]}', flush=True)

    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('src_dir', help='Source novel directory')
    parser.add_argument('trans_dir', help='Translated novel directory')
    parser.add_argument('--output', default='review_report.json', help='Output report path')
    args = parser.parse_args()

    report = review_novel(args.src_dir, args.trans_dir)

    out_path = os.path.join(args.trans_dir, args.output)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f'\nReport saved: {out_path}', flush=True)
