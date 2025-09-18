# utils/enhanced_fix.py
# =====================================================
# دفعة إصلاح مُحسَّنة:
# - تنظيف لغوي (clean_article)
# - Normalize Headings
# - تقليل عبارات الجزم → صياغة احتمالية
# - إدراج "متى لا ينطبق التفسير؟" إذا غاب
# - إعادة توليد الخاتمة لتكون مسؤولة مع تنويه مهني
# =====================================================

from __future__ import annotations
from typing import Dict, Any, List, Tuple
import re

from .text_cleanup import clean_article
from .heading_tools import normalize_headings
from .section_tools import list_sections, regenerate_section

# ————————————————
# 1) تقليل عبارات الجزم
# ————————————————
# ملاحظات:
# - التحويل محافظ: نستبدل العبارات القطعية بصيغ احتمالية شائعة.
# - نحاول عدم العبث بالعلامات داخل **Bold** أو الروابط قدر الإمكان.
CERTAINTY_MAP: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"(?<!\S)(?:بالتأكيد|حتماً|قطعاً|دون\s+شك|لا\s+ريب)(?!\S)"), "في الغالب"),
    (re.compile(r"(?<!\S)(?:سيحدث|سيقع|ستحصل)(?!\S)"), "قد يحدث"),
    (re.compile(r"(?<!\S)من\s+المؤكد\s+أن(?!\S)"), "من المحتمل أن"),
    (re.compile(r"(?<!\S)لا\s*بد\s*أن(?!\S)"), "يرجّح أن"),
]

def soften_certainty_language(text: str) -> Dict[str, Any]:
    """
    يحوّل تعابير الجزم إلى احتمالية بشكل محافظ.
    يرجع {text, replacements_count}
    """
    out = text
    cnt = 0
    # نتجنب تعديل العناوين (##/###) قدر الإمكان
    lines = out.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("##"):
            continue
        # تجنب لمس الروابط/الأكواد البسيطة
        if re.search(r"`.+?`|\[.+?\]\(.+?\)", ln):
            # استبدالات خفيفة فقط (الكلمة المفردة)
            for pat, repl in CERTAINTY_MAP[:1]:  # أول نمط عام فقط
                new_ln, n = pat.subn(repl, ln)
                if n:
                    cnt += n
                    ln = new_ln
        else:
            for pat, repl in CERTAINTY_MAP:
                new_ln, n = pat.subn(repl, ln)
                if n:
                    cnt += n
                    ln = new_ln
        lines[i] = ln
    return {"text": "".join(lines), "replacements_count": cnt}

# ——————————————————————
# 2) إدراج "متى لا ينطبق التفسير؟"
# ——————————————————————
NOT_APPLICABLE_TITLE = "متى لا ينطبق التفسير؟"

DEFAULT_NOT_APPLICABLE_BLOCK = """## متى لا ينطبق التفسير؟
- إذا جاء الحلم بعد توتر شديد أو نقاش محتدم قبل النوم.
- عند تغيّر نمط النوم بسبب أدوية/منبهات أو إرهاق واضح.
- إذا تكرّرت الرؤيا مع حدث حياتي راهن يهيمن على التفكير.
- عندما تكون الرموز شخصية جدًا أو مرتبطة بثقافة مختلفة.
"""

def ensure_not_applicable_section(article_md: str) -> Dict[str, Any]:
    """
    إن لم يوجد قسم H2 بعنوان "متى لا ينطبق التفسير؟" نضيف كتلة جاهزة قبل الخاتمة إن أمكن، وإلا في النهاية.
    """
    secs = list_sections(article_md)
    titles = [t for (t, lvl, s, e) in secs if lvl == 2]
    if any(re.fullmatch(r"متى\s+لا\s+ينطبق\s+التفسير\؟?", t) for t in titles):
        return {"text": article_md, "inserted": False}

    # موقع إدراج قبل "خاتمة" إن وُجدت
    insert_pos = len(article_md)
    for t, lvl, start, end in secs:
        if lvl == 2 and re.fullmatch(r"خاتمة", t):
            insert_pos = start
            break

    new_text = article_md[:insert_pos] + ("\n\n" if not article_md[:insert_pos].endswith("\n\n") else "") + DEFAULT_NOT_APPLICABLE_BLOCK.strip() + "\n\n" + article_md[insert_pos:]
    return {"text": new_text, "inserted": True}

# ————————————————
# 3) الدفعة المُحسّنة الكاملة
# ————————————————
def run_enhanced_fix(
    article_md: str,
    *,
    keyword: str = "",
    related_keywords: List[str] | None = None,
    tone: str = "هادئة",
    clean_opts: Dict[str, Any] | None = None,
    heading_opts: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    يُطبق الدفعة المُحسّنة ويعيد:
    {
      "article": النص بعد الإصلاح,
      "reports": {
        "clean": {...},
        "headings": {...},
        "soften": {"replacements_count": n},
        "not_applicable_inserted": bool,
        "outro_regenerated": bool
      }
    }
    """
    related_keywords = related_keywords or []
    clean_opts = clean_opts or {"remove_filler": True, "aggressive": False, "fix_punct": True, "normalize_ws": True}
    heading_opts = heading_opts or {"h1_to_h2": True, "h4plus_to_h3": True, "unify_space_after_hash": True,
                                    "trim_trailing_punct": True, "collapse_spaces": True,
                                    "remove_consecutive_duplicates": True, "autonumber": False}

    # 1) تنظيف
    cleaned = clean_article(article_md, **clean_opts)
    text = cleaned["cleaned"]
    rep_clean = cleaned["report"]

    # 2) Normalize Headings
    nh = normalize_headings(text, **heading_opts)
    text = nh["normalized"]
    rep_head = nh["changes"]

    # 3) تقليل الجزم
    soft = soften_certainty_language(text)
    text = soft["text"]
    rep_soft = {"replacements_count": soft["replacements_count"]}

    # 4) إدراج "متى لا ينطبق" إذا غاب
    ins = ensure_not_applicable_section(text)
    text = ins["text"]
    inserted = ins["inserted"]

    # 5) إعادة توليد الخاتمة (مسؤولة + تنويه)
    secs = list_sections(text)
    outro_title = None
    for t, lvl, s, e in secs:
        if re.fullmatch(r"خاتمة", t):
            outro_title = t
            break

    outro_done = False
    if outro_title:
        try:
            text = regenerate_section(
                article_md=text,
                section_title=outro_title,
                keyword=keyword,
                related_keywords=related_keywords,
                tone=tone,
                section_type="outro",
            )
            outro_done = True
        except Exception:
            outro_done = False

    return {
        "article": text,
        "reports": {
            "clean": rep_clean,
            "headings": rep_head,
            "soften": rep_soft,
            "not_applicable_inserted": inserted,
            "outro_regenerated": outro_done,
        }
    }
