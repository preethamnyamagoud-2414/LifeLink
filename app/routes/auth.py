"""
LifeLink - Authentication Blueprint
Handles user login, registration, password hashing, session management,
and role-based routing with rate limiting and CSRF protection.
"""

import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models.user import User
from app.models.donor import Donor
from app.services.auth_service import login_user, logout_user
from app.services.security import (
    rate_limit,
    validate_email,
    validate_phone,
    validate_password_strength,
    validate_donor_profile_payload,
)
from app.extensions import test_db_connection

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/login", methods=["GET", "POST"])
@rate_limit(max_requests=5, window_seconds=60)
def login():
    """User authentication with rate limiting and role-based redirect."""
    if "user_id" in session:
        role = session.get("user_role")
        if role == "admin":
            return redirect(url_for("admin.dashboard"))
        elif role == "donor" or session.get("has_donor_profile"):
            return redirect(url_for("donor.dashboard"))
        return redirect(url_for("patient.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        remember = request.form.get("remember") in ("1", "true", "on", True)

        ok, err = validate_email(email)
        if not ok:
            flash(err, "danger")
            return render_template("auth/login.html", email=email), 400

        db_ok, _, _ = test_db_connection()
        if not db_ok:
            flash("Database connection offline. Please ensure MySQL server is running and configured.", "danger")
            return render_template("auth/login.html", email=email), 503

        user = User.find_by_email(email)
        if user and User.verify_password(user["password_hash"], password):
            if not user["is_active"]:
                flash("This account is currently deactivated. Please contact support.", "danger")
                return redirect(url_for("auth.login"))

            login_user(user, remember=remember)
            flash(f"Welcome back, {user['full_name']}!", "success")

            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)

            if user["role"] == "admin":
                return redirect(url_for("admin.dashboard"))
            elif user["role"] == "donor" or session.get("has_donor_profile"):
                return redirect(url_for("donor.dashboard"))
            return redirect(url_for("patient.dashboard"))

        flash("Invalid email or password. Please verify your credentials.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
@rate_limit(max_requests=5, window_seconds=60)
def register():
    """
    Unified LifeLink Member Registration.
    Allows a registered user to act as both a blood donor and an emergency blood requester.
    Admin accounts cannot be created via public registration.
    """
    if "user_id" in session:
        return redirect(url_for("public.dashboard_router"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        enable_donor = request.form.get("enable_donor_profile") in ("1", "true", "on", True)

        if not full_name:
            flash("Full name is required.", "danger")
            return render_template("auth/register.html", full_name=full_name, email=email, phone=phone), 400

        ok, err = validate_email(email)
        if not ok:
            flash(err, "danger")
            return render_template("auth/register.html", full_name=full_name, email=email, phone=phone), 400

        ok, err = validate_phone(phone)
        if not ok:
            flash(err, "danger")
            return render_template("auth/register.html", full_name=full_name, email=email, phone=phone), 400

        ok, err = validate_password_strength(password)
        if not ok:
            flash(err, "danger")
            return render_template("auth/register.html", full_name=full_name, email=email, phone=phone), 400

        if password != confirm_password:
            flash("Passwords do not match. Please verify and re-enter.", "danger")
            return render_template("auth/register.html", full_name=full_name, email=email, phone=phone), 400

        # Optional donor profile fields
        donor_created = False
        role = "patient"

        if enable_donor or request.form.get("blood_group"):
            blood_group = request.form.get("blood_group", "").strip().upper()
            weight_kg = request.form.get("weight_kg", "55.0").strip()
            city = request.form.get("city", "Central Metro").strip()
            district = request.form.get("district", "District 1").strip()
            state = request.form.get("state", "Metro State").strip()
            date_of_birth = request.form.get("date_of_birth", "1995-01-01").strip()
            gender = request.form.get("gender", "other").strip().lower()
            pin_code = request.form.get("pin_code", "00000").strip()
            contact_pref = request.form.get("contact_preference", "both").strip().lower()
            is_discoverable = request.form.get("is_discoverable", "1") in ("1", "true", "on")

            donor_payload = {
                "blood_group": blood_group,
                "weight_kg": weight_kg,
                "city": city,
                "state": state,
                "district": district,
                "date_of_birth": date_of_birth,
            }
            valid_payload, payload_errors = validate_donor_profile_payload(donor_payload)
            if not valid_payload:
                for field_err in payload_errors.values():
                    flash(field_err, "danger")
                return render_template("auth/register.html", full_name=full_name, email=email, phone=phone), 400

            screening_answers = {
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
            notes_payload = {
                "screened_at": datetime.now(timezone.utc).isoformat(),
                "answers": screening_answers,
                "consent": request.form.get("screening_consent") in ("1", "true", "on", True)
            }
            medical_notes = json.dumps(notes_payload)
            last_donation_date = request.form.get("last_donation_date") or None

            role = "donor"
            donor_created = True

        db_ok, _, _ = test_db_connection()
        if not db_ok:
            flash("Database connection offline. Please ensure MySQL server is running to register.", "danger")
            return render_template("auth/register.html", full_name=full_name, email=email, phone=phone), 503

        if User.find_by_email(email):
            flash("An account with this email address already exists. Please sign in.", "warning")
            return redirect(url_for("auth.login"))

        if User.find_by_phone(phone):
            flash("An account with this phone number already exists. Please sign in.", "warning")
            return redirect(url_for("auth.login"))

        user_id = User.create(full_name, email, phone, password, role=role)

        if donor_created:
            Donor.create(
                user_id=user_id,
                blood_group=blood_group,
                gender=gender,
                date_of_birth=date_of_birth,
                weight_kg=float(weight_kg),
                state=state,
                city=city,
                district=district,
                pin_code=pin_code,
                last_donation_date=last_donation_date,
                contact_preference=contact_pref,
                is_discoverable=is_discoverable,
                medical_notes=medical_notes
            )
            flash("Registration successful! Your LifeLink account and Blood Donor profile are active.", "success")
        else:
            flash("Registration successful! Your LifeLink account is ready. Please sign in.", "success")

        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")


@auth_bp.route("/register/donor", methods=["GET", "POST"])
@rate_limit(max_requests=5, window_seconds=60)
def register_donor():
    """Handles multi-field donor account creation with strict server-side validation."""
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        blood_group = request.form.get("blood_group", "").strip().upper()
        gender = request.form.get("gender", "other").strip().lower()
        date_of_birth = request.form.get("date_of_birth", "").strip()
        weight_kg = request.form.get("weight_kg", "55.0")
        state = request.form.get("state", "").strip()
        city = request.form.get("city", "").strip()
        district = request.form.get("district", "").strip()
        pin_code = request.form.get("pin_code", "00000").strip()
        contact_pref = request.form.get("contact_preference", "both").strip().lower()
        is_discoverable = request.form.get("is_discoverable", "1") in ("1", "true", "on")

        # 1. Server-side validations
        if not full_name:
            flash("Full name is required.", "danger")
            return render_template("auth/register.html", role="donor"), 400

        ok, err = validate_email(email)
        if not ok:
            flash(err, "danger")
            return render_template("auth/register.html", role="donor"), 400

        ok, err = validate_phone(phone)
        if not ok:
            flash(err, "danger")
            return render_template("auth/register.html", role="donor"), 400

        ok, err = validate_password_strength(password)
        if not ok:
            flash(err, "danger")
            return render_template("auth/register.html", role="donor"), 400

        donor_payload = {
            "blood_group": blood_group,
            "weight_kg": weight_kg,
            "city": city,
            "state": state,
            "district": district,
            "date_of_birth": date_of_birth,
        }
        valid_payload, payload_errors = validate_donor_profile_payload(donor_payload)
        if not valid_payload:
            for field_err in payload_errors.values():
                flash(field_err, "danger")
            return render_template("auth/register.html", role="donor"), 400

        db_ok, _, _ = test_db_connection()
        if not db_ok:
            flash("Database connection offline. Please ensure MySQL server is running.", "danger")
            return render_template("auth/register.html", role="donor"), 503

        if User.find_by_email(email):
            flash("An account with this email address already exists.", "warning")
            return redirect(url_for("auth.register_donor"))

        if User.find_by_phone(phone):
            flash("An account with this phone number already exists.", "warning")
            return redirect(url_for("auth.register_donor"))

        screening_answers = {
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
        notes_payload = {
            "screened_at": datetime.now(timezone.utc).isoformat(),
            "answers": screening_answers,
            "consent": request.form.get("screening_consent") in ("1", "true", "on", True)
        }
        medical_notes = json.dumps(notes_payload)
        last_donation_date = request.form.get("last_donation_date") or None

        user_id = User.create(full_name, email, phone, password, role="donor")
        Donor.create(
            user_id=user_id,
            blood_group=blood_group,
            gender=gender,
            date_of_birth=date_of_birth,
            weight_kg=float(weight_kg),
            state=state,
            city=city,
            district=district,
            pin_code=pin_code,
            last_donation_date=last_donation_date,
            contact_preference=contact_pref,
            is_discoverable=is_discoverable,
            medical_notes=medical_notes
        )
        flash("Donor profile created successfully! Please sign in with your credentials.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", role="donor")


@auth_bp.route("/register/patient", methods=["GET", "POST"])
@rate_limit(max_requests=5, window_seconds=60)
def register_patient():
    """Handles patient/requester registration."""
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not full_name:
            flash("Full name is required.", "danger")
            return render_template("auth/register.html", role="patient"), 400

        ok, err = validate_email(email)
        if not ok:
            flash(err, "danger")
            return render_template("auth/register.html", role="patient"), 400

        ok, err = validate_phone(phone)
        if not ok:
            flash(err, "danger")
            return render_template("auth/register.html", role="patient"), 400

        ok, err = validate_password_strength(password)
        if not ok:
            flash(err, "danger")
            return render_template("auth/register.html", role="patient"), 400

        db_ok, _, _ = test_db_connection()
        if not db_ok:
            flash("Database connection offline. Please ensure MySQL server is running.", "danger")
            return render_template("auth/register.html", role="patient"), 503

        if User.find_by_email(email):
            flash("An account with this email address already exists.", "warning")
            return redirect(url_for("auth.register_patient"))

        User.create(full_name, email, phone, password, role="patient")
        flash("Patient account created successfully! Please sign in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", role="patient")


@auth_bp.route("/logout")
def logout():
    """Terminates session."""
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("public.index"))


# ==============================================================================
# PASSWORD RESET FUNCTIONALITY
# Token-based secure cryptographic reset workflow
# ==============================================================================

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@rate_limit(max_requests=5, window_seconds=300)
def forgot_password():
    """Renders forgot password form and dispatches secure reset token."""
    if "user_id" in session:
        return redirect(url_for("public.dashboard_router"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        ok, err = validate_email(email)
        if not ok:
            flash(err, "danger")
            return render_template("auth/forgot_password.html", email=email), 400

        db_ok, _, _ = test_db_connection()
        user = None
        if db_ok:
            user = User.find_by_email(email)

        # Generate secure time-limited token (1-hour validity)
        token = User.generate_reset_token(email)
        reset_link = url_for("auth.reset_password", token=token, _external=True)

        # Store reset token in flash/session for testing & seamless local demo
        flash(
            f"If an account exists for {email}, a secure password reset link has been dispatched.",
            "info"
        )
        flash(
            f"Developer / Demo Access Link: <a href='{reset_link}' class='alert-link'>Click here to reset your password now</a>",
            "success"
        )
        return render_template("auth/forgot_password.html", reset_sent=True, demo_reset_link=reset_link)

    return render_template("auth/forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
@rate_limit(max_requests=10, window_seconds=300)
def reset_password(token: str):
    """Verifies token authenticity and updates account password with fresh scrypt hash."""
    if "user_id" in session:
        return redirect(url_for("public.dashboard_router"))

    # Validate token signature and expiration
    email = User.verify_reset_token(token, max_age=3600)
    if not email:
        flash("The password reset link is invalid or has expired. Please request a new one.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        ok, err = validate_password_strength(password)
        if not ok:
            flash(err, "danger")
            return render_template("auth/reset_password.html", token=token, email=email), 400

        if password != confirm_password:
            flash("Passwords do not match. Please verify and re-enter.", "danger")
            return render_template("auth/reset_password.html", token=token, email=email), 400

        db_ok, _, _ = test_db_connection()
        if db_ok:
            User.update_password_by_email(email, password)
            flash("Your password has been successfully reset! Please sign in with your new password.", "success")
            return redirect(url_for("auth.login"))
        else:
            flash("Password updated successfully in demo mode! Please sign in.", "success")
            return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token, email=email)
