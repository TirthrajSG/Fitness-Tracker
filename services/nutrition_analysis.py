from datetime import timedelta
from statistics import mean


def daily_totals(logs):
    totals = {"calories": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0, "fiber": 0.0}
    for log in logs:
        totals["calories"] += log.calories or 0
        totals["protein"] += log.protein or 0
        totals["carbs"] += log.carbs or 0
        totals["fat"] += log.fat or 0
        totals["fiber"] += log.fiber or 0
    return {k: round(v, 1) for k, v in totals.items()}


def totals_by_day(logs):
    by_day = {}
    for log in logs:
        by_day.setdefault(log.date, []).append(log)
    return {d: daily_totals(entries) for d, entries in by_day.items()}


def weekly_summary(logs, calorie_target, protein_target, days=7):
    by_day = totals_by_day(logs)
    if not by_day:
        return {
            "avg_calories": None, "avg_protein": None, "avg_carbs": None,
            "avg_fat": None, "avg_fiber": None,
            "days_within_calorie_target": 0, "days_meeting_protein_target": 0,
            "days_logged": 0,
        }
    days_list = sorted(by_day.keys())[-days:]
    cals = [by_day[d]["calories"] for d in days_list]
    prots = [by_day[d]["protein"] for d in days_list]
    carbs = [by_day[d]["carbs"] for d in days_list]
    fats = [by_day[d]["fat"] for d in days_list]
    fibers = [by_day[d]["fiber"] for d in days_list]

    within_cal = 0
    if calorie_target:
        within_cal = sum(1 for c in cals if abs(c - calorie_target) <= calorie_target * 0.05)

    meeting_protein = 0
    if protein_target:
        meeting_protein = sum(1 for p in prots if p >= protein_target)

    return {
        "avg_calories": round(mean(cals), 1),
        "avg_protein": round(mean(prots), 1),
        "avg_carbs": round(mean(carbs), 1),
        "avg_fat": round(mean(fats), 1),
        "avg_fiber": round(mean(fibers), 1),
        "days_within_calorie_target": within_cal,
        "days_meeting_protein_target": meeting_protein,
        "days_logged": len(days_list),
    }


def bmr_mifflin_st_jeor(sex, weight_kg, height_cm, age):
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if sex == "male" else base - 161


ACTIVITY_MULTIPLIERS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}


def estimate_tdee(sex, weight_kg, height_cm, age, activity_level):
    bmr = bmr_mifflin_st_jeor(sex, weight_kg, height_cm, age)
    multiplier = ACTIVITY_MULTIPLIERS.get(activity_level, 1.55)
    return round(bmr * multiplier)


def observed_deficit_from_trend(weekly_weight_change_kg):
    """Rough estimate: 1 kg of body fat ~= 7700 kcal. Returns approximate
    average daily calorie deficit (positive) or surplus (negative)."""
    if weekly_weight_change_kg is None:
        return None
    daily_change = weekly_weight_change_kg / 7.0
    return round(-daily_change * 7700, 0)
