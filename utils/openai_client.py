# utils/openai_client.py
# =====================================================
# واجهة موحّدة للتعامل مع OpenAI
# - Two-pass generation (Outline -> Article) مع خيار قفل الـ Outline
# - قوالب Outline داخلية: modern | classic | none (عبر outline_mode)
# - التزام بالطول مع expand_to_target
# - verify_and_correct_structure لمطابقة العناوين
# - طبقة توافق max_output_tokens/max_tokens
# =====================================================

from __future__ import annotations
from typing import List, Dict, Any, Tuple
import os
import re

# مكتبة OpenAI
try:
    from openai import OpenAI
except Exception:
    raise RuntimeError("لم يتم العثور على مكتبة OpenAI. ثبّت: pip install openai --upgrade")

client = OpenAI()

# استيراد قوالب الـ Outline المضمّنة
from utils.outline_presets import get_outline

MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4.1")

LENGTH_TARGETS: Dict[str, Tuple[int, int]] = {
    "short":  (600,  800),
    "medium": (900,  1200),
    "long":   (1300, 1600),
}

_WORD_RE = re.compile(r"[A-Za-z\u0600-\u06FF]+")
_HX_RE   = re.compile(r"^(#{2,6})\s*(.+?)\s*$")

def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))

def _safe_join_keywords(keywords: List[str]) -> str:
    return ", ".join([k.strip() for k in keywords if k and k.strip()]) or "لا يوجد"

def _extract_h2_h3_titles(md: str) -> List[str]:
    titles = []
    for line in (md or "").splitlines():
        m = _HX_RE.match(line)
        if m:
            level = len(m.group(1))
            if level in (2, 3):
                titles.append(m.group(2).strip())
    return titles

def _normalize_outline_md(outline_md: str) -> str:
    fixed = []
    for ln in (outline_md or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith("#"):
            fixed.append(s)
        else:
            fixed.append("## " + s.lstrip("-• ").strip())
    return "\n".join(fixed).strip()

def chat_complete(
    *,
    messages: List[Dict[str, str]],
    temperature: float = 0.6,
    max_output_tokens: int = 3800,
    model: str = MODEL_NAME,
) -> str:
    """
    طبقة توافق: بعض إصدارات بايثون-OpenAI تستخدم max_output_tokens
    وأخرى تستخدم max_tokens. نجرب الأولى ثم نسقط للثانية.
    """
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
    except TypeError:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_output_tokens,
        )
    return (resp.choices[0].message.content or "").strip()

# ---------- بناء برومبت عام (بدون قفل Outline) ----------
def build_article_prompt(
    *,
    keyword: str,
    related_keywords: List[str],
    length_preset: str,
    tone: str,
    include_outline: bool,
    enable_editor_note: bool,
    enable_not_applicable: bool,
    enable_methodology: bool,
    enable_sources: bool,
    enable_scenarios: bool,
    enable_faq: bool,
    enable_comparison: bool,
    scenarios_count: int,
    faq_count: int,
) -> Dict[str, Any]:
    length_min, length_max = LENGTH_TARGETS.get(length_preset, (900, 1200))
    rk = _safe_join_keywords(related_keywords)

    sections = ["## افتتاحية", "## لماذا قد يظهر الرمز؟"]
    if enable_not_applicable: sections.append("## متى لا ينطبق التفسير؟")
    if enable_scenarios:      sections.append("## سيناريوهات واقعية")
    if enable_faq:            sections.append("## أسئلة شائعة")
    if enable_comparison:     sections.append("## مقارنة دقيقة")
    if enable_methodology:    sections.append("## منهجية التفسير")
    if enable_sources:        sections.append("## مصادر صريحة")
    if enable_editor_note:    sections.append("## تعليق محرّر")
    sections.append("## خاتمة")

    system = (
        "أنت محرر عربي محترف لمقالات تفسير أحلام بشرية.\n"
        "- لغة بسيطة مباشرة وجُمل قصيرة ومنع الحشو.\n"
        "- صياغة احتمالية ومنع الجزم/الوعود/التنبؤات.\n"
        "- تمييز الرأي المعاصر عن النقل التراثي.\n"
        "- تنويه مهني واضح في الخاتمة.\n"
    )
    hard = [
        f"- إجمالي الكلمات بين {length_min} و {length_max} كلمة.",
        "- ابدأ الافتتاحية بـ «خلاصة سريعة» (3–4 أسطر: المعنى الأشهر + متى يختلف + تنبيه احتمالية).",
        "- لا يقل كل قسم H2 أساسي عن 120–180 كلمة.",
        "- لا تُكرر نفس الفكرة بأكثر من صياغتين.",
    ]
    if enable_not_applicable:
        hard.append("- «متى لا ينطبق التفسير؟»: 3–5 نقاط واقعية.")
    if enable_scenarios:
        hard.append(f"- سيناريوهات واقعية: {scenarios_count} عناصر ≤ سطرين لكل عنصر مع تعليق.")
    if enable_faq:
        hard.append(f"- FAQ: {faq_count} أسئلة — سؤال ≤ 12 كلمة، جواب ≤ 30 كلمة (**س:**/**ج:**).")
    if enable_comparison:
        hard.append("- مقارنة دقيقة: 2–3 فروق جوهرية كنقاط قصيرة.")
    if enable_methodology:
        hard.append("- منهجية: كيف ندمج التراث + علم نفس الأحلام + خصوصية الرائي + حدود التفسير.")
    if enable_sources:
        hard.append("- مصادر صريحة: 3–6 (اسم الكتاب/الباب/الفصل؛ ضع «بحاجة مراجعة بشرية» عند الشك).")

    user = (
        f"الكلمة المفتاحية: {keyword}\nالكلمات المرتبطة: {rk}\nالنبرة: {tone}\n\n"
        "اكتب مقال Markdown بالعناوين التالية (H2) بالترتيب:\n" + "\n".join(sections) + "\n\n"
        "[قائمة تحقق — إلزم بها]\n" + "\n".join(hard) + "\n"
    )
    return {"system": system, "user": user, "sections": sections,
            "length_min": length_min, "length_max": length_max}

# ---------- برومبت من Outline مقفول ----------
def build_from_outline_prompt(
    *,
    outline_md: str,
    keyword: str,
    related_keywords: List[str],
    length_preset: str,
    tone: str,
    scenarios_count: int,
    faq_count: int,
) -> Dict[str, Any]:
    length_min, length_max = LENGTH_TARGETS.get(length_preset, (900, 1200))
    rk = _safe_join_keywords(related_keywords)
    normalized_outline = _normalize_outline_md(outline_md)

    system = (
        "أنت محرر عربي محترف. اكتب مقالًا يلتزم حرفيًا بالعناوين (H2/H3) أدناه بلا أي تغيير بالصياغة أو الترتيب.\n"
        "- امنع إضافة/حذف/إعادة تسمية عناوين.\n"
        "- املأ كل عنوان بمحتوى متوازن وبشري وصياغة احتمالية."
    )
    user = (
        f"الكلمة المفتاحية: {keyword}\nالكلمات المرتبطة: {rk}\nالنبرة: {tone}\n\n"
        "Outline (التزم به حرفيًا):\n-----\n" + normalized_outline + "\n-----\n\n"
        "[قائمة تحقق]\n"
        f"- إجمالي الكلمات بين {length_min} و {length_max}.\n"
        "- ابدأ الافتتاحية بخلاصة سريعة (3–4 أسطر) إن وُجد عنوانها.\n"
        "- لا يقل كل H2 عن 120–180 كلمة.\n"
        f"- سيناريوهات (إن وجدت): ≤ {scenarios_count} عناصر قصيرة مع تعليق.\n"
        f"- FAQ (إن وجد): ≤ {faq_count} أسئلة بصيغة س/ج قصيرة.\n"
        "- تنويه مهني في الخاتمة.\n"
    )
    return {"system": system, "user": user, "normalized_outline": normalized_outline,
            "length_min": length_min, "length_max": length_max}

# ---------- توسيع المقال ----------
def expand_to_target(article_md: str, *, keyword: str,
                     related_keywords: List[str],
                     length_preset: str,
                     model: str = MODEL_NAME) -> str:
    length_min, length_max = LENGTH_TARGETS.get(length_preset, (900, 1200))
    if _word_count(article_md) >= length_min:
        return article_md
    deficit = max(length_min - _word_count(article_md), 250)

    system = ("أنت محرر يعمّق المقال دون تغيير هيكله أو عناوينه."
              " وسّع المحتوى بأمثلة/سيناريوهات/FAQ قصيرة وصياغة احتمالية بلا حشو.")
    user = (
        f"الكلمة المفتاحية: {keyword}\nالكلمات المرتبطة: {_safe_join_keywords(related_keywords)}\n"
        f"المقال الحالي:\n-----\n{article_md}\n-----\n"
        f"زد المحتوى بنحو {deficit} كلمة على الأقل مع الحفاظ على العناوين،"
        f" وبحد أقصى يقارب {length_max} كلمة إجمالًا."
    )
    new_article = chat_complete(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.55,
        max_output_tokens=2200,
        model=model,
    )
    return new_article if "## " in new_article else article_md

# ---------- تصحيح البنية ----------
def verify_and_correct_structure(*, article_md: str, outline_md: str,
                                 model: str = MODEL_NAME) -> str:
    norm_outline = _normalize_outline_md(outline_md)
    target = _extract_h2_h3_titles(norm_outline)
    produced = _extract_h2_h3_titles(article_md)
    if produced == target:
        return article_md

    system = ("أنت محرر دقيق. صحّح المقال ليطابق الـ Outline (H2/H3) حرفيًا وترتيبًا،"
              " دون إضافة عناوين جديدة. انقل الفقرات للعنوان الصحيح عند الحاجة.")
    user = ("Outline المطلوب:\n-----\n" + norm_outline + "\n-----\n\n"
            "النص الحالي (صحّح البنية ثم أعد النص كاملًا):\n-----\n" + article_md + "\n-----\n")
    fixed = chat_complete(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        max_output_tokens=3000,
        model=MODEL_NAME,
    )
    return fixed if _extract_h2_h3_titles(fixed) == target else article_md

# ---------- الدالة الرئيسية ----------
def generate_article(
    *,
    keyword: str,
    related_keywords: List[str],
    length_preset: str,      # "short" | "medium" | "long"
    tone: str,               # "هادئة" | "قصصية" | "تحليلية"
    include_outline: bool,
    enable_editor_note: bool,
    enable_not_applicable: bool,
    enable_methodology: bool,
    enable_sources: bool,
    enable_scenarios: bool,
    enable_faq: bool,
    enable_comparison: bool,
    scenarios_count: int = 3,
    faq_count: int = 4,
    enforce_outline: bool = False,
    outline_mode: str = "modern",     # <<< جديد: "modern" | "classic" | "none"
    model: str = MODEL_NAME,
) -> Dict[str, Any]:

    # اختيار القالب الداخلي
    internal_outline = get_outline(outline_mode)
    use_internal_outline = bool(internal_outline)

    outline_md = ""
    if use_internal_outline:
        # نستخدم القالب الداخلي ونقفله
        outline_md = internal_outline
        include_outline = True
        enforce_outline = True

    # (أ) الكتابة من Outline مقفول
    if include_outline and enforce_outline and outline_md:
        P = build_from_outline_prompt(
            outline_md=outline_md,
            keyword=keyword,
            related_keywords=related_keywords,
            length_preset=length_preset,
            tone=tone,
            scenarios_count=scenarios_count,
            faq_count=faq_count,
        )
        first_pass = chat_complete(
            messages=[{"role": "system", "content": P["system"]},
                      {"role": "user", "content": P["user"]}],
            temperature=0.6,
            max_output_tokens=3800,
            model=model,
        )
        article = verify_and_correct_structure(
            article_md=first_pass,
            outline_md=outline_md,
            model=model,
        )
    else:
        # (ب) كتابة مباشرة بدون قفل Outline
        P = build_article_prompt(
            keyword=keyword,
            related_keywords=related_keywords,
            length_preset=length_preset,
            tone=tone,
            include_outline=include_outline,
            enable_editor_note=enable_editor_note,
            enable_not_applicable=enable_not_applicable,
            enable_methodology=enable_methodology,
            enable_sources=enable_sources,
            enable_scenarios=enable_scenarios,
            enable_faq=enable_faq,
            enable_comparison=enable_comparison,
            scenarios_count=scenarios_count,
            faq_count=faq_count,
        )
        article = chat_complete(
            messages=[{"role": "system", "content": P["system"]},
                      {"role": "user", "content": P["user"]}],
            temperature=0.6,
            max_output_tokens=3800,
            model=model,
        )

    # (ج) توسيع للطول المستهدف
    article = expand_to_target(
        article_md=article,
        keyword=keyword,
        related_keywords=related_keywords,
        length_preset=length_preset,
        model=model,
    )

    length_min, length_max = LENGTH_TARGETS.get(length_preset, (900, 1200))
    if _word_count(article) < length_min:
        article = expand_to_target(
            article_md=article,
            keyword=keyword,
            related_keywords=related_keywords,
            length_preset=length_preset,
            model=model,
        )

    quality_notes = {
        "length_target": f"{length_min}-{length_max} كلمة",
        "sections_target": "Outline داخلي مقفول" if (include_outline and enforce_outline and outline_md)
                           else "بدون قفل",
        "tone": tone,
        "outline_used": bool(include_outline and outline_md),
        "enforced_rules": [
            "صياغة احتمالية",
            "منع الجزم/الوعود",
            "تنويه مهني في الخاتمة",
            "تفكيك الرمز نفسيًا/اجتماعيًا",
            "سيناريوهات/FAQ عند التفعيل",
            "تمييز الرأي عن النقل",
        ],
    }

    return {
        "article": article,
        "outline": outline_md,
        "meta": {"title": f"تفسير {keyword}", "description": ""},
        "quality_notes": quality_notes,
    }
