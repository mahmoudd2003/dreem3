# utils/meta_generator.py
# -----------------------------------------
# توليد وتحسين Meta (العنوان + الوصف) بطريقة متوافقة مع الطول الموصى به (≤ 155 حرفًا للوصف)
# يستخدم OpenAI عند توفره، وإلا يعتمد على خوارزمية احتياطية بسيطة.

from typing import Dict
import re

try:
    from utils.openai_client import chat_complete
    _HAS_OPENAI = True
except Exception:
    _HAS_OPENAI = False

DESC_MAX = 155

SYSTEM_META = (
    "أنت محرر SEO عربي محترف. المطلوب: توليد عنوان جذاب وموجز ووصف Meta ≤ 155 حرفًا "
    "باللغة العربية، بصياغة بشرية تُضمّن الكلمة المفتاحية طبيعيًا دون حشو."
)

def _fallback_meta(keyword: str, article_markdown: str) -> Dict[str, str]:
    """خطة احتياطية إذا API غير متوفّر."""
    # عنوان مبسّط
    title = keyword.strip()
    title = re.sub(r"\s+", " ", title)
    if len(title) < 10 and article_markdown:
        # خذ أول H2 كعنوان بديل
        m = re.search(r"^\s*##\s+(.+)$", article_markdown, flags=re.MULTILINE)
        if m:
            title = m.group(1).strip()

    # وصف مختصر من أول سطرين نص
    body = re.sub(r"#.*", "", article_markdown or "")
    body = re.sub(r"\s+", " ", body).strip()
    desc = f"{keyword} — مقال يشرح الدلالات المحتملة بحسب السياق مع تنبيه واجتهاد بشري."
    if body:
        desc = body[:DESC_MAX]
    if len(desc) > DESC_MAX:
        desc = desc[:DESC_MAX-1] + "…"

    return {"title": title, "description": desc}

def generate_meta(keyword: str, article_markdown: str) -> Dict[str, str]:
    """
    يكوّن Meta (title/description) ذكيًا.
    - يضمن ≤155 حرفًا للوصف.
    - يدمج الكلمة المفتاحية طبيعيًا.
    """
    if not _HAS_OPENAI:
        return _fallback_meta(keyword, article_markdown)

    user = (
        f"الكلمة المفتاحية: {keyword}\n"
        f"نص المقال (مقتطفات مهمة للاطلاع):\n{article_markdown[:1800]}\n\n"
        "أعطني JSON بالمفاتيح: title, description (≤ 155 حرفًا للوصف)."
    )
    try:
        meta_json = chat_complete(
            messages=[{"role": "system", "content": SYSTEM_META},
                      {"role": "user", "content": user}],
            temperature=0.5,
            max_output_tokens=220,
        )
        import json
        meta = json.loads(meta_json)
        title = str(meta.get("title", "")).strip()
        desc = str(meta.get("description", "")).strip()
    except Exception:
        # fallback عند أي خطأ
        return _fallback_meta(keyword, article_markdown)

    # تطبيع الطول
    if len(desc) > DESC_MAX:
        desc = desc[:DESC_MAX-1] + "…"

    # لو العنوان فاضي، استعمل بديل
    if not title:
        title = _fallback_meta(keyword, article_markdown)["title"]

    return {"title": title, "description": desc}
