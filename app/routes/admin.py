"""
LifeLink - Administrative Blueprint
Handles administrative dashboard, system KPIs, user account management,
clinical donor verifications, request moderation, and security audit logs.
Strictly protected with server-side admin authorization.
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, session, jsonify
from app.models.user import User
from app.models.donor import Donor
from app.models.blood_request import BloodRequest
from app.models.message import ContactMessage, AdminActivityLog
from app.services.auth_service import login_required, role_required, login_user
from app.services.security import rate_limit, validate_email
from app.extensions import test_db_connection

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/login", methods=["GET", "POST"])
@rate_limit(max_requests=5, window_seconds=60)
def login():
    """
    Dedicated Administrative Portal Authentication.
    Strictly verifies credentials and enforces admin role authorization.
    """
    if "user_id" in session and session.get("user_role") == "admin":
        return redirect(url_for("admin.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") in ("1", "true", "on", True)

        ok, err = validate_email(email)
        if not ok:
            flash(err, "danger")
            return render_template("admin/login.html", email=email), 400

        db_ok, _, _ = test_db_connection()
        if not db_ok:
            flash("Database connection offline. Please ensure MySQL server is running.", "danger")
            return render_template("admin/login.html", email=email), 503

        user = User.find_by_email(email)
        if user and User.verify_password(user["password_hash"], password):
            if user.get("role") != "admin":
                flash("Access Denied: This account does not possess administrative privileges.", "danger")
                return render_template("admin/login.html", email=email), 403

            if not user.get("is_active"):
                flash("This administrative account has been deactivated.", "danger")
                return render_template("admin/login.html", email=email), 403

            login_user(user, remember=remember)
            AdminActivityLog.log(
                admin_user_id=user["id"],
                action_type="ADMIN_LOGIN",
                target_entity="users",
                target_id=user["id"],
                description=f"Administrator {user['full_name']} logged in to Admin Console",
                ip_address=request.remote_addr
            )
            flash(f"Welcome to Admin Console, {user['full_name']}.", "success")
            return redirect(url_for("admin.dashboard"))

        flash("Invalid administrative credentials. Access denied.", "danger")

    return render_template("admin/login.html")


@admin_bp.route("/dashboard")
@admin_bp.route("/")
@login_required
@role_required("admin")
def dashboard():
    """
    Renders administrative overview with real-time MySQL metrics,
    system KPI cards, inventory breakdown, and recent audit activity.
    """
    user_counts = User.get_counts()
    donor_stats = Donor.get_aggregate_stats()
    request_counts = BloodRequest.get_status_counts()
    blood_distribution = Donor.get_blood_group_distribution()
    recent_users = User.get_all(limit=10)
    recent_requests = BloodRequest.get_all(limit=10)
    audit_logs = AdminActivityLog.get_recent(limit=10)

    # Consolidated KPIs
    kpis = {
        "total_users": user_counts.get("total_users", 0),
        "total_donors": donor_stats.get("total_donors", 0),
        "active_donors": donor_stats.get("active_donors", 0),
        "active_requests": request_counts.get("active", 0),
        "fulfilled_requests": request_counts.get("fulfilled", 0),
        "cancelled_requests": request_counts.get("cancelled", 0),
        "total_requests": request_counts.get("total", 0),
        "verified_accounts": user_counts.get("verified_users", 0)
    }

    return render_template(
        "admin/dashboard.html",
        kpis=kpis,
        blood_distribution=blood_distribution,
        users=recent_users,
        requests=recent_requests,
        audit_logs=audit_logs,
        active_tab="overview"
    )


@admin_bp.route("/admin-dashboard.html")
def legacy_admin_dashboard_redirect():
    """Handles legacy static file links by cleanly redirecting to the official Flask admin dashboard route."""
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/users")
@login_required
@role_required("admin")
def manage_users():
    """User accounts administration portal."""
    role_filter = request.args.get("role")
    users = User.get_all(role=role_filter, limit=100)
    user_counts = User.get_counts()
    return render_template(
        "admin/dashboard.html",
        users=users,
        user_counts=user_counts,
        selected_role=role_filter,
        active_tab="users"
    )


@admin_bp.route("/requests")
@login_required
@role_required("admin")
def manage_requests():
    """Transfusion requests moderation portal."""
    status_filter = request.args.get("status")
    requests_list = BloodRequest.get_all(status=status_filter, limit=100)
    request_counts = BloodRequest.get_status_counts()
    return render_template(
        "admin/dashboard.html",
        requests=requests_list,
        request_counts=request_counts,
        selected_status=status_filter,
        active_tab="requests"
    )


@admin_bp.route("/audit-logs")
@login_required
@role_required("admin")
def audit_logs():
    """Security audit logs and suspicious activity inspection."""
    logs = AdminActivityLog.get_recent(limit=100)
    return render_template(
        "admin/dashboard.html",
        audit_logs=logs,
        active_tab="logs"
    )


@admin_bp.route("/donors/verify/<int:user_id>", methods=["POST"])
@login_required
@role_required("admin")
def verify_donor(user_id: int):
    """Admin action to mark a donor as clinically verified."""
    admin_id = session.get("user_id")
    db_ok, _, _ = test_db_connection()
    if db_ok:
        User.set_verified(user_id, status=True)
        AdminActivityLog.log(
            admin_user_id=admin_id,
            action_type="DONOR_VERIFIED",
            target_entity="donor_profiles",
            target_id=user_id,
            description=f"Admin verified medical credentials for donor ID {user_id}",
            ip_address=request.remote_addr
        )
    flash(f"Donor profile #{user_id} successfully marked as Clinically Verified.", "success")
    return redirect(request.referrer or url_for("admin.dashboard"))


@admin_bp.route("/users/<int:user_id>/toggle-status", methods=["POST"])
@login_required
@role_required("admin")
def toggle_user_status(user_id: int):
    """Admin action to activate or deactivate user accounts."""
    admin_id = session.get("user_id")
    current_status = request.form.get("status") in ("1", "true", "True")
    new_status = not current_status

    db_ok, _, _ = test_db_connection()
    if db_ok:
        User.set_active(user_id, status=new_status)
        AdminActivityLog.log(
            admin_user_id=admin_id,
            action_type="ACCOUNT_STATUS_CHANGE",
            target_entity="users",
            target_id=user_id,
            description=f"Admin changed user #{user_id} active status to {new_status}",
            ip_address=request.remote_addr
        )
    flash(f"User account #{user_id} is now {'Active' if new_status else 'Deactivated'}.", "info")
    return redirect(request.referrer or url_for("admin.manage_users"))


@admin_bp.route("/requests/<int:request_id>/moderate", methods=["POST"])
@login_required
@role_required("admin")
def moderate_request(request_id: int):
    """Admin moderation action to fulfill or cancel a request."""
    admin_id = session.get("user_id")
    new_status = request.form.get("status", "FULFILLED").upper()

    BloodRequest.update_status(request_id, new_status)
    AdminActivityLog.log(
        admin_user_id=admin_id,
        action_type="REQUEST_MODERATED",
        target_entity="blood_requests",
        target_id=request_id,
        description=f"Admin marked request #{request_id} as {new_status}",
        ip_address=request.remote_addr
    )
    flash(f"Request #{request_id} status updated to {new_status}.", "success")
    return redirect(request.referrer or url_for("admin.manage_requests"))
