"""
LifeLink - Application Factory
Initializes Flask app instance, loads configuration, sets up database teardown,
attaches CSRF protection middleware, registers context processors, and mounts blueprints.
"""

import os
import logging
from datetime import datetime
from flask import Flask, jsonify, render_template

from app.config import config_by_name
from app.extensions import close_db, test_db_connection
from app.routes import register_blueprints
from app.services.security import generate_csrf_token, validate_csrf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


def create_app(config_name: str = None) -> Flask:
    """
    Application factory for LifeLink.
    
    :param config_name: 'development', 'production', or 'testing'.
                        If omitted, resolves from FLASK_ENV or defaults to 'development'.
    :return: Fully configured Flask application instance.
    """
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development").lower()

    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static"
    )

    # 1. Load configuration
    selected_config = config_by_name.get(config_name, config_by_name["default"])
    app.config.from_object(selected_config)
    app.config["DB_CONFIG"] = selected_config.get_db_config()

    if config_name == "production" and hasattr(selected_config, "validate"):
        selected_config.validate()

    # 2. Register database connection teardown
    app.teardown_appcontext(close_db)

    # 3. Security: Register CSRF verification on unsafe HTTP methods
    app.before_request(validate_csrf)

    # 4. Register global Jinja variables and CSRF token generator
    @app.context_processor
    def inject_global_template_variables():
        return {
            "app_name": app.config.get("APP_NAME", "LifeLink"),
            "app_tagline": app.config.get("APP_TAGLINE", "Smart Blood Donor Portal"),
            "current_year": datetime.utcnow().year,
            "csrf_token": generate_csrf_token,
        }

    # 5. Register all modular Blueprints (Public, Auth, Donor, Patient, Requests, Admin)
    register_blueprints(app)

    # 6. Core Health Check Endpoint
    @app.route("/health")
    def health_check():
        db_ok, db_msg, db_details = test_db_connection()
        return jsonify({
            "status": "healthy" if db_ok else "degraded",
            "app": app.config.get("APP_NAME", "LifeLink"),
            "environment": config_name,
            "blueprints": list(app.blueprints.keys()),
            "database": {
                "connected": db_ok,
                "message": db_msg,
                "version": db_details.get("mysql_version"),
                "table_count": db_details.get("table_count", 0),
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }), (200 if db_ok else 503)

    # 7. Global HTTP Error Handlers
    @app.errorhandler(400)
    def handle_bad_request(error):
        msg = getattr(error, "description", "Bad Request")
        return render_template("errors/404.html", custom_title="400 — Bad Request", custom_message=str(msg)), 400

    @app.errorhandler(429)
    def handle_too_many_requests(error):
        msg = getattr(error, "description", "Too Many Requests")
        return render_template("errors/404.html", custom_title="429 — Rate Limit Exceeded", custom_message=str(msg)), 429

    @app.errorhandler(403)
    def handle_forbidden(error):
        return render_template("errors/403.html"), 403

    # 8. Administrative CLI Command for Secure Admin Account Provisioning
    @app.cli.command("create-admin")
    def create_admin_cmd():
        """Provisions a secure system administrator account (cannot be created via public web registration)."""
        import click
        from app.models.user import User
        from app.services.security import validate_email, validate_password_strength

        click.echo("")
        click.echo("==================================================")
        click.echo("  LifeLink - Secure Administrator Provisioning   ")
        click.echo("==================================================")

        name = click.prompt("Admin Full Name", type=str).strip()
        email = click.prompt("Admin Email Address", type=str).strip().lower()

        ok, err = validate_email(email)
        if not ok:
            click.echo(f"Validation Error: {err}")
            return

        phone = click.prompt("Admin Phone Number", type=str).strip()
        password = click.prompt("Master Password", hide_input=True)
        confirm_password = click.prompt("Confirm Master Password", hide_input=True)

        if password != confirm_password:
            click.echo("Security Error: Passwords do not match.")
            return

        ok_pw, err_pw = validate_password_strength(password)
        if not ok_pw:
            click.echo(f"Password Complexity Error: {err_pw}")
            return

        try:
            user_id = User.create_admin(name, email, phone, password)
            click.echo(f"Provisioning Complete: Administrator '{name}' created with ID #{user_id}.")
        except Exception as e:
            click.echo(f"Failed to create admin: {e}")

    @app.errorhandler(404)
    def handle_not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def handle_server_error(error):
        logger.error(f"Internal Server Error: {error}", exc_info=True)
        return render_template("errors/500.html"), 500

    logger.info(f"LifeLink Flask Application initialized [Config: {config_name}] with Blueprints: {list(app.blueprints.keys())}")
    return app
