# utils/openai_client.py
# ==========================================
# عميل OpenAI + أدوات بناء المخرجات التحريرية
# - chat_complete: استدعاء محادثة قياسي
# - load_article_templates: تحميل قوالب الأقسام من YAML
# - build_article_prompt: تركيب البرومبت من القوالب وخيارات الواجهة
# - generate_article: توليد المقال (Markdown) + ملاحظات جودة + (Outline اختياري)
# ملاحظات:
# * يعتمد على متغيرات البيئة:
#   - OPENAI_API_KEY
#   - OPENAI_MODEL (اختياري) الافتراضي "gpt-4.1"
# * تأكد من وجود PyYAML في requirements.txt

from __future__ import annotations
from typing import List, Dict, Any
from pathlib import Path
import os
import json

# محاولة استيراد مكتبة OpenAI الحديثة
try:
    from openai import OpenAI
except Exception:
    raise RuntimeError("لم يتم العثور على مكتبة OpenAI الحديثة. ثبّت: pip install openai --upgrade")

# YAML لتحميل القوالب
try:
    import yaml
except Exception:
    raise RuntimeError("مفقود PyYAML. ثبّت: pip install pyyaml")

# تهيئة العميل
_api_key = os.getenv("OPENAI_API_KEY")
if not _api_key:
    raise RuntimeError("لم يتم العثور على OPENAI_API_KEY في متغيرات البيئة.")

_client = OpenAI(api_key=_api_key)

# اختيار النموذج
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1").strip()

# ------------------------------
# واجهة مساعدة: Chat Completion
# ------------------------------
def chat_complete(
    messages: List[Dict[str, str]],
    temperature: float = 0.6,
    max_output_tokens: int = 800,
) -> str:
    """
    استدعاء محادثة قياسي. يرجع نص المخرجات (content) كسلسلة.
    messages = [{"role":"system/user/assistant","content":"..."}]
    """
    resp = _client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=temperature,
        max_tokens=max_output_tokens,
    )
    # الحصول على أول مخرَج نصّي
    choice = resp.choices[0]
    content = choice.message.content or ""
    return content.strip()

# ------------------------------
# تحميل القوالب من YAML (كاش)
# ------------------------------
_TPL_CACHE: Dict[str, Any] | None = None

def load_article_templates() -> Dict[str, Any]:
    global _TPL_CACHE
    if _TPL_CACHE is not None:
        return _TPL_CACHE
    p = Path(__file__).parent / "article_templates.yaml"
    if not p.exists():
        raise RuntimeError(f"لم يتم العثور على ملف القوالب: {p}")
    with p.open("r", encoding="utf-8") as f:
        _TPL_CACHE = yaml.safe_load(f) or {}
    return _TPL_CACHE

def _bool_label(v: bool) -> str:
    return "نعم" if v else "لا"

# ------------------------------
# بناء البرومبت من القوالب
# ------------------------------
def build_article_prompt(
    keyword: str,
    related_keywords: List[str],
    length_preset: str,
    tone: str,
    *,
    enable_editor_note: bool,
    enable_not_applicable: bool,
    enable_methodology: bool,
    enable_sources: bool,
    enable_scenarios: bool,
    enable_faq: bool,
    enable_comparison: bool,
    scenarios_count: int = 3,
    faq_count: int = 4,
) -> str:
    """
    يركّب برومبت شامل يضم بنية المقال والأقسام المطلوبة،
    ويُمرّر قوالب الصياغة كتعليمات للنموذج.
    """
    tpl = load_article_templates()

    governance = (
        "اكتب بالعربية البسيطة وبجمل قصيرة وفقرات منسّقة Markdown.\n"
        "الصياغة احتمالية دائمًا (قد/يُحتمل/بحسب السياق). لا جزم ولا وعود/تنبؤات.\n"
        "احترم الحساسية الدينية/الثقافية. لا نصائح طبية/نفسية/مالية قاطعة.\n"
        "ميّز بين النقل الموثّق ورأي المحرّر. أدرج إخلاء مسؤولية في الخاتمة."
    )

    parts = [
        f"## افتتاحية\n{tpl.get('intro','')}",
        f"## لماذا قد يظهر الرمز؟\n{tpl.get('why_symbol_appears','')}",
    ]

    if enable_not_applicable:
        parts.append(f"## متى لا ينطبق التفسير؟\n{tpl.get('not_applicable','')}")

    if enable_scenarios:
        parts.append(f"## سيناريوهات واقعية\n{tpl.get('scenarios_preamble','')}")

    if enable_faq:
        parts.append(f"## أسئلة شائعة\n{tpl.get('faq_preamble','')}")

    if enable_comparison:
        parts.append(f"## مقارنة دقيقة\n{tpl.get('comparison','')}")

    if enable_methodology:
        parts.append(f"## منهجية التفسير\n{tpl.get('methodology','')}")

    if enable_sources:
        parts.append(f"## مصادر صريحة\n{tpl.get('sources_preamble','')}")

    if enable_editor_note:
        parts.append(f"## تعليق محرّر\n{tpl.get('editor_note','')}")

    parts.append(f"## خاتمة\n{tpl.get('outro','')}\n\n{tpl.get('disclaimer','')}")

    summary = (
        f"الكلمة المفتاحية: {keyword}\n"
        f"الكلمات المرتبطة: {', '.join(related_keywords) if related_keywords else 'لا يوجد'}\n"
        f"الطول المستهدف: {length_preset} (short/medium/long)\n"
        f"النبرة: {tone}\n"
        f"سيناريوهات: {_bool_label(enable_scenarios)} (عدد={scenarios_count})\n"
        f"أسئلة شائعة: {_bool_label(enable_faq)} (عدد={faq_count})\n"
        f"مقارنة: {_bool_label(enable_comparison)} | منهجية: {_bool_label(enable_methodology)} | مصادر: {_bool_label(enable_sources)}\n"
        f"تعليق محرر: {_bool_label(enable_editor_note)}\n"
        "التزم بالاحتمالية وعدم الجزم. ميّز النقل عن الرأي."
    )

    repeat_instructions = (
        f"\n\nعند توليد السيناريوهات: أنشئ {scenarios_count} عناصر بصيغ ومشاعر مختلفة "
        f"باستخدام القالب: {tpl.get('scenario_item','')}\n"
        f"عند توليد الأسئلة الشائعة: أنشئ {faq_count} عناصر موجزة باستخدام القالب: {tpl.get('faq_item','')}\n"
        "حافظ على حدود الطول لكل عنصر كما هو مذكور."
    )

    prompt = (
        f"{governance}\n\n"
        f"اكتب مقالًا عن: {keyword}\n"
        f"ادمج الكلمة المفتاحية طبيعيًا في العنوان والافتتاحية دون حشو.\n\n"
        f"{summary}\n\n"
        f"**بنية المقال (Markdown):**\n"
        f"{'-'*16}\n"
        + "\n\n".join(parts)
        + repeat_instructions
        + "\n\nلا تُدرج أي كود، فقط نص Markdown."
    )
    return prompt

# ------------------------------
# توليد المقال
# ------------------------------
def generate_article(
    keyword: str,
    related_keywords: List[str],
    length_preset: str,
    tone: str,
    include_outline: bool = False,
    *,
    enable_editor_note: bool = True,
    enable_not_applicable: bool = True,
    enable_methodology: bool = True,
    enable_sources: bool = True,
    enable_scenarios: bool = True,
    enable_faq: bool = True,
    enable_comparison: bool = True,
    scenarios_count: int = 3,
    faq_count: int = 4,
) -> Dict[str, Any]:
    """
    يولّد المقال Markdown وفق القوالب والخيارات، ويرجع:
    { article, meta, quality_notes, outline? }
    """
    user_prompt = build_article_prompt(
        keyword=keyword,
        related_keywords=related_keywords,
        length_preset=length_preset,
        tone=tone,
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

    system = "أنت محرر عربي محترف في تفسير الأحلام. التزم بالاعتبارات التحريرية والاحتمالية."

    article_md = chat_complete(
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user_prompt}],
        temperature=0.65,
        max_output_tokens=2000,
    )

    # Outline (اختياري)
    outline_md = ""
    if include_outline:
        outline_md = chat_complete(
            messages=[
                {"role": "system", "content": "أنشئ مخطط عناوين موجز لمقال عربي بصيغة Markdown."},
                {"role": "user", "content": f"المقال عن: {keyword}\nاتّبع الأقسام المذكورة في القوالب."}
            ],
            temperature=0.4,
            max_output_tokens=400,
        )

    # Meta مبدئي (ستتحسن لاحقًا عبر meta_generator)
    meta = {
        "title": f"{keyword} — دلالات محتملة بحسب السياق",
        "description": f"مقال يشرح احتمالات {keyword} مع أمثلة وسيناريوهات وتنبيه مهني."
    }

    quality_notes = {
        "length_target": length_preset,
        "sections_target": "Intro/Why/NotApplicable/Scenarios/FAQ/Comparison/Methodology/Sources/Outro",
        "tone": tone,
        "outline_used": include_outline,
        "enforced_rules": [
            "لغة بسيطة وجمل قصيرة",
            "صياغة احتمالية دائمًا",
            "تمييز النقل عن رأي المحرّر",
            "إخلاء مسؤولية مهني في الخاتمة",
            "متى لا ينطبق التفسير (إن كان مفعّلًا)",
            "منهجية التفسير (إن كانت مفعّلة)",
            "مراجع صريحة (إن كانت مفعّلة)"
        ],
    }

    return {
        "article": article_md,
        "meta": meta,
        "quality_notes": quality_notes,
        "outline": outline_md if include_outline else ""
    }
