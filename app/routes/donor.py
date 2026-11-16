"""
LifeLink - Donor Portal Blueprint
Handles donor dashboard, live availability toggle, medical profile editing,
contact preferences, donation logging, and volunteer history.
"""

from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from app.models.donor import Donor
from app.models.blood_request import BloodRequest
from app.models.response import RequestResponse
from app.models.notification import Notification
from app.services.auth_service import login_required, role_required
from app.services.donor_service import check_eligibility, DONOR_SCREENING_QUESTIONS
from app.services.security import validate_donor_profile_payload
from app.extensions import test_db_connection

donor_bp = Blueprint("donor", __name__, url_prefix="/donor")


@donor_bp.route("/dashboard")
@login_required
@role_required("donor", "patient", "admin")
def dashboard():
    """Renders the donor dashboard overview with real-time stats, screening questions, and local requests."""
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    donor_profile = Donor.find_by_user_id(user_id)
    recent_requests = []
    eligibility_status = {}
    responded_requests = []
    notifications = []

    profile_completion = Donor.calculate_profile_completion(donor_profile)

    if donor_profile:
        recent_requests = BloodRequest.get_active(limit=10, city=donor_profile.get("city"))
        _, _, eligibility_status = check_eligibility(
            birth_date=donor_profile.get("date_of_birth"),
            weight_kg=float(donor_profile.get("weight_kg", 55.0) or 55.0),
            last_donation=donor_profile.get("last_donation_date"),
            gender=donor_profile.get("gender"),
            medical_notes=donor_profile.get("medical_notes")
        )
        responded_requests = RequestResponse.find_by_donor(user_id)
        notifications = Notification.get_by_user(user_id, limit=10)

    return render_template(
        "donor/dashboard.html",
        donor=donor_profile,
        profile_completion=profile_completion,
        requests=recent_requests,
        responded_requests=responded_requests,
        notifications=notifications,
        eligibility=eligibility_status,
        screening_questions=DONOR_SCREENING_QUESTIONS
    )


@donor_bp.route("/availability", methods=["POST"])
@login_required
@role_required("donor", "patient", "admin")
def toggle_availability():
    """AJAX endpoint for toggling donor emergency availability state."""
    data = request.get_json(silent=True) or request.form
    is_available = data.get("is_available") in [True, "true", "1", 1, "on"]
    user_id = session.get("user_id")

    db_ok, _, _ = test_db_connection()
    if db_ok and user_id:
        Donor.set_availability(user_id, is_available)

    return jsonify({
        "success": True,
        "is_available": is_available,
        "message": f"Availability updated to {'AVAILABLE' if is_available else 'PAUSED'}."
    })


@donor_bp.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("donor", "patient", "admin")
def profile():
    """Allows donor to edit profile, location, contact preferences, and discoverability."""
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    donor_profile = Donor.find_by_user_id(user_id)

    if request.method == "POST":
        weight_kg = request.form.get("weight_kg", "55.0")
        state = request.form.get("state", "").strip()
        city = request.form.get("city", "").strip()
        district = request.form.get("district", "").strip()
        pin_code = request.form.get("pin_code", "").strip()
        contact_preference = request.form.get("contact_preference", "both").strip().lower()
        is_discoverable = request.form.get("is_discoverable") in ("1", "true", "on")
        medical_notes = request.form.get("medical_notes", "").strip()

        payload = {
            "blood_group": donor_profile.get("blood_group", "O+") if donor_profile else "O+",
            "weight_kg": weight_kg,
            "city": city,
            "state": state,
            "district": district,
            "date_of_birth": str(donor_profile.get("date_of_birth", "2000-01-01")) if donor_profile else "2000-01-01",
        }
        valid, errors = validate_donor_profile_payload(payload)
        if not valid:
            for err in errors.values():
                flash(err, "danger")
            return redirect(url_for("donor.profile"))

        db_ok, _, _ = test_db_connection()
        if db_ok and user_id:
            if not donor_profile:
                # User has not created donor profile yet - create it now
                blood_group = request.form.get("blood_group", "O+").strip().upper()
                Donor.create(
                    user_id=user_id,
                    blood_group=blood_group,
                    gender=request.form.get("gender", "other"),
                    date_of_birth=request.form.get("date_of_birth", "2000-01-01"),
                    weight_kg=float(weight_kg),
                    state=state,
                    city=city,
                    district=district,
                    pin_code=pin_code,
                    contact_preference=contact_preference,
                    is_discoverable=is_discoverable,
                    medical_notes=medical_notes
                )
                session["has_donor_profile"] = True
                flash("Your Blood Donor Profile has been created successfully!", "success")
            else:
                Donor.update_profile(
                    user_id=user_id,
                    weight_kg=float(weight_kg),
                    state=state,
                    city=city,
                    district=district,
                    pin_code=pin_code,
                    contact_preference=contact_preference,
                    is_discoverable=is_discoverable,
                    medical_notes=medical_notes
                )
                flash("Donor profile and contact preferences updated successfully.", "success")
        else:
            flash("Database connection offline.", "danger")

        return redirect(url_for("donor.dashboard"))

    profile_completion = Donor.calculate_profile_completion(donor_profile)
    return render_template(
        "donor/dashboard.html", 
        donor=donor_profile, 
        profile_completion=profile_completion,
        edit_mode=True
    )


@donor_bp.route("/history", methods=["GET", "POST"])
@login_required
@role_required("donor", "patient", "admin")
def donation_history():
    """Allows recording a completed donation and viewing history."""
    user_id = session.get("user_id")

    if request.method == "POST":
        donation_date = request.form.get("donation_date")
        db_ok, _, _ = test_db_connection()
        if db_ok and user_id:
            Donor.record_donation(user_id, donation_date)
            flash("Donation recorded! Thank you for saving lives.", "success")
        else:
            flash("Database connection offline.", "danger")
        return redirect(url_for("donor.dashboard"))

    return redirect(url_for("donor.dashboard"))
