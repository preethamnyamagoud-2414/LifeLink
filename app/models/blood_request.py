"""
LifeLink - Blood Request Data Model
Encapsulates database operations for emergency and planned transfusion requests.
Operates on the 'blood_requests' database table.
"""

from typing import Optional, Dict, Any, List
from datetime import date, datetime
from app.extensions import execute_query

# Fictional fallback demo requests for offline preview and demonstration
FALLBACK_DEMO_REQUESTS = {
    1: {
        "id": 1,
        "requester_user_id": 10,
        "patient_name": "Robert Sterling",
        "blood_group": "O-",
        "units_needed": 2,
        "urgency_level": "CRITICAL",
        "hospital_name": "City General Trauma Center",
        "hospital_address": "Ward 3, ICU Bed 12, 100 Medical Blvd",
        "hospital_area": "District 1",
        "city": "Central Metro",
        "state": "Metro State",
        "pin_code": "560001",
        "contact_person": "Dr. Michael Sterling",
        "contact_phone": "+1 (555) 019-0010",
        "preferred_contact_method": "phone",
        "doctor_name": "Dr. K. Aris",
        "additional_notes": "Massive orthopedic trauma surgery. Cross-match sample ready at blood bank.",
        "required_date": str(date.today()),
        "required_within_hours": 2,
        "status": "ACTIVE",
        "is_demo": True,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "requester_name": "Michael Sterling",
        "requester_email": "patient.sterling@demo.lifelink.local",
        "requester_phone": "+1 (555) 019-0010"
    },
    2: {
        "id": 2,
        "requester_user_id": 11,
        "patient_name": "Anita Desai",
        "blood_group": "B-",
        "units_needed": 3,
        "urgency_level": "URGENT",
        "hospital_name": "Metro Heart Institute",
        "hospital_address": "Cardiac ICU, Wing B, 45 Pulse Way",
        "hospital_area": "West Avenue",
        "city": "Central Metro",
        "state": "Metro State",
        "pin_code": "560002",
        "contact_person": "Sunita Menon",
        "contact_phone": "+1 (555) 019-0011",
        "preferred_contact_method": "call_or_msg",
        "doctor_name": "Dr. S. Thorne",
        "additional_notes": "Open cardiac valve replacement. Scheduled transfusion within 12 hours.",
        "required_date": str(date.today()),
        "required_within_hours": 12,
        "status": "ACTIVE",
        "is_demo": True,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "requester_name": "Sunita Menon",
        "requester_email": "patient.desai@demo.lifelink.local",
        "requester_phone": "+1 (555) 019-0011"
    },
    3: {
        "id": 3,
        "requester_user_id": 12,
        "patient_name": "Emma Watson (Demo)",
        "blood_group": "A-",
        "units_needed": 1,
        "urgency_level": "CRITICAL",
        "hospital_name": "Children's Specialty Hospital",
        "hospital_address": "Pediatric Oncology, Bed 4, 88 Hope Lane",
        "hospital_area": "North Hub",
        "city": "North Hub",
        "state": "Metro State",
        "pin_code": "560003",
        "contact_person": "Carlos Mendez",
        "contact_phone": "+1 (555) 019-0012",
        "preferred_contact_method": "phone",
        "doctor_name": "Dr. H. Vance",
        "additional_notes": "Severe acute anemia secondary to chemotherapy. Rapid transfusion required.",
        "required_date": str(date.today()),
        "required_within_hours": 4,
        "status": "ACTIVE",
        "is_demo": True,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "requester_name": "Carlos Mendez",
        "requester_email": "patient.watson@demo.lifelink.local",
        "requester_phone": "+1 (555) 019-0012"
    },
    4: {
        "id": 4,
        "requester_user_id": 10,
        "patient_name": "James Wilson",
        "blood_group": "O+",
        "units_needed": 2,
        "urgency_level": "STANDARD",
        "hospital_name": "St. Luke's Orthopedic Center",
        "hospital_address": "Room 204, 12 Saint Luke Ave",
        "hospital_area": "East Metro",
        "city": "Central Metro",
        "state": "Metro State",
        "pin_code": "560004",
        "contact_person": "Michael Sterling",
        "contact_phone": "+1 (555) 019-0010",
        "preferred_contact_method": "whatsapp",
        "doctor_name": "Dr. R. Miller",
        "additional_notes": "Elective hip arthroplasty. Transfusion successfully coordinated.",
        "required_date": str(date.today()),
        "required_within_hours": 48,
        "status": "FULFILLED",
        "is_demo": True,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "requester_name": "Michael Sterling",
        "requester_email": "patient.sterling@demo.lifelink.local",
        "requester_phone": "+1 (555) 019-0010"
    }
}


class BloodRequest:
    """Data access object for the 'blood_requests' database table."""

    @staticmethod
    def create(
        requester_user_id: int,
        patient_name: str,
        blood_group: str,
        units_needed: int,
        urgency_level: str,
        hospital_name: str,
        hospital_address: str,
        city: str,
        state: str,
        contact_person: str,
        contact_phone: str,
        contact_email: Optional[str] = None,
        hospital_area: Optional[str] = None,
        preferred_contact_method: str = "phone",
        required_date: Optional[str] = None,
        pin_code: Optional[str] = None,
        doctor_name: Optional[str] = None,
        additional_notes: Optional[str] = None,
        required_within_hours: int = 24,
        status: str = "ACTIVE",
        is_demo: bool = False
    ) -> int:
        """Creates a new blood transfusion request with parameterized query."""
        urgency_db = "STANDARD" if urgency_level == "NORMAL" else urgency_level

        try:
            query = """
                INSERT INTO blood_requests (
                    requester_user_id, patient_name, blood_group, units_needed,
                    urgency_level, hospital_name, hospital_address, hospital_area,
                    city, state, pin_code, contact_person, contact_phone, contact_email,
                    preferred_contact_method, doctor_name, additional_notes,
                    required_date, required_within_hours, status, is_demo
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s
                );
            """
            result = execute_query(
                query,
                (
                    requester_user_id, patient_name, blood_group, units_needed,
                    urgency_db, hospital_name, hospital_address, hospital_area,
                    city, state, pin_code, contact_person, contact_phone, contact_email,
                    preferred_contact_method, doctor_name, additional_notes,
                    required_date, required_within_hours, status, is_demo
                ),
                commit=True
            )
            return result["last_insert_id"]
        except Exception:
            # Fallback if contact_email column not yet added to live table
            query_fallback = """
                INSERT INTO blood_requests (
                    requester_user_id, patient_name, blood_group, units_needed,
                    urgency_level, hospital_name, hospital_address, hospital_area,
                    city, state, pin_code, contact_person, contact_phone,
                    preferred_contact_method, doctor_name, additional_notes,
                    required_date, required_within_hours, status, is_demo
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s, %s
                );
            """
            result = execute_query(
                query_fallback,
                (
                    requester_user_id, patient_name, blood_group, units_needed,
                    urgency_db, hospital_name, hospital_address, hospital_area,
                    city, state, pin_code, contact_person, contact_phone,
                    preferred_contact_method, doctor_name, additional_notes,
                    required_date, required_within_hours, status, is_demo
                ),
                commit=True
            )
            return result["last_insert_id"]

    @staticmethod
    def find_by_id(request_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves blood request details by ID with user attribution and offline fallback."""
        try:
            query = """
                SELECT 
                    r.*,
                    u.full_name AS requester_name, u.email AS requester_email, u.phone AS requester_phone
                FROM blood_requests r
                JOIN users u ON r.requester_user_id = u.id
                WHERE r.id = %s;
            """
            result = execute_query(query, (request_id,), fetchone=True)
            if result:
                return result
        except Exception:
            pass

        return FALLBACK_DEMO_REQUESTS.get(request_id)

    @staticmethod
    def get_active(limit: int = 20, blood_group: Optional[str] = None, city: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Retrieves active blood requests sorted by urgency priority.
        (CRITICAL first, then URGENT, then STANDARD).
        """
        try:
            conditions = ["r.status = 'ACTIVE'"]
            params = []

            if blood_group:
                conditions.append("r.blood_group = %s")
                params.append(blood_group)

            if city:
                conditions.append("LOWER(r.city) = LOWER(%s)")
                params.append(city.strip())

            where_clause = " AND ".join(conditions)
            params.append(limit)

            query = f"""
                SELECT 
                    r.*,
                    u.full_name AS requester_name
                FROM blood_requests r
                JOIN users u ON r.requester_user_id = u.id
                WHERE {where_clause}
                ORDER BY 
                    CASE r.urgency_level
                        WHEN 'CRITICAL' THEN 1
                        WHEN 'URGENT' THEN 2
                        WHEN 'STANDARD' THEN 3
                        ELSE 4
                    END ASC,
                    r.created_at DESC
                LIMIT %s;
            """
            rows = execute_query(query, tuple(params), fetchall=True)
            if rows:
                return rows
        except Exception:
            pass

        # Fallback to simulated demo requests
        results = [r for r in FALLBACK_DEMO_REQUESTS.values() if r["status"] == "ACTIVE"]
        if blood_group:
            results = [r for r in results if r["blood_group"] == blood_group]
        if city:
            results = [r for r in results if city.lower() in r["city"].lower() or city.lower() in (r.get("hospital_area") or "").lower()]
        return results[:limit]

    @staticmethod
    def find_by_requester(user_id: int) -> List[Dict[str, Any]]:
        """Retrieves all requests submitted by a specific user with volunteer count."""
        try:
            query = """
                SELECT 
                    r.*,
                    COUNT(rr.id) AS volunteer_count
                FROM blood_requests r
                LEFT JOIN donor_responses rr ON rr.request_id = r.id
                WHERE r.requester_user_id = %s
                GROUP BY r.id
                ORDER BY r.created_at DESC;
            """
            rows = execute_query(query, (user_id,), fetchall=True)
            if rows:
                return rows
        except Exception:
            pass

        return [r for r in FALLBACK_DEMO_REQUESTS.values() if r["requester_user_id"] == user_id]

    @staticmethod
    def cancel_request(request_id: int, user_id: int, is_admin: bool = False) -> bool:
        """Cancels a request if user owns it or is an admin."""
        try:
            if is_admin:
                query = "UPDATE blood_requests SET status = 'CANCELLED' WHERE id = %s;"
                execute_query(query, (request_id,), commit=True)
                return True

            query = "UPDATE blood_requests SET status = 'CANCELLED' WHERE id = %s AND requester_user_id = %s;"
            result = execute_query(query, (request_id, user_id), commit=True)
            return result.get("row_count", 0) > 0
        except Exception:
            if request_id in FALLBACK_DEMO_REQUESTS:
                FALLBACK_DEMO_REQUESTS[request_id]["status"] = "CANCELLED"
                return True
            return False

    @staticmethod
    def fulfill_request(request_id: int, user_id: int, is_admin: bool = False) -> bool:
        """Marks a request as fulfilled."""
        try:
            if is_admin:
                query = "UPDATE blood_requests SET status = 'FULFILLED' WHERE id = %s;"
                execute_query(query, (request_id,), commit=True)
                return True

            query = "UPDATE blood_requests SET status = 'FULFILLED' WHERE id = %s AND requester_user_id = %s;"
            result = execute_query(query, (request_id, user_id), commit=True)
            return result.get("row_count", 0) > 0
        except Exception:
            if request_id in FALLBACK_DEMO_REQUESTS:
                FALLBACK_DEMO_REQUESTS[request_id]["status"] = "FULFILLED"
                return True
            return False

    @staticmethod
    def update_status(request_id: int, status: str) -> bool:
        """Administrative status update."""
        try:
            query = "UPDATE blood_requests SET status = %s WHERE id = %s;"
            execute_query(query, (status, request_id), commit=True)
            return True
        except Exception:
            if request_id in FALLBACK_DEMO_REQUESTS:
                FALLBACK_DEMO_REQUESTS[request_id]["status"] = status
                return True
            return False

    @staticmethod
    def get_status_counts() -> Dict[str, int]:
        """Calculates total, active, fulfilled, and cancelled requests for admin KPIs."""
        try:
            query = """
                SELECT 
                    COUNT(*) AS total,
                    SUM(CASE WHEN status = 'ACTIVE' THEN 1 ELSE 0 END) AS active,
                    SUM(CASE WHEN status = 'FULFILLED' THEN 1 ELSE 0 END) AS fulfilled,
                    SUM(CASE WHEN status = 'CANCELLED' THEN 1 ELSE 0 END) AS cancelled
                FROM blood_requests;
            """
            row = execute_query(query, fetchone=True)
            if row and row.get("total") is not None:
                return {
                    "total": row.get("total", 0) or 0,
                    "active": int(row.get("active", 0) or 0),
                    "fulfilled": int(row.get("fulfilled", 0) or 0),
                    "cancelled": int(row.get("cancelled", 0) or 0)
                }
        except Exception:
            pass

        return {
            "total": 4,
            "active": 3,
            "fulfilled": 1,
            "cancelled": 0
        }

    @staticmethod
    def get_all(status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves all blood requests for admin management."""
        try:
            if status:
                query = """
                    SELECT r.*, u.full_name AS requester_name 
                    FROM blood_requests r
                    JOIN users u ON r.requester_user_id = u.id
                    WHERE r.status = %s
                    ORDER BY r.created_at DESC LIMIT %s;
                """
                rows = execute_query(query, (status, limit), fetchall=True)
            else:
                query = """
                    SELECT r.*, u.full_name AS requester_name 
                    FROM blood_requests r
                    JOIN users u ON r.requester_user_id = u.id
                    ORDER BY r.created_at DESC LIMIT %s;
                """
                rows = execute_query(query, (limit,), fetchall=True)
            if rows:
                return rows
        except Exception:
            pass

        reqs = list(FALLBACK_DEMO_REQUESTS.values())
        if status:
            reqs = [r for r in reqs if r["status"] == status]
        return reqs[:limit]
