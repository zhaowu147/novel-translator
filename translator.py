"""Translation module with concurrent agent architecture.
Each chapter is translated by an independent agent, reviewed by a review agent."""

import json
import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import MIMO_API_KEY, MIMO_API_URL, MIMO_MODEL, TRANSLATE_BATCH_SIZE, MAX_RETRIES
from prompts import JA_TO_EN_PROMPT, JA_TO_AR_PROMPT, DIRECT_JA_TO_AR_PROMPT, REVIEW_PROMPT


def call_api(prompt, max_tokens=8000, system=None):
    """Call MiMo API (Anthropic format) with retry logic."""
    for attempt in range(MAX_RETRIES):
        try:
            payload = {
                "model": MIMO_MODEL,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                payload["system"] = system

            resp = requests.post(
                MIMO_API_URL,
                headers={
                    "x-api-key": MIMO_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json=payload,
                timeout=300,
            )

            if resp.status_code == 429:
                wait = int(resp.headers.get("retry-after", 30))
                wait = max(wait, 30)
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            data = resp.json()

            # Anthropic format - find text content (skip thinking)
            if "content" in data:
                for item in data["content"]:
                    if item.get("type") == "text" and item.get("text"):
                        return item["text"]
            return None

        except Exception as e:
            print(f"    API error (attempt {attempt+1}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(1)
    return None


def review_text(source, translation, source_lang, target_lang):
    """Review translation quality using the review agent."""
    prompt = REVIEW_PROMPT.format(
        source_lang=source_lang,
        source=source[:2000],
        target_lang=target_lang,
        translation=translation[:2000],
    )

    result = call_api(prompt, max_tokens=500)
    if not result:
        return {"clean": True, "issues": [], "score": 5}

    try:
        # Try to parse JSON from response
        result = result.strip()
        if result.startswith("```"):
            result = result.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        return json.loads(result)
    except json.JSONDecodeError:
        # Fallback: check for basic issues
        has_garbled = bool(__import__('re').search(r'[�]', translation))
        has_symbols = bool(__import__('re').search(r'[★☆♠♣♥♦]', translation))
        return {
            "clean": not has_garbled and not has_symbols,
            "issues": ["Could not parse review response"],
            "score": 5,
        }


def translate_ja_to_en(text):
    """Agent 1: Japanese to English translation + review."""
    prompt = JA_TO_EN_PROMPT.format(text=text)
    en = call_api(prompt)
    if not en:
        return None, "Translation returned None"

    # Review
    review = review_text(text, en, "Japanese", "English")
    if not review.get("clean", True):
        issues = review.get("issues", [])
        print(f"    Review (JA→EN): score={review.get('score')}, issues={issues}")

    return en, None


def translate_en_to_ar(text):
    """Agent 2: English to Arabic translation + review."""
    prompt = JA_TO_AR_PROMPT.format(text=text)
    ar = call_api(prompt)
    if not ar:
        return None, "Translation returned None"

    # Review
    review = review_text(text, ar, "English", "Arabic")
    if not review.get("clean", True):
        issues = review.get("issues", [])
        print(f"    Review (EN→AR): score={review.get('score')}, issues={issues}")

    return ar, None


def translate_chapter(chapter_text, chapter_num):
    """Translation agent: translate one chapter JA→EN→AR."""
    print(f"    [Agent] Chapter {chapter_num}: translating JA→EN...")
    en, err1 = translate_ja_to_en(chapter_text)
    if not en:
        print(f"    [Agent] Chapter {chapter_num}: JA→EN FAILED: {err1}")
        return None

    print(f"    [Agent] Chapter {chapter_num}: translating EN→AR...")
    ar, err2 = translate_en_to_ar(en)
    if not ar:
        # Fallback: direct JA→AR
        print(f"    [Agent] Chapter {chapter_num}: EN→AR FAILED, trying direct JA→AR...")
        prompt = DIRECT_JA_TO_AR_PROMPT.format(text=chapter_text)
        ar = call_api(prompt)
        if ar:
            review = review_text(chapter_text, ar, "Japanese", "Arabic")
            print(f"    [Agent] Chapter {chapter_num}: direct JA→AR score={review.get('score')}")
        else:
            print(f"    [Agent] Chapter {chapter_num}: ALL FAILED")
            return None

    return ar


def translate_novel_chapters(chapters, max_workers=5):
    """Translate all chapters concurrently using multiple agents."""
    results = [None] * len(chapters)

    def translate_one(args):
        i, chapter_text = args
        return i, translate_chapter(chapter_text, i + 1)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(translate_one, (i, ch)): i
                   for i, ch in enumerate(chapters)}
        for future in as_completed(futures):
            i, result = future.result()
            results[i] = result
            status = "OK" if result else "FAILED"
            print(f"    Chapter {i+1}: {status}")

    return results


def translate_long_text(text):
    """Split long text into chunks and translate concurrently."""
    if len(text) <= TRANSLATE_BATCH_SIZE:
        return translate_chapter(text, 1)

    paragraphs = text.split("\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 1 > TRANSLATE_BATCH_SIZE:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para
        else:
            current_chunk = current_chunk + "\n" + para if current_chunk else para
    if current_chunk:
        chunks.append(current_chunk)

    print(f"    Split into {len(chunks)} chunks")
    translated = translate_novel_chapters(chunks, max_workers=min(3, len(chunks)))
    valid = [t for t in translated if t]
    return "\n\n".join(valid) if valid else None


def translate_novel(ncode, title, source="syosetu", max_chapters=10):
    """Translate a full novel."""
    print(f"\n--- Translating: {title} ({ncode}, source: {source}) ---")

    if source == "kakuyomu":
        from scraper_kakuyomu import get_novel_text
        chapters = get_novel_text(ncode, max_chapters)
    elif source == "alphapolis":
        from scraper_alphapolis import get_novel_text
        chapters = get_novel_text(ncode, max_chapters)
    else:
        from scraper_syosetu import get_novel_text
        chapters = get_novel_text(ncode)
        if chapters and len(chapters) > max_chapters:
            chapters = chapters[:max_chapters]

    if not chapters:
        print("  ERROR: Could not fetch text")
        return None

    # Translate title
    print("  Translating title...")
    title_prompt = JA_TO_AR_PROMPT.format(text=title)
    title_ar = call_api(title_prompt) or title
    time.sleep(0.5)

    # Translate all chapters concurrently
    print(f"  Translating {len(chapters)} chapters with multiple agents...")
    chapters_ar = translate_novel_chapters(chapters, max_workers=min(5, len(chapters)))

    valid_chapters = [c for c in chapters_ar if c]
    if not valid_chapters:
        return None

    return {
        "title_ar": title_ar,
        "total_chapters": len(chapters),
        "chapters_ar": valid_chapters,
    }


def test_api():
    """Test the MiMo API connection."""
    result = call_api("Translate to English: こんにちは、世界。", max_tokens=100)
    print(f"Test result: {result}")
    return result is not None


if __name__ == "__main__":
    test_api()
