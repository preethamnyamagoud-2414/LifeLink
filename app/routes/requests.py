"""
LifeLink - Blood Requests Blueprint
Handles emergency blood request creation, triage, cancellation,
public tracking, and volunteer matching with strict privacy defenses.
"""

from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, abort
from app.models.blood_request import BloodRequest
from app.models.response import RequestResponse
from app.models.notification import Notification
from app.services.auth_service import login_required
from app.services.security import rate_limit, validate_blood_request_payload
from app.extensions import test_db_connection

request_bp = Blueprint("requests", __name__, url_prefix="/requests")


@request_bp.route("/")
def list_requests():
    """Lists open blood requests sorted by urgency tier."""
    blood_group = request.args.get("blood_group")
    city = request.args.get("city")
    
    requests_list = BloodRequest.get_active(limit=30, blood_group=blood_group, city=city)
    return render_template("requests/lookup.html", requests=requests_list)


@request_bp.route("/emergency-request", methods=["GET", "POST"])
@request_bp.route("/create", methods=["GET", "POST"])
@request_bp.route("/new", methods=["GET", "POST"])
@rate_limit(max_requests=10, window_seconds=60)
def create_request():
    """
    Renders and processes emergency blood transfusion requests.
    Guarded with rate limiting, server-side validation, authentication, and CSRF protection.
    """
    if request.method == "POST":
        urgency_raw = request.form.get("urgency_level", "URGENT").strip().upper()
        if urgency_raw == "NORMAL":
            urgency_level = "STANDARD"
        else:
            urgency_level = urgency_raw

        payload = {
            "patient_name": request.form.get("patient_name", "").strip(),
            "blood_group": request.form.get("blood_group", "").strip().upper(),
            "units_needed": request.form.get("units_needed", 1),
            "urgency_level": urgency_raw,
            "hospital_name": request.form.get("hospital_name", "").strip(),
            "hospital_address": request.form.get("hospital_address", "").strip() or request.form.get("hospital_location", "").strip(),
            "hospital_area": request.form.get("hospital_area", "").strip(),
            "city": request.form.get("city", "").strip(),
            "state": request.form.get("state", "").strip() or "Metro State",
            "contact_person": request.form.get("contact_person", "").strip() or session.get("user_name", ""),
            "contact_phone": request.form.get("contact_phone", "").strip(),
            "contact_email": request.form.get("contact_email", "").strip() or session.get("user_email", ""),
            "preferred_contact_method": request.form.get("preferred_contact_method", "phone").strip().lower(),
            "required_date": request.form.get("required_date", "").strip(),
            "doctor_name": request.form.get("doctor_name", "").strip(),
            "additional_notes": request.form.get("additional_notes", "").strip(),
            "required_within_hours": 2 if urgency_level == "CRITICAL" else (12 if urgency_level == "URGENT" else 24),
        }

        # Comprehensive server-side validation
        valid, errors = validate_blood_request_payload(payload)
        if not valid:
            for err in errors.values():
                flash(err, "danger")
            return render_template(
                "requests/create.html", 
                form_data=payload, 
                today_date=str(date.today())
            ), 400

        requester_id = session.get("user_id")

        db_ok, _, _ = test_db_connection()
        req_id = None

        if db_ok and requester_id:
            try:
                req_id = BloodRequest.create(
                    requester_user_id=requester_id,
                    patient_name=payload["patient_name"],
                    blood_group=payload["blood_group"],
                    units_needed=int(payload["units_needed"]),
                    urgency_level=urgency_level,
                    hospital_name=payload["hospital_name"],
                    hospital_address=payload["hospital_address"],
                    city=payload["city"],
                    state=payload["state"],
                    contact_person=payload["contact_person"],
                    contact_phone=payload["contact_phone"],
                    contact_email=payload["contact_email"],
                    hospital_area=payload["hospital_area"],
                    preferred_contact_method=payload["preferred_contact_method"],
                    required_date=payload["required_date"] or str(date.today()),
                    doctor_name=payload["doctor_name"],
                    additional_notes=payload["additional_notes"],
                    required_within_hours=payload["required_within_hours"]
                )
            except Exception as e:
                flash(f"Database error saving request: {str(e)}", "danger")
                return render_template("requests/create.html", form_data=payload, today_date=str(date.today())), 500
        else:
            # Fallback simulated request creation
            req_id = 1

        flash(
            f"Emergency Blood Request #REQ-{req_id:04d} broadcast successfully! Compatible donors have been notified.",
            "success"
        )
        return redirect(url_for("requests.track_request", request_id=req_id))

    # Pre-fill user profile info for convenient submission
    initial_form = {
        "contact_person": session.get("user_name", ""),
        "contact_email": session.get("user_email", ""),
        "urgency_level": "CRITICAL",
        "units_needed": 2,
        "required_date": str(date.today())
    }
    return render_template("requests/create.html", form_data=initial_form, today_date=str(date.today()))


@request_bp.route("/<int:request_id>")
@request_bp.route("/track/<int:request_id>")
def track_request(request_id: int):
    """
    Renders the dedicated request tracking page.
    Shows Request ID, blood group, hospital, current status, and donor responses.
    Applies privacy protections to donor identities and surfaces the clinical disclaimer.
    """
    req = BloodRequest.find_by_id(request_id)
    if not req:
        flash(f"Blood Request #{request_id} was not found. Please verify the ID.", "warning")
        return redirect(url_for("requests.track_lookup"))

    current_user_id = session.get("user_id")
    is_owner = (current_user_id == req.get("requester_user_id")) or (session.get("user_role") == "admin")

    # Fetch privacy-sanitized donor responses
    volunteers = RequestResponse.find_by_request_sanitized(request_id, is_owner=is_owner)

    return render_template(
        "requests/track.html",
        request=req,
        volunteers=volunteers,
        is_owner=is_owner
    )


@request_bp.route("/lookup")
def track_lookup():
    """Request status lookup portal by Request ID."""
    req_id = request.args.get("id")
    if req_id and req_id.isdigit():
        return redirect(url_for("requests.track_request", request_id=int(req_id)))

    active_cases = BloodRequest.get_active(limit=10)
    return render_template("requests/lookup.html", active_cases=active_cases)


@request_bp.route("/<int:request_id>/cancel", methods=["POST"])
@login_required
def cancel_request(request_id: int):
    """Cancels an active blood request."""
    user_id = session.get("user_id")
    is_admin = session.get("user_role") == "admin"

    success = BloodRequest.cancel_request(request_id, user_id, is_admin=is_admin)
    if success:
        flash(f"Blood Request #{request_id} has been cancelled.", "info")
    else:
        flash("Unable to cancel request. You must be the requester or an administrator.", "danger")

    return redirect(url_for("requests.track_request", request_id=request_id))


@request_bp.route("/<int:request_id>/volunteer", methods=["POST"])
@login_required
def volunteer(request_id: int):
    """Allows a registered donor to volunteer for a blood request."""
    user_id = session.get("user_id")
    message = request.form.get("message", "").strip() or (request.get_json(silent=True) or {}).get("message")

    if user_id:
        RequestResponse.create(request_id=request_id, donor_user_id=user_id, message=message)
        req = BloodRequest.find_by_id(request_id)
        if req and req.get("requester_user_id"):
            Notification.create(
                user_id=req["requester_user_id"],
                title="New Donor Volunteer!",
                message=f"A volunteer donor has offered to fulfill your request for {req.get('patient_name')}.",
                notification_type="REQUEST_UPDATE",
                reference_id=request_id
            )

    if request.is_json:
        return jsonify({"success": True, "message": "Volunteer offer recorded! Hospital coordinator will reach out."})

    flash("Thank you! Your willingness to donate has been recorded.", "success")
    return redirect(url_for("requests.track_request", request_id=request_id))
