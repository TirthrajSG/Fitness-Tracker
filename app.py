from flask import Flask, redirect, url_for, request
from flask_wtf import CSRFProtect
from flask_login import LoginManager, current_user

from config import Config
from models import db, User, Settings

import os

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    CSRFProtect(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from routes.auth import bp as auth_bp
    from routes.onboarding import bp as onboarding_bp
    from routes.dashboard import bp as dashboard_bp
    from routes.weight import bp as weight_bp
    from routes.nutrition import bp as nutrition_bp
    from routes.workout import bp as workout_bp
    from routes.calendar import bp as calendar_bp
    from routes.reports import bp as reports_bp
    from routes.settings import bp as settings_bp
    from routes.data import bp as data_bp

    app.register_blueprint(auth_bp)
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

    @app.before_request
    def require_login_and_onboarding():
        exempt = {"auth.login", "auth.register", "static"}
        if request.endpoint in exempt or request.endpoint is None:
            return
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if request.endpoint == "onboarding.setup":
            return
        settings = Settings.query.filter_by(user_id=current_user.id).first()
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
    def inject_globals():
        dark_mode = False
        if current_user.is_authenticated:
            settings = Settings.query.filter_by(user_id=current_user.id).first()
            dark_mode = bool(settings and settings.dark_mode)
        return {"dark_mode": dark_mode}

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
