"""
LifeLink - Security & Validation Layer
Provides CSRF protection, client IP rate limiting, input sanitizers,
and server-side validation rules.
"""

import re
import time
import secrets
import logging
from datetime import datetime, date
from functools import wraps
from typing import Dict, Tuple, Optional, Any, List
from flask import session, request, abort, render_template, current_app

logger = logging.getLogger(__name__)

# Allowed blood groups
VALID_BLOOD_GROUPS = {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"}

# In-memory sliding window rate limiter store: {client_ip_endpoint: [(timestamp), ...]}
_RATE_LIMIT_STORE: Dict[str, List[float]] = {}


# ==============================================================================
# 1. CSRF PROTECTION (SESSION-BOUND CRYPTOGRAPHIC TOKEN)
# ==============================================================================

def generate_csrf_token() -> str:
    """Generates or retrieves the active session-bound CSRF token."""
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]


def validate_csrf():
    """
    Validates CSRF token on unsafe HTTP methods (POST, PUT, DELETE, PATCH).
    Exempts GET, HEAD, OPTIONS.
    """
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        # Check endpoint exemption
        endpoint = request.endpoint
        if endpoint and getattr(current_app.view_functions.get(endpoint, None), "_csrf_exempt", False):
            return

        # Retrieve token from form payload, JSON, or request header
        token = (
            request.form.get("csrf_token")
            or request.headers.get("X-CSRFToken")
            or (request.get_json(silent=True) or {}).get("csrf_token")
        )

        session_token = session.get("_csrf_token")
        if not session_token or not token or not secrets.compare_digest(session_token, token):
            logger.warning(f"CSRF validation failed for IP {request.remote_addr} on endpoint {request.endpoint}")
            abort(400, description="Invalid or missing CSRF token. Please refresh the page and try again.")


def csrf_exempt(f):
    """Decorator marking a view function as exempt from CSRF verification."""
    f._csrf_exempt = True
    return f


# ==============================================================================
# 2. IN-MEMORY RATE LIMITING (SLIDING WINDOW)
# ==============================================================================

def rate_limit(max_requests: int = 10, window_seconds: int = 60):
    """
    Decorator implementing an in-memory sliding window rate limiter per client IP.
    
    :param max_requests: Maximum allowed calls within the time window.
    :param window_seconds: Duration of the sliding window in seconds.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Bypass rate limit during automated test runs
            if current_app and current_app.config.get("TESTING", False):
                return f(*args, **kwargs)

            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr) or "127.0.0.1"
            # Normalize multi-ip headers
            client_ip = client_ip.split(",")[0].strip()
            bucket_key = f"{client_ip}:{request.endpoint}"
            now = time.time()

            # Clean expired timestamps
            timestamps = _RATE_LIMIT_STORE.get(bucket_key, [])
            valid_timestamps = [ts for ts in timestamps if now - ts < window_seconds]

            if len(valid_timestamps) >= max_requests:
                retry_after = int(window_seconds - (now - valid_timestamps[0]))
                logger.warning(f"Rate limit exceeded for {bucket_key}. Requests: {len(valid_timestamps)}/{max_requests}")
                response = abort(429, description=f"Too many requests. Please wait {retry_after} seconds before retrying.")
                return response

            valid_timestamps.append(now)
            _RATE_LIMIT_STORE[bucket_key] = valid_timestamps
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ==============================================================================
# 3. SERVER-SIDE INPUT VALIDATION & SANITIZATION
# ==============================================================================

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^\+?[0-9\s\-()]{7,20}$")


def validate_email(email: str) -> Tuple[bool, str]:
    """Validates email format."""
    if not email or len(email.strip()) > 120:
        return False, "Email address is required and cannot exceed 120 characters."
    if not EMAIL_REGEX.match(email.strip()):
        return False, "Please provide a valid email address."
    return True, ""


def validate_phone(phone: str) -> Tuple[bool, str]:
    """Validates phone number format."""
    if not phone or len(phone.strip()) < 7 or len(phone.strip()) > 20:
        return False, "Phone number must be between 7 and 20 characters."
    if not PHONE_REGEX.match(phone.strip()):
        return False, "Phone number contains invalid characters."
    return True, ""


def validate_blood_group(blood_group: str) -> Tuple[bool, str]:
    """Validates ABO and Rh blood group."""
    bg = (blood_group or "").strip().upper()
    if bg not in VALID_BLOOD_GROUPS:
        return False, f"Invalid blood group '{blood_group}'. Allowed values: {', '.join(sorted(VALID_BLOOD_GROUPS))}."
    return True, ""


def validate_password_strength(password: str) -> Tuple[bool, str]:
    """
    Enforces minimum security requirements for passwords.
    Minimum 8 characters with at least one letter and one number.
    """
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not any(c.isalpha() for c in password):
        return False, "Password must include at least one alphabetic letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must include at least one numerical digit."
    return True, ""


def validate_donor_profile_payload(data: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    """Comprehensive server-side validation for donor registration/editing."""
    errors: Dict[str, str] = {}

    # Blood group check
    ok, msg = validate_blood_group(data.get("blood_group", ""))
    if not ok:
        errors["blood_group"] = msg

    # Weight check (minimum 40 kg, standard whole blood recommendation >= 45-50 kg)
    try:
        weight = float(data.get("weight_kg", 0))
        if weight < 40.0 or weight > 250.0:
            errors["weight_kg"] = "Weight must be between 40.0 kg and 250.0 kg."
    except (ValueError, TypeError):
        errors["weight_kg"] = "Weight must be a valid numerical value."

    # Location checks
    if not (data.get("city") or "").strip():
        errors["city"] = "City name is required."
    if not (data.get("state") or "").strip():
        errors["state"] = "State / Province is required."
    if not (data.get("district") or "").strip():
        errors["district"] = "District or area name is required."

    # Date of birth / age check
    dob_str = (data.get("date_of_birth") or "").strip()
    if not dob_str:
        errors["date_of_birth"] = "Date of birth is required."
    else:
        try:
            from datetime import datetime, date
            dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if age < 18 or age > 65:
                errors["date_of_birth"] = f"Voluntary blood donors must be between 18 and 65 years old (age calculated: {age})."
        except ValueError:
            errors["date_of_birth"] = "Invalid date format. Use YYYY-MM-DD."

    return (len(errors) == 0, errors)


def validate_blood_request_payload(data: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    """Comprehensive server-side validation for emergency blood requests."""
    errors: Dict[str, str] = {}

    # 1. Patient name
    if not (data.get("patient_name") or "").strip():
        errors["patient_name"] = "Patient name is required."

    # 2. Contact phone
    ok_phone, msg_phone = validate_phone(data.get("contact_phone", ""))
    if not ok_phone:
        errors["contact_phone"] = msg_phone

    # 3. Contact email (optional, but validated if provided)
    contact_email = (data.get("contact_email") or "").strip()
    if contact_email:
        ok_email, msg_email = validate_email(contact_email)
        if not ok_email:
            errors["contact_email"] = msg_email

    # 4. Blood group
    ok, msg = validate_blood_group(data.get("blood_group", ""))
    if not ok:
        errors["blood_group"] = msg

    # 5. Units needed
    try:
        units = int(data.get("units_needed", 0))
        if units < 1 or units > 20:
            errors["units_needed"] = "Units required must be between 1 and 20."
    except (ValueError, TypeError):
        errors["units_needed"] = "Units needed must be a positive integer."

    # 6. Urgency Level (Critical, Urgent, Normal / Standard)
    urgency = (data.get("urgency_level") or "").strip().upper()
    if urgency in ("NORMAL", "STANDARD", "URGENT", "CRITICAL"):
        pass
    else:
        errors["urgency_level"] = "Urgency must be Critical, Urgent, or Normal."

    # 7. Hospital details
    if not (data.get("hospital_name") or "").strip():
        errors["hospital_name"] = "Hospital name is required."
    if not (data.get("hospital_address") or data.get("hospital_location") or "").strip():
        errors["hospital_address"] = "Hospital location / address is required."
    if not (data.get("city") or "").strip():
        errors["city"] = "Hospital city is required."

    # 8. Contact person
    if not (data.get("contact_person") or "").strip():
        errors["contact_person"] = "Contact person / attendant name is required."

    # 9. Preferred Contact Method
    pref_method = (data.get("preferred_contact_method") or "phone").strip().lower()
    if pref_method not in ("phone", "whatsapp", "email", "call_or_msg"):
        errors["preferred_contact_method"] = "Invalid preferred contact method selected."

    # 10. Required Date validation (optional, defaults to current date)
    req_date = (data.get("required_date") or "").strip()
    if req_date:
        try:
            parsed_date = datetime.strptime(req_date, "%Y-%m-%d").date()
            if parsed_date < date.today():
                errors["required_date"] = "Required transfusion date cannot be in the past."
        except ValueError:
            errors["required_date"] = "Invalid date format for required date. Expected YYYY-MM-DD."

    return (len(errors) == 0, errors)
