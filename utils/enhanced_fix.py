# utils/enhanced_fix.py
# =====================================================
# دفعة إصلاح مُحسَّنة:
# - تنظيف لغوي (clean_article)
# - Normalize Headings
# - تقليل عبارات الجزم → صياغة احتمالية (قاموس موسّع)
# - إدراج "متى لا ينطبق التفسير؟" بعد "لماذا قد يظهر الرمز؟" (إن وُجد)،
#   وإلا قبل الخاتمة ("خاتمة" أو "الخلاصة")، وإلا في نهاية المقال.
# - إعادة توليد الخاتمة لتكون مسؤولة مع تنويه مهني
# =====================================================

from __future__ import annotations
from typing import Dict, Any, List, Tuple
import re

from .text_cleanup import clean_article
from .heading_tools import normalize_headings
from .section_tools import list_sections, regenerate_section

# ————————————————
# 1) تقليل عبارات الجزم (قاموس موسّع)
# ————————————————
# ملاحظات:
# - التحويل محافظ: نستبدل العبارات القطعية بصيغ احتمالية شائعة.
# - نحاول عدم العبث بالعلامات داخل **Bold** أو الروابط قدر الإمكان.
CERTAINTY_MAP: List[Tuple[re.Pattern, str]] = [
    # كلمات/تراكيب قطعية → بدائل احتمالية
    (re.compile(r"(?<!\S)(?:بالتأكيد|حتماً|قطعاً|دون\s+شك|لا\s+ريب)(?!\S)"), "في الغالب"),
    (re.compile(r"(?<!\S)(?:سيحدث|سيقع|ستحصل)(?!\S)"), "قد يحدث"),
    (re.compile(r"(?<!\S)من\s+المؤكد\s+أن(?!\S)"), "من المحتمل أن"),
    (re.compile(r"(?<!\S)لا\s*بد\s*أن(?!\S)"), "يرجّح أن"),
    (re.compile(r"(?<!\S)لا\s*محالة(?!\S)"), "على الأرجح"),
    (re.compile(r"(?<!\S)من\s+دون\s+شك(?!\S)"), "في الغالب"),
    (re.compile(r"(?<!\S)حتمًا(?!\S)"), "على الأرجح"),
    # صيَغ تنبؤية قوية
    (re.compile(r"(?<!\S)س(?:وف)?\s*ي(?:كون|حدث|قع)\b"), "قد يكون"),
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
#    (الأولوية: بعد "لماذا قد يظهر الرمز؟" → قبل الخاتمة → نهاية النص)
# ——————————————————————
NOT_APPLICABLE_TITLE = "متى لا ينطبق التفسير؟"

DEFAULT_NOT_APPLICABLE_BLOCK = """## متى لا ينطبق التفسير؟
- إذا جاء الحلم بعد توتر شديد أو نقاش محتدم قبل النوم.
- عند تغيّر نمط النوم بسبب أدوية/منبهات أو إرهاق واضح.
- إذا تكرّرت الرؤيا مع حدث حياتي راهن يهيمن على التفكير.
- عندما تكون الرموز شخصية جدًا أو مرتبطة بثقافة مختلفة.
"""

WHY_REGEX = re.compile(r"لماذا\s+قد\s+يظهر\s+الرمز\؟?", re.IGNORECASE)
OUTRO_REGEX = re.compile(r"(خاتمة|الخلاصة)$")

def ensure_not_applicable_section(article_md: str) -> Dict[str, Any]:
    """
    إن لم يوجد قسم H2 بعنوان "متى لا ينطبق التفسير؟" نضيف كتلة جاهزة:
    1) بعد "لماذا قد يظهر الرمز؟" إن وُجد
    2) وإلا قبل "خاتمة/الخلاصة" إن وُجدت
    3) وإلا في نهاية المقال
    """
    secs = list_sections(article_md)
    titles = [(t, lvl, s, e) for (t, lvl, s, e) in secs if lvl == 2]

    # موجود مسبقًا؟
    if any(re.fullmatch(r"متى\s+لا\s+ينطبق\s+التفسير\؟?", t) for (t, _, __, ___) in titles):
        return {"text": article_md, "inserted": False}

    insert_pos = None
    # 1) بعد "لماذا قد يظهر الرمز؟"
    for (t, lvl, start, end) in titles:
        if WHY_REGEX.fullmatch(t):
            insert_pos = end  # بعد نهاية قسم "لماذا"
            break

    # 2) وإلا قبل الخاتمة ("خاتمة" أو "الخلاصة")
    if insert_pos is None:
        for (t, lvl, start, end) in titles:
            if OUTRO_REGEX.fullmatch(t):
                insert_pos = start
                break

    # 3) وإلا نهاية المقال
    if insert_pos is None:
        insert_pos = len(article_md)

    prefix = "" if (insert_pos > 0 and article_md[insert_pos-1] == "\n") else "\n"
    new_text = (
        article_md[:insert_pos]
        + (prefix + "\n" if not article_md[:insert_pos].endswith("\n\n") else "")
        + DEFAULT_NOT_APPLICABLE_BLOCK.strip()
        + "\n\n"
        + article_md[insert_pos:]
    )
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
    heading_opts = heading_opts or {
        "h1_to_h2": True, "h4plus_to_h3": True, "unify_space_after_hash": True,
        "trim_trailing_punct": True, "collapse_spaces": True,
        "remove_consecutive_duplicates": True, "autonumber": False
    }

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

    # 4) إدراج "متى لا ينطبق" إذا غاب (بعد "لماذا" إن وُجد)
    ins = ensure_not_applicable_section(text)
    text = ins["text"]
    inserted = ins["inserted"]

    # 5) إعادة توليد الخاتمة (مسؤولة + تنويه) — يقبل "خاتمة" أو "الخلاصة"
    secs = list_sections(text)
    outro_title = None
    for t, lvl, s, e in secs:
        if OUTRO_REGEX.fullmatch(t):
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
