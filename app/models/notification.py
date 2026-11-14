"""
LifeLink - Notifications Data Model
Encapsulates database operations for system alerts, emergency broadcasts,
and user notifications.
Operates on the 'notifications' database table.
"""

from typing import Optional, Dict, Any, List
from app.extensions import execute_query


class Notification:
    """Data access object for the 'notifications' database table."""

    @staticmethod
    def create(
        user_id: int,
        title: str,
        message: str,
        notification_type: str = "SYSTEM",
        reference_id: Optional[int] = None,
        is_demo: bool = False
    ) -> int:
        """Dispatches a new notification to a user."""
        query = """
            INSERT INTO notifications (user_id, title, message, notification_type, reference_id, is_read, is_demo)
            VALUES (%s, %s, %s, %s, %s, FALSE, %s);
        """
        result = execute_query(
            query,
            (user_id, title, message, notification_type, reference_id, is_demo),
            commit=True
        )
        return result["last_insert_id"]

    @staticmethod
    def get_by_user(user_id: int, unread_only: bool = False, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves notifications for a specific user."""
        if unread_only:
            query = """
                SELECT * FROM notifications 
                WHERE user_id = %s AND is_read = FALSE 
                ORDER BY created_at DESC LIMIT %s;
            """
            return execute_query(query, (user_id, limit), fetchall=True)

        query = """
            SELECT * FROM notifications 
            WHERE user_id = %s 
            ORDER BY created_at DESC LIMIT %s;
        """
        return execute_query(query, (user_id, limit), fetchall=True)

    @staticmethod
    def mark_as_read(notification_id: int, user_id: int) -> bool:
        """Marks a notification as read."""
        query = "UPDATE notifications SET is_read = TRUE WHERE id = %s AND user_id = %s;"
        execute_query(query, (notification_id, user_id), commit=True)
        return True

    @staticmethod
    def mark_all_as_read(user_id: int) -> bool:
        """Marks all notifications for a user as read."""
        query = "UPDATE notifications SET is_read = TRUE WHERE user_id = %s AND is_read = FALSE;"
        execute_query(query, (user_id,), commit=True)
        return True
