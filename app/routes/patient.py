"""
LifeLink - Patient / Requester Portal Blueprint
Handles patient dashboard, tracking open transfusion requests, viewing matched donors,
and managing submitted medical requisitions.
"""

from flask import Blueprint, render_template, session, redirect, url_for, flash
from app.models.blood_request import BloodRequest
from app.models.response import RequestResponse
from app.services.auth_service import login_required, role_required
from app.extensions import test_db_connection

patient_bp = Blueprint("patient", __name__, url_prefix="/patient")


@patient_bp.route("/dashboard")
@login_required
@role_required("patient", "donor", "admin")
def dashboard():
    """
    Renders the dedicated patient dashboard.
    Retrieves active requests, past requests, donor responses, and tracking links.
    """
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    all_requests = BloodRequest.find_by_requester(user_id)

    # Separate active from previous requests
    active_requests = [r for r in all_requests if r.get("status") == "ACTIVE"]
    previous_requests = [r for r in all_requests if r.get("status") in ("FULFILLED", "CANCELLED")]

    # Fetch donor volunteer responses for this patient's requests
    donor_responses = RequestResponse.find_by_patient(user_id)

    # Calculate summary metrics
    stats = {
        "active_count": len(active_requests),
        "total_requests": len(all_requests),
        "volunteers_count": len(donor_responses),
        "fulfilled_count": sum(1 for r in all_requests if r.get("status") == "FULFILLED")
    }

    return render_template(
        "patient/dashboard.html",
        active_requests=active_requests,
        previous_requests=previous_requests,
        donor_responses=donor_responses,
        stats=stats
    )
