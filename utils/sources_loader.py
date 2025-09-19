# utils/sources_loader.py
# ==========================================
# تحميل مصادر من data/sources.yaml + تنسيقها Markdown
# ==========================================

from __future__ import annotations
from typing import List, Dict, Any
import os
import random

try:
    import yaml  # PyYAML
except Exception:
    raise RuntimeError("مطلوب PyYAML. ثبّت: pip install pyyaml")

DEFAULT_PATHS = [
    os.path.join("data", "sources.yaml"),
    os.path.join(os.path.dirname(__file__), "..", "data", "sources.yaml"),
]

def load_all_sources(paths: List[str] | None = None) -> List[Dict[str, Any]]:
    paths = paths or DEFAULT_PATHS
    for p in paths:
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                items = data.get("sources", [])
                # تنظيف بسيط
                return [s for s in items if isinstance(s, dict)]
    return []

def pick_sources_for_article(
    *,
    all_sources: List[Dict[str, Any]],
    want_count: int = 5,
    mix_classical_modern: bool = True
) -> List[Dict[str, Any]]:
    if not all_sources:
        return []
    classical = [s for s in all_sources if s.get("type") == "classical"]
    modern    = [s for s in all_sources if s.get("type") == "modern"]

    selected: List[Dict[str, Any]] = []
    if mix_classical_modern:
        # حاول نضمن 2 تراث + 2 معاصر كحد أدنى إن أمكن
        random.shuffle(classical)
        random.shuffle(modern)
        selected.extend(classical[: min(2, len(classical))])
        selected.extend(modern[: min(2, len(modern))])

    # اكمل للعدد المطلوب من الباقي
    pool = [s for s in all_sources if s not in selected]
    random.shuffle(pool)
    while len(selected) < min(want_count, len(all_sources)) and pool:
        selected.append(pool.pop())

    # قص إلى want_count كحد أقصى
    return selected[:want_count]

def _badge(reliability: str) -> str:
    if str(reliability).lower() == "verified":
        return "✔️ موثوق"
    return "⚠️ بحاجة مراجعة"

def format_sources_markdown(sources: List[Dict[str, Any]]) -> str:
    if not sources:
        return "_لا توجد مصادر متاحة حاليًا._"
    lines = []
    for s in sources:
        title = s.get("title", "").strip()
        author = s.get("author", "").strip()
        year = s.get("year", "").strip()
        url = s.get("url", "").strip()
        badge = _badge(s.get("reliability", ""))

        # سطر أساس
        main = f"- {title}"
        parts = []
        if author: parts.append(author)
        if year:   parts.append(year)
        meta = ", ".join(parts)
        if meta:
            main += f" — {meta}"

        main += f" ({badge})"
        if url:
            main += f" [رابط]({url})"

        # تلميح باب/فصل
        ch = s.get("chapter_hint", "").strip()
        if ch:
            main += f" — *{ch}*"

        lines.append(main)
    lines.append("\n> **تنبيه:** الروابط للاطّلاع وليست بديلًا عن الرجوع للطبعات المحقَّقة.")
    return "\n".join(lines)
