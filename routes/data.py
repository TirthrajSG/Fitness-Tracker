import csv
import io
import os
import sqlite3
import tempfile
import zipfile
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from flask_login import login_required, current_user
from werkzeug.security import check_password_hash

from models import (db, Settings, WeightEntry, BodyMeasurement, Food, FoodLog, Exercise,
                     Workout, WorkoutExercise, SetEntry, WorkoutTemplate, TemplateExercise)

bp = Blueprint("data", __name__, url_prefix="/data")


def _table_to_csv(rows, fieldnames, row_to_dict):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(row_to_dict(r))
    return buf.getvalue()


def _clear_user_data(uid):
    workout_ids = [w.id for w in Workout.query.filter_by(user_id=uid).all()]
    if workout_ids:
        we_ids = [we.id for we in WorkoutExercise.query.filter(WorkoutExercise.workout_id.in_(workout_ids)).all()]
        if we_ids:
            SetEntry.query.filter(SetEntry.workout_exercise_id.in_(we_ids)).delete(synchronize_session=False)
        WorkoutExercise.query.filter(WorkoutExercise.workout_id.in_(workout_ids)).delete(synchronize_session=False)
    Workout.query.filter_by(user_id=uid).delete(synchronize_session=False)

    template_ids = [t.id for t in WorkoutTemplate.query.filter_by(user_id=uid).all()]
    if template_ids:
        TemplateExercise.query.filter(TemplateExercise.template_id.in_(template_ids)).delete(synchronize_session=False)
    WorkoutTemplate.query.filter_by(user_id=uid).delete(synchronize_session=False)

    FoodLog.query.filter_by(user_id=uid).delete(synchronize_session=False)
    Food.query.filter_by(user_id=uid).delete(synchronize_session=False)
    BodyMeasurement.query.filter_by(user_id=uid).delete(synchronize_session=False)
    WeightEntry.query.filter_by(user_id=uid).delete(synchronize_session=False)
    Exercise.query.filter_by(user_id=uid).delete(synchronize_session=False)


@bp.route("/")
@login_required
def index():
    return render_template("data.html")


@bp.route("/export")
@login_required
def export_all():
    uid = current_user.id
    mem = io.BytesIO()
    with zipfile.ZipFile(mem, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("weight_entries.csv", _table_to_csv(
            WeightEntry.query.filter_by(user_id=uid).order_by(WeightEntry.date).all(),
            ["date", "time", "weight_kg", "note"],
            lambda e: {"date": e.date, "time": e.time, "weight_kg": e.weight_kg, "note": e.note or ""}))

        zf.writestr("body_measurements.csv", _table_to_csv(
            BodyMeasurement.query.filter_by(user_id=uid).order_by(BodyMeasurement.date).all(),
            ["date", "measurement_type", "value", "unit"],
            lambda e: {"date": e.date, "measurement_type": e.measurement_type,
                       "value": e.value, "unit": e.unit}))

        zf.writestr("food_logs.csv", _table_to_csv(
            FoodLog.query.filter_by(user_id=uid).order_by(FoodLog.date).all(),
            ["date", "meal", "food_name", "quantity", "calories", "protein", "carbs", "fat", "fiber"],
            lambda e: {"date": e.date, "meal": e.meal, "food_name": e.food_name, "quantity": e.quantity,
                       "calories": e.calories, "protein": e.protein, "carbs": e.carbs,
                       "fat": e.fat, "fiber": e.fiber}))

        zf.writestr("foods.csv", _table_to_csv(
            Food.query.filter_by(user_id=uid).order_by(Food.name).all(),
            ["name", "serving_size", "serving_unit", "calories", "protein", "carbs", "fat", "fiber"],
            lambda e: {"name": e.name, "serving_size": e.serving_size, "serving_unit": e.serving_unit,
                       "calories": e.calories, "protein": e.protein, "carbs": e.carbs,
                       "fat": e.fat, "fiber": e.fiber}))

        set_rows = []
        for w in Workout.query.filter_by(user_id=uid).order_by(Workout.date).all():
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


@bp.route("/export/database")
@login_required
def export_database_file():
    uid = current_user.id
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_username = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in current_user.username)

    fd, temp_path = tempfile.mkstemp(prefix="fitness_account_", suffix=".db")
    os.close(fd)
    try:
        conn = sqlite3.connect(temp_path)
        cur = conn.cursor()

        cur.execute(
            "CREATE TABLE export_meta (source_username TEXT NOT NULL, source_password_hash TEXT NOT NULL, exported_at TEXT NOT NULL)"
        )
        cur.execute(
            "INSERT INTO export_meta (source_username, source_password_hash, exported_at) VALUES (?, ?, ?)",
            (current_user.username, current_user.password_hash, datetime.utcnow().isoformat())
        )

        cur.execute(
            """
            CREATE TABLE settings (
              name TEXT,
              age INTEGER,
              sex TEXT,
              height_cm REAL,
              activity_level TEXT,
              starting_weight_kg REAL,
              target_weight_kg REAL,
              target_date TEXT,
              desired_weekly_rate_kg REAL,
              tdee_estimate REAL,
              calorie_target REAL,
              protein_target REAL,
              weight_unit TEXT,
              height_unit TEXT,
              dark_mode INTEGER,
              onboarded INTEGER
            )
            """
        )
        s = Settings.query.filter_by(user_id=uid).first()
        if s:
            cur.execute(
                """
                INSERT INTO settings (
                  name, age, sex, height_cm, activity_level, starting_weight_kg, target_weight_kg,
                  target_date, desired_weekly_rate_kg, tdee_estimate, calorie_target, protein_target,
                  weight_unit, height_unit, dark_mode, onboarded
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s.name, s.age, s.sex, s.height_cm, s.activity_level, s.starting_weight_kg, s.target_weight_kg,
                    s.target_date.isoformat() if s.target_date else None,
                    s.desired_weekly_rate_kg, s.tdee_estimate, s.calorie_target, s.protein_target,
                    s.weight_unit, s.height_unit, 1 if s.dark_mode else 0, 1 if s.onboarded else 0,
                ),
            )

        cur.execute("CREATE TABLE weight_entries (date TEXT, time TEXT, weight_kg REAL NOT NULL, note TEXT)")
        for e in WeightEntry.query.filter_by(user_id=uid).order_by(WeightEntry.date).all():
            cur.execute(
                "INSERT INTO weight_entries (date, time, weight_kg, note) VALUES (?, ?, ?, ?)",
                (e.date.isoformat(), e.time.isoformat() if e.time else None, e.weight_kg, e.note),
            )

        cur.execute("CREATE TABLE body_measurements (date TEXT, measurement_type TEXT, value REAL, unit TEXT)")
        for e in BodyMeasurement.query.filter_by(user_id=uid).order_by(BodyMeasurement.date).all():
            cur.execute(
                "INSERT INTO body_measurements (date, measurement_type, value, unit) VALUES (?, ?, ?, ?)",
                (e.date.isoformat(), e.measurement_type, e.value, e.unit),
            )

        cur.execute(
            "CREATE TABLE foods (name TEXT, serving_size REAL, serving_unit TEXT, calories REAL, protein REAL, carbs REAL, fat REAL, fiber REAL)"
        )
        for f in Food.query.filter_by(user_id=uid).order_by(Food.name).all():
            cur.execute(
                "INSERT INTO foods (name, serving_size, serving_unit, calories, protein, carbs, fat, fiber) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (f.name, f.serving_size, f.serving_unit, f.calories, f.protein, f.carbs, f.fat, f.fiber),
            )

        cur.execute(
            "CREATE TABLE food_logs (date TEXT, meal TEXT, food_name TEXT, quantity REAL, calories REAL, protein REAL, carbs REAL, fat REAL, fiber REAL)"
        )
        for fl in FoodLog.query.filter_by(user_id=uid).order_by(FoodLog.date).all():
            cur.execute(
                "INSERT INTO food_logs (date, meal, food_name, quantity, calories, protein, carbs, fat, fiber) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (fl.date.isoformat(), fl.meal, fl.food_name, fl.quantity, fl.calories, fl.protein, fl.carbs, fl.fat, fl.fiber),
            )

        cur.execute("CREATE TABLE exercises (name TEXT, muscle_group TEXT, equipment TEXT, notes TEXT)")
        for ex in Exercise.query.filter_by(user_id=uid).order_by(Exercise.name).all():
            cur.execute(
                "INSERT INTO exercises (name, muscle_group, equipment, notes) VALUES (?, ?, ?, ?)",
                (ex.name, ex.muscle_group, ex.equipment, ex.notes),
            )

        cur.execute("CREATE TABLE workouts (workout_key INTEGER, date TEXT, name TEXT, duration_minutes INTEGER, notes TEXT)")
        cur.execute(
            "CREATE TABLE workout_sets (workout_key INTEGER, date TEXT, workout_name TEXT, exercise_name TEXT, set_number INTEGER, weight_kg REAL, reps INTEGER, rpe REAL, rir REAL)"
        )
        workouts = Workout.query.filter_by(user_id=uid).order_by(Workout.date, Workout.id).all()
        for i, w in enumerate(workouts, start=1):
            cur.execute(
                "INSERT INTO workouts (workout_key, date, name, duration_minutes, notes) VALUES (?, ?, ?, ?, ?)",
                (i, w.date.isoformat(), w.name, w.duration_minutes, w.notes),
            )
            for we in w.exercises:
                for s in we.sets:
                    cur.execute(
                        "INSERT INTO workout_sets (workout_key, date, workout_name, exercise_name, set_number, weight_kg, reps, rpe, rir) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (i, w.date.isoformat(), w.name, we.exercise.name, s.set_number, s.weight_kg, s.reps, s.rpe, s.rir),
                    )

        conn.commit()
        conn.close()

        with open(temp_path, "rb") as fh:
            payload = io.BytesIO(fh.read())
        payload.seek(0)
        filename = f"fitness_account_{safe_username}_{stamp}.db"
        return send_file(payload, mimetype="application/x-sqlite3", as_attachment=True, download_name=filename)
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@bp.route("/import/database", methods=["POST"])
@login_required
def import_database_file():
    file = request.files.get("db_file")
    if not file or file.filename == "":
        flash("No database file selected.", "danger")
        return redirect(url_for("data.index"))

    source_password = request.form.get("source_password", "")
    fd, temp_path = tempfile.mkstemp(prefix="fitness_import_", suffix=".db")
    os.close(fd)

    try:
        file.save(temp_path)
        conn = sqlite3.connect(temp_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        meta = cur.execute("SELECT source_username, source_password_hash FROM export_meta LIMIT 1").fetchone()
        if not meta:
            flash("Invalid export file: missing export metadata.", "danger")
            conn.close()
            return redirect(url_for("data.index"))

        source_username = meta["source_username"]
        if source_username != current_user.username:
            if not source_password:
                flash("Source account password is required when importing another account's export.", "danger")
                conn.close()
                return redirect(url_for("data.index"))
            if not check_password_hash(meta["source_password_hash"], source_password):
                flash("Incorrect source account password.", "danger")
                conn.close()
                return redirect(url_for("data.index"))

        uid = current_user.id
        _clear_user_data(uid)

        settings_row = cur.execute("SELECT * FROM settings LIMIT 1").fetchone()
        settings = Settings.query.filter_by(user_id=uid).first()
        if settings is None:
            settings = Settings(user_id=uid)
            db.session.add(settings)
        if settings_row:
            settings.name = settings_row["name"] or ""
            settings.age = settings_row["age"]
            settings.sex = settings_row["sex"]
            settings.height_cm = settings_row["height_cm"]
            settings.activity_level = settings_row["activity_level"]
            settings.starting_weight_kg = settings_row["starting_weight_kg"]
            settings.target_weight_kg = settings_row["target_weight_kg"]
            settings.target_date = datetime.strptime(settings_row["target_date"], "%Y-%m-%d").date() if settings_row["target_date"] else None
            settings.desired_weekly_rate_kg = settings_row["desired_weekly_rate_kg"]
            settings.tdee_estimate = settings_row["tdee_estimate"]
            settings.calorie_target = settings_row["calorie_target"]
            settings.protein_target = settings_row["protein_target"]
            settings.weight_unit = settings_row["weight_unit"] or "kg"
            settings.height_unit = settings_row["height_unit"] or "cm"
            settings.dark_mode = bool(settings_row["dark_mode"])
            settings.onboarded = bool(settings_row["onboarded"])

        for row in cur.execute("SELECT * FROM weight_entries"):
            db.session.add(WeightEntry(
                user_id=uid,
                date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
                time=datetime.strptime(row["time"], "%H:%M:%S").time() if row["time"] else None,
                weight_kg=row["weight_kg"],
                note=row["note"],
            ))

        for row in cur.execute("SELECT * FROM body_measurements"):
            db.session.add(BodyMeasurement(
                user_id=uid,
                date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
                measurement_type=row["measurement_type"],
                value=row["value"],
                unit=row["unit"] or "cm",
            ))

        for row in cur.execute("SELECT * FROM foods"):
            db.session.add(Food(
                user_id=uid,
                name=row["name"],
                serving_size=row["serving_size"] or 1.0,
                serving_unit=row["serving_unit"] or "serving",
                calories=row["calories"],
                protein=row["protein"] or 0.0,
                carbs=row["carbs"] or 0.0,
                fat=row["fat"] or 0.0,
                fiber=row["fiber"] or 0.0,
            ))

        for row in cur.execute("SELECT * FROM food_logs"):
            db.session.add(FoodLog(
                user_id=uid,
                date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
                meal=row["meal"],
                food_name=row["food_name"],
                quantity=row["quantity"] or 1.0,
                calories=row["calories"],
                protein=row["protein"] or 0.0,
                carbs=row["carbs"] or 0.0,
                fat=row["fat"] or 0.0,
                fiber=row["fiber"] or 0.0,
            ))

        for row in cur.execute("SELECT * FROM exercises"):
            db.session.add(Exercise(
                user_id=uid,
                name=row["name"],
                muscle_group=row["muscle_group"],
                equipment=row["equipment"],
                notes=row["notes"],
            ))

        workouts_by_key = {}
        workout_rows = list(cur.execute("SELECT * FROM workouts"))
        for idx, row in enumerate(workout_rows, start=1):
            workout_key = row["workout_key"] if "workout_key" in row.keys() else idx
            workout = Workout(
                user_id=uid,
                date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
                name=row["name"] or "Workout",
                duration_minutes=row["duration_minutes"],
                notes=row["notes"],
            )
            db.session.add(workout)
            workouts_by_key[workout_key] = workout

        db.session.flush()

        exercises_by_name = {
            e.name: e
            for e in Exercise.query.filter_by(user_id=uid).all()
        }

        we_by_workout_exercise = {}
        for row in cur.execute("SELECT * FROM workout_sets"):
            exercise_name = row["exercise_name"]
            if not exercise_name:
                continue

            workout_key = row["workout_key"] if "workout_key" in row.keys() else None
            workout = workouts_by_key.get(workout_key)
            if workout is None:
                continue

            exercise = exercises_by_name.get(exercise_name)
            if exercise is None:
                exercise = Exercise(user_id=uid, name=exercise_name)
                db.session.add(exercise)
                db.session.flush()
                exercises_by_name[exercise_name] = exercise

            pair_key = (workout.id, exercise.id)
            we = we_by_workout_exercise.get(pair_key)
            if we is None:
                we = WorkoutExercise(
                    workout_id=workout.id,
                    exercise_id=exercise.id,
                    order=len([k for k in we_by_workout_exercise if k[0] == workout.id]),
                )
                db.session.add(we)
                db.session.flush()
                we_by_workout_exercise[pair_key] = we

            db.session.add(SetEntry(
                workout_exercise_id=we.id,
                set_number=int(row["set_number"] or 1),
                weight_kg=float(row["weight_kg"]),
                reps=int(row["reps"]),
                rpe=float(row["rpe"]) if row["rpe"] not in (None, "") else None,
                rir=float(row["rir"]) if row["rir"] not in (None, "") else None,
            ))

        db.session.commit()
        conn.close()
        flash("Database import completed. Imported data is now tied only to your account.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Database import failed: {e}", "danger")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return redirect(url_for("data.index"))


@bp.route("/import/weight", methods=["POST"])
@login_required
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
            db.session.add(WeightEntry(user_id=current_user.id, date=entry_date, time=entry_time,
                                        weight_kg=weight, note=row.get("note") or None))
            count += 1
        db.session.commit()
        flash(f"Imported {count} weight entries.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Import failed: {e}", "danger")
    return redirect(url_for("data.index"))


@bp.route("/clear", methods=["POST"])
@login_required
def clear_all():
    confirm = request.form.get("confirm")
    if confirm != "DELETE":
        flash('Type DELETE exactly to confirm clearing all data.', "danger")
        return redirect(url_for("data.index"))

    uid = current_user.id
    _clear_user_data(uid)

    db.session.commit()
    flash("All your tracked data has been cleared. Your account and settings were kept.", "info")
    return redirect(url_for("data.index"))
