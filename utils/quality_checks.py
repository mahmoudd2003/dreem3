# utils/quality_checks.py
# =====================================================
# Quality Gates موسّعة لمقالات تفسير الأحلام
# - تتحقق من وجود أقسام أساسية واختيارية
# - تعدّ العناصر (سيناريوهات/FAQ/مصادر) ضمن نطاقات مستهدفة
# - تكشف الحشو/الجزم/غياب التنويه/ادعاءات مهنية محظورة
# - ترجع تقريرًا مفصّلًا + توصيات إصلاح عملية
# =====================================================

from __future__ import annotations
from typing import Dict, Any, Tuple, List
import re

# -----------------------------
# إعدادات عامة (يمكن تعديلها)
# -----------------------------
SCENARIOS_RANGE = (3, 5)  # حد أدنى/أقصى للسيناريوهات
FAQ_RANGE = (3, 6)        # حد أدنى/أقصى لأسئلة الـ PAA
SOURCES_RANGE = (3, 6)    # حد أدنى/أقصى للمراجع

# أنماط للكشف عن الجزم/الحشو/الاحتمالية
CERTAINTY_PATTERNS = [
    r"\b(قطعًا|حتماً|بالتأكيد|ودون شك|لا ريب)\b",
    r"\b(سيحدث|سيقع|ستحصل)\b",
]
FILLER_PATTERNS = [
    r"^هذا الموضوع .* (مهم|يشغل|يهم) .*",
    r"^من المعروف أن .*",
    r"^لا يخفى على أحد .*",
    r"^يعتبر .* من المواضيع .*",
    r"(في الختام|خلاصة القول|وفي النهاية)[:,]?\s*$",
]
PROBABILITY_LEXICON = [
    r"\bقد\b", r"\bيُحتمل\b", r"\bربما\b", r"\bوفقًا للسياق\b", r"\bبحسب السياق\b"
]

# ادعاءات مهنية محظورة (بدون دليل صريح)
PRO_CLAIMS_FORBIDDEN = [
    r"\b(أنا|نحن)\s+(طبيب|أخصائي|معالج|مُعالج|استشاري)\b",
    r"\bخبرتنا\s+(الطبية|النفسية|السريرية)\b",
]

# عناوين الأقسام (تنويعات مقبولة)
SEC_TITLES = {
    "intro": [r"^##\s*افتتاحية"],
    "why": [r"^##\s*لماذا\s+قد\s+يظهر\s+الرمز"],
    "not_applicable": [r"^##\s*متى\s+لا\s+ينطبق\s+التفسير"],
    "scenarios": [r"^##\s*سيناريوهات\s+واقعية"],
    "faq": [r"^##\s*أسئلة\s+شائعة"],
    "comparison": [r"^##\s*مقارنة\s+دقيقة"],
    "methodology": [r"^##\s*منهجية\s+التفسير"],
    "sources": [r"^##\s*مصادر\s+صريحة"],
    "editor_note": [r"^##\s*تعليق\s+محرّر"],
    "outro": [r"^##\s*خاتمة"],
}

DISCLAIMER_PATTERNS = [
    r"المحتوى\s+تثقيفي",
    r"ليس\s+نصيحة\s+(?:نفسية|دينية)\s+قاطعة",
]

# -----------------------------
# أدوات مساعدة
# -----------------------------
def _find_sections(md: str) -> List[Tuple[str, int]]:
    """
    يرجع قائمة [(line, idx)] لعناوين المستوى H2 فقط.
    """
    lines = md.splitlines()
    out = []
    for i, ln in enumerate(lines):
        if ln.strip().startswith("## "):
            out.append((ln.strip(), i))
    return out

def _section_block(md: str, start_idx: int) -> str:
    """
    يعيد نص القسم من العنوان (الموجود في start_idx) حتى العنوان H2 التالي أو نهاية النص.
    """
    lines = md.splitlines()
    start = start_idx
    end = len(lines)
    for j in range(start_idx + 1, len(lines)):
        if lines[j].strip().startswith("## "):
            end = j
            break
    return "\n".join(lines[start:end]).strip()

def _match_any(patterns: List[str], text: str, flags=re.IGNORECASE | re.MULTILINE) -> bool:
    return any(re.search(p, text, flags) for p in patterns)

def _count_hits(patterns: List[str], text: str, flags=re.IGNORECASE | re.MULTILINE) -> int:
    return sum(len(re.findall(p, text, flags)) for p in patterns)

def _count_words(md: str) -> int:
    tokens = re.findall(r"[A-Za-z\u0600-\u06FF]+", md or "")
    return len(tokens)

def _count_headings(md: str) -> Tuple[int, int]:
    h2 = len(re.findall(r"(?m)^##\s+", md))
    h3 = len(re.findall(r"(?m)^###\s+", md))
    return h2, h3

def _locate_section_index(sections: List[Tuple[str, int]], title_patterns: List[str]) -> int:
    for idx, (line, i) in enumerate(sections):
        if _match_any(title_patterns, line):
            return idx
    return -1

def _strip_md_bullets(block: str) -> List[str]:
    items = []
    for ln in block.splitlines():
        s = ln.strip()
        if s.startswith("- ") or s.startswith("* ") or s.startswith("• "):
            items.append(s)
    return items

# -----------------------------
# محلّل الأقسام والمقاييس
# -----------------------------
def _analyze_structure(md: str) -> Dict[str, Any]:
    sections = _find_sections(md)
    result = {"present": {}, "blocks": {}}

    for key, pats in SEC_TITLES.items():
        idx = _locate_section_index(sections, pats)
        if idx >= 0:
            result["present"][key] = True
            line, start_line = sections[idx]
            block = _section_block(md, start_line)
            result["blocks"][key] = block
        else:
            result["present"][key] = False
            result["blocks"][key] = ""

    return result

def _count_scenarios(block: str) -> int:
    # عناصر تبدأ بشرطة. كل عنصر سيناريو سطرين كحد أقصى عادةً.
    return len(_strip_md_bullets(block))

def _count_faq(block: str) -> int:
    # نعتمد تنسيق **س:** و **ج:** في سطور متقاربة
    q_cnt = len(re.findall(r"(?m)^\*\*س:\*\*", block))
    a_cnt = len(re.findall(r"(?m)^\*\*ج:\*\*", block))
    return min(q_cnt, a_cnt)

def _count_sources(block: str) -> Tuple[int, int]:
    items = _strip_md_bullets(block)
    total = len(items)
    flagged = 0
    for it in items:
        # نوسم “بحاجة مراجعة بشرية” كمؤشر جيد، لكن لو ما فيه بيانات كتاب/باب قد نرفع تنبيه.
        if "بحاجة مراجعة بشرية" in it:
            flagged += 1
        # تحذير بسيط لو يبدو المرجع عامًا جدًا (غير دقيق)
        if re.search(r"(ابن\s+سيرين|النابلسي).*(باب|فصل)", it, re.IGNORECASE) is None:
            # لو لم يُذكر باب/فصل مع مرجع تراثي بشكل صريح
            if re.search(r"(ابن\s+سيرين|النابلسي)", it, re.IGNORECASE):
                flagged += 1
    return total, flagged

def _has_disclaimer(outro_block: str) -> bool:
    return _match_any(DISCLAIMER_PATTERNS, outro_block)

def _has_forbidden_claims(editor_block: str) -> bool:
    return _match_any(PRO_CLAIMS_FORBIDDEN, editor_block)

# -----------------------------
# الواجهة الرئيسية للتقرير
# -----------------------------
def run_quality_report(article_markdown: str, expected_length_preset: str = "medium") -> Dict[str, Any]:
    md = article_markdown or ""
    words = _count_words(md)
    h2, h3 = _count_headings(md)

    structure = _analyze_structure(md)

    # مقاييس عامة
    certainty_hits = _count_hits(CERTAINTY_PATTERNS, md)
    filler_hits = _count_hits(FILLER_PATTERNS, md)
    prob_hits = _count_hits(PROBABILITY_LEXICON, md)

    # أقسام واختبارات خاصة
    outro_block = structure["blocks"].get("outro", "")
    disclaimer_present = _has_disclaimer(outro_block)

    editor_block = structure["blocks"].get("editor_note", "")
    forbidden_claims = _has_forbidden_claims(editor_block)

    scenarios_block = structure["blocks"].get("scenarios", "")
    scenarios_count = _count_scenarios(scenarios_block) if scenarios_block else 0

    faq_block = structure["blocks"].get("faq", "")
    faq_count = _count_faq(faq_block) if faq_block else 0

    sources_block = structure["blocks"].get("sources", "")
    sources_count, sources_flagged = _count_sources(sources_block) if sources_block else (0, 0)

    # تحقق وجود الأقسام
    missing_sections = []
    required_keys = ["intro", "why", "outro"]
    for k in required_keys:
        if not structure["present"].get(k, False):
            missing_sections.append(k)

    # الأقسام الاختيارية المهمة (لو مفعّلة في النظام عادةً)
    optional_keys = ["not_applicable", "scenarios", "faq", "comparison", "methodology", "sources", "editor_note"]
    for k in optional_keys:
        if not structure["present"].get(k, False):
            missing_sections.append(k)

    # نطاقات مستهدفة
    range_warnings = []
    low, high = SCENARIOS_RANGE
    if structure["present"]["scenarios"] and not (low <= scenarios_count <= high):
        range_warnings.append(f"عدد السيناريوهات خارج النطاق ({scenarios_count}/{low}-{high})")

    fql, fqh = FAQ_RANGE
    if structure["present"]["faq"] and not (fql <= faq_count <= fqh):
        range_warnings.append(f"عدد الأسئلة الشائعة خارج النطاق ({faq_count}/{fql}-{fqh})")

    sl, sh = SOURCES_RANGE
    if structure["present"]["sources"] and not (sl <= sources_count <= sh):
        range_warnings.append(f"عدد المراجع خارج النطاق ({sources_count}/{sl}-{sh})")

    # مستوى المخاطر (تجميعي)
    risk_score = 0
    # غياب التنويه خطير
    if not disclaimer_present:
        risk_score += 3
    # ادعاءات مهنية غير مسموحة
    if forbidden_claims:
        risk_score += 2
    # مصادر قليلة/غير دقيقة
    if structure["present"]["sources"] and (sources_count < sl or sources_flagged > 0):
        risk_score += 1
    # جزم أو حشو مرتفع
    if certainty_hits >= 2:
        risk_score += 1
    if filler_hits >= 2:
        risk_score += 1
    # أقسام مفقودة كثيرة
    missing_core = [k for k in ["intro", "why", "outro"] if k in missing_sections]
    if len(missing_core) >= 1:
        risk_score += 2
    if len(missing_sections) >= 4:
        risk_score += 1

    if risk_score >= 5:
        risk_level = "مرتفع"
    elif risk_score >= 3:
        risk_level = "متوسط"
    else:
        risk_level = "منخفض"

    # توصيات عملية
    actions: List[str] = []

    if not disclaimer_present:
        actions.append("أضف إخلاء مسؤولية مهني واضح في الخاتمة (المحتوى تثقيفي… استشر مختصًا عند الضيق).")

    if forbidden_claims:
        actions.append("احذف أي ادعاء مهني محمي (طبيب/أخصائي/معالج) ما لم يكن موثّقًا وصحيحًا بالفعل.")

    if "not_applicable" in missing_sections:
        actions.append("أضف قسم: «متى لا ينطبق التفسير؟» مع 3–5 نقاط واقعية لتقليل التعميم.")

    if "methodology" in missing_sections:
        actions.append("أضف قسم: «منهجية التفسير» يوضح الجمع بين مصادر التراث + علم نفس الأحلام + سياق القارئ وحدود التفسير.")

    if "sources" in missing_sections:
        actions.append("أضف قسم: «مصادر صريحة» (3–6 مراجع). استخدم مكتبة مراجع مؤكدة أو وسم «بحاجة مراجعة بشرية».")
    else:
        if sources_count < sl:
            actions.append(f"زد عدد المراجع إلى ≥ {sl}.")
        if sources_count > sh:
            actions.append(f"خفّض عدد المراجع إلى ≤ {sh}.")
        if sources_flagged > 0:
            actions.append("راجع المراجع الموسومة «بحاجة مراجعة بشرية» وأكمل بيانات الكتاب/الباب/الفصل.")

    if "scenarios" in missing_sections:
        actions.append("أدرج 3–5 سيناريوهات واقعية مختصرة بمشاعر مختلفة وتعليق يشرح اختلاف التأويل.")
    elif not (SCENARIOS_RANGE[0] <= scenarios_count <= SCENARIOS_RANGE[1]):
        actions.append(f"عدّل عدد السيناريوهات إلى {SCENARIOS_RANGE[0]}–{SCENARIOS_RANGE[1]}.")

    if "faq" in missing_sections:
        actions.append("أدرج أسئلة شائعة قصيرة (4–6)، كل سؤال ≤ 12 كلمة، جواب ≤ 30 كلمة.")
    elif not (FAQ_RANGE[0] <= faq_count <= FAQ_RANGE[1]):
        actions.append(f"عدّل عدد أسئلة PAA إلى {FAQ_RANGE[0]}–{FAQ_RANGE[1]}.")

    if "comparison" in missing_sections:
        actions.append("أضف «مقارنة دقيقة» بين رموز متقاربة لتوضيح الفروق الدقيقة بحسب المشاعر والظروف.")

    if "editor_note" in missing_sections:
        actions.append("أضف «تعليق محرّر» بصياغة خبرة تحريرية عامة بلا ادعاءات مهنية محمية.")

    if certainty_hits >= 2:
        actions.append("قلّل عبارات الجزم (مثل: بالتأكيد/سيحدث) واستبدلها بصيغ احتمالية (قد/يُحتمل/بحسب السياق).")

    if filler_hits >= 2:
        actions.append("أزل الجُمَل الحشوية والختاميات الإنشائية، وركّز على محتوى عملي ومحدد.")

    # إشارات PAA (وجود قسم FAQ قصير)
    paa_signals = "قوي" if (structure["present"]["faq"] and FAQ_RANGE[0] <= faq_count <= FAQ_RANGE[1]) else "ضعيف"

    report: Dict[str, Any] = {
        "risk_level": risk_level,
        "metrics": {
            "words": words,
            "h2_count": h2,
            "h3_count": h3,
            "certainty_hits": certainty_hits,
            "filler_hits": filler_hits,
            "probability_lexicon_hits": prob_hits,
            "disclaimer_present": disclaimer_present,
            "missing_sections": [*missing_sections],  # قد تشمل الاختيارية أيضًا
            "paa_signals": paa_signals,
            # مقاييس إضافية:
            "scenarios_count": scenarios_count,
            "faq_count": faq_count,
            "sources_count": sources_count,
            "sources_flagged": sources_flagged,
            "methodology_present": structure["present"]["methodology"],
            "not_applicable_present": structure["present"]["not_applicable"],
            "comparison_present": structure["present"]["comparison"],
            "editor_note_present": structure["present"]["editor_note"],
            "forbidden_claims": forbidden_claims,
            "range_warnings": range_warnings,
        },
        "suggested_actions": actions,
    }
    return report
