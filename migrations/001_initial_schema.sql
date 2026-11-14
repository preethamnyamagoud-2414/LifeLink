-- ==============================================================================
-- LifeLink Database Migration 001 - Authoritative Schema
-- Synchronized with database/schema.sql
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS `lifelink_db`
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE `lifelink_db`;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `admin_activity_logs`;
DROP TABLE IF EXISTS `notifications`;
DROP TABLE IF EXISTS `donor_responses`;
DROP TABLE IF EXISTS `blood_requests`;
DROP TABLE IF EXISTS `donor_profiles`;
DROP TABLE IF EXISTS `users`;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE `users` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `full_name` VARCHAR(100) NOT NULL,
    `email` VARCHAR(120) NOT NULL UNIQUE,
    `phone` VARCHAR(20) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `role` ENUM('donor', 'patient', 'admin') NOT NULL DEFAULT 'patient',
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `is_verified` BOOLEAN NOT NULL DEFAULT FALSE,
    `is_demo` BOOLEAN NOT NULL DEFAULT FALSE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX `idx_users_role` (`role`),
    INDEX `idx_users_email` (`email`),
    INDEX `idx_users_phone` (`phone`),
    INDEX `idx_users_demo` (`is_demo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `donor_profiles` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL UNIQUE,
    `blood_group` ENUM('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-') NOT NULL,
    `gender` ENUM('male', 'female', 'other') NOT NULL,
    `date_of_birth` DATE NOT NULL,
    `weight_kg` DECIMAL(5, 2) NOT NULL,
    `state` VARCHAR(80) NOT NULL,
    `city` VARCHAR(80) NOT NULL,
    `district` VARCHAR(80) NOT NULL,
    `pin_code` VARCHAR(10) NOT NULL,
    `last_donation_date` DATE NULL,
    `is_available` BOOLEAN NOT NULL DEFAULT TRUE,
    `is_discoverable` BOOLEAN NOT NULL DEFAULT TRUE,
    `contact_preference` ENUM('phone', 'email', 'both') NOT NULL DEFAULT 'both',
    `total_donations` INT NOT NULL DEFAULT 0,
    `medical_notes` TEXT NULL,
    `is_demo` BOOLEAN NOT NULL DEFAULT FALSE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_donor_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `chk_donor_weight` CHECK (`weight_kg` >= 40.0),
    INDEX `idx_donors_blood_group` (`blood_group`),
    INDEX `idx_donors_location` (`city`, `state`),
    INDEX `idx_donors_availability` (`is_available`),
    INDEX `idx_donors_cooldown` (`last_donation_date`),
    INDEX `idx_donors_demo` (`is_demo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `blood_requests` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `requester_user_id` INT NOT NULL,
    `patient_name` VARCHAR(100) NOT NULL,
    `blood_group` ENUM('A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-') NOT NULL,
    `units_needed` INT NOT NULL DEFAULT 1,
    `urgency_level` ENUM('CRITICAL', 'URGENT', 'STANDARD') NOT NULL DEFAULT 'URGENT',
    `hospital_name` VARCHAR(150) NOT NULL,
    `hospital_address` TEXT NOT NULL,
    `hospital_area` VARCHAR(100) NULL,
    `city` VARCHAR(80) NOT NULL,
    `state` VARCHAR(80) NOT NULL,
    `pin_code` VARCHAR(10) NULL,
    `contact_person` VARCHAR(100) NOT NULL,
    `contact_phone` VARCHAR(20) NOT NULL,
    `preferred_contact_method` ENUM('phone', 'whatsapp', 'email', 'call_or_msg') NOT NULL DEFAULT 'phone',
    `doctor_name` VARCHAR(100) NULL,
    `additional_notes` TEXT NULL,
    `required_date` DATE NULL,
    `required_within_hours` INT NOT NULL DEFAULT 24,
    `status` ENUM('PENDING', 'ACTIVE', 'FULFILLED', 'CANCELLED') NOT NULL DEFAULT 'ACTIVE',
    `is_demo` BOOLEAN NOT NULL DEFAULT FALSE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_requests_requester` FOREIGN KEY (`requester_user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `chk_units_needed` CHECK (`units_needed` > 0),
    INDEX `idx_requests_blood_group` (`blood_group`),
    INDEX `idx_requests_location` (`city`, `state`),
    INDEX `idx_requests_urgency` (`urgency_level`),
    INDEX `idx_requests_status` (`status`),
    INDEX `idx_requests_required_date` (`required_date`),
    INDEX `idx_requests_created` (`created_at`),
    INDEX `idx_requests_demo` (`is_demo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `donor_responses` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `request_id` INT NOT NULL,
    `donor_user_id` INT NOT NULL,
    `status` ENUM('INTERESTED', 'ACCEPTED', 'DONATED', 'DECLINED') NOT NULL DEFAULT 'INTERESTED',
    `message` VARCHAR(255) NULL,
    `is_demo` BOOLEAN NOT NULL DEFAULT FALSE,
    `responded_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_responses_request` FOREIGN KEY (`request_id`)
        REFERENCES `blood_requests` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT `fk_responses_donor` FOREIGN KEY (`donor_user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE KEY `uq_request_donor` (`request_id`, `donor_user_id`),
    INDEX `idx_responses_status` (`status`),
    INDEX `idx_responses_donor` (`donor_user_id`),
    INDEX `idx_responses_demo` (`is_demo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `notifications` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `user_id` INT NOT NULL,
    `title` VARCHAR(150) NOT NULL,
    `message` TEXT NOT NULL,
    `notification_type` ENUM('EMERGENCY_ALERT', 'REQUEST_UPDATE', 'AVAILABILITY_REMINDER', 'SYSTEM') NOT NULL DEFAULT 'SYSTEM',
    `reference_id` INT NULL,
    `is_read` BOOLEAN NOT NULL DEFAULT FALSE,
    `is_demo` BOOLEAN NOT NULL DEFAULT FALSE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_notifications_user` FOREIGN KEY (`user_id`)
        REFERENCES `users` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
    INDEX `idx_notifications_user_read` (`user_id`, `is_read`),
    INDEX `idx_notifications_type` (`notification_type`),
    INDEX `idx_notifications_created` (`created_at`),
    INDEX `idx_notifications_demo` (`is_demo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `admin_activity_logs` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `admin_user_id` INT NULL,
    `action_type` VARCHAR(60) NOT NULL,
    `target_entity` VARCHAR(50) NOT NULL,
    `target_id` INT NULL,
    `description` TEXT NOT NULL,
    `ip_address` VARCHAR(45) NULL,
    `is_demo` BOOLEAN NOT NULL DEFAULT FALSE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_admin_logs_admin` FOREIGN KEY (`admin_user_id`)
        REFERENCES `users` (`id`) ON DELETE SET NULL ON UPDATE CASCADE,
    INDEX `idx_admin_logs_admin` (`admin_user_id`),
    INDEX `idx_admin_logs_action` (`action_type`),
    INDEX `idx_admin_logs_created` (`created_at`),
    INDEX `idx_admin_logs_demo` (`is_demo`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
