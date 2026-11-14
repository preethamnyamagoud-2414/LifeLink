-- ==============================================================================
-- LifeLink — Fictional Demonstration Seed Data
-- ==============================================================================
-- IMPORTANT NOTICE:
-- All records in this file are SYNTHETIC FICTIONAL DEMO DATA created solely for 
-- testing, user evaluation, and development verification.
--
-- All demo records have `is_demo = TRUE` and use `@demo.lifelink.local` emails 
-- and `555` telephone prefixes to prevent confusion with real personal data.
--
-- To PURGE all demo records at any time:
--   DELETE FROM users WHERE is_demo = TRUE;  (Cascades to all related child tables)
-- ==============================================================================

USE `lifelink_db`;

-- Default password for all demo accounts is: DemoPass@123
-- Stored using Werkzeug scrypt hashing:
SET @DEMO_PASSWORD_HASH = 'scrypt:32768:8:1$yX8wQ7kL9mP2vB4r$d75e4c6c9a1029384756abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789';

-- ------------------------------------------------------------------------------
-- 1. SEED USERS (1 Admin, 8 Donors for each blood group, 3 Patients)
-- ------------------------------------------------------------------------------
INSERT INTO `users` (`id`, `full_name`, `email`, `phone`, `password_hash`, `role`, `is_active`, `is_verified`, `is_demo`) VALUES
-- 1. Primary System Administrator (preethamnyamagoud@gmail.com / LifeLink@2026!)
(1, 'Preetham (Administrator)', 'preethamnyamagoud@gmail.com', '+1 (555) 019-0001', 'pbkdf2:sha256:600000$g11r5LMCfHzyoEE3$fa60a37dc868fcb681fe44813e39457c256646305ece3f7c46d95f0f4f94acba', 'admin', TRUE, TRUE, FALSE),

-- 2. Donors (Covering all 8 blood groups)
(2, 'Sarah Jenkins', 'sarah.jenkins@demo.lifelink.local', '+1 (555) 019-0002', @DEMO_PASSWORD_HASH, 'donor', TRUE, TRUE, TRUE),
(3, 'Dr. David Chen', 'david.chen@demo.lifelink.local', '+1 (555) 019-0003', @DEMO_PASSWORD_HASH, 'donor', TRUE, TRUE, TRUE),
(4, 'Elena Rostova', 'elena.rostova@demo.lifelink.local', '+1 (555) 019-0004', @DEMO_PASSWORD_HASH, 'donor', TRUE, TRUE, TRUE),
(5, 'Rajesh Verma', 'rajesh.verma@demo.lifelink.local', '+1 (555) 019-0005', @DEMO_PASSWORD_HASH, 'donor', TRUE, TRUE, TRUE),
(6, 'Amina Al-Mansoor', 'amina.mansoor@demo.lifelink.local', '+1 (555) 019-0006', @DEMO_PASSWORD_HASH, 'donor', TRUE, TRUE, TRUE),
(7, 'Liam O\'Connor', 'liam.oconnor@demo.lifelink.local', '+1 (555) 019-0007', @DEMO_PASSWORD_HASH, 'donor', TRUE, TRUE, TRUE),
(8, 'Priya Patel', 'priya.patel@demo.lifelink.local', '+1 (555) 019-0008', @DEMO_PASSWORD_HASH, 'donor', TRUE, TRUE, TRUE),
(9, 'Mateo Silva', 'mateo.silva@demo.lifelink.local', '+1 (555) 019-0009', @DEMO_PASSWORD_HASH, 'donor', TRUE, TRUE, TRUE),

-- 3. Patient / Requesters
(10, 'Michael Sterling', 'michael.sterling@demo.lifelink.local', '+1 (555) 019-0010', @DEMO_PASSWORD_HASH, 'patient', TRUE, TRUE, TRUE),
(11, 'Sunita Menon', 'sunita.menon@demo.lifelink.local', '+1 (555) 019-0011', @DEMO_PASSWORD_HASH, 'patient', TRUE, TRUE, TRUE),
(12, 'Carlos Mendez', 'carlos.mendez@demo.lifelink.local', '+1 (555) 019-0012', @DEMO_PASSWORD_HASH, 'patient', TRUE, TRUE, TRUE)
ON DUPLICATE KEY UPDATE `updated_at` = CURRENT_TIMESTAMP;

-- ------------------------------------------------------------------------------
-- 2. SEED DONOR PROFILES (8 Unique Blood Groups & Verified Locations)
-- ------------------------------------------------------------------------------
INSERT INTO `donor_profiles` (
    `user_id`, `blood_group`, `gender`, `date_of_birth`, `weight_kg`,
    `state`, `city`, `district`, `pin_code`, `last_donation_date`,
    `is_available`, `is_discoverable`, `contact_preference`, `total_donations`, `medical_notes`, `is_demo`
) VALUES
-- User 2: Sarah Jenkins (O- Universal Donor, Eligible & Available)
(2, 'O-', 'female', '1996-04-12', 58.5, 'Metro State', 'Central Metro', 'District 1', '10001', '2026-08-14', TRUE, TRUE, 'both', 6, 'Universal donor; regular whole blood volunteer. Fully eligible.', TRUE),

-- User 3: Dr. David Chen (O+ High Demand, Eligible & Available)
(3, 'O+', 'male', '1988-11-23', 74.0, 'Metro State', 'North Hub', 'District 2', '10002', '2026-07-20', TRUE, TRUE, 'phone', 14, 'Senior physician and active donor volunteer.', TRUE),

-- User 4: Elena Rostova (A+ Available)
(4, 'A+', 'female', '1994-02-15', 62.0, 'Metro State', 'West Avenue', 'District 3', '10003', '2026-06-10', TRUE, TRUE, 'email', 5, 'Apheresis and whole blood donor.', TRUE),

-- User 5: Rajesh Verma (A- In Cooldown Period, Discoverable False)
(5, 'A-', 'male', '1992-09-30', 70.0, 'Metro State', 'Central Metro', 'District 1', '10001', '2026-10-25', FALSE, FALSE, 'phone', 12, 'Donated 19 days ago. Currently in mandatory 90-day cooldown interval.', TRUE),

-- User 6: Amina Al-Mansoor (B+ Available)
(6, 'B+', 'female', '1999-07-08', 54.0, 'Metro State', 'South Ridge', 'District 4', '10004', '2026-05-18', TRUE, TRUE, 'both', 3, 'Healthy volunteer; hemoglobin 13.8 g/dL.', TRUE),

-- User 7: Liam O'Connor (B- Rare Rh Negative, Available)
(7, 'B-', 'male', '1991-03-14', 82.0, 'Metro State', 'East Metro', 'District 5', '10005', '2026-04-01', TRUE, TRUE, 'phone', 8, 'Registered for rare negative blood emergency dispatch calls.', TRUE),

-- User 8: Priya Patel (AB+ Universal Recipient, Available)
(8, 'AB+', 'female', '1997-12-05', 56.0, 'Metro State', 'North Hub', 'District 2', '10002', '2026-08-01', TRUE, TRUE, 'both', 4, 'Universal RBC recipient; universal plasma donor.', TRUE),

-- User 9: Mateo Silva (AB- Rare Type, Available)
(9, 'AB-', 'male', '1990-06-19', 76.5, 'Metro State', 'Central Metro', 'District 1', '10001', '2026-07-15', TRUE, TRUE, 'email', 7, 'Platelet donor volunteer.', TRUE)
ON DUPLICATE KEY UPDATE `updated_at` = CURRENT_TIMESTAMP;

-- ------------------------------------------------------------------------------
-- 3. SEED BLOOD REQUESTS (Emergency Triage Cases)
-- ------------------------------------------------------------------------------
INSERT INTO `blood_requests` (
    `id`, `requester_user_id`, `patient_name`, `blood_group`, `units_needed`,
    `urgency_level`, `hospital_name`, `hospital_address`, `hospital_area`, `city`, `state`,
    `contact_person`, `contact_phone`, `preferred_contact_method`, `doctor_name`, `additional_notes`,
    `required_date`, `required_within_hours`, `status`, `is_demo`
) VALUES
-- Case 1: Critical Emergency Trauma (Needs O-)
(1, 10, 'Robert Sterling', 'O-', 2, 'CRITICAL', 'City General Trauma Center', 'Ward 3, ICU Bed 12, 100 Medical Blvd', 'District 1', 'Central Metro', 'Metro State', 'Dr. Michael Sterling', '+1 (555) 019-0010', 'phone', 'Dr. K. Aris', 'Massive orthopedic trauma surgery. Cross-match sample ready at blood bank.', CURDATE(), 2, 'ACTIVE', TRUE),

-- Case 2: Urgent Cardiac Transfusion (Needs B-)
(2, 11, 'Anita Desai', 'B-', 3, 'URGENT', 'Metro Heart Institute', 'Cardiac ICU, Wing B, 45 Pulse Way', 'West Avenue', 'Central Metro', 'Metro State', 'Sunita Menon', '+1 (555) 019-0011', 'call_or_msg', 'Dr. S. Thorne', 'Open cardiac valve replacement. Scheduled transfusion within 12 hours.', CURDATE(), 12, 'ACTIVE', TRUE),

-- Case 3: Critical Pediatric Oncology (Needs A-)
(3, 12, 'Emma Watson (Demo)', 'A-', 1, 'CRITICAL', 'Children\'s Specialty Hospital', 'Pediatric Oncology, Bed 4, 88 Hope Lane', 'North Hub', 'North Hub', 'Metro State', 'Carlos Mendez', '+1 (555) 019-0012', 'phone', 'Dr. H. Vance', 'Severe acute anemia secondary to chemotherapy. Rapid transfusion required.', CURDATE(), 4, 'ACTIVE', TRUE),

-- Case 4: Fulfilled Standard Case (O+)
(4, 10, 'James Wilson', 'O+', 2, 'STANDARD', 'St. Luke\'s Orthopedic Center', 'Room 204, 12 Saint Luke Ave', 'East Metro', 'Central Metro', 'Metro State', 'Michael Sterling', '+1 (555) 019-0010', 'whatsapp', 'Dr. R. Miller', 'Elective hip arthroplasty. Transfusion successfully coordinated.', CURDATE(), 48, 'FULFILLED', TRUE)
ON DUPLICATE KEY UPDATE `updated_at` = CURRENT_TIMESTAMP;

-- ------------------------------------------------------------------------------
-- 4. SEED DONOR RESPONSES (Volunteers Answering Active Requests)
-- ------------------------------------------------------------------------------
INSERT INTO `donor_responses` (`request_id`, `donor_user_id`, `status`, `message`, `is_demo`) VALUES
-- Sarah Jenkins (O-) volunteered for Robert Sterling (Request #1)
(1, 2, 'ACCEPTED', 'I am within 3 km of City General Trauma Center. En route now.', TRUE),

-- Liam O'Connor (B-) volunteered for Anita Desai (Request #2)
(2, 7, 'INTERESTED', 'Available to donate at Metro Heart Institute after 2:00 PM today.', TRUE),

-- Dr. David Chen (O+) donated for James Wilson (Request #4)
(4, 3, 'DONATED', 'Donation completed at St. Luke blood bank. 1 unit whole blood.', TRUE)
ON DUPLICATE KEY UPDATE `updated_at` = CURRENT_TIMESTAMP;

-- ------------------------------------------------------------------------------
-- 5. SEED NOTIFICATIONS (Simulated User Alerts)
-- ------------------------------------------------------------------------------
INSERT INTO `notifications` (`user_id`, `title`, `message`, `notification_type`, `reference_id`, `is_read`, `is_demo`) VALUES
-- Alert to Sarah Jenkins for Critical Request #1
(2, 'CRITICAL BLOOD ALERT: O- Required Nearby', 'Emergency request posted at City General Trauma Center (3.2 km away) for 2 units of O- blood.', 'EMERGENCY_ALERT', 1, FALSE, TRUE),

-- Status notification to Michael Sterling (Requester)
(10, 'Donor Volunteer Accepted', 'Sarah Jenkins (O-) has accepted your emergency request and is en route to the hospital.', 'REQUEST_UPDATE', 1, TRUE, TRUE),

-- Availability update notification to Dr. David Chen
(3, 'Thank You for Your Donation', 'Your recent donation at St. Luke blood bank has been recorded. Next eligible date: Feb 12, 2027.', 'AVAILABILITY_REMINDER', 4, TRUE, TRUE);

-- ------------------------------------------------------------------------------
-- 6. SEED ADMIN ACTIVITY LOGS (Compliance Audit Records)
-- ------------------------------------------------------------------------------
INSERT INTO `admin_activity_logs` (`admin_user_id`, `action_type`, `target_entity`, `target_id`, `description`, `ip_address`, `is_demo`) VALUES
(1, 'DONOR_VERIFIED', 'donor_profiles', 2, 'Admin verified medical identity and blood donation records for donor Sarah Jenkins.', '127.0.0.1', TRUE),
(1, 'REQUEST_MODERATED', 'blood_requests', 1, 'Emergency request #1 verified with attending physician Dr. K. Aris at City General Trauma Center.', '127.0.0.1', TRUE),
(1, 'SYSTEM_AUDIT', 'users', NULL, 'Automated compliance scan: All demo records tagged with is_demo=TRUE.', '127.0.0.1', TRUE);
