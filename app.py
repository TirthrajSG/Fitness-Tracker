from flask import Flask, redirect, url_for, request
from flask_wtf import CSRFProtect

from config import Config
from models import db, Settings


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    CSRFProtect(app)

    from routes.onboarding import bp as onboarding_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.weight import bp as weight_bp
    from routes.nutrition import bp as nutrition_bp
    from routes.workout import bp as workout_bp
    from routes.calendar import bp as calendar_bp
    from routes.reports import bp as reports_bp
    from routes.settings import bp as settings_bp
    from routes.data import bp as data_bp

    app.register_blueprint(onboarding_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(weight_bp)
    app.register_blueprint(nutrition_bp)
    app.register_blueprint(workout_bp)
    app.register_blueprint(calendar_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(data_bp)

    with app.app_context():
        db.create_all()
        if Settings.query.first() is None:
            db.session.add(Settings())
            db.session.commit()

    @app.before_request
    def require_onboarding():
        exempt = {"onboarding.setup", "static"}
        if request.endpoint in exempt or request.endpoint is None:
            return
        settings = Settings.query.first()
        if settings is None or not settings.onboarded:
            return redirect(url_for("onboarding.setup"))

    @app.template_filter("fmt_date")
    def fmt_date(value, fmt="%d %b %Y"):
        if value is None:
            return "-"
        return value.strftime(fmt)

    @app.template_filter("fmt1")
    def fmt1(value, decimals=1):
        if value is None:
            return "-"
        return f"{value:.{decimals}f}"

    @app.context_processor
    def inject_dark_mode():
        settings = Settings.query.first()
        return {"dark_mode": bool(settings and settings.dark_mode)}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)
