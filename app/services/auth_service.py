"""
LifeLink - Authentication & Authorization Service
Provides session-based role verification and security decorators.
"""

from functools import wraps
from typing import Optional, Dict, Any, List
from flask import session, redirect, url_for, flash, request, abort
from app.models.user import User


def login_required(f):
    """Decorator ensuring that only authenticated users can access the endpoint."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access this page.", "warning")
            if request.path.startswith("/admin"):
                return redirect(url_for("admin.login", next=request.url))
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*roles: str):
    """
    Decorator restricting endpoint access to specific roles.
    Example: @role_required('admin') or @role_required('donor', 'admin')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Please sign in to access this area.", "warning")
                if request.path.startswith("/admin"):
                    return redirect(url_for("admin.login", next=request.url))
                return redirect(url_for("auth.login", next=request.url))

            user_role = session.get("user_role")
            if user_role not in roles:
                flash("Access denied: You do not have permission for this portal.", "danger")
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def login_user(user_dict: Dict[str, Any], remember: bool = True) -> None:
    """Sets session keys for an authenticated user with session regeneration."""
    session.clear()
    session["user_id"] = user_dict["id"]
    session["user_name"] = user_dict["full_name"]
    session["user_email"] = user_dict["email"]
    session["user_role"] = user_dict["role"]
    session["is_admin"] = (user_dict["role"] == "admin")
    
    # Track whether user has active clinical donor profile
    try:
        session["has_donor_profile"] = User.has_donor_profile(user_dict["id"])
    except Exception:
        session["has_donor_profile"] = (user_dict.get("role") == "donor")

    session.permanent = remember


def logout_user() -> None:
    """Clears authenticated session."""
    session.clear()


def get_current_user() -> Optional[Dict[str, Any]]:
    """Retrieves full record of the currently logged-in user."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.find_by_id(user_id)
