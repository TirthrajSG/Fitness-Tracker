from datetime import date, timedelta


def epley_1rm(weight_kg, reps):
    if reps <= 0:
        return round(weight_kg, 2)
    return round(weight_kg * (1 + reps / 30.0), 2)


def exercise_history(db, Exercise, WorkoutExercise, Workout, SetEntry, exercise_id):
    """Return all (workout, workout_exercise, sets) for an exercise, oldest first."""
    rows = (
        db.session.query(WorkoutExercise)
        .join(Workout)
        .filter(WorkoutExercise.exercise_id == exercise_id)
        .order_by(Workout.date.asc())
        .all()
    )
    return rows


def session_stats(workout_exercise):
    sets = workout_exercise.sets
    if not sets:
        return None
    best_weight = max(s.weight_kg for s in sets)
    best_reps = max(s.reps for s in sets)
    volume = sum(s.volume for s in sets)
    best_1rm = max(epley_1rm(s.weight_kg, s.reps) for s in sets)
    return {
        "date": workout_exercise.workout.date,
        "best_weight": best_weight,
        "best_reps": best_reps,
        "volume": volume,
        "estimated_1rm": best_1rm,
        "sets": sets,
    }


def progression_series(workout_exercises):
    """List of session_stats dicts, oldest first, for charting."""
    out = []
    for we in workout_exercises:
        s = session_stats(we)
        if s:
            out.append(s)
    return out


def detect_prs(progression):
    """Given a chronological progression_series output, annotate each
    session with whether it set a new PR for weight, 1RM, or volume,
    and return the running best-of records plus a flat PR event list."""
    best_weight = 0
    best_1rm = 0
    best_volume = 0
    pr_events = []
    for s in progression:
        flags = []
        if s["best_weight"] > best_weight:
            best_weight = s["best_weight"]
            flags.append("weight")
        if s["estimated_1rm"] > best_1rm:
            best_1rm = s["estimated_1rm"]
            flags.append("1rm")
        if s["volume"] > best_volume:
            best_volume = s["volume"]
            flags.append("volume")
        if flags:
            pr_events.append({"date": s["date"], "flags": flags, **s})
    return {
        "best_weight": best_weight,
        "best_1rm": best_1rm,
        "best_volume": best_volume,
        "events": list(reversed(pr_events)),  # most recent first
    }


def training_streak(workout_dates):
    """Count consecutive days-with-a-workout ending today or yesterday
    (streak breaks if more than 1 day has passed since the last workout)."""
    if not workout_dates:
        return 0
    days = sorted(set(workout_dates), reverse=True)
    today = date.today()
    if days[0] < today - timedelta(days=1):
        return 0
    streak = 1
    for i in range(len(days) - 1):
        if (days[i] - days[i + 1]).days == 1:
            streak += 1
        else:
            break
    return streak
