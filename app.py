# app.py
# ===========================
# واجهة Streamlit لنظام كتابة مقالات تفسير الأحلام
# يعتمد على:
# - utils/openai_client.py    (generate_article)
# - utils/exporters.py        (تصدير Markdown/DOCX/JSON)
# - utils/quality_checks.py   (تقرير الجودة التفصيلي)
# - utils/meta_generator.py   (مولّد الميتا الذكي)
# - utils/internal_links.py   (اقتراح الروابط الداخلية)
# - utils/style_diversity.py  (مؤشر تنوّع الأسلوب)
# - utils/section_tools.py    (تحرير قسم محدد)
# ===========================

import streamlit as st
from utils.openai_client import generate_article
from utils.exporters import to_markdown, to_docx_bytes, to_json_bytes
from utils.quality_checks import run_quality_report
from utils.meta_generator import generate_meta
from utils.internal_links import parse_inventory, suggest_internal_links
from utils.style_diversity import style_diversity_report
from utils.section_tools import list_sections, extract_section_text, regenerate_section

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

# مخزون الروابط الداخلية (اختياري)
st.markdown("### 🧭 مخزون الروابط الداخلية (اختياري)")
inventory_raw = st.text_area(
    "ضع قائمة مقالات موقعك بصيغة JSON (title, url, tags). مثال:",
    height=160,
    value='''[
  {"title":"تفسير رؤية البحر","url":"/sea-dream","tags":["البحر","الموج","السباحة"]},
  {"title":"تفسير رؤية المال","url":"/money-dream","tags":["مال","رزق","ديون"]},
  {"title":"تفسير رؤية الغرق","url":"/drowning-dream","tags":["الغرق","البحر","الخوف"]},
  {"title":"تفسير رؤية السباحة","url":"/swim-dream","tags":["سباحة","ماء","ثقة"]},
  {"title":"تفسير رؤية الذهب","url":"/gold-dream","tags":["ذهب","مال","زينة"]}
]'''
)

# كوربس المقالات السابقة للمقارنة الأسلوبية (اختياري)
st.markdown("### 🧪 مقالات سابقة للمقارنة الأسلوبية (اختياري)")
previous_corpus_raw = st.text_area(
    "ألصق مقالاتك السابقة للمقارنة. تقبل الصيغتين:\n"
    "1) JSON: [{\"title\":\"...\",\"content\":\"...\"}, ...]\n"
    "2) نص مفصول بـ --- حيث السطر الأول عنوان والباقي محتوى لكل مقال.",
    height=200,
    value=""
)

# تحويل نص الطول إلى preset داخلي
def _length_preset_from_label(label: str) -> str:
    if label.startswith("قصير"):
        return "short"
    if label.startswith("موسع"):
        return "long"
    return "medium"

length_preset = _length_preset_from_label(length_option_label)
related_keywords = [k.strip() for k in related_keywords_raw.splitlines() if k.strip()]

# حافظة الحالة
if "result" not in st.session_state:
    st.session_state["result"] = None
if "keyword" not in st.session_state:
    st.session_state["keyword"] = ""
if "related_keywords" not in st.session_state:
    st.session_state["related_keywords"] = []
if "tone" not in st.session_state:
    st.session_state["tone"] = tone

# ===== توليد المقال =====
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

    # تحسين/تأكيد الميتا (ذكي، ≤155 حرف للوصف)
    try:
        improved_meta = generate_meta(keyword.strip(), result["article"])
        if improved_meta.get("title") or improved_meta.get("description"):
            result["meta"] = improved_meta
    except Exception:
        pass

    # حفظ في الحالة
    st.session_state["result"] = result
    st.session_state["keyword"] = keyword.strip()
    st.session_state["related_keywords"] = related_keywords
    st.session_state["tone"] = tone

# ===== العرض =====
if st.session_state["result"]:
    result = st.session_state["result"]  # للسهولة
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

        # زر تحسين الميتا يدويًا
        if st.button("✨ تحسين الميتا (عنوان + وصف)"):
            try:
                improved_meta_btn = generate_meta(st.session_state["keyword"], result["article"])
                if improved_meta_btn:
                    meta = improved_meta_btn
                    result["meta"] = improved_meta_btn
                    st.session_state["result"] = result
                    st.success("تم تحسين الميتا.")
                    st.write(f"**العنوان (Title):** {meta.get('title', '')}")
                    st.write(f"**الوصف (Description):** {meta.get('description', '')}")
            except Exception as e:
                st.error(f"تعذّر تحسين الميتا: {e}")

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
            keyword=st.session_state["keyword"],
            related_keywords=st.session_state["related_keywords"],
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

    # ===== اقتراح الروابط الداخلية =====
    inventory = parse_inventory(inventory_raw)
    if inventory:
        st.subheader("🔗 اقتراح روابط داخلية")
        suggestions = suggest_internal_links(
            keyword=st.session_state["keyword"],
            related_keywords=st.session_state["related_keywords"],
            article_markdown=result["article"],
            inventory=inventory,
            top_k=6,
        )
        if suggestions:
            for s in suggestions:
                st.markdown(f"- [{s['title']}]({s['url']}) — **Score:** {s['score']}")
        else:
            st.info("لم يتم العثور على تطابقات كافية مع مخزون الروابط الحالي.")
    else:
        st.caption("لم يتم إدخال مخزون روابط داخلية؛ أضِف JSON في الحقل أعلاه لرؤية اقتراحات.")

    # ===== مؤشر تنوّع الأسلوب =====
    if previous_corpus_raw and previous_corpus_raw.strip():
        st.subheader("🎭 مؤشّر تنوّع الأسلوب")
        srep = style_diversity_report(result["article"], previous_corpus_raw, top_k=5)

        st.write(f"**حجم كوربس المقارنة:** {srep.get('corpus_size')}")
        st.write(f"**متوسط التشابه (Jaccard 3-grams):** {srep.get('avg_similarity')}")
        st.write(f"**مستوى المخاطر:** {srep.get('risk_level')}")

        sm = srep.get("style_metrics", {})
        st.write(
            f"- TTR (تنوّع المفردات): {sm.get('type_token_ratio')}\n"
            f"- متوسط طول الجملة (توكنز): {sm.get('avg_sentence_length_tokens')}\n"
            f"- كثافة الترقيم: {sm.get('punctuation_density')} | عدد الجمل: {sm.get('sentences_count')} | عدد التوكنز: {sm.get('tokens_count')}"
        )

        # أعلى المقالات تشابهًا
        top_sim = srep.get("top_similar", [])
        if top_sim:
            st.write("**أعلى المقالات تشابهًا:**")
            for i, item in enumerate(top_sim, 1):
                st.write(f"{i}. {item['title']} — similarity: {item['similarity']}")
        else:
            st.caption("لا توجد مقالات متشابهة بدرجة ملحوظة.")

        # توصيات
        sugg = srep.get("suggestions", [])
        if sugg:
            st.write("**توصيات تقليل التشابه:**")
            for s in sugg:
                st.write(f"• {s}")
        else:
            st.caption("لا توجد توصيات — التنوع جيد 👍")
    else:
        st.caption("لم يتم إدخال مقالات سابقة للمقارنة الأسلوبية.")

    # ===== تحرير قسم محدد (Regenerate Section) =====
    st.markdown("---")
    st.subheader("✍️ إعادة توليد قسم محدد")

    secs = list_sections(result["article"])
    if not secs:
        st.caption("لا توجد عناوين H2/H3 لاختيار قسم.")
    else:
        titles = [t for (t, lvl, s, e) in secs]
        selected = st.selectbox("اختر قسمًا لإعادة توليده:", titles, index=0)
        if selected:
            preview = extract_section_text(result["article"], selected)
            with st.expander("معاينة القسم الحالي"):
                st.markdown(preview)

            if st.button("🔁 إعادة توليد هذا القسم"):
                with st.spinner("يعاد توليد القسم المحدد…"):
                    try:
                        new_article = regenerate_section(
                            article_md=result["article"],
                            section_title=selected,
                            keyword=st.session_state["keyword"],
                            related_keywords=st.session_state["related_keywords"],
                            tone=st.session_state["tone"],
                        )
                        # تحديث الحالة والعرض
                        result["article"] = new_article
                        st.session_state["result"] = result
                        st.success("✅ تم تحديث القسم بنجاح.")
                        st.markdown(new_article)
                    except Exception as e:
                        st.error(f"تعذّرت إعادة توليد القسم: {e}")

    st.success("✅ المقال جاهز مع إمكانية إعادة توليد أي قسم دون إعادة كتابة المقال بالكامل.")
