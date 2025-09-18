# utils/text_cleanup.py
# ---------------------------------------------------
# فلترة/تحسينات لغوية بسيطة للنص العربي (Markdown):
# - تطبيع المسافات (داخل/حول الترقيم، أسطر فارغة زائدة)
# - تصحيح مسافات الترقيم العربية (, → ، عند الحاجة، المسافات قبل/بعد ؟ ! ، . ؛ :)
# - تقليص التكرارات (,,,, ؛؛؛ !!! ...) والـ "..." إلى "…"
# - إزالة جُمَل/أسطر حشوية وفق أنماط quality_checks (اختياري)
# - تقرير بعدد التغييرات المنفذة

from __future__ import annotations
import re
from typing import Dict

# نحاول استخدام أنماط الحشو من quality_checks إن توفّرت لنحافظ على اتّساق المعايير
try:
    from utils.quality_checks import FILLER_PATTERNS as QC_FILLER
except Exception:
    QC_FILLER = [
        r"هذا الموضوع .* (مهم|يشغل|يهم) .*",
        r"(في الختام|خلاصة القول|وفي النهاية)[:,]?\s*$",
        r"من المعروف أن .*", r"لا يخفى على أحد .*",
        r"يعتبر .* من المواضيع .*",
    ]

_AR_LETTER = r"\u0600-\u06FF"
_LAT_LETTER = r"A-Za-z"
# حروف الترقيم المستهدفة
_PUNCT = r"[،,؛;:!؟\.\(\)\[\]\{\}«»\"'“”‘’\-—]"

def _normalize_ellipsis(text: str, report: Dict[str, int]) -> str:
    # "..." -> "…", وتخفيض التكرارات "……" -> "…"
    before = text
    text = re.sub(r"\.{3,}", "…", text)
    report["ellipsis_fixed"] += 0 if text == before else 1
    return text

def _collapse_repeated_punct(text: str, report: Dict[str, int]) -> str:
    # تقليص تكرارات علامات الترقيم (!!! → ! ،،، → ،)
    before = text
    # علامات: ! ؟ ، ؛ …
    text = re.sub(r"([!؟،؛…])\1{1,}", r"\1", text)
    # نقاط: "...." → "."
    text = re.sub(r"(\.)\1{1,}", r"\1", text)
    report["repeated_punct_collapsed"] += 0 if text == before else 1
    return text

def _fix_comma_shape(text: str, report: Dict[str, int]) -> str:
    # استبدال الفواصل الإنجليزية ',' بفواصل عربية '،' إذا جاءت بين حروف عربية
    before = text
    text = re.sub(fr"([{_AR_LETTER}])\s*,\s*([{_AR_LETTER}])", r"\1، \2", text)
    report["arabic_comma_applied"] += 0 if text == before else 1
    return text

def _fix_spacing_around_punct(text: str, report: Dict[str, int]) -> str:
    before = text
    # إزالة مسافات قبل علامات الترقيم: "كلمة !" → "كلمة!"
    text = re.sub(fr"\s+({_PUNCT})", r"\1", text)
    # إضافة مسافة واحدة بعد علامات الجمل إن لزم: "كلمة!كلمة" → "كلمة! كلمة"
    text = re.sub(r"([!؟؛:،\.])([^\s\n])", r"\1 \2", text)
    # إزالة مسافة بعد قوس فتح أو قبل قوس غلق: "( كلمة )" → "(كلمة)"
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    text = re.sub(r"«\s+", "«", text)
    text = re.sub(r"\s+»", "»", text)
    report["spacing_fixed"] += 0 if text == before else 1
    return text

def _normalize_whitespace(text: str, report: Dict[str, int]) -> str:
    before = text
    # تحويل مسافات متعددة إلى واحدة (في نفس السطر)
    text = re.sub(r"[ \t]{2,}", " ", text)
    # سطرين فارغين متتاليين إلى سطر فارغ واحد
    text = re.sub(r"\n{3,}", "\n\n", text)
    # مسافات في بداية/نهاية الأسطر
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = text.strip() + "\n"
    report["whitespace_normalized"] += 0 if text == before else 1
    return text

def _remove_filler_lines(text: str, report: Dict[str, int], aggressive: bool = False) -> str:
    # إزالة الأسطر أو الجمل التي تطابق أنماط الحشو
    if not QC_FILLER:
        return text
    removed = 0
    lines = text.splitlines()
    kept = []
    for ln in lines:
        hit = False
        for pat in QC_FILLER:
            if re.search(pat, ln.strip()):
                hit = True
                break
        # في الوضع غير العدواني: لا نحذف عناوين (##/###) حتى لو طابقت
        if hit and not (ln.lstrip().startswith("##") or ln.lstrip().startswith("###")):
            if aggressive:
                removed += 1
                continue
            # في الوضع العادي: لا نحذف بالكامل — نستبدل بنسخة مقصوصة إن كانت طويلة جدًا
            if len(ln) > 50:
                kept.append(re.sub(r"\s{2,}", " ", ln)[:50].rstrip("،,.؛:!؟") + "…")
                removed += 1
                continue
        kept.append(ln)
    report["filler_removed"] += removed
    return "\n".join(kept) + ("\n" if kept else "")

def clean_article(
    article_markdown: str,
    *,
    remove_filler: bool = True,
    aggressive: bool = False,
    fix_punct: bool = True,
    normalize_ws: bool = True,
) -> Dict[str, object]:
    """
    يعيد dict:
      - cleaned: النص بعد التنظيف
      - report: إحصاءات {'ellipsis_fixed','repeated_punct_collapsed','arabic_comma_applied','spacing_fixed','whitespace_normalized','filler_removed'}
    """
    report = {
        "ellipsis_fixed": 0,
        "repeated_punct_collapsed": 0,
        "arabic_comma_applied": 0,
        "spacing_fixed": 0,
        "whitespace_normalized": 0,
        "filler_removed": 0,
    }

    text = article_markdown or ""
    if fix_punct:
        text = _normalize_ellipsis(text, report)
        text = _collapse_repeated_punct(text, report)
        text = _fix_comma_shape(text, report)
        text = _fix_spacing_around_punct(text, report)

    if remove_filler:
        text = _remove_filler_lines(text, report, aggressive=aggressive)

    if normalize_ws:
        text = _normalize_whitespace(text, report)

    return {"cleaned": text, "report": report}
