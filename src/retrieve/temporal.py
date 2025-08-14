from datetime import datetime, timezone
from dateutil.parser import isoparse
import math, re

_recent_re = re.compile(r"\b(recent|today|yesterday|this\s+(week|month)|last\s+(day|week|month|few\s+days))\b", re.I)

def parse_ts(val):
    if not val:
        return None
    try:
        return isoparse(val)
    except Exception:
        return None

def temporal_weight(meta: dict, query_text: str, default_days: int = 30) -> float:
    """
    returns a multiplicative weight >= 0 based on recency.
    if the query hints recency, aggressively downweight old docs.
    """
    ts = parse_ts(meta.get("published_at"))
    if not ts:
        return 1.0  # no penalty/boost if unknown
    now = datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    days = (now - ts).total_seconds() / 86400.0
    # if query implies recency, halve the time constant
    horizon = max(3.0, (default_days * (0.5 if _recent_re.search(query_text or "") else 1.0)))
    # smooth exponential decay, clamp min
    w = math.exp(-days / horizon)
    return max(0.2, min(1.5, w * (1.2 if days <= 2 else 1.0)))
