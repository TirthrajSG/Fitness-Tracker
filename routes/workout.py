from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

from models import (db, Exercise, Workout, WorkoutExercise, SetEntry,
                     WorkoutTemplate, TemplateExercise)
from services import workout_analysis as wka

bp = Blueprint("workout", __name__, url_prefix="/workout")


# ---------- Exercises ----------

@bp.route("/exercises")
def exercises():
    all_exercises = Exercise.query.order_by(Exercise.name).all()
    return render_template("exercises.html", exercises=all_exercises)


@bp.route("/exercises/add", methods=["POST"])
def add_exercise():
    try:
        ex = Exercise(
            name=request.form["name"].strip(),
            muscle_group=request.form.get("muscle_group", "").strip(),
            equipment=request.form.get("equipment", "").strip(),
            notes=request.form.get("notes", "").strip() or None,
        )
        db.session.add(ex)
        db.session.commit()
        flash("Exercise added.", "success")
    except (ValueError, KeyError) as e:
        flash(f"Could not add exercise: {e}", "danger")
    return redirect(url_for("workout.exercises"))


@bp.route("/exercises/edit/<int:exercise_id>", methods=["POST"])
def edit_exercise(exercise_id):
    ex = Exercise.query.get_or_404(exercise_id)
    ex.name = request.form["name"].strip()
    ex.muscle_group = request.form.get("muscle_group", "").strip()
    ex.equipment = request.form.get("equipment", "").strip()
    ex.notes = request.form.get("notes", "").strip() or None
    db.session.commit()
    flash("Exercise updated.", "success")
    return redirect(url_for("workout.exercises"))


@bp.route("/exercises/delete/<int:exercise_id>", methods=["POST"])
def delete_exercise(exercise_id):
    ex = Exercise.query.get_or_404(exercise_id)
    db.session.delete(ex)
    db.session.commit()
    flash("Exercise deleted.", "info")
    return redirect(url_for("workout.exercises"))


# ---------- Workouts ----------

@bp.route("/")
def index():
    workouts = Workout.query.order_by(Workout.date.desc()).limit(50).all()
    return render_template("workouts.html", workouts=workouts)


@bp.route("/new", methods=["GET", "POST"])
def new_workout():
    if request.method == "POST":
        try:
            w = Workout(
                date=datetime.strptime(request.form["date"], "%Y-%m-%d").date(),
                name=request.form.get("name", "Workout").strip() or "Workout",
                duration_minutes=int(request.form["duration"]) if request.form.get("duration") else None,
                notes=request.form.get("notes", "").strip() or None,
            )
            db.session.add(w)
            db.session.commit()

            template_id = request.form.get("template_id")
            if template_id:
                template = WorkoutTemplate.query.get(int(template_id))
                if template:
                    for i, te in enumerate(template.exercises):
                        db.session.add(WorkoutExercise(workout_id=w.id, exercise_id=te.exercise_id, order=i))
                    db.session.commit()

            return redirect(url_for("workout.detail", workout_id=w.id))
        except (ValueError, KeyError) as e:
            flash(f"Could not create workout: {e}", "danger")

    exercises_list = Exercise.query.order_by(Exercise.name).all()
    templates = WorkoutTemplate.query.order_by(WorkoutTemplate.name).all()
    return render_template("new_workout.html", exercises=exercises_list, templates=templates,
                            today=date.today().isoformat())


@bp.route("/<int:workout_id>")
def detail(workout_id):
    w = Workout.query.get_or_404(workout_id)
    exercises_list = Exercise.query.order_by(Exercise.name).all()

    previous_sets = {}
    for we in w.exercises:
        prior = (
            WorkoutExercise.query.join(Workout)
            .filter(WorkoutExercise.exercise_id == we.exercise_id, Workout.date < w.date)
            .order_by(Workout.date.desc()).first()
        )
        if prior:
            previous_sets[we.id] = prior.sets

    return render_template("workout_detail.html", workout=w, exercises=exercises_list,
                            previous_sets=previous_sets)


@bp.route("/<int:workout_id>/delete", methods=["POST"])
def delete_workout(workout_id):
    w = Workout.query.get_or_404(workout_id)
    db.session.delete(w)
    db.session.commit()
    flash("Workout deleted.", "info")
    return redirect(url_for("workout.index"))


@bp.route("/<int:workout_id>/add-exercise", methods=["POST"])
def add_exercise_to_workout(workout_id):
    w = Workout.query.get_or_404(workout_id)
    exercise_id = int(request.form["exercise_id"])
    order = len(w.exercises)
    we = WorkoutExercise(workout_id=w.id, exercise_id=exercise_id, order=order)
    db.session.add(we)
    db.session.commit()
    return redirect(url_for("workout.detail", workout_id=workout_id))


@bp.route("/exercise-entry/<int:we_id>/remove", methods=["POST"])
def remove_exercise_from_workout(we_id):
    we = WorkoutExercise.query.get_or_404(we_id)
    workout_id = we.workout_id
    db.session.delete(we)
    db.session.commit()
    return redirect(url_for("workout.detail", workout_id=workout_id))


@bp.route("/exercise-entry/<int:we_id>/add-set", methods=["POST"])
def add_set(we_id):
    we = WorkoutExercise.query.get_or_404(we_id)
    try:
        weight = float(request.form["weight"])
        reps = int(request.form["reps"])
        if weight < 0 or reps <= 0:
            raise ValueError("Invalid weight/reps")
        set_number = len(we.sets) + 1
        s = SetEntry(
            workout_exercise_id=we.id, set_number=set_number, weight_kg=weight, reps=reps,
            rpe=float(request.form["rpe"]) if request.form.get("rpe") else None,
            rir=float(request.form["rir"]) if request.form.get("rir") else None,
        )
        db.session.add(s)
        db.session.commit()
    except (ValueError, KeyError) as e:
        flash(f"Could not add set: {e}", "danger")
    return redirect(url_for("workout.detail", workout_id=we.workout_id))


@bp.route("/set/<int:set_id>/delete", methods=["POST"])
def delete_set(set_id):
    s = SetEntry.query.get_or_404(set_id)
    workout_id = s.workout_exercise.workout_id
    db.session.delete(s)
    db.session.commit()
    return redirect(url_for("workout.detail", workout_id=workout_id))


# ---------- Templates ----------

@bp.route("/templates")
def templates():
    all_templates = WorkoutTemplate.query.order_by(WorkoutTemplate.name).all()
    exercises_list = Exercise.query.order_by(Exercise.name).all()
    return render_template("templates.html", templates=all_templates, exercises=exercises_list)


@bp.route("/templates/add", methods=["POST"])
def add_template():
    name = request.form["name"].strip()
    if not name:
        flash("Template name is required.", "danger")
        return redirect(url_for("workout.templates"))
    t = WorkoutTemplate(name=name)
    db.session.add(t)
    db.session.commit()
    exercise_ids = request.form.getlist("exercise_ids")
    for i, eid in enumerate(exercise_ids):
        db.session.add(TemplateExercise(template_id=t.id, exercise_id=int(eid), order=i))
    db.session.commit()
    flash("Template created.", "success")
    return redirect(url_for("workout.templates"))


@bp.route("/templates/<int:template_id>/delete", methods=["POST"])
def delete_template(template_id):
    t = WorkoutTemplate.query.get_or_404(template_id)
    db.session.delete(t)
    db.session.commit()
    flash("Template deleted.", "info")
    return redirect(url_for("workout.templates"))


# ---------- Progress / PRs ----------

@bp.route("/progress")
def progress():
    exercises_list = Exercise.query.order_by(Exercise.name).all()
    selected_id = request.args.get("exercise_id", type=int)
    if not selected_id and exercises_list:
        selected_id = exercises_list[0].id

    progression = []
    prs = None
    if selected_id:
        rows = wka.exercise_history(db, Exercise, WorkoutExercise, Workout, SetEntry, selected_id)
        progression = wka.progression_series(rows)
        prs = wka.detect_prs(progression)

    return render_template("progress.html", exercises=exercises_list, selected_id=selected_id,
                            progression=progression, prs=prs)


@bp.route("/progress/chart-data")
def progress_chart_data():
    exercise_id = request.args.get("exercise_id", type=int)
    rows = wka.exercise_history(db, Exercise, WorkoutExercise, Workout, SetEntry, exercise_id)
    progression = wka.progression_series(rows)
    return jsonify({
        "labels": [s["date"].isoformat() for s in progression],
        "estimated_1rm": [s["estimated_1rm"] for s in progression],
        "volume": [s["volume"] for s in progression],
        "best_weight": [s["best_weight"] for s in progression],
    })


@bp.route("/prs")
def all_prs():
    exercises_list = Exercise.query.order_by(Exercise.name).all()
    pr_summary = []
    for ex in exercises_list:
        rows = wka.exercise_history(db, Exercise, WorkoutExercise, Workout, SetEntry, ex.id)
        progression = wka.progression_series(rows)
        if not progression:
            continue
        prs = wka.detect_prs(progression)
        pr_summary.append({"exercise": ex, "prs": prs})
    return render_template("prs.html", pr_summary=pr_summary)
