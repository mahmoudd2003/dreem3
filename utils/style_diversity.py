# utils/style_diversity.py
# ---------------------------------------------------
# مؤشر تنوّع الأسلوب:
# - قياس تشابه المقال الحالي مع مقالات سابقة عبر Jaccard 3-grams (أسلوب بسيط وفعّال).
# - مقاييس إضافية: تنوّع المفردات، متوسط طول الجمل، كثافة علامات الترقيم.
# - تقرير نهائي بمستوى المخاطر وتوصيات تخفيف التشابه.

from __future__ import annotations
from typing import List, Dict, Any
import re
import json
from statistics import mean

# تقسيم مبسّط للكلمات العربية/اللاتينية
TOKEN_RE = re.compile(r"[A-Za-z\u0600-\u06FF]+")

def _normalize(text: str) -> List[str]:
    text = (text or "").lower()
    text = re.sub(r"[ًٌٍَُِّْـ]", "", text)  # إزالة التشكيل
    return TOKEN_RE.findall(text)

def _sentences(text: str) -> List[str]:
    # تقطيع جُمَل بسيط
    return [s.strip() for s in re.split(r"[.!؟\n]+", text or "") if s.strip()]

def _punct_density(text: str) -> float:
    if not text:
        return 0.0
    punct = re.findall(r"[،,.؛:!؟\-—]", text)
    return round(len(punct) / max(1, len(text)), 4)

def _ttr(tokens: List[str]) -> float:
    # Type-Token Ratio: تنوّع المفردات
    if not tokens:
        return 0.0
    return round(len(set(tokens)) / len(tokens), 4)

def _make_ngrams(tokens: List[str], n: int = 3) -> List[str]:
    if len(tokens) < n:
        return []
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]

def jaccard(a: List[str], b: List[str]) -> float:
    A, B = set(a), set(b)
    if not A and not B:
        return 0.0
    return round(len(A & B) / max(1, len(A | B)), 4)

def parse_corpus(raw: str) -> List[Dict[str, str]]:
    """
    يقبل أحد الشكلين:
    1) JSON: [{"title":"...","content":"..."}, ...]
    2) نص متعدد يفصل بينه '---'، حيث السطر الأول عنوان والباقي محتوى.
    """
    if not raw or not raw.strip():
        return []
    # حاول JSON أولًا
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            out = []
            for it in data:
                title = str(it.get("title", "")).strip()
                content = str(it.get("content", "")).strip()
                if content:
                    out.append({"title": title or "(بدون عنوان)", "content": content})
            if out:
                return out
    except Exception:
        pass

    # fallback: تقسيم بــ '---'
    parts = [p.strip() for p in raw.split('---') if p.strip()]
    out = []
    for chunk in parts:
        lines = chunk.splitlines()
        if not lines:
            continue
        title = lines[0].strip() if lines[0].strip() else "(بدون عنوان)"
        content = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        if content:
            out.append({"title": title, "content": content})
    return out

def style_diversity_report(current_article: str, corpus_raw: str, top_k: int = 5) -> Dict[str, Any]:
    """
    يُنتج تقرير تنوّع أسلوبي:
    - أعلى المقالات تشابهًا (Jaccard 3-grams).
    - متوسط التشابه العام.
    - مؤشرات أسلوبية (TTR، طول الجملة، كثافة الترقيم).
    - تقدير خطر + توصيات.
    """
    report: Dict[str, Any] = {
        "corpus_size": 0,
        "top_similar": [],
        "avg_similarity": 0.0,
        "style_metrics": {},
        "risk_level": "منخفض",
        "suggestions": [],
        "notes": [
            "القياس تقريبي. نوصي بإعادة الصياغة في حال التشابه العالي.",
            "يمكن لاحقًا استخدام تطابق دلالي متقدّم (TF-IDF أو Embeddings) إذا رغبت."
        ]
    }

    corpus = parse_corpus(corpus_raw)
    report["corpus_size"] = len(corpus)
    if not corpus:
        report["notes"].append("لم تُقدّم مقالات سابقة للمقارنة.")
        return report

    cur_tokens = _normalize(current_article)
    cur_3grams = _make_ngrams(cur_tokens, 3)

    sims = []
    pairs = []
    for doc in corpus:
        title = doc.get("title", "(بدون عنوان)")
        content = doc.get("content", "")
        toks = _normalize(content)
        grams = _make_ngrams(toks, 3)
        sim = jaccard(cur_3grams, grams)
        sims.append(sim)
        pairs.append({"title": title, "similarity": sim})

    pairs.sort(key=lambda x: -x["similarity"])
    report["top_similar"] = pairs[:top_k]
    report["avg_similarity"] = round(mean(sims), 4) if sims else 0.0

    # مؤشرات أسلوبية للمقال الحالي
    sents = _sentences(current_article)
    avg_sent_len = round(mean([len(_normalize(s)) for s in sents]), 2) if sents else 0.0
    ttr = _ttr(cur_tokens)
    pden = _punct_density(current_article)

    report["style_metrics"] = {
        "avg_sentence_length_tokens": avg_sent_len,
        "type_token_ratio": ttr,
        "punctuation_density": pden,
        "sentences_count": len(sents),
        "tokens_count": len(cur_tokens),
    }

    # تقدير خطر بسيط
    max_sim = pairs[0]["similarity"] if pairs else 0.0
    risk_points = 0
    if max_sim >= 0.35:  # تشابه مرتفع
        risk_points += 3
    elif max_sim >= 0.25:
        risk_points += 2
    elif max_sim >= 0.18:
        risk_points += 1

    # تنوّع مفردات ضعيف
    if ttr < 0.25:
        risk_points += 1

    if risk_points >= 4:
        report["risk_level"] = "مرتفع"
    elif risk_points >= 2:
        report["risk_level"] = "متوسط"
    else:
        report["risk_level"] = "منخفض"

    # توصيات
    if max_sim >= 0.25:
        report["suggestions"].append(
            "أعد صياغة الفقرات الأكثر شبهًا، وبدّل القوالب الافتتاحية والخاتمة."
        )
    if ttr < 0.25:
        report["suggestions"].append(
            "زِد تنوّع المفردات باستبدال مرادفات وإضافة أمثلة جديدة."
        )
    if avg_sent_len < 8:
        report["suggestions"].append(
            "ارفع متوسط طول الجملة قليلًا بتجميع بعض الجمل القصيرة لخلق إيقاع مختلف."
        )
    if pden < 0.003:
        report["suggestions"].append(
            "استخدم تنويعًا في علامات الترقيم (؛ : —) بعقلانية لكسر النمط."
        )

    return report
