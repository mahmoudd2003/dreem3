import streamlit as st

# إعداد الصفحة
st.set_page_config(
    page_title="📝 نظام مقالات تفسير الأحلام",
    page_icon="🌙",
    layout="wide"
)

st.title("📝 نظام كتابة مقالات تفسير الأحلام")
st.markdown("ابدأ بإدخال الكلمة المفتاحية والكلمات المرتبطة لتوليد مقال متكامل.")

# إدخالات المستخدم
keyword = st.text_input("🔑 الكلمة المفتاحية (مثال: تفسير رؤية البحر في المنام)")
related_keywords = st.text_area("📝 الكلمات المرتبطة (سطر لكل كلمة)", height=120)

# اختيار الطول
length_option = st.radio(
    "📏 اختر طول المقال:",
    ("قصير (600-800 كلمة)", "متوسط (900-1200 كلمة)", "موسع (1300-1600 كلمة)")
)

# زر التوليد
if st.button("🚀 إنشاء المقال"):
    if not keyword.strip():
        st.error("⚠️ يرجى إدخال الكلمة المفتاحية أولاً.")
    else:
        st.info("✍️ جاري إنشاء المقال... (الوظائف التفصيلية ستُضاف لاحقًا)")

        # Placeholder (مقال تجريبي مؤقت)
        st.subheader("📄 المقال الناتج")
        st.write(f"الكلمة المفتاحية: {keyword}")
        st.write(f"الكلمات المرتبطة: {related_keywords.splitlines()}")
        st.write(f"الطول المختار: {length_option}")
        st.success("✅ المقال الحقيقي سيظهر هنا بعد ربط GPT-4.1K وفلترة الجودة.")
