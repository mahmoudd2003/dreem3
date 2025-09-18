# utils/heading_tools.py
# ---------------------------------------------------
# أدوات لتطبيع عناوين الماركداون:
# - حصر العناوين في H2/H3 (## / ###)
# - تحويل H1 إلى H2، وإنزال H4+ إلى H3
# - توحيد المسافات بعد #، وإزالة مسافات/ترقيم زائدة
# - إزالة العناوين المكررة المتتالية
# - (اختياري) ترقيم تلقائي للأقسام H2/H3
#
# ملاحظات:
# - لا نغيّر نصوص الفقرات؛ فقط أسطر العناوين.
# - “الترقيم” يضيف بادئة رقمية مثل "1. " لعناوين H2 و"1.1 " لعناوين H3 إذا فُعّل.
# ---------------------------------------------------

from __future__ import annotations
import re
from typing import Dict, List, Tuple

HLINE_RE = re.compile(r"^(#{1,6})\s*(.+?)\s*$", re.MULTILINE)  # #..###### + النص
TRAIL_PUNCT_RE = re.compile(r"[،,:;.!؟…\-—]+$")  # يحذف علامات ترقيم في نهاية العنوان

def _clean_heading_text(text: str, trim_trailing_punct: bool, collapse_spaces: bool) -> str:
    s = text.strip()
    if collapse_spaces:
        s = re.sub(r"\s{2,}", " ", s)
    if trim_trailing_punct:
        s = TRAIL_PUNCT_RE.sub("", s).strip()
    return s

def _dedupe_consecutive(headings: List[Tuple[str,int,int,int]]) -> List[int]:
    """
    يرجع فهارس العناوين التي يجب حذفها (مكررة مباشرة).
    كل عنصر: (title, level, start, end)
    """
    to_remove = []
    prev_title = None
    prev_level = None
    for idx, (title, level, s, e) in enumerate(headings):
        if prev_title == title and prev_level == level:
            to_remove.append(idx)
        else:
            prev_title, prev_level = title, level
    return to_remove

def normalize_headings(
    article_md: str,
    *,
    h1_to_h2: bool = True,
    h4plus_to_h3: bool = True,
    unify_space_after_hash: bool = True,
    trim_trailing_punct: bool = True,
    collapse_spaces: bool = True,
    remove_consecutive_duplicates: bool = True,
    autonumber: bool = False,
) -> Dict[str, object]:
    """
    يعيد:
      - normalized: النص بعد التطبيع
      - changes: إحصاءات
    """
    text = article_md or ""
    changes = {
        "h1_to_h2": 0,
        "h4plus_to_h3": 0,
        "space_after_hash_fixed": 0,
        "trimmed_trailing_punct": 0,
        "collapsed_spaces": 0,
        "deduped_headings": 0,
        "autonumbered": 0,
        "total_headings": 0,
    }

    # نجمع كل العناوين ونبني النص خطوة بخطوة
    out_lines = []
    last_end = 0
    headings: List[Tuple[str,int,int,int]] = []  # (title, level, start, end)

    for m in HLINE_RE.finditer(text):
        hashes = m.group(1)
        raw = m.group(2)
        level = len(hashes)

        # قبل العنوان: أضف النص كما هو
        out_lines.append(text[last_end:m.start()])

        # تحجيم المستوى
        orig_level = level
        if h1_to_h2 and level == 1:
            level = 2
            if level != orig_level:
                changes["h1_to_h2"] += 1

        if h4plus_to_h3 and level >= 4:
            level = 3
            if level != orig_level:
                changes["h4plus_to_h3"] += 1

        # تنظيف نص العنوان
        cleaned = _clean_heading_text(raw, trim_trailing_punct, collapse_spaces)
        if trim_trailing_punct and cleaned != raw and TRAIL_PUNCT_RE.search(raw or ""):
            changes["trimmed_trailing_punct"] += 1
        if collapse_spaces and re.search(r"\s{2,}", raw or ""):
            changes["collapsed_spaces"] += 1

        # توحيد المسافة بعد # (##Title → ## Title)
        hashes_norm = "#" * level
        hline = f"{hashes_norm} {cleaned}" if unify_space_after_hash else f"{hashes_norm}{cleaned}"
        if unify_space_after_hash and (m.group(0).startswith(hashes_norm) and not m.group(0).startswith(hashes_norm + " ")):
            changes["space_after_hash_fixed"] += 1

        # احفظ العنوان
        headings.append((cleaned, level, len("".join(out_lines)), len("".join(out_lines)) + len(hline)))
        out_lines.append(hline + "\n")
        last_end = m.end()

    # أضف بقية النص بعد آخر عنوان
    out_lines.append(text[last_end:])

    normalized = "".join(out_lines)
    changes["total_headings"] = len(headings)

    # إزالة العناوين المكررة المتتالية (نحتاج تمريرة ثانية)
    if remove_consecutive_duplicates and headings:
        # نبني من جديد بدون المكررات
        remove_idx = set(_dedupe_consecutive(headings))
        if remove_idx:
            changes["deduped_headings"] = len(remove_idx)
            rebuilt = []
            cur_idx = 0
            for m in HLINE_RE.finditer(normalized):
                # نص قبل هذا العنوان
                rebuilt.append(normalized[cur_idx:m.start()])
                hashes = m.group(1); raw = m.group(2)
                idx = len(re.findall(HLINE_RE, normalized[:m.start()]))  # index تقديري
                if idx in remove_idx:
                    # نتجاهل هذا العنوان: لا نضيف سطر العنوان
                    cur_idx = m.end()
                    continue
                rebuilt.append(m.group(0) + "\n")
                cur_idx = m.end()
            rebuilt.append(normalized[cur_idx:])
            normalized = "".join(rebuilt)

    # ترقيم تلقائي
    if autonumber and changes["total_headings"] > 0:
        lines = normalized.splitlines(keepends=False)
        h2_idx = 0
        h3_idx = 0
        for i, ln in enumerate(lines):
            m = re.match(r"^(##{1,2})\s+(.+)$", ln)
            if not m:
                continue
            marks = m.group(1)
            title = m.group(2).strip()
            if marks == "##":
                h2_idx += 1
                h3_idx = 0
                # أزل أي ترقيم سابق في البداية مثل "1. " أو "1.1 "
                title_clean = re.sub(r"^\d+(\.\d+)?\s+", "", title)
                lines[i] = f"## {h2_idx}. {title_clean}"
                changes["autonumbered"] += 1
            elif marks == "###":
                h3_idx += 1
                title_clean = re.sub(r"^\d+(\.\d+)?\s+", "", title)
                lines[i] = f"### {h2_idx}.{h3_idx} {title_clean}"
                changes["autonumbered"] += 1
        normalized = "\n".join(lines) + "\n"

    return {"normalized": normalized, "changes": changes}
