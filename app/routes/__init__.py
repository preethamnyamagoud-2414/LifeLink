"""
LifeLink - Route Blueprints Registration
Centralizes the mounting of all application blueprints.
"""

from flask import Flask
from app.routes.public import public_bp
from app.routes.auth import auth_bp
from app.routes.donor import donor_bp
from app.routes.patient import patient_bp
from app.routes.requests import request_bp
from app.routes.admin import admin_bp


def register_blueprints(app: Flask) -> None:
    """
    Registers all modular Blueprints with the Flask application instance.
    
    :param app: The Flask application instance.
    """
    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(donor_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(request_bp)
    app.register_blueprint(admin_bp)
