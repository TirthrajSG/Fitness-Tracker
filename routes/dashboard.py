from datetime import date, timedelta
from flask import Blueprint, render_template
from flask_login import login_required, current_user

from models import db, Settings, WeightEntry, FoodLog, Workout, WorkoutExercise, Exercise, SetEntry
from services import weight_analysis as wa
from services import nutrition_analysis as na
from services import workout_analysis as wka

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def index():
    uid = current_user.id
    settings = Settings.query.filter_by(user_id=uid).first()
    today = date.today()

    weight_entries = WeightEntry.query.filter_by(user_id=uid).order_by(WeightEntry.date).all()
    daily = wa.daily_series_with_averages(weight_entries)

    current_weight = daily[-1]["weight"] if daily else None
    avg7 = wa.rolling_average(weight_entries, 7)
    avg30 = wa.rolling_average(weight_entries, 30)
    week_rate = wa.weekly_rate(weight_entries, days_back=28)

    starting = settings.starting_weight_kg
    target = settings.target_weight_kg
    total_lost = (starting - current_weight) if (starting and current_weight) else None
    remaining = (current_weight - target) if (current_weight and target) else None
    pct_complete = None
    if starting is not None and target is not None and current_weight is not None and starting != target:
        pct_complete = max(0, min(100, round((starting - current_weight) / (starting - target) * 100, 1)))

    est_target_date = wa.estimate_target_date(avg7 or current_weight, target, week_rate)

    # Calories today / 7-day
    logs_today = FoodLog.query.filter_by(user_id=uid, date=today).all()
    totals_today = na.daily_totals(logs_today)
    week_start = today - timedelta(days=6)
    logs_week = FoodLog.query.filter(FoodLog.user_id == uid, FoodLog.date >= week_start, FoodLog.date <= today).all()
    nutrition_week = na.weekly_summary(logs_week, settings.calorie_target, settings.protein_target, days=7)

    calories_remaining = None
    if settings.calorie_target is not None:
        calories_remaining = round(settings.calorie_target - totals_today["calories"], 1)
    protein_remaining = None
    if settings.protein_target is not None:
        protein_remaining = round(settings.protein_target - totals_today["protein"], 1)

    calorie_adherence = None
    if nutrition_week["days_logged"]:
        calorie_adherence = round(
            nutrition_week["days_within_calorie_target"] / nutrition_week["days_logged"] * 100, 0)
    protein_adherence = None
    if nutrition_week["days_logged"]:
        protein_adherence = round(
            nutrition_week["days_meeting_protein_target"] / nutrition_week["days_logged"] * 100, 0)

    # Training
    workout_today = Workout.query.filter_by(user_id=uid, date=today).first() is not None
    workouts_this_week = Workout.query.filter(
        Workout.user_id == uid, Workout.date >= week_start, Workout.date <= today).count()
    month_start = today.replace(day=1)
    workouts_this_month = Workout.query.filter(
        Workout.user_id == uid, Workout.date >= month_start, Workout.date <= today).count()

    all_workout_dates = [w.date for w in Workout.query.filter_by(user_id=uid).all()]
    streak = wka.training_streak(all_workout_dates)

    recent_prs = []
    exercises = Exercise.query.filter_by(user_id=uid).all()
    for ex in exercises:
        rows = wka.exercise_history(db, Exercise, WorkoutExercise, Workout, SetEntry, ex.id, uid)
        progression = wka.progression_series(rows)
        prs = wka.detect_prs(progression)
        for event in prs["events"][:1]:
            if event["date"] >= today - timedelta(days=14):
                recent_prs.append({"exercise": ex.name, **event})
    recent_prs.sort(key=lambda e: e["date"], reverse=True)
    recent_prs = recent_prs[:5]

    return render_template(
        "dashboard.html",
        settings=settings,
        current_weight=current_weight,
        starting=starting,
        target=target,
        total_lost=total_lost,
        remaining=remaining,
        pct_complete=pct_complete,
        avg7=avg7,
        avg30=avg30,
        week_rate=week_rate,
        est_target_date=est_target_date,
        totals_today=totals_today,
        calories_remaining=calories_remaining,
        protein_remaining=protein_remaining,
        nutrition_week=nutrition_week,
        calorie_adherence=calorie_adherence,
        protein_adherence=protein_adherence,
        workout_today=workout_today,
        workouts_this_week=workouts_this_week,
        workouts_this_month=workouts_this_month,
        streak=streak,
        recent_prs=recent_prs,
        has_data=bool(weight_entries),
    )
