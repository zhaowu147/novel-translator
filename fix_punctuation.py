# -*- coding: utf-8 -*-
"""Fix non-Arabic punctuation and characters in translated files."""
import os, sys, re, json
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'G:/阿拉伯语/凡人転生の努力無双'

# Punctuation replacements: non-Arabic -> Arabic equivalent
REPLACE_MAP = {
    '*': '•',      # bullet
    '~': '—',      # tilde -> em dash
    'ー': '—',     # katakana long vowel -> em dash
    '・': '·',     # katakana middle dot -> middle dot
    '—': '—',      # em dash (keep)
    '―': '—',      # horizontal bar -> em dash
    '！': '!',     # full-width exclamation
    '？': '؟',     # full-width question -> Arabic question mark
    '【': '«',     # Japanese bracket
    '】': '»',     # Japanese bracket
    '「': '«',     # Japanese quote
    '」': '»',     # Japanese quote
    '『': '«',     # Japanese quote
    '』': '»',     # Japanese quote
    '＜': '<',     # full-width less than
    '＞': '>',     # full-width greater than
}

# Characters to strip entirely (not replace)
STRIP_CHARS = set('◆①②③④⑤⑥⑦⑧⑨⑩')

# Valid Arabic + punctuation + digits + whitespace
VALID = re.compile(r'^[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿\s0-9،.؟!؛:\-—…«»()\[\]\'\"\/\\]+$')

fixed_count = 0
already_clean = 0

for fname in sorted(os.listdir(BASE)):
    if not fname.endswith('_ar.txt'):
        continue

    fpath = os.path.join(BASE, fname)
    with open(fpath, encoding='utf-8') as f:
        text = f.read()

    if '[TRANSLATION_FAILED]' in text:
        continue

    lines = text.split('\n')
    header = lines[0] if lines[0].startswith('#') else ''
    body = '\n'.join(l for l in lines if not l.startswith('#')).strip()

    # Apply replacements
    new_body = body
    for old, new in REPLACE_MAP.items():
        new_body = new_body.replace(old, new)

    # Strip unwanted chars
    for ch in STRIP_CHARS:
        new_body = new_body.replace(ch, '')

    if new_body != body:
        # Save fixed version
        new_text = f'{header}\n\n{new_body}' if header else new_body
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(new_text)

        # Check what was fixed
        invalid_before = set(ch for ch in body if not VALID.match(ch))
        invalid_after = set(ch for ch in new_body if not VALID.match(ch))
        fixed_count += 1
    else:
        already_clean += 1

print(f'Fixed: {fixed_count}')
print(f'Already clean: {already_clean}')
