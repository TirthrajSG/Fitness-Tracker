from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models import db, WeightEntry, Settings
from services import weight_analysis as wa

bp = Blueprint("weight", __name__, url_prefix="/weight")


@bp.route("/")
@login_required
def index():
    uid = current_user.id
    date_from = request.args.get("from")
    date_to = request.args.get("to")

    query = WeightEntry.query.filter_by(user_id=uid)
    if date_from:
        query = query.filter(WeightEntry.date >= datetime.strptime(date_from, "%Y-%m-%d").date())
    if date_to:
        query = query.filter(WeightEntry.date <= datetime.strptime(date_to, "%Y-%m-%d").date())
    entries = query.order_by(WeightEntry.date.desc(), WeightEntry.time.desc()).all()

    all_entries = WeightEntry.query.filter_by(user_id=uid).order_by(WeightEntry.date).all()
    avg7 = wa.rolling_average(all_entries, 7)
    avg14 = wa.rolling_average(all_entries, 14)
    avg30 = wa.rolling_average(all_entries, 30)
    week_rate = wa.weekly_rate(all_entries, days_back=28)

    daily = wa.daily_series_with_averages(all_entries)
    total_change = None
    if len(daily) >= 2:
        total_change = round(daily[-1]["weight"] - daily[0]["weight"], 2)

    daily_change = weekly_change = None
    if len(daily) >= 2:
        daily_change = round(daily[-1]["weight"] - daily[-2]["weight"], 2)
    week_ago = daily[-1]["date"] - timedelta(days=7) if daily else None
    if week_ago:
        prior = [p for p in daily if p["date"] <= week_ago]
        if prior:
            weekly_change = round(daily[-1]["weight"] - prior[-1]["weight"], 2)

    return render_template(
        "weight.html", entries=entries, avg7=avg7, avg14=avg14, avg30=avg30,
        week_rate=week_rate, total_change=total_change, daily_change=daily_change,
        weekly_change=weekly_change, date_from=date_from or "", date_to=date_to or "",
    )


@bp.route("/add", methods=["POST"])
@login_required
def add():
    try:
        entry_date = datetime.strptime(request.form["date"], "%Y-%m-%d").date()
        entry_time = None
        if request.form.get("time"):
            entry_time = datetime.strptime(request.form["time"], "%H:%M").time()
        weight = float(request.form["weight"])
        if weight <= 0 or weight > 500:
            raise ValueError("Weight out of realistic range")
        entry = WeightEntry(user_id=current_user.id, date=entry_date, time=entry_time, weight_kg=weight,
                             note=request.form.get("note", "").strip() or None)
        db.session.add(entry)
        db.session.commit()
        flash("Weight entry saved.", "success")
    except (ValueError, KeyError) as e:
        flash(f"Could not save entry: {e}", "danger")
    return redirect(url_for("weight.index"))


@bp.route("/edit/<int:entry_id>", methods=["POST"])
@login_required
def edit(entry_id):
    entry = WeightEntry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    try:
        entry.date = datetime.strptime(request.form["date"], "%Y-%m-%d").date()
        if request.form.get("time"):
            entry.time = datetime.strptime(request.form["time"], "%H:%M").time()
        weight = float(request.form["weight"])
        if weight <= 0 or weight > 500:
            raise ValueError("Weight out of realistic range")
        entry.weight_kg = weight
        entry.note = request.form.get("note", "").strip() or None
        db.session.commit()
        flash("Weight entry updated.", "success")
    except (ValueError, KeyError) as e:
        flash(f"Could not update entry: {e}", "danger")
    return redirect(url_for("weight.index"))


@bp.route("/delete/<int:entry_id>", methods=["POST"])
@login_required
def delete(entry_id):
    entry = WeightEntry.query.filter_by(id=entry_id, user_id=current_user.id).first_or_404()
    db.session.delete(entry)
    db.session.commit()
    flash("Weight entry deleted.", "info")
    return redirect(url_for("weight.index"))


@bp.route("/chart-data")
@login_required
def chart_data():
    uid = current_user.id
    range_key = request.args.get("range", "90")
    settings = Settings.query.filter_by(user_id=uid).first()
    entries = WeightEntry.query.filter_by(user_id=uid).order_by(WeightEntry.date).all()

    if range_key != "all":
        days = int(range_key)
        cutoff = date.today() - timedelta(days=days)
        entries = [e for e in entries if e.date >= cutoff]

    daily = wa.daily_series_with_averages(entries)
    slope, intercept, _ = wa.linear_trend(entries)

    labels = [p["date"].isoformat() for p in daily]
    weights = [p["weight"] for p in daily]
    avg7 = [p["avg_7"] for p in daily]

    projection = []
    if slope is not None and daily:
        x0 = daily[0]["date"]
        for p in daily:
            x = (p["date"] - x0).days
            projection.append(round(intercept + slope * x, 2))

    return jsonify({
        "labels": labels,
        "weight": weights,
        "avg7": avg7,
        "target": settings.target_weight_kg,
        "projection": projection,
    })
