from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash

from models import db, Settings
from services.nutrition_analysis import estimate_tdee

bp = Blueprint("onboarding", __name__)


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    settings = Settings.query.first()
    if settings.onboarded:
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        try:
            settings.name = request.form.get("name", "").strip()
            settings.age = int(request.form["age"])
            settings.sex = request.form["sex"]
            settings.height_cm = float(request.form["height_cm"])
            settings.activity_level = request.form["activity_level"]
            settings.starting_weight_kg = float(request.form["current_weight"])
            settings.target_weight_kg = float(request.form["target_weight"])
            target_date = request.form.get("target_date")
            settings.target_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else None
            settings.desired_weekly_rate_kg = float(request.form.get("desired_weekly_rate", 0.4) or 0.4)

            calorie_target = request.form.get("calorie_target")
            protein_target = request.form.get("protein_target")

            tdee = estimate_tdee(settings.sex, settings.starting_weight_kg,
                                  settings.height_cm, settings.age, settings.activity_level)
            settings.tdee_estimate = tdee
            settings.calorie_target = float(calorie_target) if calorie_target else tdee - 500
            settings.protein_target = float(protein_target) if protein_target else round(settings.starting_weight_kg * 1.8)

            settings.onboarded = True
            db.session.commit()

            from models import WeightEntry
            db.session.add(WeightEntry(date=datetime.utcnow().date(), weight_kg=settings.starting_weight_kg,
                                        note="Starting weight"))
            db.session.commit()

            return redirect(url_for("dashboard.index"))
        except (ValueError, KeyError) as e:
            flash(f"Please check your inputs: {e}", "danger")

    return render_template("onboarding.html", settings=settings)
