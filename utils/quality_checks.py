# utils/quality_checks.py
# ---------------------------------------------------
# فحوصات محلية (هيوريستك) لجودة المقال:
# - كشف العبارات الجازمة (تستبدل بصيغ احتمالية على الأقل تنبيهًا).
# - كشف الجمل الحشوية/العامة قليلة القيمة.
# - التحقق من وجود التنويه (Disclaimer).
# - التحقق من وجود الأقسام الإلزامية المقترحة.
# - مؤشرات People Also Ask مدمجة داخل النص.
# - قياسات عامة: عدد الكلمات، عدد العناوين H2/H3، نسبة مفردات الاحتمال.
# - توصيات إصلاح عملية.
# ---------------------------------------------------

from __future__ import annotations
import re
from typing import Dict, List

# عبارات جزم/قطع (وسنقترح بدائل احتمالية)
CERTAINTY_PATTERNS = [
    r"\b(دائمًا|دوماً|حتماً|حتمًا|بالضرورة|لا\ شك|لا شكّ|مؤكد|مؤكّد|سيحدث|لا بد|أبدًا)\b",
]

# مفردات احتمالية (نريد وجود بعضها)
PROBABILITY_TOKENS = [
    r"\bقد\b", r"\bيُحتمل\b", r"\bمن المحتمل\b", r"\bربما\b",
    r"\bبحسب السياق\b", r"\bفي الغالب\b", r"\bأحيانًا\b"
]

# مؤشرات حشو/عموميات (قابلة للتخصيص)
FILLER_PATTERNS = [
    r"هذا الموضوع .* (مهم|يشغل|يهم) .*",
    r"(في الختام|خلاصة القول|وفي النهاية)[:,]?\s*$",     # خاتمة نمطية
    r"من المعروف أن .*", r"لا يخفى على أحد .*",
    r"يعتبر .* من المواضيع .*",
]

# أقسام/فقرات موصى بها
REQUIRED_SECTIONS = {
    "لماذا قد يظهر": r"(?i)لماذا\s+قد\s+يظهر",
    "ما الذي لا يعنيه": r"(?i)ما\s+الذي\s+لا\s+يعنيه",
    "تعليق محرر": r"(?i)تعليق\s+محرر",
    "سيناريو واقعي": r"(?i)(سيناريو|مثال)\s+(واقعي|مُفرّغ\s+الهوية)",
    "تنويه": r"(?i)(تنويه|Disclaimer|إخلاء\s+مسؤولية)",
}

# مؤشرات PAA ضمن المتن (أسئلة مدمجة)
PAA_HINTS = [
    r"؟\s*$",                                # أسئلة تنتهي بعلامة استفهام كسطر
    r"(?i)يسأل\s+الناس|يتساءل\s+الكثيرون",   # صياغات شائعة
    r"(?i)س(?:ؤال|ؤالات)\s+شائعة",
]

# عناوين ماركداون
H2 = re.compile(r"^\s*##\s+.+$", re.MULTILINE)
H3 = re.compile(r"^\s*###\s+.+$", re.MULTILINE)

WORD_RE = re.compile(r"\w+", re.UNICODE)


def _count_words(text: str) -> int:
    return len(WORD_RE.findall(text or ""))


def _count_matches(patterns: List[str], text: str) -> int:
    total = 0
    for p in patterns:
        total += len(re.findall(p, text or "", flags=re.MULTILINE))
    return total


def _has_any(patterns: List[str], text: str) -> bool:
    return _count_matches(patterns, text) > 0


def _has_disclaimer(text: str) -> bool:
    pat = REQUIRED_SECTIONS["تنويه"]
    return re.search(pat, text or "") is not None


def _missing_required_sections(text: str) -> List[str]:
    missing = []
    for label, pat in REQUIRED_SECTIONS.items():
        if re.search(pat, text or "") is None:
            missing.append(label)
    return missing


def _paa_signals(text: str) -> int:
    return _count_matches(PAA_HINTS, text)


def _probability_lexicon_hits(text: str) -> int:
    return _count_matches(PROBABILITY_TOKENS, text)


def run_quality_report(text: str, expected_length_preset: str | None = None) -> Dict:
    """
    يعيد تقريرًا موجزًا مع توصيات قابلة للتنفيذ.
    expected_length_preset: one of {"short","medium","long"} لتقدير نطاق الكلمات المناسب.
    """
    text = text or ""
    words = _count_words(text)
    h2_count = len(H2.findall(text))
    h3_count = len(H3.findall(text))

    certainty_hits = _count_matches(CERTAINTY_PATTERNS, text)
    filler_hits = _count_matches(FILLER_PATTERNS, text)
    prob_hits = _probability_lexicon_hits(text)
    disclaimer_ok = _has_disclaimer(text)
    missing_sections = _missing_required_sections(text)
    paa_count = _paa_signals(text)

    # نطاقات مستهدفة بحسب الطول
    target_ranges = {
        "short":  (600, 800, (3, 4)),
        "medium": (900, 1200, (4, 5)),
        "long":   (1300, 1600, (5, 6)),
    }
    target = target_ranges.get(expected_length_preset, None)

    # تقييم المخاطر بشكل بسيط
    risk_points = 0
    if certainty_hits > 0: risk_points += 2
    if filler_hits > 1: risk_points += 2
    if not disclaimer_ok: risk_points += 2
    if missing_sections: risk_points += min(3, len(missing_sections))
    if prob_hits == 0: risk_points += 1

    if risk_points >= 6:
        risk = "مرتفع"
    elif risk_points >= 3:
        risk = "متوسط"
    else:
        risk = "منخفض"

    # توصيات عملية
    actions: List[str] = []

    if target:
        lo, hi, (min_h2, max_h2) = target
        if words < lo:
            actions.append(f"زِد المحتوى إلى ~{lo} كلمة على الأقل (حاليًا {words}).")
        elif words > hi:
            actions.append(f"خفّف الإطالة/الحشو إلى ≤{hi} كلمة تقريبًا (حاليًا {words}).")

        if h2_count < min_h2:
            actions.append(f"أضِف عناوين H2 لبلوغ {min_h2}–{max_h2} أقسام (حاليًا {h2_count}).")
        elif h2_count > max_h2 + 1:
            actions.append(f"قلّل العناوين الرئيسية، الهدف {min_h2}–{max_h2} (حاليًا {h2_count}).")

    if certainty_hits > 0:
        actions.append("حوّل العبارات الجازمة إلى احتمالية (استعمل: قد/يُحتمل/بحسب السياق).")

    if filler_hits > 0:
        actions.append("احذف الجُمَل العامة والحشوية واستبدلها بمعلومة/سبب/مثال.")

    if prob_hits == 0:
        actions.append("أدرج مفردات احتمالية موزّعة (قد/يُحتمل/ربما/بحسب السياق).")

    if not disclaimer_ok:
        actions.append("أدرج فقرة تنبيه (Disclaimer) واضحة في الخاتمة.")

    if missing_sections:
        actions.append("أضف الأقسام الناقصة: " + "، ".join(missing_sections))

    if paa_count == 0:
        actions.append("ادمج 2–4 أسئلة شائعة (People also ask) داخل الأقسام بإجابات موجزة.")

    report: Dict = {
        "metrics": {
            "words": words,
            "h2_count": h2_count,
            "h3_count": h3_count,
            "certainty_hits": certainty_hits,
            "filler_hits": filler_hits,
            "probability_lexicon_hits": prob_hits,
            "paa_signals": paa_count,
            "disclaimer_present": disclaimer_ok,
            "missing_sections": missing_sections,
        },
        "risk_level": risk,
        "suggested_actions": actions,
        "notes": [
            "الفحص هيوريستك (تقريبي) للمساعدة التحريرية، وليس حكمًا نهائيًا.",
            "يمكنك تخصيص القوائم (الحشو/الجزم) لاحقًا لأسلوب موقعك.",
        ],
    }
    return report
