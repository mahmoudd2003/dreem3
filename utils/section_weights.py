# utils/section_weights.py
# =====================================================
# توزيع الطول على أقسام H2/H3 حسب بروفايلات جاهزة
# - modern_balanced (الافتراضي)
# - modern_slim     (تقليل "حسب حالة الرائي" + "أقوال المفسرين")
# - modern_deep     (تعميق التحليل/السيناريوهات)
# =====================================================

from __future__ import annotations
from typing import Dict, List, Tuple

# مفاتيح الأقسام كما تظهر في العناوين (H2/H3)
H2_KEYS = [
    "خلاصة سريعة",
    "لماذا قد يظهر هذا الرمز؟",
    "متى لا ينطبق التفسير؟",
    "سيناريوهات واقعية",
    "تفسير حسب حالة الرائي (مختصر ومنظم)",
    "أقوال المفسرين (ابن سيرين / النابلسي / ابن شاهين)",
    "أسئلة شائعة",
    "مقارنة دقيقة",
    "منهجية التفسير",
    "مصادر صريحة",
    "خاتمة مسؤولة + تنويه مهني",
]

SUB_KEYS_CASES = ["للعزباء", "للمتزوجة", "للحامل", "للمطلقة", "للرجل"]

Profile = Dict[str, float]

PROFILES: Dict[str, Profile] = {
    # توزيع متوازن
    "modern_balanced": {
        "خلاصة سريعة": 0.05,
        "لماذا قد يظهر هذا الرمز؟": 0.10,
        "متى لا ينطبق التفسير؟": 0.07,
        "سيناريوهات واقعية": 0.13,
        "تفسير حسب حالة الرائي (مختصر ومنظم)": 0.20,  # داخله يتوزع فرعيًا
        "أقوال المفسرين (ابن سيرين / النابلسي / ابن شاهين)": 0.12,
        "أسئلة شائعة": 0.08,
        "مقارنة دقيقة": 0.08,
        "منهجية التفسير": 0.07,
        "مصادر صريحة": 0.03,
        "خاتمة مسؤولة + تنويه مهني": 0.07,
    },
    # يقلّل وزن "حسب حالة الرائي" + "أقوال المفسرين" (طلبك)
    "modern_slim": {
        "خلاصة سريعة": 0.06,
        "لماذا قد يظهر هذا الرمز؟": 0.12,
        "متى لا ينطبق التفسير؟": 0.08,
        "سيناريوهات واقعية": 0.16,
        "تفسير حسب حالة الرائي (مختصر ومنظم)": 0.12,  # مختصر
        "أقوال المفسرين (ابن سيرين / النابلسي / ابن شاهين)": 0.08,  # مختصر
        "أسئلة شائعة": 0.10,
        "مقارنة دقيقة": 0.10,
        "منهجية التفسير": 0.08,
        "مصادر صريحة": 0.04,
        "خاتمة مسؤولة + تنويه مهني": 0.06,
    },
    # يعمّق التحليل والسيناريوهات
    "modern_deep": {
        "خلاصة سريعة": 0.05,
        "لماذا قد يظهر هذا الرمز؟": 0.14,
        "متى لا ينطبق التفسير؟": 0.09,
        "سيناريوهات واقعية": 0.20,
        "تفسير حسب حالة الرائي (مختصر ومنظم)": 0.18,
        "أقوال المفسرين (ابن سيرين / النابلسي / ابن شاهين)": 0.10,
        "أسئلة شائعة": 0.06,
        "مقارنة دقيقة": 0.08,
        "منهجية التفسير": 0.06,
        "مصادر صريحة": 0.02,
        "خاتمة مسؤولة + تنويه مهني": 0.02,
    },
}

def get_profile(name: str) -> Profile:
    name = (name or "modern_balanced").strip().lower()
    return PROFILES.get(name, PROFILES["modern_balanced"])

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def compute_targets(total_words: int, profile_name: str = "modern_balanced") -> Dict[str, int]:
    """
    يرجع قاموس {عنوان H2: عدد كلمات مستهدف} بمجموع ≈ total_words.
    """
    profile = get_profile(profile_name)
    # تأكيد وجود كل المفاتيح، وألا تتجاوز الأوزان 1.0 تقريبًا
    weight_sum = sum(profile.get(k, 0.0) for k in H2_KEYS)
    if weight_sum <= 0.0:
        profile = get_profile("modern_balanced")
        weight_sum = sum(profile.get(k, 0.0) for k in H2_KEYS)

    targets: Dict[str, int] = {}
    accum = 0
    for i, key in enumerate(H2_KEYS):
        w = profile.get(key, 0.0)
        # حماية من قيم شاذة
        w = clamp(w, 0.0, 0.5)
        words = int(round(total_words * (w / weight_sum)))
        # حد أدنى صغير لأقسام حاسمة
        if key in ("مصادر صريحة", "خاتمة مسؤولة + تنويه مهني"):
            words = max(words, 50)
        targets[key] = max(words, 80)  # H2 لا يقل كثيرًا
        accum += targets[key]

    # موازنة بسيطة للاقتراب من المجموع
    diff = total_words - accum
    # وزّع الفرق على الأقسام ذات الوزن الأكبر
    if diff != 0:
        order = sorted(H2_KEYS, key=lambda k: profile.get(k, 0.0), reverse=(diff > 0))
        for k in order:
            if diff == 0:
                break
            bump = 10 if abs(diff) >= 10 else diff
            targets[k] = max(60, targets[k] + bump)
            diff -= bump

    return targets

def format_targets_hint(targets: Dict[str, int]) -> str:
    """
    يُنتج سطور تعليمية تُضمَّن في البرومبت (Hint) ليعرف النموذج ميزانية كل قسم.
    """
    lines: List[str] = ["[ميزانية الكلمات لكل قسم — دليل تقريبي (لا تغيّر العناوين)]"]
    for k in H2_KEYS:
        if k in targets:
            lines.append(f"- {k}: ~{targets[k]} كلمة")
    lines.append("مسموح بفروقات بسيطة، لكن حافظ على التوزيع العام بدون حشو.")
    return "\n".join(lines)

def format_cases_hint(per_case_words: int = 90) -> str:
    """
    يُنتج إشارة لحجم كل حالة فرعية داخل 'تفسير حسب حالة الرائي'.
    """
    lines = ["[إرشاد فرعي — حالة الرائي (H3)]"]
    for s in SUB_KEYS_CASES:
        lines.append(f"- {s}: ~{per_case_words} كلمة")
    lines.append("اختصر بدون تكرار؛ ركّز على المشاعر والسياق.")
    return "\n".join(lines)
