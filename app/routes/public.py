"""
LifeLink - Public Routes Blueprint
Handles public landing page, privacy-preserving donor search, about page,
contact inquiries, and secure donor contact alerts.
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from app.models.donor import Donor
from app.models.blood_request import BloodRequest
from app.models.message import ContactMessage
from app.models.notification import Notification
from app.services.matching_service import get_compatible_donors
from app.services.security import rate_limit, validate_email, validate_phone
from app.extensions import test_db_connection

public_bp = Blueprint("public", __name__)

# Fictional fallback demo donors for preview / offline demonstration
FALLBACK_DEMO_DONORS = [
    {
        "id": 1,
        "user_id": 2,
        "display_name": "Sarah J.",
        "blood_group": "O-",
        "city": "Central Metro",
        "district": "District 1",
        "state": "Metro State",
        "is_available": True,
        "total_donations": 6,
        "contact_preference": "both",
        "is_verified": True,
        "is_demo": True
    },
    {
        "id": 2,
        "user_id": 3,
        "display_name": "Dr. David C.",
        "blood_group": "O+",
        "city": "Central Metro",
        "district": "North Hub",
        "state": "Metro State",
        "is_available": True,
        "total_donations": 14,
        "contact_preference": "phone",
        "is_verified": True,
        "is_demo": True
    },
    {
        "id": 3,
        "user_id": 4,
        "display_name": "Elena R.",
        "blood_group": "A+",
        "city": "Central Metro",
        "district": "West Avenue",
        "state": "Metro State",
        "is_available": True,
        "total_donations": 5,
        "contact_preference": "email",
        "is_verified": True,
        "is_demo": True
    },
    {
        "id": 4,
        "user_id": 6,
        "display_name": "Amina A.",
        "blood_group": "B+",
        "city": "Central Metro",
        "district": "South Ridge",
        "state": "Metro State",
        "is_available": True,
        "total_donations": 3,
        "contact_preference": "both",
        "is_verified": True,
        "is_demo": True
    },
    {
        "id": 5,
        "user_id": 7,
        "display_name": "Liam O.",
        "blood_group": "B-",
        "city": "Central Metro",
        "district": "East Metro",
        "state": "Metro State",
        "is_available": True,
        "total_donations": 8,
        "contact_preference": "phone",
        "is_verified": True,
        "is_demo": True
    },
    {
        "id": 6,
        "user_id": 8,
        "display_name": "Priya P.",
        "blood_group": "AB+",
        "city": "Central Metro",
        "district": "North Hub",
        "state": "Metro State",
        "is_available": True,
        "total_donations": 4,
        "contact_preference": "both",
        "is_verified": True,
        "is_demo": True
    }
]


@public_bp.route("/")
def index():
    """Renders the main platform homepage with statistics and emergency ticker."""
    active_requests = []
    stats = {}

    db_ok, _, _ = test_db_connection()
    if db_ok:
        active_requests = BloodRequest.get_active(limit=5)
        stats = Donor.get_aggregate_stats()

    return render_template(
        "public/index.html",
        active_requests=active_requests,
        stats=stats
    )


@public_bp.route("/find-donors")
def find_donors():
    """
    Handles privacy-preserving donor search.
    Supports both server-rendered HTML and asynchronous JSON API requests.
    Only shows donors who have opted in to be discoverable (`is_discoverable = TRUE`).
    Never exposes street addresses or private personal information.
    """
    blood_group = request.args.get("blood_group", "").strip().upper()
    location = request.args.get("location", "").strip()
    include_compatible = request.args.get("compatible", "1") in ("1", "true", "on")
    available_only = request.args.get("available_only", "1") in ("1", "true", "on")

    # Determine blood groups to match
    search_groups = []
    if blood_group and blood_group != "ALL":
        if include_compatible:
            search_groups = get_compatible_donors(blood_group)
        else:
            search_groups = [blood_group]

    donors = []
    db_ok, _, _ = test_db_connection()

    if db_ok:
        donors = Donor.search_privacy_filtered(
            blood_groups=search_groups,
            city=location if location else None,
            limit=50
        )
    else:
        # Fallback to simulated demo donors
        donors = [d for d in FALLBACK_DEMO_DONORS if not available_only or d["is_available"]]
        if search_groups:
            donors = [d for d in donors if d["blood_group"] in search_groups]
        if location:
            donors = [d for d in donors if location.lower() in d["city"].lower() or location.lower() in d["district"].lower()]

    # Return JSON response for AJAX requests
    if request.headers.get("Accept") == "application/json" or request.args.get("format") == "json":
        return jsonify({
            "success": True,
            "count": len(donors),
            "donors": donors,
            "query": {
                "blood_group": blood_group,
                "location": location,
                "compatible": include_compatible,
                "available_only": available_only
            }
        })

    return render_template(
        "public/search.html",
        donors=donors,
        selected_blood_group=blood_group or "ALL",
        selected_location=location,
        include_compatible=include_compatible,
        available_only=available_only
    )


@public_bp.route("/api/donors/contact-request", methods=["POST"])
@rate_limit(max_requests=10, window_seconds=60)
def contact_donor_request():
    """
    Mediated contact request API.
    Enables requesters to notify a donor without discovering the donor's private phone or email.
    """
    data = request.get_json(silent=True) or request.form
    donor_user_id = data.get("donor_user_id")
    requester_name = (data.get("requester_name") or "").strip()
    requester_phone = (data.get("requester_phone") or "").strip()
    case_notes = (data.get("case_notes") or "").strip()

    if not donor_user_id or not requester_name or not requester_phone:
        return jsonify({"success": False, "message": "Requester name and contact phone are required."}), 400

    ok, err = validate_phone(requester_phone)
    if not ok:
        return jsonify({"success": False, "message": err}), 400

    db_ok, _, _ = test_db_connection()
    if db_ok:
        Notification.create(
            user_id=int(donor_user_id),
            title="Emergency Transfusion Contact Alert",
            message=f"{requester_name} has requested urgent blood donation coordination. Reach out at {requester_phone}. Notes: {case_notes}",
            notification_type="EMERGENCY_ALERT"
        )

    return jsonify({
        "success": True,
        "message": f"Your urgent contact alert has been delivered to the donor's notifications."
    })


@public_bp.route("/about")
def about():
    """Renders about page, interactive eligibility guide, and compatibility matrix."""
    return render_template("public/about.html")


@public_bp.route("/dashboard")
def general_dashboard():
    """Smart role-based dashboard router."""
    from flask import session
    if "user_id" not in session:
        return redirect(url_for("auth.login"))

    role = session.get("user_role")
    if role == "admin":
        return redirect(url_for("admin.dashboard"))
    elif session.get("has_donor_profile") or role == "donor":
        return redirect(url_for("donor.dashboard"))
    return redirect(url_for("patient.dashboard"))


@public_bp.route("/dashboard-router")
def dashboard_router():
    """Alias for general dashboard."""
    return general_dashboard()


@public_bp.route("/admin-dashboard.html")
def legacy_admin_dashboard_redirect():
    """Redirects legacy direct /admin-dashboard.html requests to the canonical Flask route."""
    return redirect(url_for("admin.dashboard"))


@public_bp.route("/emergency-request", methods=["GET", "POST"])
@public_bp.route("/emergency-request.html", methods=["GET", "POST"])
def emergency_request():
    """Canonical Emergency Blood Request entry point."""
    return redirect(url_for("requests.create_request"))


@public_bp.route("/track-request")
@public_bp.route("/track-request.html")
def track_request_public():
    """Canonical Request Tracking entry point."""
    from app.routes.requests import track_lookup
    return track_lookup()


@public_bp.route("/contact", methods=["GET", "POST"])
@rate_limit(max_requests=5, window_seconds=60)
def contact():
    """Handles contact submissions with rate limiting and input validation."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()

        ok, err = validate_email(email)
        if not ok:
            flash(err, "danger")
            return redirect(url_for("public.contact"))

        if not name or not message:
            flash("Please complete all required fields.", "warning")
            return redirect(url_for("public.contact"))

        db_ok, _, _ = test_db_connection()
        if db_ok:
            ContactMessage.create(name, email, subject, message)
            flash("Thank you for reaching out. A LifeLink coordinator will respond promptly.", "success")
        else:
            flash("Inquiry sent (Demo Mode).", "info")

        return redirect(url_for("public.contact"))

    return render_template("public/about.html")
