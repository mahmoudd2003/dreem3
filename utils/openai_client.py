# utils/openai_client.py
# =====================================================
# واجهة موحّدة للتعامل مع OpenAI (توافق بين إصدارات SDK)
# - chat_complete: نداء دردشة عام مع طبقة توافق max_output_tokens/max_tokens
# - build_article_prompt: برومبت مضبوط + قائمة تحقق للطول
# - generate_article: توليد المقال (+ Outline اختياري) + توسيع تلقائي
# - expand_to_target: يعمّق المقال إن كان أقصر من الحد الأدنى
# =====================================================

from __future__ import annotations
from typing import List, Dict, Any, Tuple
import os
import re

# التحقق من المكتبة
try:
    from openai import OpenAI
except Exception:
    raise RuntimeError(
        "لم يتم العثور على مكتبة OpenAI الحديثة. ثبّت: pip install openai --upgrade"
    )

client = OpenAI()

# اضبط اسم الموديل من البيئة أو استخدم افتراضي
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4.1")

# خرائط الطول
LENGTH_TARGETS: Dict[str, Tuple[int, int]] = {
    "short":  (600,  800),
    "medium": (900,  1200),
    "long":   (1300, 1600),
}

# أدوات مساعدة
_WORD_RE = re.compile(r"[A-Za-z\u0600-\u06FF]+", re.UNICODE)
def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))

def _safe_join_keywords(keywords: List[str]) -> str:
    return ", ".join([k.strip() for k in keywords if k and k.strip()]) or "لا يوجد"

# ---------------------------------
# واجهة دردشة + طبقة توافق
# ---------------------------------
def chat_complete(
    *,
    messages: List[Dict[str, str]],
    temperature: float = 0.6,
    max_output_tokens: int = 3800,
    model: str = MODEL_NAME,
) -> str:
    """
    نداء موحّد لـ Chat Completions.
    - بعض إصدارات SDK تستخدم max_tokens بدل max_output_tokens.
    - نجرّب أولاً max_output_tokens، وإن فشل نعيد المحاولة بـ max_tokens.
    """
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
    except TypeError:
        # طبقة توافق لإصدارات SDK الأقدم
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_output_tokens,
        )
    return resp.choices[0].message.content or ""

# ---------------------------------
# بناء برومبت المقال
# ---------------------------------
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

    sections = [
        "## افتتاحية",
        "## لماذا قد يظهر الرمز؟",
    ]
    if enable_not_applicable:
        sections.append("## متى لا ينطبق التفسير؟")
    if enable_scenarios:
        sections.append("## سيناريوهات واقعية")
    if enable_faq:
        sections.append("## أسئلة شائعة")
    if enable_comparison:
        sections.append("## مقارنة دقيقة")
    if enable_methodology:
        sections.append("## منهجية التفسير")
    if enable_sources:
        sections.append("## مصادر صريحة")
    if enable_editor_note:
        sections.append("## تعليق محرّر")
    sections.append("## خاتمة")

    system = (
        "أنت محرر عربي محترف يكتب مقالات تفسير أحلام بشرية الطابع.\n"
        "التزم بالآتي:\n"
        "- لغة بسيطة مباشرة، جمل قصيرة وفقرات منسّقة.\n"
        "- صياغة احتمالية دائمًا (قد/يُحتمل/بحسب السياق)، ومنع الجزم والوعود/التنبؤات.\n"
        "- تمييز الرأي المعاصر عن النقل التراثي عند ذكره.\n"
        "- لا نصائح طبية/نفسية/مالية قاطعة. احترام الحساسية الدينية.\n"
        "- تضمين تنويه مهني واضح في الخاتمة.\n"
        "- لا حشو ولا تكرار.\n"
    )

    hard_constraints = [
        f"- إجمالي الكلمات بين {length_min} و {length_max} كلمة.",
        "- لا يقل كل قسم أساسي (افتتاحية/لماذا/خاتمة) عن 120–180 كلمة.",
    ]
    if enable_not_applicable:
        hard_constraints.append("- قسم «متى لا ينطبق التفسير؟»: 3–5 نقاط واقعية لتقليل التعميم.")
    if enable_scenarios:
        hard_constraints.append(f"- سيناريوهات واقعية: {scenarios_count} عناصر، كل عنصر ≤ سطرين مع تعليق موجز.")
    if enable_faq:
        hard_constraints.append(f"- أسئلة شائعة: {faq_count} أسئلة، سؤال ≤ 12 كلمة، جواب ≤ 30 كلمة، تنسيق (**س:**/**ج:**).")
    if enable_comparison:
        hard_constraints.append("- مقارنة دقيقة: 2–3 فروق جوهرية بصياغة نقاط قصيرة.")
    if enable_methodology:
        hard_constraints.append("- منهجية التفسير: فقرة توضّح الجمع بين التراث + علم نفس الأحلام + سياق القارئ وحدود التفسير.")
    if enable_sources:
        hard_constraints.append("- مصادر صريحة: 3–6 مراجع؛ استخدم «بحاجة مراجعة بشرية» عند الشك.")
    if enable_editor_note:
        hard_constraints.append("- تعليق محرّر: خبرة تحريرية عامة بلا ادعاءات مهنية محمية.")

    user = (
        f"الكلمة المفتاحية: {keyword}\n"
        f"الكلمات المرتبطة: {rk}\n"
        f"النبرة المستهدفة: {tone}\n\n"
        "اكتب مقالًا بصيغة Markdown بالعناوين التالية (H2) مرتّبة كما هي:\n"
        + "\n".join(sections) + "\n\n"
        "[قائمة تحقق صريحة — لا تُهملها]\n"
        + "\n".join(hard_constraints) + "\n\n"
        "تذكير مهم:\n"
        "- اشرح «لماذا قد يظهر الرمز» نفسيًا/اجتماعيًا عند اللزوم.\n"
        "- أدرج نصائح تهدئة ومتى أستشير مختصًا عند القلق.\n"
        "- «ما الذي لا يعنيه الحلم؟» تُدمج ضمن الأقسام الملائمة لتبديد المعتقدات الشائعة.\n"
        "- أدرج أمثلة واقعية مُقننة وFAQ قصير إذا كانت الأقسام مفعّلة.\n"
        "- لا تضف H1 داخل النص؛ العنوان الرئيسي خارج الماركداون.\n"
    )

    return {
        "system": system,
        "user": user,
        "sections": sections,
        "length_min": length_min,
        "length_max": length_max,
    }

# ---------------------------------
# توسيع المقال إن كان أقصر من المطلوب
# ---------------------------------
def expand_to_target(
    article_md: str,
    *,
    keyword: str,
    related_keywords: List[str],
    length_preset: str,
    model: str = MODEL_NAME,
) -> str:
    length_min, length_max = LENGTH_TARGETS.get(length_preset, (900, 1200))
    curr = _word_count(article_md)
    if curr >= length_min:
        return article_md

    deficit = max(length_min - curr, 250)
    system = (
        "أنت محرر يعمّق المقال دون تغيير هيكله أو عناوينه.\n"
        "وسّع كل قسم بمحتوى تطبيقي وأمثلة موجزة وأسئلة/إجابات قصيرة عند الحاجة، "
        "مع الحفاظ على نفس العناوين وترتيبها وصياغة احتمالية، ومنع الحشو والجزم."
    )
    user = (
        f"الكلمة المفتاحية: {keyword}\n"
        f"الكلمات المرتبطة: {_safe_join_keywords(related_keywords)}\n"
        f"المقال الحالي (Markdown):\n-----\n{article_md}\n-----\n"
        f"المطلوب: زد المحتوى بنحو {deficit} كلمة على الأقل، "
        f"مع الحفاظ على التنسيق والعناوين، وتجنّب الحشو والجزم، "
        f"وابق ضمن سقف أقصى يقارب {length_max} كلمة قدر الإمكان."
    )
    addition = chat_complete(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.55,
        max_output_tokens=2200,
        model=model,
    )
    new_article = addition.strip()
    if "## " not in new_article:
        return article_md
    return new_article

# ---------------------------------
# توليد المقال
# ---------------------------------
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
    model: str = MODEL_NAME,
) -> Dict[str, Any]:
    prompt = build_article_prompt(
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

    outline_md = ""
    if include_outline:
        outline_system = (
            "أنت خبير إعداد مخطط (Outline) لمقال تفسير أحلام. "
            "أنشئ مخططًا موجزًا من 6–10 عناصر (H2/H3) يراعي البنية المطلوبة."
        )
        outline_user = (
            f"العنوان المقترح: تفسير {keyword}\n"
            f"الكلمات المرتبطة: {_safe_join_keywords(related_keywords)}\n"
            "أعطني Outline مختصرًا ومتوازنًا، بدون متن، بصيغة Markdown (عناوين فقط)."
        )
        outline_md = chat_complete(
            messages=[{"role": "system", "content": outline_system},
                      {"role": "user", "content": outline_user}],
            temperature=0.5,
            max_output_tokens=700,
            model=model,
        ).strip()

    # التوليد الأساسي
    messages = [
        {"role": "system", "content": prompt["system"]},
        {"role": "user", "content": prompt["user"]},
    ]
    first_pass = chat_complete(
        messages=messages,
        temperature=0.6,
        max_output_tokens=3800,
        model=model,
    ).strip()

    # توسيع تلقائي حتى بلوغ الحد الأدنى
    article = expand_to_target(
        article_md=first_pass,
        keyword=keyword,
        related_keywords=related_keywords,
        length_preset=length_preset,
        model=model,
    )
    # محاولة ثانية نادرة إذا ما زال أقل (احتياط)
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
        "sections_target": "؛ ".join([s.replace("## ", "") for s in build_article_prompt(
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
        )["sections"]]),
        "tone": tone,
        "outline_used": bool(include_outline and outline_md),
        "enforced_rules": [
            "صياغة احتمالية",
            "منع الجزم/الوعود",
            "تنويه مهني في الخاتمة",
            "تفكيك الحلم ودمج مشاعر/سياق",
            "سيناريوهات واقعية/FAQ عند التفعيل",
            "تمييز الرأي عن النقل",
            "مراعاة الحساسية الدينية/الثقافية",
        ],
    }

    return {
        "article": article,
        "outline": outline_md,
        "meta": {
            "title": f"تفسير {keyword}",
            "description": "",
        },
        "quality_notes": quality_notes,
    }
