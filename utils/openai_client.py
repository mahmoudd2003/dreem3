# utils/openai_client.py
# -----------------------------------------
# طبقة التعامل مع OpenAI + دوال التوليد عالية المستوى
# تدعم: قراءة المفتاح من Streamlit secrets أو البيئة، اختيار الموديل، وضبط حرارة الأسلوب

import os
from typing import List, Optional, Literal, Dict, Any

try:
    import streamlit as st  # اختياري، لقراءة secrets إن وُجدت
except ImportError:
    st = None

# ملاحظة: هذه الواجهة تناسب مكتبة OpenAI الرسمية الحديثة (from openai import OpenAI)
# لو تستخدم إصدارًا أقدم، استبدلها بـ openai.ChatCompletion.create بصيغة الإصدار لديك.
try:
    from openai import OpenAI
except Exception as e:
    raise RuntimeError(
        "لم يتم العثور على مكتبة OpenAI الحديثة. ثبّت: pip install openai --upgrade"
    )

# =========================
# تهيئة العميل
# =========================
def get_client() -> OpenAI:
    """يُرجع عميل OpenAI بعد محاولة قراءة الـ API Key من عدة مصادر."""
    api_key = None

    # 1) Streamlit secrets لو متوفر
    if st is not None:
        api_key = (
            st.secrets.get("OPENAI_API_KEY", None)
            if hasattr(st, "secrets") else None
        )

    # 2) متغيرات البيئة
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "لم يتم العثور على OPENAI_API_KEY. ضعه في Streamlit secrets أو كمتغير بيئة."
        )

    # ملاحظة: لو تستخدم Azure OpenAI، يمكنك هنا قراءة AZURE_OPENAI_* وتكوين العميل وفق بيئتك.
    client = OpenAI(api_key=api_key)
    return client


def _get_model_name() -> str:
    """
    يحدد اسم الموديل الافتراضي. يمكنك تغييره من Streamlit secrets (OPENAI_MODEL).
    اقتراح: gpt-4.1 (للجودة) أو gpt-4.1-mini (للتكلفة الأقل).
    """
    # تُمكّن التخصيص عبر secrets أو env
    model = None
    if st is not None and hasattr(st, "secrets"):
        model = st.secrets.get("OPENAI_MODEL", None)

    if not model:
        model = os.getenv("OPENAI_MODEL", None)

    # افتراضي
    return model or "gpt-4.1"


# =========================
# لبّ التوليد
# =========================
def chat_complete(
    messages: List[Dict[str, str]],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_output_tokens: int = 1400,
) -> str:
    """
    استدعاء بسيط على دردشة OpenAI. يُعيد النص النهائي.
    """
    client = get_client()
    model_name = model or _get_model_name()

    resp = client.chat.completions.create(
        model=model_name,
        temperature=temperature,
        max_tokens=max_output_tokens,
        messages=messages,
    )

    return (resp.choices[0].message.content or "").strip()


# =========================
# توليد مقال تفسير أحلام
# =========================
LengthPreset = Literal["short", "medium", "long"]
TonePreset = Literal["هادئة", "قصصية", "تحليلية"]

def generate_article(
    keyword: str,
    related_keywords: List[str],
    length_preset: LengthPreset = "medium",
    tone: TonePreset = "هادئة",
    include_outline: bool = False,
) -> Dict[str, Any]:
    """
    يولّد مقالًا متكاملًا عن تفسير الأحلام وفق المتطلبات:
    - لغة بسيطة، جُمل قصيرة، صياغة احتمالية.
    - تنويع الأسلوب + سيناريو واقعي مختصر.
    - فلترة ضد الحشو والجزم (تعليمات صارمة في البرومبت).
    - تعليق محرّر متغيّر.
    - تنبيه واضح (Disclaimer).
    - خيار توليد Outline أولًا (اختياري)، ثم متن المقال.

    يُرجع dict يحتوي:
      - article: نص المقال النهائي (Markdown)
      - outline: خطة عناوين (إن طُلِبت)
      - meta: {'title': str, 'description': str}
      - quality_notes: ملاحظات موجزة عمّا تم تطبيقه (إرشادية)
    """

    # خرائط الطول إلى نطاق الكلمات وعدد الأقسام المقترح
    length_map = {
        "short":  {"words": "600-800",   "sections": "3-4"},
        "medium": {"words": "900-1200",  "sections": "4-5"},
        "long":   {"words": "1300-1600", "sections": "5-6"},
    }
    length_info = length_map.get(length_preset, length_map["medium"])

    # نبني مطالبات واضحة تقلل الحشو/الجزم وتضمن E-E-A-T
    sys = (
        "أنت محرر عربي محترف يكتب مقالات تفسير أحلام People-first متوافقة مع "
        "Google Helpful Content وE-E-A-T. التزم بما يلي بدقة: "
        "لغة بسيطة مباشرة، جُمل قصيرة، تقسيم منطقي، منع الحشو، صياغة احتمالية (قد/يُحتمل/بحسب السياق)، "
        "تمييز النقل التقليدي عن رأي المحرر المعاصر، إضافة تنبيه (Disclaimer)، احترام الحساسية الدينية، "
        "وعدم تقديم وعود/تنبؤات أو نصائح طبية/نفسية/مالية قاطعة."
    )

    # سنُنشئ outline اختياريًا
    outline_md = ""
    if include_outline:
        outline_user = (
            f"أنشئ Outline منظم لمقال عن: {keyword}\n"
            f"- الكلمات المرتبطة: {', '.join(related_keywords) if related_keywords else 'لا يوجد'}\n"
            f"- الطول المستهدف: {length_info['words']} كلمة تقريبًا، بعدد أقسام {length_info['sections']}.\n"
            f"- يجب أن يتضمن: مقدمة موجزة، تفسيرات حسب (حالة الرائي/المشاعر/المكان/التكرار)، "
            f"لماذا قد يظهر الرمز نفسيًا/اجتماعيًا، فقرة 'ما الذي لا يعنيه الحلم؟' لتفنيد المعتقدات، "
            f"سيناريو واقعي مختصر (مُفرّغ الهوية)، أسئلة شائعة (People also ask) مدمجة داخل الأقسام، "
            f"خاتمة + تنويه + مراجع (إن ذُكر نقل تقليدي). "
            f"- يجب توزيع الكلمات بذكاء حسب الطول المحدد."
        )
        outline_md = chat_complete(
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": outline_user}],
            temperature=0.4,
            max_output_tokens=600,
        )

    # الآن توليد المقال الكامل
    article_user = (
        f"اكتب مقال تفسير أحلام كامل حول: {keyword}\n"
        f"- الكلمات المرتبطة لإدماجها بسلاسة: {', '.join(related_keywords) if related_keywords else 'لا يوجد'}\n"
        f"- الطول المستهدف: {length_info['words']} كلمة تقريبًا، بعدد أقسام {length_info['sections']}.\n"
        f"- الأسلوب: نبرة {tone}، بشرية، جُمل قصيرة وفقرة/سطر لكل فكرة.\n"
        f"- التزامات إجبارية:\n"
        f"  1) صياغة احتمالية دائمًا (قد/يُحتمل/بحسب السياق)، ومنع الجزم والوعود والتنبؤات.\n"
        f"  2) منع الحشو: احذف أي جملة عامة بلا قيمة.\n"
        f"  3) تمييز النقل التقليدي (ابن سيرين/النابلسي…) عن رأي المحرر المعاصر، مع ذكر مرجع إن وُجد نقل.\n"
        f"  4) فقرة 'لماذا قد يظهر الرمز؟' بزوايا نفسية/اجتماعية بحذر (دون تشخيص أو طب).\n"
        f"  5) فقرة 'ما الذي لا يعنيه الحلم؟' لتبديد المعتقدات الشائعة.\n"
        f"  6) سيناريو واقعي قصير مفرّغ الهوية يُظهر أثر اختلاف السياق.\n"
        f"  7) إدماج 3–5 أسئلة حقيقية (People also ask) داخل الأقسام بدل FAQ منفصل، بإجابات موجزة.\n"
        f"  8) 'تعليق محرر' متغيّر (جملتان) في موضع مناسب.\n"
        f"  9) تنبيه (Disclaimer) واضح في الخاتمة يوضح أن التفسير اجتهادي ومتأثر بالظروف.\n"
        f"- الإخراج: Markdown بعناوين H2/H3 مناسبة، دون مبالغة بلاغية، ودون تكرار نمطي في الخاتمة.\n"
        f"{'هذا هو الـ Outline المعتمد:\n' + outline_md if outline_md else ''}"
    )

    article_md = chat_complete(
        messages=[
            {"role": "system", "content": sys},
            {"role": "user", "content": article_user},
        ],
        temperature=0.7,
        max_output_tokens=1800,
    )

    # توليد Meta (عنوان + وصف) مقتضب وجاذب
    meta_user = (
        f"اقترح عنوان SEO ووصف Meta مختصرين لمقال '{keyword}' "
        f"يلتزمان باللغة العربية وبأسلوب بشري، ويدمجان الكلمة المفتاحية طبيعيًا. "
        f"أعطني JSON بالمفاتيح: title, description. أقصى طول للوصف ~155 حرفًا."
    )
    meta_json = chat_complete(
        messages=[{"role": "system", "content": sys}, {"role": "user", "content": meta_user}],
        temperature=0.5,
        max_output_tokens=220,
    )

    # نحاول تحويل الـ JSON إن أمكن (بدون فرض مكتبات JSON هنا لتقليل الاعتمادية)
    meta: Dict[str, str] = {"title": "", "description": ""}
    try:
        import json  # استخدام محلي
        meta = json.loads(meta_json)
        # تأكد من المفاتيح
        meta = {
            "title": str(meta.get("title", "")).strip(),
            "description": str(meta.get("description", "")).strip(),
        }
    except Exception:
        # لو فشل التحويل، نضع النص كما هو في العنوان ونترك الوصف فارغًا
        meta["title"] = meta_json.strip()

    quality_notes = {
        "length_target": length_info["words"],
        "sections_target": length_info["sections"],
        "tone": tone,
        "enforced_rules": [
            "صياغة احتمالية",
            "منع الحشو",
            "تمييز النقل عن الرأي",
            "سيناريو واقعي",
            "تعليق محرر",
            "تنبيه (Disclaimer)",
            "دمج People Also Ask داخل الأقسام",
        ],
        "outline_used": bool(outline_md),
    }

    return {
        "article": article_md,
        "outline": outline_md,
        "meta": meta,
        "quality_notes": quality_notes,
    }
