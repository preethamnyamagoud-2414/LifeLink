"""
LifeLink - Donor Response Data Model
Encapsulates matching responses when a registered donor volunteers to fulfill a request.
Operates on the 'donor_responses' database table.
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
from app.extensions import execute_query

# Fictional fallback demo responses for offline preview / demonstration
FALLBACK_DEMO_RESPONSES = {
    1: [
        {
            "id": 1,
            "request_id": 1,
            "donor_user_id": 2,
            "status": "ACCEPTED",
            "message": "I am within 3 km of City General Trauma Center. En route now.",
            "is_demo": True,
            "responded_at": "2026-11-13 18:30:00",
            "donor_name": "Sarah Jenkins",
            "donor_phone": "+1 (555) 019-0002",
            "donor_email": "sarah.jenkins@demo.lifelink.local",
            "blood_group": "O-",
            "donor_city": "Central Metro",
            "total_donations": 6
        }
    ],
    2: [
        {
            "id": 2,
            "request_id": 2,
            "donor_user_id": 7,
            "status": "INTERESTED",
            "message": "Available to donate at Metro Heart Institute after 2:00 PM today.",
            "is_demo": True,
            "responded_at": "2026-11-13 17:45:00",
            "donor_name": "Liam O'Connor",
            "donor_phone": "+1 (555) 019-0007",
            "donor_email": "liam.oconnor@demo.lifelink.local",
            "blood_group": "B-",
            "donor_city": "Central Metro",
            "total_donations": 8
        }
    ],
    4: [
        {
            "id": 3,
            "request_id": 4,
            "donor_user_id": 3,
            "status": "DONATED",
            "message": "Donation completed at St. Luke blood bank. 1 unit whole blood.",
            "is_demo": True,
            "responded_at": "2026-11-13 14:15:00",
            "donor_name": "Dr. David Chen",
            "donor_phone": "+1 (555) 019-0003",
            "donor_email": "david.chen@demo.lifelink.local",
            "blood_group": "O+",
            "donor_city": "Central Metro",
            "total_donations": 14
        }
    ]
}


class RequestResponse:
    """Data access object for the 'donor_responses' database table."""

    @staticmethod
    def create(request_id: int, donor_user_id: int, message: Optional[str] = None, is_demo: bool = False) -> int:
        """Records a donor volunteering for a blood request."""
        try:
            query = """
                INSERT INTO donor_responses (request_id, donor_user_id, status, message, is_demo)
                VALUES (%s, %s, 'INTERESTED', %s, %s)
                ON DUPLICATE KEY UPDATE 
                    status = 'INTERESTED',
                    message = VALUES(message),
                    responded_at = CURRENT_TIMESTAMP;
            """
            result = execute_query(query, (request_id, donor_user_id, message, is_demo), commit=True)
            return result.get("last_insert_id", 1)
        except Exception:
            # Fallback simulated recording
            new_resp = {
                "id": len(FALLBACK_DEMO_RESPONSES.get(request_id, [])) + 10,
                "request_id": request_id,
                "donor_user_id": donor_user_id,
                "status": "INTERESTED",
                "message": message or "Willing to donate.",
                "is_demo": True,
                "responded_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "donor_name": "Voluntary Lifesaver",
                "donor_phone": "Confidential",
                "donor_email": "confidential@lifelink.local",
                "blood_group": "O-",
                "donor_city": "Regional Area",
                "total_donations": 1
            }
            if request_id not in FALLBACK_DEMO_RESPONSES:
                FALLBACK_DEMO_RESPONSES[request_id] = []
            FALLBACK_DEMO_RESPONSES[request_id].append(new_resp)
            return new_resp["id"]

    @staticmethod
    def find_by_request(request_id: int) -> List[Dict[str, Any]]:
        """Retrieves all donor volunteers for a specific request."""
        try:
            query = """
                SELECT 
                    rr.*,
                    u.full_name AS donor_name, u.phone AS donor_phone, u.email AS donor_email,
                    d.blood_group, d.city AS donor_city, d.total_donations
                FROM donor_responses rr
                JOIN users u ON rr.donor_user_id = u.id
                JOIN donor_profiles d ON d.user_id = u.id
                WHERE rr.request_id = %s
                ORDER BY rr.responded_at DESC;
            """
            rows = execute_query(query, (request_id,), fetchall=True)
            if rows:
                return rows
        except Exception:
            pass

        return FALLBACK_DEMO_RESPONSES.get(request_id, [])

    @staticmethod
    def find_by_request_sanitized(request_id: int, is_owner: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieves donor volunteers with privacy protection.
        Masks donor names (e.g. 'Sarah J.') and conceals phone numbers for public tracking.
        """
        raw_responses = RequestResponse.find_by_request(request_id)
        sanitized = []

        for resp in raw_responses:
            full_name = resp.get("donor_name") or "Voluntary Donor"
            name_parts = full_name.split()
            if len(name_parts) > 1:
                masked_name = f"{name_parts[0]} {name_parts[-1][0]}."
            else:
                masked_name = name_parts[0]

            item = {
                "id": resp.get("id"),
                "request_id": resp.get("request_id"),
                "status": resp.get("status"),
                "message": resp.get("message"),
                "blood_group": resp.get("blood_group"),
                "donor_city": resp.get("donor_city"),
                "total_donations": resp.get("total_donations", 0),
                "responded_at": resp.get("responded_at"),
                "is_verified_availability": False  # Explicit medical safeguard
            }

            if is_owner:
                item["donor_display_name"] = full_name
                item["donor_phone"] = resp.get("donor_phone")
                item["donor_email"] = resp.get("donor_email")
            else:
                item["donor_display_name"] = masked_name
                item["donor_phone"] = "Protected by LifeLink Privacy"
                item["donor_email"] = "Protected by LifeLink Privacy"

            sanitized.append(item)

        return sanitized

    @staticmethod
    def update_status(response_id: int, status: str) -> bool:
        """Updates volunteer status (e.g. 'ACCEPTED', 'DONATED', 'DECLINED')."""
        try:
            query = "UPDATE donor_responses SET status = %s WHERE id = %s;"
            execute_query(query, (status, response_id), commit=True)
            return True
        except Exception:
            for resp_list in FALLBACK_DEMO_RESPONSES.values():
                for r in resp_list:
                    if r["id"] == response_id:
                        r["status"] = status
                        return True
            return False

    @staticmethod
    def find_by_donor(donor_user_id: int) -> List[Dict[str, Any]]:
        """Retrieves requests that a specific donor has responded to."""
        try:
            query = """
                SELECT 
                    rr.*,
                    r.patient_name, r.blood_group AS request_blood_group, r.units_needed,
                    r.urgency_level, r.hospital_name, r.city AS hospital_city, r.status AS request_status
                FROM donor_responses rr
                JOIN blood_requests r ON rr.request_id = r.id
                WHERE rr.donor_user_id = %s
                ORDER BY rr.responded_at DESC;
            """
            rows = execute_query(query, (donor_user_id,), fetchall=True)
            if rows:
                return rows
        except Exception:
            pass

        # Fallback demo responses for user 2 (Sarah Jenkins)
        if donor_user_id == 2:
            return [
                {
                    "id": 1,
                    "request_id": 1,
                    "donor_user_id": 2,
                    "status": "ACCEPTED",
                    "message": "I am within 3 km of City General Trauma Center. En route now.",
                    "responded_at": "2026-11-13 18:30:00",
                    "patient_name": "Robert Sterling",
                    "request_blood_group": "O-",
                    "units_needed": 2,
                    "urgency_level": "CRITICAL",
                    "hospital_name": "City General Trauma Center",
                    "hospital_city": "Central Metro",
                    "request_status": "ACTIVE"
                }
            ]
        return []

    @staticmethod
    def find_by_patient(patient_user_id: int) -> List[Dict[str, Any]]:
        """Retrieves donor volunteers answering requests submitted by this patient."""
        try:
            query = """
                SELECT 
                    rr.*,
                    r.patient_name, r.blood_group AS request_blood_group,
                    u.full_name AS donor_name, u.phone AS donor_phone,
                    d.blood_group AS donor_blood_group, d.city AS donor_city
                FROM donor_responses rr
                JOIN blood_requests r ON rr.request_id = r.id
                JOIN users u ON rr.donor_user_id = u.id
                JOIN donor_profiles d ON d.user_id = u.id
                WHERE r.requester_user_id = %s
                ORDER BY rr.responded_at DESC;
            """
            rows = execute_query(query, (patient_user_id,), fetchall=True)
            if rows:
                return rows
        except Exception:
            pass

        # Fallback demo responses for patient user 10 (Michael Sterling)
        if patient_user_id == 10:
            return [
                {
                    "id": 1,
                    "request_id": 1,
                    "patient_name": "Robert Sterling",
                    "request_blood_group": "O-",
                    "donor_name": "Sarah Jenkins",
                    "donor_phone": "+1 (555) 019-0002",
                    "donor_blood_group": "O-",
                    "donor_city": "Central Metro",
                    "status": "ACCEPTED",
                    "message": "I am within 3 km of City General Trauma Center. En route now.",
                    "responded_at": "2026-11-13 18:30:00"
                }
            ]
        return []
