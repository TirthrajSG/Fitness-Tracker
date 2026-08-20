import csv
import io
import zipfile
from datetime import datetime

from flask import (Blueprint, render_template, request, redirect, url_for,
                    flash, send_file)

from models import (db, WeightEntry, BodyMeasurement, Food, FoodLog, Exercise,
                     Workout, WorkoutExercise, SetEntry, WorkoutTemplate, TemplateExercise)

bp = Blueprint("data", __name__, url_prefix="/data")


def _table_to_csv(rows, fieldnames, row_to_dict):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(row_to_dict(r))
    return buf.getvalue()


@bp.route("/")
def index():
    return render_template("data.html")


@bp.route("/export")
def export_all():
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("weight_entries.csv", _table_to_csv(
            WeightEntry.query.order_by(WeightEntry.date).all(),
            ["date", "time", "weight_kg", "note"],
            lambda e: {"date": e.date, "time": e.time, "weight_kg": e.weight_kg, "note": e.note or ""}))

        zf.writestr("body_measurements.csv", _table_to_csv(
            BodyMeasurement.query.order_by(BodyMeasurement.date).all(),
            ["date", "measurement_type", "value", "unit"],
            lambda e: {"date": e.date, "measurement_type": e.measurement_type,
                       "value": e.value, "unit": e.unit}))

        zf.writestr("food_logs.csv", _table_to_csv(
            FoodLog.query.order_by(FoodLog.date).all(),
            ["date", "meal", "food_name", "quantity", "calories", "protein", "carbs", "fat", "fiber"],
            lambda e: {"date": e.date, "meal": e.meal, "food_name": e.food_name, "quantity": e.quantity,
                       "calories": e.calories, "protein": e.protein, "carbs": e.carbs,
                       "fat": e.fat, "fiber": e.fiber}))

        zf.writestr("foods.csv", _table_to_csv(
            Food.query.order_by(Food.name).all(),
            ["name", "serving_size", "serving_unit", "calories", "protein", "carbs", "fat", "fiber"],
            lambda e: {"name": e.name, "serving_size": e.serving_size, "serving_unit": e.serving_unit,
                       "calories": e.calories, "protein": e.protein, "carbs": e.carbs,
                       "fat": e.fat, "fiber": e.fiber}))

        set_rows = []
        for w in Workout.query.order_by(Workout.date).all():
            for we in w.exercises:
                for s in we.sets:
                    set_rows.append({
                        "date": w.date, "workout_name": w.name, "exercise": we.exercise.name,
                        "set_number": s.set_number, "weight_kg": s.weight_kg, "reps": s.reps,
                        "rpe": s.rpe or "", "rir": s.rir or "",
                    })
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=["date", "workout_name", "exercise", "set_number",
                                                  "weight_kg", "reps", "rpe", "rir"])
        writer.writeheader()
        writer.writerows(set_rows)
        zf.writestr("workout_sets.csv", buf.getvalue())

    mem.seek(0)
    filename = f"fitness_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    return send_file(mem, mimetype="application/zip", as_attachment=True, download_name=filename)


@bp.route("/import/weight", methods=["POST"])
def import_weight_csv():
    file = request.files.get("csv_file")
    if not file or file.filename == "":
        flash("No file selected.", "danger")
        return redirect(url_for("data.index"))
    try:
        content = file.stream.read().decode("utf-8")
        reader = csv.DictReader(io.StringIO(content))
        count = 0
        for row in reader:
            entry_date = datetime.strptime(row["date"], "%Y-%m-%d").date()
            weight = float(row["weight_kg"])
            entry_time = None
            if row.get("time"):
                try:
                    entry_time = datetime.strptime(row["time"], "%H:%M:%S").time()
                except ValueError:
                    entry_time = datetime.strptime(row["time"], "%H:%M").time()
            db.session.add(WeightEntry(date=entry_date, time=entry_time, weight_kg=weight,
                                        note=row.get("note") or None))
            count += 1
        db.session.commit()
        flash(f"Imported {count} weight entries.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Import failed: {e}", "danger")
    return redirect(url_for("data.index"))


@bp.route("/clear", methods=["POST"])
def clear_all():
    confirm = request.form.get("confirm")
    if confirm != "DELETE":
        flash('Type DELETE exactly to confirm clearing all data.', "danger")
        return redirect(url_for("data.index"))

    for model in [SetEntry, WorkoutExercise, Workout, TemplateExercise, WorkoutTemplate,
                  FoodLog, Food, BodyMeasurement, WeightEntry, Exercise]:
        model.query.delete()
    db.session.commit()
    flash("All tracked data has been cleared. Settings were kept.", "info")
    return redirect(url_for("data.index"))
