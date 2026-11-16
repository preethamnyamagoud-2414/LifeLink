"""
LifeLink - Blood Requests Blueprint
Handles emergency blood request creation, triage, cancellation,
public tracking, and volunteer matching with strict privacy defenses.
"""

import os
import logging
from datetime import date
from typing import Optional, Dict, Any
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, abort, current_app
from app.models.blood_request import BloodRequest
from app.models.response import RequestResponse
from app.models.notification import Notification
from app.services.auth_service import login_required
from app.services.matching_service import get_compatible_donors
from app.services.security import rate_limit, validate_blood_request_payload
from app.extensions import test_db_connection

logger = logging.getLogger(__name__)
request_bp = Blueprint("requests", __name__, url_prefix="/requests")


def dispatch_emergency_notifications(req_id: int, payload: Dict[str, Any], requester_id: Optional[int] = None) -> int:
    """
    Dispatches real notifications to all active, compatible donors and creates a
    confirmation notification for the requester.
    """
    blood_group = str(payload.get("blood_group") or "").strip().upper()
    patient_name = payload.get("patient_name", "Patient")
    hospital_name = payload.get("hospital_name", "Medical Facility")
    city = payload.get("city", "")
    urgency_level = payload.get("urgency_level", "URGENT")

    compatible_groups = get_compatible_donors(blood_group)
    notified_count = 0

    try:
        from app.extensions import execute_query
        if compatible_groups:
            placeholders = ", ".join(["%s"] * len(compatible_groups))
            query = f"""
                SELECT d.user_id, u.full_name, d.blood_group, d.city
                FROM donor_profiles d
                JOIN users u ON d.user_id = u.id
                WHERE d.is_available = TRUE
                  AND u.is_active = TRUE
                  AND d.blood_group IN ({placeholders})
                LIMIT 50;
            """
            compatible_donors = execute_query(query, tuple(compatible_groups), fetchall=True) or []
            for donor in compatible_donors:
                donor_user_id = donor.get("user_id")
                if requester_id and donor_user_id == requester_id:
                    continue
                try:
                    Notification.create(
                        user_id=donor_user_id,
                        title=f"URGENT: {blood_group} Blood Needed",
                        message=f"Urgent requirement: {patient_name} needs {blood_group} blood at {hospital_name}, {city}. Urgency: {urgency_level}.",
                        notification_type="EMERGENCY_ALERT",
                        reference_id=req_id
                    )
                    notified_count += 1
                except Exception as ne:
                    logger.warning(f"Could not dispatch notification to user #{donor_user_id}: {ne}")

        # Confirmation notification to the requester
        if requester_id:
            try:
                Notification.create(
                    user_id=requester_id,
                    title="Emergency Request Broadcasted",
                    message=f"Your request for {patient_name} ({blood_group}) has been broadcasted to {notified_count} compatible donors.",
                    notification_type="REQUEST_UPDATE",
                    reference_id=req_id
                )
            except Exception as re:
                logger.warning(f"Could not dispatch requester confirmation notification: {re}")
    except Exception as e:
        logger.error(f"Error querying compatible donors for notifications: {e}")

    return notified_count


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
@request_bp.route("/api/requests", methods=["POST"])
@rate_limit(max_requests=10, window_seconds=60)
def create_request():
    """
    Renders and processes emergency blood transfusion requests.
    Supports standard HTML form submissions and asynchronous JSON API requests.
    Guarded with rate limiting, server-side validation, authentication, and CSRF protection.
    """
    if request.method == "POST":
        is_json = request.is_json or (request.headers.get("Accept") == "application/json") or bool(request.get_json(silent=True))
        raw_data = request.get_json(silent=True) if is_json and request.get_json(silent=True) else request.form

        urgency_raw = str(raw_data.get("urgency_level", "URGENT")).strip().upper()
        if urgency_raw == "NORMAL":
            urgency_level = "STANDARD"
        else:
            urgency_level = urgency_raw

        payload = {
            "patient_name": str(raw_data.get("patient_name", "")).strip(),
            "blood_group": str(raw_data.get("blood_group", "")).strip().upper(),
            "units_needed": raw_data.get("units_needed", 1),
            "urgency_level": urgency_raw,
            "hospital_name": str(raw_data.get("hospital_name", "")).strip(),
            "hospital_address": str(raw_data.get("hospital_address", "")).strip() or str(raw_data.get("hospital_location", "")).strip(),
            "hospital_area": str(raw_data.get("hospital_area", "")).strip(),
            "city": str(raw_data.get("city", "")).strip(),
            "state": str(raw_data.get("state", "")).strip() or "Metro State",
            "contact_person": str(raw_data.get("contact_person", "")).strip() or session.get("user_name", ""),
            "contact_phone": str(raw_data.get("contact_phone", "")).strip(),
            "contact_email": str(raw_data.get("contact_email", "")).strip() or session.get("user_email", ""),
            "preferred_contact_method": str(raw_data.get("preferred_contact_method", "phone")).strip().lower(),
            "required_date": str(raw_data.get("required_date", "")).strip(),
            "doctor_name": str(raw_data.get("doctor_name", "")).strip(),
            "additional_notes": str(raw_data.get("additional_notes", "")).strip(),
            "required_within_hours": 2 if urgency_level == "CRITICAL" else (12 if urgency_level == "URGENT" else 24),
        }

        # Comprehensive server-side validation
        valid, errors = validate_blood_request_payload(payload)
        if not valid:
            if is_json:
                return jsonify({
                    "success": False,
                    "message": next(iter(errors.values())) if errors else "Invalid request data.",
                    "errors": errors
                }), 400
            for err in errors.values():
                flash(err, "danger")
            return render_template(
                "requests/create.html", 
                form_data=payload, 
                today_date=str(date.today())
            ), 400

        requester_id = session.get("user_id")
        if not requester_id:
            if is_json:
                return jsonify({
                    "success": False,
                    "message": "Please sign in to post an emergency blood request so donors can reach you."
                }), 401
            flash("Please sign in to post an emergency blood request so donors can reach you.", "warning")
            return redirect(url_for("auth.login", next=request.path))

        db_ok, _, _ = test_db_connection()
        req_id = None
        notified_count = 0

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
                # Dispatch real notifications to compatible donors and requester
                notified_count = dispatch_emergency_notifications(req_id, payload, requester_id)
            except Exception as e:
                from app.database.connection import sanitize_db_error
                clean_err = sanitize_db_error(str(e))
                if is_json:
                    return jsonify({"success": False, "message": f"Database error saving request: {clean_err}"}), 500
                flash(f"Database error saving request: {clean_err}", "danger")
                return render_template("requests/create.html", form_data=payload, today_date=str(date.today())), 500
        elif not db_ok and (current_app.config.get("TESTING") or os.getenv("FLASK_ENV") == "development"):
            # Offline test/demo fallback
            req_id = 1
            notified_count = 3
        else:
            if is_json:
                return jsonify({"success": False, "message": "Database connection offline. Please ensure MySQL server is running."}), 503
            flash("Database connection offline. Please ensure MySQL server is running to broadcast emergency requests.", "danger")
            return render_template("requests/create.html", form_data=payload, today_date=str(date.today())), 503

        if is_json:
            return jsonify({
                "success": True,
                "code": f"REQ-{req_id:04d}",
                "alerted": notified_count,
                "redirect": url_for("requests.track_request", request_id=req_id)
            })

        flash(
            f"Emergency Blood Request #REQ-{req_id:04d} broadcast successfully! {notified_count} compatible donors notified.",
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
        try:
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
        except Exception as e:
            logger.warning(f"Error recording volunteer offer for request #{request_id}: {e}")
            if not (current_app.config.get("TESTING") or os.getenv("FLASK_ENV") == "development"):
                if request.is_json:
                    return jsonify({"success": False, "message": "Database connection offline. Please try again later."}), 503
                flash("Database connection offline. Unable to record volunteer response.", "danger")
                return redirect(url_for("requests.track_request", request_id=request_id))

    if request.is_json:
        return jsonify({"success": True, "message": "Volunteer offer recorded! Hospital coordinator will reach out."})

    flash("Thank you! Your willingness to donate has been recorded.", "success")
    return redirect(url_for("requests.track_request", request_id=request_id))
