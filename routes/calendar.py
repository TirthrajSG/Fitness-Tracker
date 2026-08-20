import calendar as cal
from datetime import date
from flask import Blueprint, render_template, request

from models import WeightEntry, FoodLog, Workout, Settings
from services import nutrition_analysis as na

bp = Blueprint("calendar", __name__, url_prefix="/calendar")


@bp.route("/")
def index():
    today = date.today()
    year = request.args.get("year", type=int, default=today.year)
    month = request.args.get("month", type=int, default=today.month)

    settings = Settings.query.first()
    first_day = date(year, month, 1)
    days_in_month = cal.monthrange(year, month)[1]
    last_day = date(year, month, days_in_month)

    weight_days = {e.date for e in WeightEntry.query.filter(
        WeightEntry.date >= first_day, WeightEntry.date <= last_day)}
    workout_days = {w.date for w in Workout.query.filter(
        Workout.date >= first_day, Workout.date <= last_day)}

    logs = FoodLog.query.filter(FoodLog.date >= first_day, FoodLog.date <= last_day).all()
    by_day = na.totals_by_day(logs)
    nutrition_days = set(by_day.keys())
    protein_met_days = {
        d for d, totals in by_day.items()
        if settings.protein_target and totals["protein"] >= settings.protein_target
    }

    cal.setfirstweekday(cal.MONDAY)
    weeks = cal.monthcalendar(year, month)

    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year
    next_month = month % 12 + 1
    next_year = year + 1 if month == 12 else year

    return render_template(
        "calendar.html", weeks=weeks, year=year, month=month,
        month_name=cal.month_name[month], weight_days=weight_days,
        workout_days=workout_days, nutrition_days=nutrition_days,
        protein_met_days=protein_met_days, today=today,
        prev_month=prev_month, prev_year=prev_year,
        next_month=next_month, next_year=next_year,
    )
