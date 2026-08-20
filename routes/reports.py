from datetime import date, timedelta
from flask import Blueprint, render_template, request, jsonify

from models import db, Settings, WeightEntry, FoodLog, Workout, WorkoutExercise, Exercise, SetEntry
from services import weight_analysis as wa
from services import nutrition_analysis as na
from services import workout_analysis as wka

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.route("/weekly")
def weekly():
    settings = Settings.query.first()
    today = date.today()
    week_start = today - timedelta(days=6)

    weight_entries = WeightEntry.query.filter(
        WeightEntry.date >= week_start - timedelta(days=30)).order_by(WeightEntry.date).all()
    daily = wa.daily_series_with_averages(weight_entries)
    week_points = [p for p in daily if p["date"] >= week_start]

    start_weight = week_points[0]["weight"] if week_points else None
    end_weight = week_points[-1]["weight"] if week_points else None
    weight_change = round(end_weight - start_weight, 2) if start_weight and end_weight else None
    avg_weight = round(sum(p["weight"] for p in week_points) / len(week_points), 2) if week_points else None

    logs = FoodLog.query.filter(FoodLog.date >= week_start, FoodLog.date <= today).all()
    nutrition = na.weekly_summary(logs, settings.calorie_target, settings.protein_target, days=7)

    workouts = Workout.query.filter(Workout.date >= week_start, Workout.date <= today).all()
    total_volume = 0
    for w in workouts:
        for we in w.exercises:
            for s in we.sets:
                total_volume += s.volume

    strength_changes = []
    exercises = Exercise.query.all()
    for ex in exercises:
        rows = wka.exercise_history(db, Exercise, WorkoutExercise, Workout, SetEntry, ex.id)
        progression = wka.progression_series(rows)
        recent = [s for s in progression if s["date"] >= week_start]
        older = [s for s in progression if s["date"] < week_start]
        if recent and older:
            change = round(recent[-1]["estimated_1rm"] - older[-1]["estimated_1rm"], 2)
            if change != 0:
                strength_changes.append({"exercise": ex.name, "change": change})

    weekly_rate = wa.weekly_rate(weight_entries, days_back=28)
    status = wa.goal_status(-abs(settings.desired_weekly_rate_kg or 0), weekly_rate)

    return render_template(
        "weekly_report.html", week_start=week_start, week_end=today,
        start_weight=start_weight, end_weight=end_weight, weight_change=weight_change,
        avg_weight=avg_weight, nutrition=nutrition, workouts=workouts,
        total_volume=total_volume, strength_changes=strength_changes, status=status,
        settings=settings,
    )


@bp.route("/trends")
def trends():
    entries = WeightEntry.query.order_by(WeightEntry.date).all()
    daily = wa.daily_series_with_averages(entries)

    recent = daily[-10:] if len(daily) >= 2 else daily
    range_low = min(p["weight"] for p in recent) if recent else None
    range_high = max(p["weight"] for p in recent) if recent else None

    slope, _, r = wa.linear_trend(entries, days_back=28)
    week_rate = round(slope * 7, 3) if slope is not None else None
    vol = wa.volatility(entries, days_back=14)
    plateau = wa.detect_plateau(entries)

    summary = None
    if range_low is not None and week_rate is not None:
        direction = "decreasing" if week_rate < 0 else "increasing" if week_rate > 0 else "stable"
        summary = (
            f"Your weight has fluctuated between {range_low}-{range_high} kg during the last "
            f"{len(recent)} days, but your underlying trend is {direction} at approximately "
            f"{abs(week_rate)} kg/week."
        )

    return render_template(
        "trends.html", range_low=range_low, range_high=range_high, week_rate=week_rate,
        volatility=vol, plateau=plateau, summary=summary, r_value=r, has_data=len(daily) >= 2,
    )


@bp.route("/strength-vs-weight")
def strength_vs_weight():
    exercises = Exercise.query.order_by(Exercise.name).all()
    selected_id = request.args.get("exercise_id", type=int)
    if not selected_id and exercises:
        selected_id = exercises[0].id
    return render_template("strength_vs_weight.html", exercises=exercises, selected_id=selected_id)


@bp.route("/strength-vs-weight/chart-data")
def strength_vs_weight_data():
    exercise_id = request.args.get("exercise_id", type=int)
    weight_entries = WeightEntry.query.order_by(WeightEntry.date).all()
    daily_weight = wa.daily_series_with_averages(weight_entries)

    rows = wka.exercise_history(db, Exercise, WorkoutExercise, Workout, SetEntry, exercise_id)
    progression = wka.progression_series(rows)

    weight_by_date = {p["date"]: p["avg_7"] or p["weight"] for p in daily_weight}

    labels = [s["date"].isoformat() for s in progression]
    strength = [s["estimated_1rm"] for s in progression]
    weight = [weight_by_date.get(s["date"]) for s in progression]

    interpretation = None
    if len(progression) >= 2 and len(daily_weight) >= 2:
        w_change = daily_weight[-1]["weight"] - daily_weight[0]["weight"]
        s_change = progression[-1]["estimated_1rm"] - progression[0]["estimated_1rm"]
        if w_change < 0 and s_change >= 0:
            interpretation = "Weight is decreasing while estimated strength is holding or increasing — a good sign for this cutting phase."
        elif w_change < 0 and s_change < 0:
            interpretation = "Weight is decreasing and estimated strength is also decreasing — worth watching, consider more protein or recovery."
        elif w_change >= 0:
            interpretation = "Weight is not decreasing over this window."

    return jsonify({"labels": labels, "strength": strength, "weight": weight, "interpretation": interpretation})


@bp.route("/calorie-vs-weight")
def calorie_vs_weight():
    return render_template("calorie_vs_weight.html")


@bp.route("/calorie-vs-weight/chart-data")
def calorie_vs_weight_data():
    days = int(request.args.get("days", 30))
    cutoff = date.today() - timedelta(days=days - 1)

    weight_entries = WeightEntry.query.filter(WeightEntry.date >= cutoff).order_by(WeightEntry.date).all()
    daily_weight = wa.daily_series_with_averages(
        WeightEntry.query.order_by(WeightEntry.date).all())
    daily_weight = [p for p in daily_weight if p["date"] >= cutoff]

    logs = FoodLog.query.filter(FoodLog.date >= cutoff).all()
    by_day = na.totals_by_day(logs)

    labels = [p["date"].isoformat() for p in daily_weight]
    calories = [by_day.get(p["date"], {"calories": None})["calories"] for p in daily_weight]
    weight = [p["weight"] for p in daily_weight]

    week_rate = wa.weekly_rate(weight_entries, days_back=days)
    observed_deficit = na.observed_deficit_from_trend(week_rate)
    avg_calories = None
    vals = [c for c in calories if c is not None and c > 0]
    if vals:
        avg_calories = round(sum(vals) / len(vals), 1)

    return jsonify({
        "labels": labels, "calories": calories, "weight": weight,
        "avg_calories": avg_calories, "observed_deficit": observed_deficit,
        "week_rate": week_rate,
    })
