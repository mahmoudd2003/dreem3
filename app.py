# app.py
# ===========================
# واجهة Streamlit لنظام كتابة مقالات تفسير الأحلام
# يعتمد على:
# - utils/openai_client.py    (generate_article + Two-pass + enforce_outline)
# - utils/exporters.py        (تصدير Markdown/DOCX/JSON)
# - utils/quality_checks.py   (تقرير الجودة التفصيلي)
# - utils/meta_generator.py   (مولّد الميتا الذكي)
# - utils/internal_links.py   (اقتراح الروابط الداخلية)
# - utils/style_diversity.py  (مؤشر تنوّع الأسلوب)
# - utils/section_tools.py    (تحرير/إعادة توليد قسم محدد)
# - utils/text_cleanup.py     (فلترة/تحسينات لغوية)
# - utils/heading_tools.py    (Normalize Headings)
# - utils/enhanced_fix.py     (دفعة إصلاح مُحسّنة)
# ===========================

import re
import streamlit as st
from utils.openai_client import generate_article
from utils.exporters import to_markdown, to_docx_bytes, to_json_bytes
from utils.quality_checks import run_quality_report
from utils.meta_generator import generate_meta
from utils.internal_links import parse_inventory, suggest_internal_links
from utils.style_diversity import style_diversity_report
from utils.section_tools import list_sections, extract_section_text, regenerate_section
from utils.text_cleanup import clean_article
from utils.heading_tools import normalize_headings
from utils.enhanced_fix import run_enhanced_fix

# إعداد الصفحة
st.set_page_config(
    page_title="📝 نظام مقالات تفسير الأحلام",
    page_icon="🌙",
    layout="wide"
)

st.title("📝 نظام كتابة مقالات تفسير الأحلام")
st.markdown(
    "أدخل الكلمة المفتاحية والكلمات المرتبطة، واختر طول المقال. "
    "يمكنك أيضًا تفعيل إنشاء Outline قبل الكتابة وقفل الالتزام به حرفيًا."
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

col_outline_a, col_outline_b = st.columns(2)
with col_outline_a:
    include_outline = st.toggle("📐 إنشاء Outline قبل كتابة المقال", value=False)
with col_outline_b:
    enforce_outline = st.checkbox("🔒 استخدم الـ Outline حرفيًا (إن وُجد)", value=True)

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

# ⚙️ خيارات الأقسام المحسّنة (تؤثر على البرومبت مباشرة)
st.markdown("### ⚙️ أقسام محسّنة (اختياري)")
col_opt1, col_opt2, col_opt3 = st.columns(3)
with col_opt1:
    enable_editor_note = st.checkbox("تعليق محرّر", value=True)
    enable_not_applicable = st.checkbox("متى لا ينطبق التفسير؟", value=True)
    enable_methodology = st.checkbox("منهجية التفسير", value=True)
with col_opt2:
    enable_sources = st.checkbox("مصادر صريحة", value=True)
    enable_scenarios = st.checkbox("سيناريوهات واقعية", value=True)
    scenarios_count = st.slider("عدد السيناريوهات", 3, 5, 3)
with col_opt3:
    enable_faq = st.checkbox("أسئلة شائعة", value=True)
    faq_count = st.slider("عدد الأسئلة الشائعة", 3, 6, 4)
    enable_comparison = st.checkbox("مقارنة دقيقة", value=True)

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
        st.error("⚠️ يرجى إدخال الكلمة المفتاحية أولًا.")
        st.stop()

    with st.spinner("✍️ جاري إنشاء المقال بواسطة GPT…"):
        try:
            result = generate_article(
                keyword=keyword.strip(),
                related_keywords=related_keywords,
                length_preset=length_preset,   # short/medium/long
                tone=tone,                     # هادئة/قصصية/تحليلية
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
                enforce_outline=enforce_outline,   # <<< الجديد
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
    st.session_state["scenarios_count"] = scenarios_count
    st.session_state["faq_count"] = faq_count

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
        st.write(f"- **البنية:** {qn.get('sections_target')}")
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

    # ===== الفلترة/التحسينات اللغوية =====
    st.markdown("---")
    st.subheader("🧹 فلترة/تحسينات لغوية")

    col_clean_a, col_clean_b = st.columns(2)
    with col_clean_a:
        opt_fix_punct = st.checkbox("تصحيح مسافات/شكل الترقيم", value=True)
        opt_remove_filler = st.checkbox("إزالة جُمل/أسطر حشوية", value=True)
    with col_clean_b:
        opt_normalize_ws = st.checkbox("تطبيع المسافات والأسطر", value=True)
        opt_aggressive = st.checkbox("نمط عدواني لإزالة الحشو (حذر)", value=False)

    if st.button("🧹 تنظيف لغوي وتطبيق"):
        with st.spinner("يتم تنظيف المقال..."):
            cleaned = clean_article(
                result["article"],
                remove_filler=opt_remove_filler,
                aggressive=opt_aggressive,
                fix_punct=opt_fix_punct,
                normalize_ws=opt_normalize_ws,
            )
            result["article"] = cleaned["cleaned"]
            st.session_state["result"] = result
            repc = cleaned["report"]
            st.success("تم تطبيق التنظيف.")
            st.write("**تقرير التنظيف:**")
            st.write(
                f"- تصحيح علامات الحذف: {repc['ellipsis_fixed']} | تقليص تكرار الترقيم: {repc['repeated_punct_collapsed']}\n"
                f"- فواصل عربية مستبدلة: {repc['arabic_comma_applied']} | إصلاح مسافات الترقيم: {repc['spacing_fixed']}\n"
                f"- تطبيع مسافات/أسطر: {repc['whitespace_normalized']} | أسطر/جمل حُذفت/قُصّت: {repc['filler_removed']}"
            )
            st.markdown("**المقال بعد التنظيف:**")
            st.markdown(result["article"])

    # ===== Normalize Headings =====
    st.markdown("---")
    st.subheader("🧭 Normalize Headings (تطبيع العناوين)")

    col_h_a, col_h_b = st.columns(2)
    with col_h_a:
        opt_h1_to_h2 = st.checkbox("تحويل H1 إلى H2", value=True)
        opt_h4_to_h3 = st.checkbox("إنزال H4+ إلى H3", value=True)
        opt_space_after_hash = st.checkbox("توحيد المسافة بعد #", value=True)
    with col_h_b:
        opt_trim_punct = st.checkbox("إزالة ترقيم زائد بنهاية العنوان", value=True)
        opt_collapse_spaces = st.checkbox("ضغط المسافات داخل العنوان", value=True)
        opt_dedupe = st.checkbox("إزالة عناوين متتالية مكررة", value=True)

    opt_autonumber = st.checkbox("ترقيم تلقائي للأقسام (H2/H3)", value=False)

    if st.button("🧭 طبّق تطبيع العناوين"):
        with st.spinner("تطبيق Normalize Headings..."):
            nh = normalize_headings(
                result["article"],
                h1_to_h2=opt_h1_to_h2,
                h4plus_to_h3=opt_h4_to_h3,
                unify_space_after_hash=opt_space_after_hash,
                trim_trailing_punct=opt_trim_punct,
                collapse_spaces=opt_collapse_spaces,
                remove_consecutive_duplicates=opt_dedupe,
                autonumber=opt_autonumber,
            )
            result["article"] = nh["normalized"]
            st.session_state["result"] = result

            ch = nh["changes"]
            st.success("تم تطبيع العناوين.")
            st.write("**ملخص التغييرات:**")
            st.write(
                f"- H1→H2: {ch['h1_to_h2']} | H4+→H3: {ch['h4plus_to_h3']} | مسافة بعد #: {ch['space_after_hash_fixed']}\n"
                f"- إزالة ترقيم نهائي: {ch['trimmed_trailing_punct']} | ضغط مسافات: {ch['collapsed_spaces']} | حذف مكرر: {ch['deduped_headings']}\n"
                f"- ترقيم تلقائي: {ch['autonumbered']} | إجمالي العناوين: {ch['total_headings']}"
            )
            st.markdown("**المقال بعد التطبيع:**")
            st.markdown(result["article"])

    # ===== دفعة إصلاح (النسخة الأساسية) =====
    st.markdown("---")
    st.subheader("🚑 دفعة إصلاح (تنظيف + Normalize + خاتمة مسؤولة)")

    col_fix_a, col_fix_b = st.columns(2)
    with col_fix_a:
        fx_fix_punct = st.checkbox("تصحيح الترقيم/المسافات", value=True, key="fx_fix_punct")
        fx_remove_filler = st.checkbox("إزالة الحشو الواضح", value=True, key="fx_remove_filler")
        fx_normalize_ws = st.checkbox("تطبيع المسافات والأسطر", value=True, key="fx_normalize_ws")
    with col_fix_b:
        fx_h1_to_h2 = st.checkbox("H1→H2", value=True, key="fx_h1_to_h2")
        fx_h4_to_h3 = st.checkbox("H4+→H3", value=True, key="fx_h4_to_h3")
        fx_autonumber = st.checkbox("ترقيم تلقائي H2/H3", value=False, key="fx_autonumber")

    if st.button("🚑 طبّق دفعة الإصلاح الآن"):
        if not result or not result.get("article"):
            st.error("لا يوجد مقال مُولد بعد.")
        else:
            with st.spinner("تطبيق الدفعة…"):
                # 1) تنظيف
                cleaned = clean_article(
                    result["article"],
                    remove_filler=fx_remove_filler,
                    aggressive=False,
                    fix_punct=fx_fix_punct,
                    normalize_ws=fx_normalize_ws,
                )
                article_fx = cleaned["cleaned"]
                rep_clean = cleaned["report"]

                # 2) Normalize Headings
                nh = normalize_headings(
                    article_fx,
                    h1_to_h2=fx_h1_to_h2,
                    h4plus_to_h3=fx_h4_to_h3,
                    unify_space_after_hash=True,
                    trim_trailing_punct=True,
                    collapse_spaces=True,
                    remove_consecutive_duplicates=True,
                    autonumber=fx_autonumber,
                )
                article_fx = nh["normalized"]
                rep_head = nh["changes"]

                # 3) إعادة توليد الخاتمة
                secs = list_sections(article_fx)
                outro_title = None
                for t, lvl, s, e in secs:
                    if re.fullmatch(r"خاتمة", t):
                        outro_title = t
                        break

                if outro_title:
                    try:
                        article_fx = regenerate_section(
                            article_md=article_fx,
                            section_title=outro_title,
                            keyword=st.session_state.get("keyword", ""),
                            related_keywords=st.session_state.get("related_keywords", []),
                            tone=st.session_state.get("tone", "هادئة"),
                            section_type="outro",
                        )
                        fx_outro_done = True
                    except Exception as e:
                        fx_outro_done = False
                        st.warning(f"تعذّرت إعادة توليد الخاتمة تلقائيًا: {e}")
                else:
                    fx_outro_done = False
                    st.info("لم يتم العثور على قسم «خاتمة». تخطّينا خطوة إعادة توليد الخاتمة.")

                result["article"] = article_fx
                st.session_state["result"] = result

            st.success("✅ تم تطبيق دفعة الإصلاح.")
            st.write("**ملخص الدفعة:**")
            st.write(
                f"- تنظيف: حذف/قص الحشو = {rep_clean['filler_removed']} | تقليص تكرار الترقيم = {rep_clean['repeated_punct_collapsed']} | فواصل عربية = {rep_clean['arabic_comma_applied']}\n"
                f"- Normalize: H1→H2 = {rep_head['h1_to_h2']} | H4+→H3 = {rep_head['h4plus_to_h3']} | حذف مكرر = {rep_head['deduped_headings']} | ترقيم تلقائي = {rep_head['autonumbered']}\n"
                f"- خاتمة مسؤولة: {'تمت' if fx_outro_done else 'تخطّينا/تعذّر'}"
            )
            st.markdown("**المقال بعد الدفعة:**")
            st.markdown(result["article"])

    # ===== دفعة إصلاح مُحسّنة =====
    st.markdown("---")
    st.subheader("🛠️ دفعة إصلاح مُحسّنة (تنظيف + Normalize + تقليل الجزم + إضافة 'متى لا ينطبق' + خاتمة مسؤولة)")

    col_efx_a, col_efx_b = st.columns(2)
    with col_efx_a:
        efx_fix_punct = st.checkbox("تصحيح الترقيم/المسافات", value=True, key="efx_fix_punct")
        efx_remove_filler = st.checkbox("إزالة الحشو الواضح", value=True, key="efx_remove_filler")
        efx_normalize_ws = st.checkbox("تطبيع المسافات والأسطر", value=True, key="efx_normalize_ws")
    with col_efx_b:
        efx_h1_to_h2 = st.checkbox("H1→H2", value=True, key="efx_h1_to_h2")
        efx_h4_to_h3 = st.checkbox("H4+→H3", value=True, key="efx_h4_to_h3")
        efx_autonumber = st.checkbox("ترقيم تلقائي H2/H3", value=False, key="efx_autonumber")

    if st.button("🛠️ طبّق الدفعة المُحسّنة الآن"):
        if not result or not result.get("article"):
            st.error("لا يوجد مقال مُولد بعد.")
        else:
            with st.spinner("تطبيق الدفعة المُحسّنة…"):
                fx = run_enhanced_fix(
                    result["article"],
                    keyword=st.session_state.get("keyword", ""),
                    related_keywords=st.session_state.get("related_keywords", []),
                    tone=st.session_state.get("tone", "هادئة"),
                    clean_opts={
                        "remove_filler": efx_remove_filler,
                        "aggressive": False,
                        "fix_punct": efx_fix_punct,
                        "normalize_ws": efx_normalize_ws,
                    },
                    heading_opts={
                        "h1_to_h2": efx_h1_to_h2,
                        "h4plus_to_h3": efx_h4_to_h3,
                        "unify_space_after_hash": True,
                        "trim_trailing_punct": True,
                        "collapse_spaces": True,
                        "remove_consecutive_duplicates": True,
                        "autonumber": efx_autonumber,
                    }
                )
                result["article"] = fx["article"]
                st.session_state["result"] = result

            st.success("✅ تم تطبيق الدفعة المُحسّنة.")
            rep2 = fx["reports"]
            st.write("**ملخص الدفعة المُحسّنة:**")
            st.write(
                f"- تنظيف: حذف/قص الحشو = {rep2['clean']['filler_removed']} | تكرار ترقيم = {rep2['clean']['repeated_punct_collapsed']} | فواصل عربية = {rep2['clean']['arabic_comma_applied']}\n"
                f"- Normalize: H1→H2 = {rep2['headings']['h1_to_h2']} | H4+→H3 = {rep2['headings']['h4plus_to_h3']} | حذف مكرر = {rep2['headings']['deduped_headings']} | ترقيم تلقائي = {rep2['headings']['autonumbered']}\n"
                f"- تقليل الجزم: استبدالات = {rep2['soften']['replacements_count']}\n"
                f"- إدراج 'متى لا ينطبق؟': {'تم' if rep2['not_applicable_inserted'] else 'كان موجودًا'}\n"
                f"- خاتمة مسؤولة: {'تمت' if rep2['outro_regenerated'] else 'تخطّينا/تعذّر'}"
            )
            st.markdown("**المقال بعد الدفعة المُحسّنة:**")
            st.markdown(result["article"])

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

    # ===== مؤشّر تنوّع الأسلوب =====
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

        top_sim = srep.get("top_similar", [])
        if top_sim:
            st.write("**أعلى المقالات تشابهًا:**")
            for i, item in enumerate(top_sim, 1):
                st.write(f"{i}. {item['title']} — similarity: {item['similarity']}")
        else:
            st.caption("لا توجد مقالات متشابهة بدرجة ملحوظة.")

        sugg = srep.get("suggestions", [])
        if sugg:
            st.write("**توصيات تقليل التشابه:**")
            for s in sugg:
                st.write(f"• {s}")
        else:
            st.caption("لا توجد توصيات — التنوع جيد 👍")
    else:
        st.caption("لم يتم إدخال مقالات سابقة للمقارنة الأسلوبية.")

    # ===== تحرير قسم محدد (أزرار سريعة + تحديد يدوي) =====
    st.markdown("---")
    st.subheader("✍️ إعادة توليد قسم محدد")

    secs = list_sections(result["article"])
    if not secs:
        st.caption("لا توجد عناوين H2/H3 لاختيار قسم.")
    else:
        titles = [t for (t, lvl, s, e) in secs]

        # أزرار سريعة
        quick_defs = [
            ("افتتاحية", "intro",  None, [r"افتتاحية"]),
            ("لماذا قد يظهر الرمز؟", "why", None, [r"لماذا\s+قد\s+يظهر\s+الرمز\؟?"]),
            ("متى لا ينطبق التفسير؟", "not_applicable", None, [r"متى\s+لا\s+ينطبق\s+التفسير\؟?"]),
            ("سيناريوهات واقعية", "scenarios", st.session_state.get("scenarios_count", 3), [r"سيناريوهات\s+واقعية"]),
            ("أسئلة شائعة", "faq", st.session_state.get("faq_count", 4), [r"أسئلة\s+شائعة"]),
            ("مقارنة دقيقة", "comparison", None, [r"مقارنة\s+دقيقة"]),
            ("منهجية التفسير", "methodology", None, [r"منهجية\s+التفسير"]),
            ("خاتمة", "outro", None, [r"خاتمة", r"الخلاصة"]),
        ]

        st.write("**أزرار سريعة:**")
        cols = st.columns(4)
        for i, (label, sec_type, target_count, patterns) in enumerate(quick_defs):
            col = cols[i % 4]
            with col:
                if st.button(label):
                    # البحث عن العنوان المطابق
                    picked_title = None
                    for t in titles:
                        for pat in patterns:
                            if re.fullmatch(pat, t):
                                picked_title = t
                                break
                        if picked_title:
                            break
                    if not picked_title:
                        st.warning(f"لم يتم العثور على قسم بعنوان «{label}».")
                    else:
                        with st.spinner(f"إعادة توليد قسم: {picked_title} …"):
                            try:
                                new_article = regenerate_section(
                                    article_md=result["article"],
                                    section_title=picked_title,
                                    keyword=st.session_state.get("keyword", ""),
                                    related_keywords=st.session_state.get("related_keywords", []),
                                    tone=st.session_state.get("tone", "هادئة"),
                                    section_type=sec_type,
                                    # تم تمرير target_count لِـfaq/scenarios تلقائيًا داخل الدالة (إن كانت تدعمه)
                                )
                                result["article"] = new_article
                                st.session_state["result"] = result
                                st.success(f"تم تحديث قسم «{picked_title}».")
                            except Exception as e:
                                st.error(f"تعذّرت إعادة توليد القسم: {e}")

        st.markdown("— أو —")

        # اختيار يدوي
        manual_title = st.selectbox("اختر عنوان قسم لإعادة توليده:", titles)
        manual_type = st.selectbox(
            "نوع القسم (يساعد النموذج على التوليد الأنسب):",
            ["intro", "why", "not_applicable", "scenarios", "faq", "comparison", "methodology", "outro"],
            index=0
        )
        manual_extra = ""
        if manual_type in ("scenarios", "faq"):
            manual_extra = st.text_input("بارامترات إضافية (اختياري): عدد العناصر (مثال: 3)")

        if st.button("🔁 أعد توليد القسم المحدد"):
            with st.spinner("يتم إعادة توليد القسم..."):
                try:
                    # تمرير العدد إن أُدخل
                    extra_kwargs = {}
                    if manual_type in ("scenarios", "faq"):
                        try:
                            n = int(manual_extra.strip()) if manual_extra.strip() else None
                            if n:
                                extra_kwargs["target_count"] = n
                        except Exception:
                            pass

                    updated = regenerate_section(
                        article_md=result["article"],
                        section_title=manual_title,
                        keyword=st.session_state.get("keyword", ""),
                        related_keywords=st.session_state.get("related_keywords", []),
                        tone=st.session_state.get("tone", "هادئة"),
                        section_type=manual_type,
                        **extra_kwargs
                    )
                    result["article"] = updated
                    st.session_state["result"] = result
                    st.success("✅ تم تحديث القسم بنجاح.")
                    st.markdown("**المقال بعد التعديل:**")
                    st.markdown(result["article"])
                except Exception as e:
                    st.error(f"حدث خطأ: {e}")
