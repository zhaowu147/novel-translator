"""Translation quality reviewer - checks for garbled text and special symbols."""

import re

# Characters that should never appear in clean Arabic/English text
GARBLED_PATTERNS = [
    re.compile(r'[�]'),  # Unicode replacement character
    re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]'),  # Control characters (except \n \t)
    re.compile(r'�'),  # Common mojibake marker
    re.compile(r'â€[^\w]'),  # UTF-8 interpreted as Latin-1
    re.compile(r'Ã[^\w]'),  # UTF-8 double-encoded
    re.compile(r'Ø[^\w]'),  # UTF-8 double-encoded Arabic
]

# Special symbols that should not appear in clean translation
SPECIAL_SYMBOLS = re.compile(r'[★☆♠♣♥♦▲▼◆◇○●□■△▽♦✦✧⚡†‡§¶©®™€£¥¢‰∞≠≤≥±×÷√∑∏∫∂√∞≈≠≤≥αβγδεζηθικλμνξοπρστυφχψω]')


def has_garbled_text(text):
    """Check if text contains garbled/mojibake characters."""
    for pattern in GARBLED_PATTERNS:
        if pattern.search(text):
            return True
    return False


def has_special_symbols(text):
    """Check if text contains special symbols that shouldn't be in clean translation."""
    return bool(SPECIAL_SYMBOLS.search(text))


def clean_special_symbols(text):
    """Remove special symbols from text, keeping only clean characters."""
    return SPECIAL_SYMBOLS.sub('', text)


def review_translation(text, source_lang="unknown"):
    """Review a translation for quality issues.

    Returns:
        dict with keys:
            - clean: bool, True if text passes all checks
            - issues: list of str, descriptions of problems found
            - cleaned_text: str, text with special symbols removed
    """
    issues = []

    if not text or not text.strip():
        issues.append("Empty or whitespace-only text")
        return {"clean": False, "issues": issues, "cleaned_text": text}

    # Check for garbled text
    if has_garbled_text(text):
        issues.append("Contains garbled/mojibake characters")

    # Check for special symbols
    if has_special_symbols(text):
        issues.append("Contains special symbols")

    # Check for common translation artifacts
    if re.search(r'\[.*翻译.*\]|\[.*translation.*\]|\[.*訳.*\]', text, re.IGNORECASE):
        issues.append("Contains translation notes")

    if re.search(r'^\s*[\[\(（【].*翻译|translation|訳', text, re.IGNORECASE):
        issues.append("Starts with translation note")

    # Clean the text
    cleaned = clean_special_symbols(text)

    return {
        "clean": len(issues) == 0,
        "issues": issues,
        "cleaned_text": cleaned,
    }


def review_pair(source, translation, source_lang, target_lang):
    """Review a source-translation pair.

    Returns:
        dict with keys:
            - clean: bool
            - issues: list of str
            - cleaned_text: str
    """
    result = review_translation(translation, target_lang)

    # Additional check: if translation is almost identical to source,
    # it might be untranslated
    if source and translation:
        source_stripped = source.strip()
        trans_stripped = translation.strip()
        if source_stripped == trans_stripped and len(source_stripped) > 20:
            result["issues"].append("Translation identical to source (possibly untranslated)")
            result["clean"] = False

    return result
