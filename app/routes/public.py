"""
LifeLink - Public Routes Blueprint
Handles public landing page, privacy-preserving donor search, about page,
contact inquiries, and secure donor contact alerts.
"""

import os
import json
import logging
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, current_app, session
from app.models.donor import Donor
from app.models.blood_request import BloodRequest
from app.models.message import ContactMessage
from app.models.notification import Notification
from app.models.user import User
from app.services.matching_service import get_compatible_donors
from app.services.donor_service import check_eligibility, DONOR_SCREENING_QUESTIONS
from app.services.auth_service import login_user
from app.services.security import rate_limit, validate_email, validate_phone, validate_password_strength
from app.extensions import test_db_connection

logger = logging.getLogger(__name__)
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
        ["pages/index.html", "public/index.html"],
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
    elif current_app.config.get("TESTING") or os.getenv("FLASK_ENV") == "development":
        donors = [d for d in FALLBACK_DEMO_DONORS if not available_only or d["is_available"]]
        if search_groups:
            donors = [d for d in donors if d["blood_group"] in search_groups]
        if location:
            donors = [d for d in donors if location.lower() in d["city"].lower() or location.lower() in d.get("district", "").lower()]
    else:
        donors = []
        flash("Database connection offline. Please ensure MySQL server is running and configured to search live donors.", "warning")

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
        ["pages/search.html", "public/search.html"],
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
    return render_template(["pages/about.html", "public/about.html"])


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
    if request.method == "POST":
        from app.routes.requests import create_request
        return create_request()
    return redirect(url_for("requests.create_request"))


@public_bp.route("/api/requests", methods=["POST"])
def api_create_request():
    """Asynchronous JSON endpoint for emergency blood requests."""
    from app.routes.requests import create_request
    return create_request()


@public_bp.route("/api/auth/me")
def api_auth_me():
    """Returns current user session, donor profile, and unread notification count."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    user = None
    try:
        from app.models.user import User
        user = User.find_by_id(user_id)
    except Exception as e:
        logger.warning(f"Database error fetching user #{user_id}: {e}")

    if not user:
        if current_app.config.get("TESTING") or os.getenv("FLASK_ENV") == "development":
            user = {
                "id": user_id,
                "full_name": session.get("user_name", "Member"),
                "email": session.get("user_email", "user@lifelink.local"),
                "phone": "+1-555-019-0010",
                "role": session.get("user_role", "patient"),
                "city": "Central Metro",
                "district": "District 1"
            }
        else:
            session.clear()
            return jsonify({"success": False, "message": "User not found"}), 401

    donor = None
    try:
        donor = Donor.find_by_user_id(user_id)
    except Exception:
        pass

    unread_count = 0
    try:
        unread_notifs = Notification.get_by_user(user_id, unread_only=True)
        unread_count = len(unread_notifs)
    except Exception:
        pass

    role = user.get("role", "patient")
    if role == "admin":
        dash_url = "/admin/dashboard"
    elif role == "donor" or session.get("has_donor_profile"):
        dash_url = "/donor/dashboard"
    else:
        dash_url = "/patient/dashboard"

    return jsonify({
        "success": True,
        "user": {
            "id": user["id"],
            "full_name": user["full_name"],
            "email": user["email"],
            "phone": user.get("phone") or (donor.get("phone") if donor else ""),
            "city": (donor.get("city") if donor else "") or user.get("city", ""),
            "district": (donor.get("district") if donor else "") or user.get("district", ""),
            "role": role
        },
        "donor": donor,
        "unread_notifications": unread_count,
        "dashboard": dash_url
    })


@public_bp.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """Asynchronous JSON logout endpoint."""
    from app.services.auth_service import logout_user
    logout_user()
    return jsonify({"success": True, "message": "Logged out successfully."})


@public_bp.route("/api/donors/search")
def api_donors_search():
    """Alias for donor search API."""
    return find_donors()


@public_bp.route("/api/profile", methods=["POST"])
def api_update_profile():
    """Asynchronous profile update endpoint."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    data = request.get_json(silent=True) or request.form
    full_name = str(data.get("full_name") or "").strip()
    phone = str(data.get("phone") or "").strip()
    city = str(data.get("city") or "").strip()
    district = str(data.get("district") or "").strip()

    if not full_name or not phone:
        return jsonify({"success": False, "message": "Name and phone are required."}), 400

    ok_p, err_p = validate_phone(phone)
    if not ok_p:
        return jsonify({"success": False, "message": err_p}), 400

    db_ok, _, _ = test_db_connection()
    if db_ok:
        try:
            from app.extensions import execute_query
            execute_query(
                "UPDATE users SET full_name = %s, phone = %s WHERE id = %s;",
                (full_name, phone, user_id),
                commit=True
            )
            execute_query(
                "UPDATE donor_profiles SET city = %s, district = %s WHERE user_id = %s;",
                (city, district, user_id),
                commit=True
            )
        except Exception as e:
            logger.error(f"Error updating user profile #{user_id}: {e}")
            return jsonify({"success": False, "message": "Database error saving profile."}), 500

    session["user_name"] = full_name
    return jsonify({"success": True, "message": "Profile updated successfully."})


@public_bp.route("/api/donor/profile", methods=["POST"])
def api_donor_profile():
    """Asynchronous endpoint to update health screening answers, donor vitals, and check clinical eligibility."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"success": False, "message": "Authentication required."}), 401

    data = request.get_json(silent=True) or request.form
    answers = data.get("answers") or {}
    if not answers and "screening_unwell" in request.form:
        answers = {
            "unwell": request.form.get("screening_unwell") == "yes",
            "antibiotics": request.form.get("screening_antibiotics") == "yes",
            "tattoo": request.form.get("screening_tattoo") == "yes",
            "surgery": request.form.get("screening_surgery") == "yes",
            "malaria": request.form.get("screening_malaria") == "yes",
            "pregnant": request.form.get("screening_pregnant") == "yes",
            "blood_pressure": request.form.get("screening_blood_pressure") == "yes",
            "infection": request.form.get("screening_infection") == "yes",
            "chronic": request.form.get("screening_chronic") == "yes",
            "insulin": request.form.get("screening_insulin") == "yes",
        }

    weight_val = data.get("weight_kg")
    weight_kg = None
    if weight_val is not None and str(weight_val).strip():
        try:
            weight_kg = float(weight_val)
        except ValueError:
            weight_kg = None

    city = (data.get("city") or "").strip() or None
    district = (data.get("district") or "").strip() or None
    gender = (data.get("gender") or "").strip().lower() or None
    dob = (data.get("dob") or data.get("date_of_birth") or "").strip() or None
    blood_group = (data.get("blood_group") or "").strip().upper() or None
    consent = data.get("consent") in (True, "true", "1", 1, "on")

    notes_payload = {
        "screened_at": datetime.now(timezone.utc).isoformat(),
        "answers": answers,
        "consent": consent
    }
    notes_json = json.dumps(notes_payload)

    db_ok, _, _ = test_db_connection()
    donor = None
    if db_ok:
        donor = Donor.find_by_user_id(user_id)
        if not donor:
            Donor.create(
                user_id=user_id,
                blood_group=blood_group or "O+",
                gender=gender or "other",
                date_of_birth=dob or "2000-01-01",
                weight_kg=weight_kg or 55.0,
                state="Metro State",
                city=city or "Central Metro",
                district=district or "District 1",
                pin_code="00000",
                medical_notes=notes_json
            )
            session["has_donor_profile"] = True
            donor = Donor.find_by_user_id(user_id)
        else:
            Donor.update_clinical_screening(
                user_id=user_id,
                medical_notes=notes_json,
                weight_kg=weight_kg,
                city=city,
                district=district
            )
            donor = Donor.find_by_user_id(user_id)

    is_eligible, message, eligibility_status = check_eligibility(
        birth_date=dob or (donor.get("date_of_birth") if donor else None),
        weight_kg=weight_kg or (float(donor.get("weight_kg", 55.0)) if donor else 55.0),
        last_donation=donor.get("last_donation_date") if donor else None,
        gender=gender or (donor.get("gender") if donor else None),
        screening_answers=answers,
        medical_notes=notes_json
    )

    return jsonify({
        "success": True,
        "message": "Health screening questionnaire updated successfully.",
        "donor": {
            **(donor or {}),
            "eligibility": eligibility_status
        }
    })


@public_bp.route("/api/auth/register", methods=["POST"])
@rate_limit(max_requests=30, window_seconds=60)
def api_auth_register():
    """Asynchronous JSON endpoint for member and donor registration."""
    data = request.get_json(silent=True) or request.form
    full_name = str(data.get("full_name") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    phone = str(data.get("phone") or "").strip()
    password = str(data.get("password") or "")
    become_donor = data.get("become_donor") in (True, "true", "1", 1, "on") or bool(data.get("donor"))

    if not full_name:
        return jsonify({"success": False, "message": "Full name is required."}), 400

    ok_email, err_email = validate_email(email)
    if not ok_email:
        return jsonify({"success": False, "message": err_email}), 400

    ok_phone, err_phone = validate_phone(phone)
    if not ok_phone:
        return jsonify({"success": False, "message": err_phone}), 400

    ok_pwd, err_pwd = validate_password_strength(password)
    if not ok_pwd:
        return jsonify({"success": False, "message": err_pwd}), 400

    db_ok, _, _ = test_db_connection()
    if not db_ok and not (current_app.config.get("TESTING") or os.getenv("FLASK_ENV") == "development"):
        return jsonify({"success": False, "message": "Database connection offline. Please ensure MySQL server is running."}), 503

    role = "donor" if become_donor else "patient"

    if db_ok:
        if User.find_by_email(email):
            return jsonify({"success": False, "message": "An account with this email address already exists."}), 409

        if User.find_by_phone(phone):
            return jsonify({"success": False, "message": "An account with this phone number already exists."}), 409

        user_id = User.create(full_name, email, phone, password, role=role)
        created_user = User.find_by_id(user_id)
    else:
        user_id = 9999
        created_user = {"id": 9999, "full_name": full_name, "email": email, "phone": phone, "role": role}

    donor_obj = None
    eligibility_info = None

    if become_donor:
        donor_data = data.get("donor") or {}
        blood_group = (donor_data.get("blood_group") or data.get("blood_group") or "O+").strip().upper()
        gender = (donor_data.get("gender") or data.get("gender") or "other").strip().lower()
        dob = (donor_data.get("dob") or donor_data.get("date_of_birth") or data.get("date_of_birth") or "2000-01-01").strip()
        weight_val = donor_data.get("weight_kg") or data.get("weight_kg") or 55.0
        try:
            weight_kg = float(weight_val)
        except (ValueError, TypeError):
            weight_kg = 55.0

        city = (donor_data.get("city") or data.get("city") or "Central Metro").strip()
        district = (donor_data.get("district") or data.get("district") or "District 1").strip()
        state = (donor_data.get("state") or data.get("state") or "Metro State").strip()
        last_donation = donor_data.get("last_donation_date") or data.get("last_donation_date") or None
        answers = donor_data.get("answers") or {}

        notes_payload = {
            "screened_at": datetime.now(timezone.utc).isoformat(),
            "answers": answers,
            "consent": donor_data.get("consent") in (True, "true", "1", 1, "on")
        }
        notes_json = json.dumps(notes_payload)

        if db_ok:
            Donor.create(
                user_id=user_id,
                blood_group=blood_group,
                gender=gender,
                date_of_birth=dob,
                weight_kg=weight_kg,
                state=state,
                city=city,
                district=district,
                pin_code="00000",
                last_donation_date=last_donation,
                medical_notes=notes_json
            )
            donor_obj = Donor.find_by_user_id(user_id)
        else:
            donor_obj = {
                "id": 9999,
                "user_id": user_id,
                "blood_group": blood_group,
                "gender": gender,
                "date_of_birth": dob,
                "weight_kg": weight_kg,
                "city": city,
                "district": district,
                "state": state
            }

        _, _, eligibility_info = check_eligibility(
            birth_date=dob,
            weight_kg=weight_kg,
            last_donation=last_donation,
            gender=gender,
            screening_answers=answers,
            medical_notes=notes_json
        )

    if created_user:
        login_user(created_user)

    redirect_url = "/donor/dashboard" if become_donor else "/patient/dashboard"
    return jsonify({
        "success": True,
        "message": "Account created successfully.",
        "user": {
            "id": user_id,
            "full_name": full_name,
            "email": email,
            "phone": phone,
            "role": role
        },
        "donor": {
            **(donor_obj or {}),
            "eligibility": eligibility_info
        } if donor_obj else None,
        "redirect": redirect_url
    })


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

    return render_template(["pages/about.html", "public/about.html"])
