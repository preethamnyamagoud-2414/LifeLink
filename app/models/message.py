"""
LifeLink - Contact & Admin Activity Data Models
Encapsulates operations for public inquiries and administrative activity audit logs.
Operates on 'contact_messages' and 'admin_activity_logs'.
"""

from typing import Optional, Dict, Any, List
from app.extensions import execute_query


class ContactMessage:
    """Data access object for the 'contact_messages' database table."""

    @staticmethod
    def create(name: str, email: str, subject: str, message: str) -> int:
        """Stores a new support/contact inquiry."""
        query = """
            INSERT INTO contact_messages (name, email, subject, message, is_resolved)
            VALUES (%s, %s, %s, %s, FALSE);
        """
        result = execute_query(query, (name, email.strip().lower(), subject, message), commit=True)
        return result["last_insert_id"]

    @staticmethod
    def get_all(resolved: Optional[bool] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves contact inquiries, optionally filtered by resolved status."""
        if resolved is not None:
            query = "SELECT * FROM contact_messages WHERE is_resolved = %s ORDER BY created_at DESC LIMIT %s;"
            return execute_query(query, (resolved, limit), fetchall=True)
        query = "SELECT * FROM contact_messages ORDER BY created_at DESC LIMIT %s;"
        return execute_query(query, (limit,), fetchall=True)

    @staticmethod
    def mark_resolved(message_id: int, resolved: bool = True) -> bool:
        """Marks a contact inquiry as resolved."""
        query = "UPDATE contact_messages SET is_resolved = %s WHERE id = %s;"
        execute_query(query, (resolved, message_id), commit=True)
        return True


class AdminActivityLog:
    """Data access object for the 'admin_activity_logs' database table."""

    @staticmethod
    def log(
        admin_user_id: Optional[int],
        action_type: str,
        target_entity: str,
        target_id: Optional[int] = None,
        description: str = "",
        ip_address: Optional[str] = None,
        is_demo: bool = False
    ) -> int:
        """Creates a security or administrative audit record."""
        query = """
            INSERT INTO admin_activity_logs (
                admin_user_id, action_type, target_entity, target_id,
                description, ip_address, is_demo
            ) VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        result = execute_query(
            query,
            (admin_user_id, action_type, target_entity, target_id, description, ip_address, is_demo),
            commit=True
        )
        return result["last_insert_id"]

    @staticmethod
    def get_recent(limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent administrative audit logs."""
        query = """
            SELECT a.*, u.full_name, u.email 
            FROM admin_activity_logs a
            LEFT JOIN users u ON a.admin_user_id = u.id
            ORDER BY a.created_at DESC LIMIT %s;
        """
        return execute_query(query, (limit,), fetchall=True)
