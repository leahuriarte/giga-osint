from typing import List, Dict
import feedparser
from dateparser import parse as dparse

def pull_rss(feed_urls: List[str]) -> List[Dict]:
    items = []
    for url in feed_urls:
        try:
            d = feedparser.parse(url)
            for e in d.entries:
                items.append({
                    "url": getattr(e, "link", None),
                    "title": getattr(e, "title", "") or "",
                    "summary": getattr(e, "summary", "") or "",
                    "published_at": (dparse(getattr(e, "published", "") or getattr(e, "updated", ""), settings={"RETURN_AS_TIMEZONE_AWARE": False}) or None),
                    "source": d.feed.get("title", url),
                })
        except Exception:
            continue
    # dedupe by url
    seen, dedup = set(), []
    for it in items:
        u = it.get("url")
        if not u or u in seen:
            continue
        seen.add(u); dedup.append(it)
    return dedup
