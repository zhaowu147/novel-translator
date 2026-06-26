"""Configuration for novel translation pipeline."""
import os

# MiMo API (Anthropic format)
MIMO_API_KEY = os.environ.get("MIMO_API_KEY", "")
MIMO_API_URL = os.environ.get("MIMO_API_URL", "https://token-plan-cn.xiaomimimo.com/anthropic/v1/messages")
MIMO_MODEL = os.environ.get("MIMO_MODEL", "mimo-v2.5-pro")

# Syosetu (成为小说家吧) API
SYOSETU_API = "https://api.syosetu.com/novelapi/api/"

# Blogger API
BLOGGER_BLOG_ID = "6994801832929106028"
BLOGGER_TOKEN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "blogger_token.json")

# Translation settings
TRANSLATE_BATCH_SIZE = 3000  # chars per batch
MAX_RETRIES = 3
TRANSLATIONS_DIR = os.environ.get("TRANSLATIONS_DIR", "G:/novel-translations")
MIN_NOVELS_BEFORE_PUBLISH = 5
