# utils/openai_client.py
# =====================================================
# واجهة موحّدة للتعامل مع OpenAI (متوافقة مع إصدارات SDK المختلفة)
# الميزات:
# - chat_complete: طبقة توافق بين max_output_tokens / max_tokens
# - Two-pass generation: توليد Outline ثم ملء المحتوى
# - enforce_outline: قفل الـ Outline حرفيًا وعدم السماح بتغييره
# - التزام بالطول عبر قائمة تحقق + مرحلة توسيع تلقائية expand_to_target
# - verify_and_correct_structure: فحص/تصحيح تطابق العناوين مع الـ Outline
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

# اسم الموديل
MODEL_NAME = os.getenv("OPENAI_MODEL", "gpt-4.1")

# خرائط الطول المستهدفة
LENGTH_TARGETS: Dict[str, Tuple[int, int]] = {
    "short":  (600,  800),
    "medium": (900,  1200),
    "long":   (1300, 1600),
}

# أدوات مساعدة
_WORD_RE = re.compile(r"[A-Za-z\u0600-\u06FF]+", re.UNICODE)
_HX_RE   = re.compile(r"^(#{2,6})\s*(.+?)\s*$", re.UNICODE)  # لأي H2..H6

def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))

def _safe_join_keywords(keywords: List[str]) -> str:
    return ", ".join([k.strip() for k in keywords if k and k.strip()]) or "لا يوجد"

def _extract_h2_h3_titles(md: str) -> List[str]:
    """يستخرج قائمة عناوين H2/H3 بالترتيب."""
    titles = []
    for line in (md or "").splitlines():
        m = _HX_RE.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            if level in (2, 3):
                titles.append(title)
    return titles

def _normalize_outline_md(outline_md: str) -> str:
    """
    يضمن أن خطوط الـ Outline تبدأ بـ ## أو ###.
    في حال أعاد النموذج نقاط بدون ##، نرفعها إلى H2.
    """
    fixed_lines = []
    for ln in (outline_md or "").splitlines():
        s = ln.strip()
        if not s:
            continue
        if s.startswith("#"):
            # اترك العناوين كما هي
            fixed_lines.append(s)
        else:
            # حوّل أي سطر نصي إلى H2
            fixed_lines.append("## " + s.lstrip("-• ").strip())
    return "\n".join(fixed_lines).strip()

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
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_output_tokens,
        )
    return resp.choices[0].message.content or ""

# ---------------------------------
# برومبت عام (بدون Outline مُقفل)
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
    """
    برومبت كتابة المقال مع قائمة تحقق للطول والبنية (عناوين افتراضية).
    يُستخدم عندما لا نريد قفل Outline حرفيًا.
    """
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
        "أنت محرر عربي محترف يكتب مقالات تفسير أحلام بشرية.\n"
        "- لغة بسيطة مباشرة، جُمل قصيرة وفقرات منسّقة.\n"
        "- صياغة احتمالية (قد/يُحتمل/بحسب السياق)، منع الجزم والوعود.\n"
        "- تمييز الرأي المعاصر عن النقل التراثي.\n"
        "- لا نصائح طبية/نفسية/مالية قاطعة؛ احترام الحساسية الدينية.\n"
        "- تضمين تنويه مهني واضح في الخاتمة.\n"
        "- لا حشو ولا تكرار.\n"
    )

    hard_constraints = [
        f"- إجمالي الكلمات بين {length_min} و {length_max} كلمة.",
        "- لا يقل كل قسم أساسي (افتتاحية/لماذا/خاتمة) عن 120–180 كلمة.",
    ]
    if enable_not_applicable:
        hard_constraints.append("- «متى لا ينطبق التفسير؟»: 3–5 نقاط واقعية لتقليل التعميم.")
    if enable_scenarios:
        hard_constraints.append(f"- سيناريوهات واقعية: {scenarios_count} عناصر، كل عنصر ≤ سطرين مع تعليق موجز.")
    if enable_faq:
        hard_constraints.append(f"- أسئلة شائعة: {faq_count} أسئلة، سؤال ≤ 12 كلمة، جواب ≤ 30 كلمة بصيغة (**س:**/**ج:**).")
    if enable_comparison:
        hard_constraints.append("- مقارنة دقيقة: 2–3 فروق جوهرية كنقاط قصيرة.")
    if enable_methodology:
        hard_constraints.append("- منهجية التفسير: فقرة توضّح التراث + علم نفس الأحلام + سياق القارئ وحدود التفسير.")
    if enable_sources:
        hard_constraints.append("- مصادر صريحة: 3–6 مراجع؛ استخدم «بحاجة مراجعة بشرية» عند الشك.")
    if enable_editor_note:
        hard_constraints.append("- تعليق محرّر: خبرة تحريرية عامة بلا ادعاءات مهنية محمية.")

    user = (
        f"الكلمة المفتاحية: {keyword}\n"
        f"الكلمات المرتبطة: {rk}\n"
        f"النبرة: {tone}\n\n"
        "اكتب مقالًا بصيغة Markdown بالعناوين التالية (H2) بالترتيب:\n"
        + "\n".join(sections) + "\n\n"
        "[قائمة تحقق — إلزم بها]\n"
        + "\n".join(hard_constraints) + "\n\n"
        "تذكير:\n"
        "- فسّر «لماذا قد يظهر الرمز» نفسيًا/اجتماعيًا.\n"
        "- أدرج نصائح تهدئة ومتى أستشير مختصًا عند القلق.\n"
        "- «ما الذي لا يعنيه الحلم؟» لتبديد معتقدات شائعة.\n"
        "- أمثلة واقعية مُقننة وFAQ قصير إذا كانت الأقسام مفعّلة.\n"
        "- لا تضع H1 داخل النص.\n"
    )

    return {
        "system": system,
        "user": user,
        "sections": sections,
        "length_min": length_min,
        "length_max": length_max,
    }

# ---------------------------------
# برومبت البناء من Outline مقفول
# ---------------------------------
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
    """
    يبني برومبت يوجب الالتزام التام بالـ Outline المُمرّر (H2/H3) دون أي تعديل.
    """
    length_min, length_max = LENGTH_TARGETS.get(length_preset, (900, 1200))
    rk = _safe_join_keywords(related_keywords)
    normalized_outline = _normalize_outline_md(outline_md)

    system = (
        "أنت محرر عربي محترف. اكتب مقالًا يلتزم حرفيًا بالعناوين (H2/H3) التالية دون أي تغيير في النص أو الترتيب.\n"
        "- يُمنع إضافة/حذف/إعادة تسمية أي عنوان.\n"
        "- املأ كل عنوان بمحتوى متوازن وبشري، صياغة احتمالية، بلا حشو.\n"
        "- لا تضع H1.\n"
    )

    user = (
        f"الكلمة المفتاحية: {keyword}\n"
        f"الكلمات المرتبطة: {rk}\n"
        f"النبرة: {tone}\n\n"
        "Outline (التزم به حرفيًا — لا تغييرات في العناوين أو ترتيبها):\n"
        "-----\n"
        f"{normalized_outline}\n"
        "-----\n\n"
        "[قائمة تحقق للطول والبناء]\n"
        f"- إجمالي الكلمات بين {length_min} و {length_max} كلمة.\n"
        "- لا يقل كل قسم أساسي (H2) عن 120–180 كلمة.\n"
        f"- سيناريوهات واقعية (إن وُجدت في العناوين): ≤ {scenarios_count} عناصر قصيرة مع تعليق.\n"
        f"- أسئلة شائعة (إن وُجدت): ≤ {faq_count} أسئلة (س ≤ 12 كلمة، ج ≤ 30 كلمة).\n"
        "- تنويه مهني واضح في الخاتمة.\n"
    )

    return {
        "system": system,
        "user": user,
        "normalized_outline": normalized_outline,
        "length_min": length_min,
        "length_max": length_max,
    }

# ---------------------------------
# توسيع المقال إذا كان أقصر من المطلوب
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
        "مع الحفاظ على نفس العناوين وترتيبها وصياغة احتمالية، وتجنّب الحشو والجزم."
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
# فحص/تصحيح البنية مقابل Outline
# ---------------------------------
def verify_and_correct_structure(
    *,
    article_md: str,
    outline_md: str,
    model: str = MODEL_NAME,
) -> str:
    """
    يتحقق أن جميع عناوين H2/H3 في المقال تطابق الـ Outline حرفيًا وبالترتيب.
    إن وجد اختلاف (نقص/زيادة/إعادة تسمية)، يطلب تصحيحًا آليًا.
    """
    norm_outline = _normalize_outline_md(outline_md)
    target_titles = _extract_h2_h3_titles(norm_outline)
    produced_titles = _extract_h2_h3_titles(article_md)

    if produced_titles == target_titles:
        return article_md  # لا حاجة للتصحيح

    # نطلب تصحيحًا دقيقًا
    system = (
        "أنت محرر دقيق. صحّح البنية لتطابق الـ Outline تمامًا (H2/H3) دون تغيير نص/ترتيب العناوين.\n"
        "انقل/ادمج الفقرات تحت العنوان الصحيح عند الحاجة. لا تضف عناوين جديدة."
    )
    user = (
        "Outline المطلوب (التزم حرفيًا):\n"
        "-----\n" + norm_outline + "\n-----\n\n"
        "المقال الحالي (بحاجة تصحيح بنية):\n"
        "-----\n" + article_md + "\n-----\n"
        "أعد النص كاملًا بعد التصحيح."
    )
    fixed = chat_complete(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        max_output_tokens=3000,
        model=model,
    ).strip()

    # تأكيد سريع بعد التصحيح
    if _extract_h2_h3_titles(fixed) == target_titles:
        return fixed
    return article_md  # كاحتياط، أعد القديم إن ظلّ هناك اختلاف

# ---------------------------------
# توليد المقال (مع Two-pass و enforce_outline)
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
    enforce_outline: bool = False,   # <<< الخيار الجديد: قفل الـ Outline
    model: str = MODEL_NAME,
) -> Dict[str, Any]:

    outline_md = ""

    # (أ) خطوة الـ Outline (اختيارية)
    if include_outline:
        outline_system = (
            "أنت خبير إعداد Outline لمقال تفسير أحلام.\n"
            "أنتج مخططًا متوازنًا (H2/H3) دون متن، يغطي الزوايا المهمة للقارئ."
        )
        outline_user = (
            f"العنوان المقترح: تفسير {keyword}\n"
            f"الكلمات المرتبطة: {_safe_join_keywords(related_keywords)}\n"
            "- اجعل العناوين H2 للأقسام الرئيسية وH3 للتفاصيل.\n"
            "- لا تضف متنًا تحت العناوين.\n"
        )
        outline_md = chat_complete(
            messages=[{"role": "system", "content": outline_system},
                      {"role": "user", "content": outline_user}],
            temperature=0.5,
            max_output_tokens=800,
            model=model,
        ).strip()
        outline_md = _normalize_outline_md(outline_md)

    if include_outline and enforce_outline and outline_md:
        # (ب) بناء المقال من Outline مقفول
        P = build_from_outline_prompt(
            outline_md=outline_md,
            keyword=keyword,
            related_keywords=related_keywords,
            length_preset=length_preset,
            tone=tone,
            scenarios_count=scenarios_count,
            faq_count=faq_count,
        )
        messages = [
            {"role": "system", "content": P["system"]},
            {"role": "user",   "content": P["user"]},
        ]
        first_pass = chat_complete(
            messages=messages,
            temperature=0.6,
            max_output_tokens=3800,
            model=model,
        ).strip()

        # تصحيح البنية إن لزم
        article = verify_and_correct_structure(
            article_md=first_pass,
            outline_md=outline_md,
            model=model,
        )
    else:
        # (ج) كتابة مباشرة بدون قفل Outline (أو عندما لا نستخدم Outline)
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
        messages = [
            {"role": "system", "content": P["system"]},
            {"role": "user",   "content": P["user"]},
        ]
        first_pass = chat_complete(
            messages=messages,
            temperature=0.6,
            max_output_tokens=3800,
            model=model,
        ).strip()
        article = first_pass

    # (د) توسيع تلقائي حتى بلوغ الحد الأدنى
    article = expand_to_target(
        article_md=article,
        keyword=keyword,
        related_keywords=related_keywords,
        length_preset=length_preset,
        model=model,
    )
    # محاولة ثانية نادرة عند الحاجة
    length_min, length_max = LENGTH_TARGETS.get(length_preset, (900, 1200))
    if _word_count(article) < length_min:
        article = expand_to_target(
            article_md=article,
            keyword=keyword,
            related_keywords=related_keywords,
            length_preset=length_preset,
            model=model,
        )

    # ملاحظات جودة مختصرة
    quality_notes = {
        "length_target": f"{length_min}-{length_max} كلمة",
        "sections_target": "Outline مقفول" if (include_outline and enforce_outline and outline_md)
                          else "عناوين افتراضية (بدون قفل)",
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
