from datetime import date, timedelta
from statistics import mean, pstdev


def _sorted_entries(entries):
    return sorted(entries, key=lambda e: (e.date, e.time or 0))


def rolling_average(entries, window_days, as_of=None):
    """Average weight over the last `window_days` days ending at as_of (inclusive)."""
    if not entries:
        return None
    as_of = as_of or max(e.date for e in entries)
    start = as_of - timedelta(days=window_days - 1)
    window = [e.weight_kg for e in entries if start <= e.date <= as_of]
    if not window:
        return None
    return round(mean(window), 2)


def daily_series_with_averages(entries, windows=(7, 14, 30)):
    """Collapse same-day entries to a daily mean, then attach rolling averages
    for each requested window. Returns a list of dicts sorted by date."""
    entries = _sorted_entries(entries)
    if not entries:
        return []

    by_day = {}
    for e in entries:
        by_day.setdefault(e.date, []).append(e.weight_kg)
    days = sorted(by_day.keys())
    daily = [{"date": d, "weight": round(mean(by_day[d]), 2)} for d in days]

    for point in daily:
        for w in windows:
            start = point["date"] - timedelta(days=w - 1)
            vals = [p["weight"] for p in daily if start <= p["date"] <= point["date"]]
            point[f"avg_{w}"] = round(mean(vals), 2) if vals else None
    return daily


def linear_trend(entries, days_back=None):
    """Ordinary least squares fit of weight vs. day-index.
    Returns (slope_kg_per_day, intercept, r_value) or (None, None, None) if
    fewer than 2 distinct days of data."""
    daily = daily_series_with_averages(entries, windows=())
    if days_back is not None and daily:
        cutoff = daily[-1]["date"] - timedelta(days=days_back)
        daily = [p for p in daily if p["date"] >= cutoff]

    if len(daily) < 2:
        return None, None, None

    x0 = daily[0]["date"]
    xs = [(p["date"] - x0).days for p in daily]
    ys = [p["weight"] for p in daily]
    n = len(xs)
    x_mean = mean(xs)
    y_mean = mean(ys)

    sxy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    sxx = sum((x - x_mean) ** 2 for x in xs)
    if sxx == 0:
        return 0.0, y_mean, 0.0

    slope = sxy / sxx
    intercept = y_mean - slope * x_mean

    syy = sum((y - y_mean) ** 2 for y in ys)
    r = sxy / (sxx ** 0.5 * syy ** 0.5) if sxx > 0 and syy > 0 else 0.0
    return slope, intercept, r


def weekly_rate(entries, days_back=28):
    """Weekly rate of change (kg/week) from the linear trend over recent data.
    Negative = losing weight."""
    slope, _, _ = linear_trend(entries, days_back=days_back)
    if slope is None:
        return None
    return round(slope * 7, 3)


def volatility(entries, days_back=14):
    daily = daily_series_with_averages(entries, windows=())
    if daily and days_back is not None:
        cutoff = daily[-1]["date"] - timedelta(days=days_back)
        daily = [p for p in daily if p["date"] >= cutoff]
    vals = [p["weight"] for p in daily]
    if len(vals) < 2:
        return None
    return round(pstdev(vals), 2)


def estimate_target_date(current_avg, target_weight, weekly_rate_kg):
    """Project the date the rolling-average weight reaches the target,
    given the current recent weekly rate. Returns None if the trend does
    not move toward the target (rate ~0 or wrong sign)."""
    if current_avg is None or target_weight is None or weekly_rate_kg is None:
        return None
    remaining = target_weight - current_avg  # negative if losing weight
    if abs(weekly_rate_kg) < 0.01:
        return None
    weeks_needed = remaining / weekly_rate_kg
    if weeks_needed < 0:
        return None
    return date.today() + timedelta(weeks=weeks_needed)


def detect_plateau(entries, min_days=21, threshold_kg_per_week=0.1):
    """A plateau is flagged only when we have at least `min_days` of data
    and the recent trend slope is smaller in magnitude than the threshold."""
    daily = daily_series_with_averages(entries, windows=())
    if len(daily) < min_days:
        return False
    span = (daily[-1]["date"] - daily[0]["date"]).days
    if span < min_days:
        return False
    rate = weekly_rate(entries, days_back=min_days)
    if rate is None:
        return False
    return abs(rate) < threshold_kg_per_week


def goal_status(desired_weekly_rate, actual_weekly_rate):
    """Compare desired vs. actual weekly loss rate. Both expected as
    negative-for-loss kg/week, or positive-for-gain depending on goal
    direction; we compare magnitudes toward the goal direction."""
    if desired_weekly_rate is None or actual_weekly_rate is None:
        return "insufficient_data"
    # Losing weight: more negative than desired => ahead of schedule
    if desired_weekly_rate < 0:
        if actual_weekly_rate <= desired_weekly_rate * 1.1:
            return "ahead"
        elif actual_weekly_rate >= desired_weekly_rate * 0.5:
            return "behind"
        return "on_track"
    else:
        if actual_weekly_rate >= desired_weekly_rate * 1.1:
            return "ahead"
        elif actual_weekly_rate <= desired_weekly_rate * 0.5:
            return "behind"
        return "on_track"
