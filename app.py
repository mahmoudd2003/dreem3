# app.py
import streamlit as st

from utils.openai_client import generate_article

st.set_page_config(
    page_title="📝 نظام مقالات تفسير الأحلام",
    page_icon="🌙",
    layout="wide"
)

st.title("📝 نظام كتابة مقالات تفسير الأحلام")
st.markdown("أدخل الكلمة المفتاحية والكلمات المرتبطة، واختر طول المقال. يمكن تفعيل إنشاء Outline قبل الكتابة.")

# إدخالات المستخدم
keyword = st.text_input("🔑 الكلمة المفتاحية (مثال: تفسير رؤية البحر في المنام)")
related_keywords_raw = st.text_area("📝 الكلمات المرتبطة (سطر لكل كلمة)", height=120, placeholder="تفسير الغرق في البحر\nتفسير السباحة\nالموج العالي")

length_option_label = st.radio(
    "📏 اختر طول المقال:",
    ("قصير (600-800 كلمة)", "متوسط (900-1200 كلمة)", "موسع (1300-1600 كلمة)")
)
tone = st.selectbox("🎙️ النبرة", ["هادئة", "قصصية", "تحليلية"])
include_outline = st.toggle("📐 إنشاء Outline قبل كتابة المقال", value=False)

# تحويل نص الطول إلى preset
def _length_preset_from_label(label: str) -> str:
    if label.startswith("قصير"):
        return "short"
    if label.startswith("موسع"):
        return "long"
    return "medium"

length_preset = _length_preset_from_label(length_option_label)
related_keywords = [k.strip() for k in related_keywords_raw.splitlines() if k.strip()]

# زر التوليد
if st.button("🚀 إنشاء المقال"):
    if not keyword.strip():
        st.error("⚠️ يرجى إدخال الكلمة المفتاحية أولاً.")
        st.stop()

    with st.spinner("✍️ جاري إنشاء المقال بواسطة GPT-4.1…"):
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

    # عرض النتائج
    col1, col2 = st.columns([2, 1], gap="large")

    with col1:
        if include_outline and result.get("outline"):
            st.subheader("📐 Outline المقترح")
            st.markdown(result["outline"])

        st.subheader("📄 المقال الناتج")
        st.markdown(result["article"])  # Markdown

    with col2:
        st.subheader("🔎 Meta (SEO)")
        meta = result.get("meta", {})
        st.write(f"**العنوان (Title):** {meta.get('title', '')}")
        st.write(f"**الوصف (Description):** {meta.get('description', '')}")

        st.subheader("✅ Quality Gates")
        qn = result.get("quality_notes", {})
        st.write(f"- **الطول المستهدف:** {qn.get('length_target')}")
        st.write(f"- **عدد الأقسام المستهدف:** {qn.get('sections_target')}")
        st.write(f"- **النبرة:** {qn.get('tone')}")
        st.write(f"- **Outline مُستخدم؟** {'نعم' if qn.get('outline_used') else 'لا'}")
        st.write("**قواعد مُطبّقة:**")
        st.write(", ".join(qn.get("enforced_rules", [])))

    st.success("✅ تم إنشاء المقال بنجاح. يمكنك الآن نسخه أو تطويره أو إضافة مزايا التصدير لاحقًا.")
