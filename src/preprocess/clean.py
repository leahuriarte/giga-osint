import re

_ws = re.compile(r"\s+")
_ctrl = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]")

def clean_text(txt: str) -> str:
    if not txt:
        return ""
    t = txt.replace("\u00A0", " ")
    t = _ctrl.sub(" ", t)
    t = _ws.sub(" ", t)
    return t.strip()

def is_trash(txt: str) -> bool:
    return len(txt or "") < 80  # tune later
