from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models import db, Food, FoodLog, Settings, WeightEntry
from services import nutrition_analysis as na

bp = Blueprint("nutrition", __name__, url_prefix="/nutrition")

MEALS = ["breakfast", "lunch", "dinner", "snack", "other"]


@bp.route("/")
@login_required
def index():
    uid = current_user.id
    settings = Settings.query.filter_by(user_id=uid).first()
    day_str = request.args.get("date")
    the_date = datetime.strptime(day_str, "%Y-%m-%d").date() if day_str else date.today()

    logs = FoodLog.query.filter_by(user_id=uid, date=the_date).order_by(FoodLog.meal).all()
    logs_by_meal = {m: [l for l in logs if l.meal == m] for m in MEALS}
    totals = na.daily_totals(logs)

    week_start = the_date - timedelta(days=6)
    week_logs = FoodLog.query.filter(
        FoodLog.user_id == uid, FoodLog.date >= week_start, FoodLog.date <= the_date).all()
    weekly = na.weekly_summary(week_logs, settings.calorie_target, settings.protein_target, days=7)

    foods = Food.query.filter_by(user_id=uid).order_by(Food.name).all()

    return render_template(
        "nutrition.html", the_date=the_date, logs_by_meal=logs_by_meal, totals=totals,
        weekly=weekly, foods=foods, meals=MEALS, settings=settings,
        prev_date=the_date - timedelta(days=1), next_date=the_date + timedelta(days=1),
    )


@bp.route("/log", methods=["POST"])
@login_required
def log_food():
    uid = current_user.id
    try:
        the_date = datetime.strptime(request.form["date"], "%Y-%m-%d").date()
        meal = request.form["meal"]
        if meal not in MEALS:
            raise ValueError("Invalid meal")
        quantity = float(request.form.get("quantity", 1))
        if quantity <= 0:
            raise ValueError("Quantity must be positive")

        food_id = request.form.get("food_id")
        if food_id:
            food = Food.query.filter_by(id=int(food_id), user_id=uid).first_or_404()
            factor = quantity / food.serving_size if food.serving_size else quantity
            log = FoodLog(
                user_id=uid, date=the_date, meal=meal, food_id=food.id, food_name=food.name, quantity=quantity,
                calories=round(food.calories * factor, 1), protein=round(food.protein * factor, 1),
                carbs=round(food.carbs * factor, 1), fat=round(food.fat * factor, 1),
                fiber=round(food.fiber * factor, 1),
            )
        else:
            # Quick manual log without saving to the food database
            log = FoodLog(
                user_id=uid, date=the_date, meal=meal,
                food_name=request.form.get("food_name", "Custom entry").strip(),
                quantity=1, calories=float(request.form.get("calories", 0)),
                protein=float(request.form.get("protein", 0) or 0),
                carbs=float(request.form.get("carbs", 0) or 0),
                fat=float(request.form.get("fat", 0) or 0),
                fiber=float(request.form.get("fiber", 0) or 0),
            )
        db.session.add(log)
        db.session.commit()
        flash("Food logged.", "success")
    except (ValueError, KeyError) as e:
        flash(f"Could not log food: {e}", "danger")
    return redirect(url_for("nutrition.index", date=request.form.get("date")))


@bp.route("/log/delete/<int:log_id>", methods=["POST"])
@login_required
def delete_log(log_id):
    log = FoodLog.query.filter_by(id=log_id, user_id=current_user.id).first_or_404()
    the_date = log.date.isoformat()
    db.session.delete(log)
    db.session.commit()
    flash("Log entry removed.", "info")
    return redirect(url_for("nutrition.index", date=the_date))


@bp.route("/foods")
@login_required
def foods():
    search = request.args.get("q", "")
    query = Food.query.filter_by(user_id=current_user.id)
    if search:
        query = query.filter(Food.name.ilike(f"%{search}%"))
    all_foods = query.order_by(Food.name).all()
    return render_template("foods.html", foods=all_foods, search=search)


@bp.route("/foods/add", methods=["POST"])
@login_required
def add_food():
    try:
        food = Food(
            user_id=current_user.id,
            name=request.form["name"].strip(),
            serving_size=float(request.form.get("serving_size", 1) or 1),
            serving_unit=request.form.get("serving_unit", "serving").strip(),
            calories=float(request.form["calories"]),
            protein=float(request.form.get("protein", 0) or 0),
            carbs=float(request.form.get("carbs", 0) or 0),
            fat=float(request.form.get("fat", 0) or 0),
            fiber=float(request.form.get("fiber", 0) or 0),
        )
        db.session.add(food)
        db.session.commit()
        flash("Food added.", "success")
    except (ValueError, KeyError) as e:
        flash(f"Could not add food: {e}", "danger")
    return redirect(url_for("nutrition.foods"))


@bp.route("/foods/edit/<int:food_id>", methods=["POST"])
@login_required
def edit_food(food_id):
    food = Food.query.filter_by(id=food_id, user_id=current_user.id).first_or_404()
    try:
        food.name = request.form["name"].strip()
        food.serving_size = float(request.form.get("serving_size", 1) or 1)
        food.serving_unit = request.form.get("serving_unit", "serving").strip()
        food.calories = float(request.form["calories"])
        food.protein = float(request.form.get("protein", 0) or 0)
        food.carbs = float(request.form.get("carbs", 0) or 0)
        food.fat = float(request.form.get("fat", 0) or 0)
        food.fiber = float(request.form.get("fiber", 0) or 0)
        db.session.commit()
        flash("Food updated.", "success")
    except (ValueError, KeyError) as e:
        flash(f"Could not update food: {e}", "danger")
    return redirect(url_for("nutrition.foods"))


@bp.route("/foods/delete/<int:food_id>", methods=["POST"])
@login_required
def delete_food(food_id):
    food = Food.query.filter_by(id=food_id, user_id=current_user.id).first_or_404()
    db.session.delete(food)
    db.session.commit()
    flash("Food deleted.", "info")
    return redirect(url_for("nutrition.foods"))


@bp.route("/calorie-calculator", methods=["GET", "POST"])
@login_required
def calorie_calculator():
    result = None
    if request.method == "POST":
        try:
            sex = request.form["sex"]
            weight = float(request.form["weight"])
            height = float(request.form["height"])
            age = int(request.form["age"])
            activity = request.form["activity_level"]
            goal = request.form["goal"]  # lose / maintain / gain

            tdee = na.estimate_tdee(sex, weight, height, age, activity)
            if goal == "lose":
                target = tdee - 500
            elif goal == "gain":
                target = tdee + 300
            else:
                target = tdee
            result = {"tdee": tdee, "target": round(target)}
        except (ValueError, KeyError) as e:
            flash(f"Invalid inputs: {e}", "danger")
    return render_template("calorie_calculator.html", result=result)


@bp.route("/chart-data")
@login_required
def chart_data():
    uid = current_user.id
    days = int(request.args.get("days", 30))
    settings = Settings.query.filter_by(user_id=uid).first()
    cutoff = date.today() - timedelta(days=days - 1)
    logs = FoodLog.query.filter(FoodLog.user_id == uid, FoodLog.date >= cutoff).all()
    by_day = na.totals_by_day(logs)

    labels = []
    calories = []
    protein = []
    d = cutoff
    while d <= date.today():
        labels.append(d.isoformat())
        totals = by_day.get(d, {"calories": 0, "protein": 0})
        calories.append(totals["calories"])
        protein.append(totals["protein"])
        d += timedelta(days=1)

    return jsonify({
        "labels": labels, "calories": calories, "protein": protein,
        "calorie_target": settings.calorie_target, "protein_target": settings.protein_target,
    })
