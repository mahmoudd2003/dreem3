# utils/internal_links.py
# -----------------------------------------
# اقتراح روابط داخلية بناءً على تشابه بسيط في الكلمات المفتاحية والعناوين.
# لا يعتمد على أي خدمة خارجية. مناسب للـ MVP.

from __future__ import annotations
from typing import List, Dict, Any
import re
import json

# تقسيم مبسّط للكلمات العربية واللاتينية
TOKEN_RE = re.compile(r"[A-Za-z\u0600-\u06FF]+")

# أوزان لكل مصدر إشارة
WEIGHTS = {
    "keyword_hit": 3.0,        # تطابق مع الكلمة المفتاحية
    "related_hit": 2.0,        # تطابق مع كلمة مرتبطة
    "heading_hit": 1.5,        # تطابق مع عنوان H2/H3 داخل المقال
    "title_hit": 1.2,          # تطابق مع عنوان المقال الخارجي
    "tag_hit": 1.0,            # تطابق مع وسم/كلمة دلالية في المخزون
}

def _normalize(text: str) -> List[str]:
    text = (text or "").lower()
    # إزالة التشكيل وبعض العلامات الشائعة
    text = re.sub(r"[ًٌٍَُِّْـ]", "", text)
    return TOKEN_RE.findall(text)

def _extract_headings(article_markdown: str) -> List[str]:
    lines = (article_markdown or "").splitlines()
    heads = []
    for ln in lines:
        if ln.lstrip().startswith("##"):
            heads.append(ln.lstrip("# ").strip())
    return heads

def parse_inventory(raw_json: str) -> List[Dict[str, Any]]:
    """
    يتوقع JSON بالشكل:
    [
      {"title": "تفسير رؤية البحر", "url": "/sea-dream", "tags": ["البحر","الموج","السباحة"]},
      ...
    ]
    """
    try:
        items = json.loads(raw_json) if raw_json and raw_json.strip() else []
        if not isinstance(items, list):
            return []
        # تطبيع الحقول
        norm = []
        for it in items:
            title = str(it.get("title", "")).strip()
            url = str(it.get("url", "")).strip()
            tags = it.get("tags", [])
            if isinstance(tags, str):
                tags = [tags]
            norm.append({"title": title, "url": url, "tags": [str(t).strip() for t in tags if str(t).strip()]})
        return norm
    except Exception:
        return []

def suggest_internal_links(
    keyword: str,
    related_keywords: List[str],
    article_markdown: str,
    inventory: List[Dict[str, Any]],
    top_k: int = 6,
) -> List[Dict[str, Any]]:
    """
    يعيد قائمة مرتبة بالروابط المقترحة:
    [{"title":..., "url":..., "score":...}, ...]
    """
    kw_tokens = set(_normalize(keyword))
    rk_tokens = set()
    for r in related_keywords or []:
        rk_tokens.update(_normalize(r))

    headings = _extract_headings(article_markdown)
    head_tokens = set()
    for h in headings:
        head_tokens.update(_normalize(h))

    results = []
    for item in inventory:
        title = item.get("title", "")
        url = item.get("url", "")
        tags = item.get("tags", [])

        # تجميع توكنز للمقارنة
        title_tokens = set(_normalize(title))
        tag_tokens = set()
        for t in tags:
            tag_tokens.update(_normalize(str(t)))

        score = 0.0

        # تطابقات
        if kw_tokens & (title_tokens | tag_tokens):
            score += WEIGHTS["keyword_hit"]

        if rk_tokens & (title_tokens | tag_tokens):
            score += WEIGHTS["related_hit"]

        if head_tokens & (title_tokens | tag_tokens):
            score += WEIGHTS["heading_hit"]

        # إشارة خفيفة لكل تقاطع عنوان-عنوان
        if title_tokens & (kw_tokens | rk_tokens):
            score += WEIGHTS["title_hit"]

        # لكل تقاطع مع وسوم المخزون
        if tag_tokens & (kw_tokens | rk_tokens | head_tokens):
            score += WEIGHTS["tag_hit"]

        if score > 0 and url:
            results.append({"title": title, "url": url, "score": round(score, 2)})

    # ترتيب تنازلي
    results.sort(key=lambda x: (-x["score"], x["title"]))
    return results[:top_k]
