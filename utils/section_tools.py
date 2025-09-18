# utils/section_tools.py
# ---------------------------------------------------
# أدوات التعامل مع أقسام الماركداون (H2/H3) + إعادة توليد قسم محدد عبر OpenAI
# - list_sections: يرجع قائمة بالعناوين (H2/H3) مع مواقعها
# - extract_section_text: يرجع نص القسم المحدد
# - replace_section_text: يستبدل محتوى قسم في المقال
# - regenerate_section: يعيد كتابة قسم بحدود واضحة واحترام قواعد النظام

from __future__ import annotations
from typing import List, Tuple, Dict
import re

from utils.openai_client import chat_complete

H2_RE = re.compile(r"(?m)^(##)\s+(.+?)\s*$")
H3_RE = re.compile(r"(?m)^(###)\s+(.+?)\s*$")

def list_sections(article_md: str) -> List[Tuple[str, int, int, int]]:
    """
    يرجع قائمة [(title, level, start_idx, end_idx)] لكل H2/H3.
    level: 2 أو 3
    start_idx = بداية العنوان في النص
    end_idx = بداية العنوان التالي أو نهاية النص
    """
    text = article_md or ""
    matches = []
    for m in H2_RE.finditer(text):
        matches.append((m.group(2).strip(), 2, m.start(), m.end()))
    for m in H3_RE.finditer(text):
        matches.append((m.group(2).strip(), 3, m.start(), m.end()))

    # ترتيب بحسب الموقع
    matches.sort(key=lambda x: x[2])

    # حساب نهاية كل قسم
    sections = []
    for i, (title, level, start, endline) in enumerate(matches):
        next_start = len(text)
        if i + 1 < len(matches):
            next_start = matches[i + 1][2]
        sections.append((title, level, start, next_start))
    return sections

def extract_section_text(article_md: str, section_title: str) -> str:
    """يستخرج نص القسم (من العنوان حتى بداية العنوان التالي)."""
    text = article_md or ""
    for title, level, start, end in list_sections(text):
        if title == section_title:
            return text[start:end].rstrip()
    return ""

def replace_section_text(article_md: str, section_title: str, new_section_md: str) -> str:
    """يستبدل نص القسم المحدد بنص جديد (يجب أن يتضمن العنوان مرة أخرى)."""
    text = article_md or ""
    sections = list_sections(text)
    for title, level, start, end in sections:
        if title == section_title:
            return text[:start] + (new_section_md.rstrip() + "\n") + text[end:]
    return text

def regenerate_section(
    article_md: str,
    section_title: str,
    keyword: str,
    related_keywords: List[str],
    tone: str = "هادئة",
) -> str:
    """
    يعيد كتابة القسم المحدد فقط، محافظًا على:
    - عنوان القسم كما هو (يفضّل إبقاءه نفسه)،
    - لغة بسيطة وجمل قصيرة،
    - صياغة احتمالية ومنع الحشو/الجزم،
    - دمج طبيعي للكلمة المفتاحية والكلمات المرتبطة إذا لزم،
    - اتساق الأسلوب مع بقية المقال.
    """
    current = extract_section_text(article_md, section_title)
    if not current:
        return article_md  # لا شيء لنعيد توليده

    system = (
        "أنت محرر عربي محترف يقوم بتحرير قسم محدد من مقال تفسير أحلام. "
        "التزم: لغة بسيطة، جمل قصيرة، صياغة احتمالية (قد/يُحتمل/بحسب السياق)، "
        "منع الحشو والجزم والوعود، احترام الحساسية الدينية، وعدم تقديم نصائح طبية/نفسية/مالية قاطعة. "
        "أعد كتابة القسم المطلوب فقط بصيغة Markdown مع الحفاظ على عنوانه (H2/H3) في أول سطر."
    )

    user = (
        f"العنوان المطلوب إعادة صياغته: {section_title}\n"
        f"النبرة المستهدفة: {tone}\n"
        f"الكلمة المفتاحية: {keyword}\n"
        f"الكلمات المرتبطة: {', '.join(related_keywords) if related_keywords else 'لا يوجد'}\n"
        "النص الحالي للقسم (Markdown):\n"
        f"-----\n{current}\n-----\n"
        "أعد كتابة القسم فقط، لا تُعد كتابة المقال كاملًا. "
        "حافظ على نفس العنوان ونفس المستوى (## أو ###) في أول السطر. "
        "احذف أي حشو، واستعمل صياغة احتمالية، وادمج أمثلة موجزة عند الحاجة."
    )

    new_sec = chat_complete(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.65,
        max_output_tokens=600,
    )

    # تأكد أن الإخراج يبدأ بعنوان
    new_sec = new_sec.strip()
    if not (new_sec.startswith("## ") or new_sec.startswith("### ")):
        # لو النموذج نسي العنوان، نعيد حقنه يدويًا كـ H2 افتراضي
        # نحدد المستوى من النص الأصلي
        level = 2
        for title, lvl, s, e in list_sections(article_md):
            if title == section_title:
                level = lvl
                break
        prefix = "## " if level == 2 else "### "
        new_sec = f"{prefix}{section_title}\n{new_sec}"

    return replace_section_text(article_md, section_title, new_sec)
