"""Blogger publisher - each chapter as one post, no translation references."""

import os
import html
import httplib2

try:
    import socks
    HAS_SOCKS = True
except ImportError:
    HAS_SOCKS = False
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from config import BLOGGER_BLOG_ID, BLOGGER_TOKEN_FILE

SCOPES = ["https://www.googleapis.com/auth/blogger"]

# Cache service object to avoid re-reading token file on every call
_service = None


def _get_http():
    proxy_host = os.environ.get("PROXY_HOST", "")
    if proxy_host and HAS_SOCKS:
        proxy_port = int(os.environ.get("PROXY_PORT", "7890"))
        return httplib2.Http(proxy_info=httplib2.ProxyInfo(socks.HTTP, proxy_host, proxy_port))
    return httplib2.Http()


def _get_service():
    global _service
    if _service is None:
        creds = Credentials.from_authorized_user_file(BLOGGER_TOKEN_FILE, SCOPES)
        http = _get_http()
        _service = build("blogger", "v3", http=AuthorizedHttp(creds, http=http))
    return _service


def publish_post(title, content, labels=None, draft=False):
    """Publish a post to Blogger."""
    service = _get_service()
    body = {
        "kind": "blogger#post",
        "blog": {"id": BLOGGER_BLOG_ID},
        "title": title,
        "content": content,
    }
    if labels:
        body["labels"] = labels
    posts = service.posts()
    if draft:
        return posts.insert(blogId=BLOGGER_BLOG_ID, body=body, isDraft=True).execute()
    return posts.insert(blogId=BLOGGER_BLOG_ID, body=body).execute()


def format_chapter(book_title_ar, chapter_num, chapter_text, total_chapters):
    """Format a single chapter as a blog post. Clean Arabic only."""
    paragraphs = chapter_text.split("\n")
    body_html = "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs if p.strip())
    chapter_label = f"الفصل {chapter_num} من {total_chapters}"

    return f"""
<div style="direction:rtl;text-align:right;font-family:Tahoma,'Noto Sans Arabic',sans-serif;">
  <div style="margin-bottom:16px;color:#888;font-size:13px;">
    {chapter_label}
  </div>
  {body_html}
  <div style="margin-top:24px;padding-top:16px;border-top:1px solid #eee;color:#888;font-size:13px;">
    {chapter_label}
  </div>
</div>
"""


def get_post_title(book_title_ar, chapter_num):
    """Generate post title."""
    return f"{book_title_ar} - الفصل {chapter_num}"
