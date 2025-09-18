# app.py
# ===========================
# واجهة Streamlit لنظام كتابة مقالات تفسير الأحلام
# يعتمد على:
# - utils/openai_client.py  (دالة generate_article)
# - utils/exporters.py      (تصدير Markdown/DOCX/JSON)
# - utils/quality_checks.py (تقرير الجودة التفصيلي)
# ===========================

import streamlit as st
from utils.openai_client import generate_article
from utils.exporters import to_markdown, to_docx_bytes, to_json_bytes
from utils.quality_checks import run_quality_report

# إعداد الصفحة
st.set_page_config(
    page_title="📝 نظام مقالات تفسير الأحلام",
    page_icon="🌙",
    layout="wide"
)

st.title("📝 نظام كتابة مقالات تفسير الأحلام")
st.markdown(
    "أدخل الكلمة المفتاحية والكلمات المرتبطة، واختر طول المقال. "
    "يمكنك أيضًا تفعيل إنشاء Outline قبل الكتابة."
)

# ===== إدخالات المستخدم =====
keyword = st.text_input("🔑 الكلمة المفتاحية (مثال: تفسير رؤية البحر في المنام)")

related_keywords_raw = st.text_area(
    "📝 الكلمات المرتبطة (سطر لكل كلمة)",
    height=120,
    placeholder="تفسير الغرق في البحر\nتفسير السباحة\nالموج العالي"
)

length_option_label = st.radio(
    "📏 اختر طول المقال:",
    ("قصير (600-800 كلمة)", "متوسط (900-1200 كلمة)", "موسع (1300-1600 كلمة)")
)

tone = st.selectbox("🎙️ النبرة", ["هادئة", "قصصية", "تحليلية"])

include_outline = st.toggle("📐 إنشاء Outline قبل كتابة المقال", value=False)

# تحويل نص الطول إلى preset داخلي
def _length_preset_from_label(label: str) -> str:
    if label.startswith("قصير"):
        return "short"
    if label.startswith("موسع"):
        return "long"
    return "medium"

length_preset = _length_preset_from_label(length_option_label)
related_keywords = [k.strip() for k in related_keywords_raw.splitlines() if k.strip()]

# ===== الإجراء =====
if st.button("🚀 إنشاء المقال"):
    if not keyword.strip():
        st.error("⚠️ يرجى إدخال الكلمة المفتاحية أولاً.")
        st.stop()

    with st.spinner("✍️ جاري إنشاء المقال بواسطة GPT…"):
        try:
            result = generate_article(
                keyword=keyword.strip(),
                related_keywords=related_keywords,
                length_preset=length_preset,   # short/medium/long
                tone=tone,                     # هادئة/قصصية/تحليلية
                include_outline=include_outline
            )
        except Exception as e:
            st.error(f"حدث خطأ أثناء التوليد: {e}")
            st.stop()

    # ===== العرض =====
    col1, col2 = st.columns([2, 1], gap="large")

    with col1:
        if include_outline and result.get("outline"):
            st.subheader("📐 Outline المقترح")
            st.markdown(result["outline"])

        st.subheader("📄 المقال الناتج")
        st.markdown(result["article"])  # يعرض Markdown مباشرة

    with col2:
        st.subheader("🔎 Meta (SEO)")
        meta = result.get("meta", {})
        st.write(f"**العنوان (Title):** {meta.get('title', '')}")
        st.write(f"**الوصف (Description):** {meta.get('description', '')}")

        st.subheader("✅ Quality Gates (مختصر)")
        qn = result.get("quality_notes", {})
        st.write(f"- **الطول المستهدف:** {qn.get('length_target')}")
        st.write(f"- **عدد الأقسام المستهدف:** {qn.get('sections_target')}")
        st.write(f"- **النبرة:** {qn.get('tone')}")
        st.write(f"- **Outline مُستخدم؟** {'نعم' if qn.get('outline_used') else 'لا'}")
        st.write("**قواعد مُطبّقة:**")
        st.write(", ".join(qn.get("enforced_rules", [])))

        # تقرير الجودة التفصيلي
        st.subheader("🧪 تقرير Quality Gates (تفصيلي)")
        rep = run_quality_report(result["article"], expected_length_preset=length_preset)

        # عرض نقاط أساسية
        st.write(f"**مستوى المخاطر:** {rep.get('risk_level')}")
        m = rep.get("metrics", {})
        st.write(
            f"- كلمات: {m.get('words')} | H2: {m.get('h2_count')} | H3: {m.get('h3_count')}\n"
            f"- عبارات جزم: {m.get('certainty_hits')} | حشو: {m.get('filler_hits')} | مفردات احتمالية: {m.get('probability_lexicon_hits')}\n"
            f"- تنويه موجود؟ {'نعم' if m.get('disclaimer_present') else 'لا'} | أقسام ناقصة: {', '.join(m.get('missing_sections', [])) or 'لا يوجد'}\n"
            f"- إشارات PAA: {m.get('paa_signals')}"
        )

        # توصيات عملية
        actions = rep.get("suggested_actions", [])
        if actions:
            st.write("**توصيات إصلاح:**")
            for a in actions:
                st.write(f"• {a}")
        else:
            st.write("لا توجد توصيات إضافية — المقال متوازن 👍")

        # أزرار التصدير
        st.subheader("📤 تصدير")
        md_bytes = to_markdown(result["article"]).encode("utf-8")
        docx_bytes = to_docx_bytes(result["article"], meta_title=meta.get("title", ""))
        json_bytes = to_json_bytes(
            article_markdown=result["article"],
            meta=meta,
            keyword=keyword.strip(),
            related_keywords=related_keywords,
        )

        st.download_button(
            "⬇️ تحميل Markdown",
            data=md_bytes,
            file_name="article.md",
            mime="text/markdown"
        )
        st.download_button(
            "⬇️ تحميل DOCX",
            data=docx_bytes,
            file_name="article.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        st.download_button(
            "⬇️ تحميل JSON",
            data=json_bytes,
            file_name="article.json",
            mime="application/json"
        )

    st.success("✅ تم إنشاء المقال بنجاح — راجع وعدّل ثم صدّر بالصيغة التي تريدها.")
