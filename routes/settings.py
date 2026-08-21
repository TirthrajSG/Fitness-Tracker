from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import db, Settings
from services.nutrition_analysis import estimate_tdee

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    settings = Settings.query.filter_by(user_id=current_user.id).first_or_404()

    if request.method == "POST":
        try:
            settings.name = request.form.get("name", "").strip()
            settings.age = int(request.form["age"])
            settings.sex = request.form["sex"]
            settings.height_cm = float(request.form["height_cm"])
            settings.activity_level = request.form["activity_level"]

            settings.target_weight_kg = float(request.form["target_weight"])
            target_date = request.form.get("target_date")
            settings.target_date = datetime.strptime(target_date, "%Y-%m-%d").date() if target_date else None
            settings.desired_weekly_rate_kg = float(request.form.get("desired_weekly_rate", 0.4) or 0.4)

            settings.calorie_target = float(request.form["calorie_target"])
            settings.protein_target = float(request.form["protein_target"])

            settings.weight_unit = request.form.get("weight_unit", "kg")
            settings.height_unit = request.form.get("height_unit", "cm")
            settings.dark_mode = "dark_mode" in request.form

            db.session.commit()
            flash("Settings saved.", "success")
        except (ValueError, KeyError) as e:
            flash(f"Could not save settings: {e}", "danger")
        return redirect(url_for("settings.index"))

    return render_template("settings.html", settings=settings)


@bp.route("/recalculate-tdee", methods=["POST"])
@login_required
def recalculate_tdee():
    settings = Settings.query.filter_by(user_id=current_user.id).first_or_404()
    try:
        current_weight = float(request.form["current_weight"])
        tdee = estimate_tdee(settings.sex, current_weight, settings.height_cm,
                              settings.age, settings.activity_level)
        settings.tdee_estimate = tdee
        db.session.commit()
        flash(f"Estimated TDEE updated to {tdee} kcal.", "success")
    except (ValueError, KeyError) as e:
        flash(f"Could not recalculate: {e}", "danger")
    return redirect(url_for("settings.index"))
