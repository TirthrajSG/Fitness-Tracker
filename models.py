from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Settings(db.Model):
    __tablename__ = "settings"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True)
    onboarded = db.Column(db.Boolean, default=False, nullable=False)

    name = db.Column(db.String(80), default="")
    age = db.Column(db.Integer)
    sex = db.Column(db.String(10))  # 'male' / 'female'
    height_cm = db.Column(db.Float)
    activity_level = db.Column(db.String(20), default="moderate")
    # sedentary / light / moderate / active / very_active

    starting_weight_kg = db.Column(db.Float)
    target_weight_kg = db.Column(db.Float)
    target_date = db.Column(db.Date)
    desired_weekly_rate_kg = db.Column(db.Float, default=0.4)

    tdee_estimate = db.Column(db.Float)
    calorie_target = db.Column(db.Float)
    protein_target = db.Column(db.Float)

    weight_unit = db.Column(db.String(5), default="kg")   # kg / lb
    height_unit = db.Column(db.String(5), default="cm")   # cm / in
    dark_mode = db.Column(db.Boolean, default=False)


class WeightEntry(db.Model):
    __tablename__ = "weight_entries"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    time = db.Column(db.Time)
    weight_kg = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class BodyMeasurement(db.Model):
    __tablename__ = "body_measurements"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    measurement_type = db.Column(db.String(20), nullable=False)
    # waist, chest, neck, hip, left_arm, right_arm, left_thigh, right_thigh
    value = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(5), default="cm")


class Food(db.Model):
    __tablename__ = "foods"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    serving_size = db.Column(db.Float, default=1.0)
    serving_unit = db.Column(db.String(30), default="serving")
    calories = db.Column(db.Float, nullable=False)
    protein = db.Column(db.Float, default=0.0)
    carbs = db.Column(db.Float, default=0.0)
    fat = db.Column(db.Float, default=0.0)
    fiber = db.Column(db.Float, default=0.0)


class FoodLog(db.Model):
    __tablename__ = "food_logs"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    meal = db.Column(db.String(20), nullable=False)
    # breakfast/lunch/dinner/snack/other
    food_id = db.Column(db.Integer, db.ForeignKey("foods.id"))
    food_name = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Float, default=1.0)  # multiple of serving_size
    calories = db.Column(db.Float, nullable=False)
    protein = db.Column(db.Float, default=0.0)
    carbs = db.Column(db.Float, default=0.0)
    fat = db.Column(db.Float, default=0.0)
    fiber = db.Column(db.Float, default=0.0)

    food = db.relationship("Food")


class Exercise(db.Model):
    __tablename__ = "exercises"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False, index=True)
    muscle_group = db.Column(db.String(50))
    equipment = db.Column(db.String(50))
    notes = db.Column(db.String(255))


class Workout(db.Model):
    __tablename__ = "workouts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    date = db.Column(db.Date, nullable=False, index=True)
    name = db.Column(db.String(120), default="Workout")
    duration_minutes = db.Column(db.Integer)
    notes = db.Column(db.String(255))

    exercises = db.relationship(
        "WorkoutExercise", backref="workout", cascade="all, delete-orphan",
        order_by="WorkoutExercise.order"
    )


class WorkoutExercise(db.Model):
    __tablename__ = "workout_exercises"
    id = db.Column(db.Integer, primary_key=True)
    workout_id = db.Column(db.Integer, db.ForeignKey("workouts.id"), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.id"), nullable=False)
    order = db.Column(db.Integer, default=0)

    exercise = db.relationship("Exercise")
    sets = db.relationship(
        "SetEntry", backref="workout_exercise", cascade="all, delete-orphan",
        order_by="SetEntry.set_number"
    )


class SetEntry(db.Model):
    __tablename__ = "sets"
    id = db.Column(db.Integer, primary_key=True)
    workout_exercise_id = db.Column(db.Integer, db.ForeignKey("workout_exercises.id"), nullable=False)
    set_number = db.Column(db.Integer, nullable=False)
    weight_kg = db.Column(db.Float, nullable=False)
    reps = db.Column(db.Integer, nullable=False)
    rpe = db.Column(db.Float)
    rir = db.Column(db.Float)

    @property
    def volume(self):
        return self.weight_kg * self.reps

    @property
    def estimated_1rm(self):
        if self.reps <= 0:
            return self.weight_kg
        return round(self.weight_kg * (1 + self.reps / 30.0), 2)


class WorkoutTemplate(db.Model):
    __tablename__ = "workout_templates"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)

    exercises = db.relationship(
        "TemplateExercise", backref="template", cascade="all, delete-orphan",
        order_by="TemplateExercise.order"
    )


class TemplateExercise(db.Model):
    __tablename__ = "template_exercises"
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("workout_templates.id"), nullable=False)
    exercise_id = db.Column(db.Integer, db.ForeignKey("exercises.id"), nullable=False)
    order = db.Column(db.Integer, default=0)

    exercise = db.relationship("Exercise")


class Reminder(db.Model):
    __tablename__ = "reminders"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)  # weigh_in / log_food / workout
    time_of_day = db.Column(db.Time, nullable=False)
    enabled = db.Column(db.Boolean, default=True)
