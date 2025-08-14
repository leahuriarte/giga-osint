from typing import Optional, Dict
import httpx, tldextract
from trafilatura import extract as t_extract
from preprocess.clean import clean_text
from bs4 import BeautifulSoup
from readability import Document

def _readability_text(html: str) -> str:
    try:
        doc = Document(html)
        summary_html = doc.summary()
        text = BeautifulSoup(summary_html, "lxml").get_text(" ", strip=True)
        return text or ""
    except Exception:
        return ""

def fetch_article(url: str, timeout: float = 15.0) -> Optional[Dict]:
    try:
        with httpx.Client(follow_redirects=True, timeout=timeout, headers={"user-agent": "giga-osint/0.1"}) as c:
            r = c.get(url)
            r.raise_for_status()
            html = r.text
    except Exception:
        return None

    # try trafilatura first
    text = t_extract(html, include_comments=False, include_tables=False, favor_recall=True) or ""
    if not text or len(text) < 200:
        # fallback path
        text = _readability_text(html)

    text = clean_text(text)
    if not text:
        return None

    host = tldextract.extract(url).registered_domain
    return {"url": url, "host": host or "", "text": text}
