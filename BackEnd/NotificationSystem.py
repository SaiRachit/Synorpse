"""
NotificationSystem - Real-time notification delivery for background tasks
Displays notifications without blocking user interaction
"""
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
from queue import Queue
from datetime import datetime


class NotificationPriority(Enum):
    """Notification priority levels"""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class Notification:
    """Represents a notification"""
    message: str
    priority: NotificationPriority
    timestamp: float
    category: str = "general"
    task_id: Optional[str] = None
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class NotificationSystem:
    """
    Manages real-time notifications for background tasks
    Displays notifications in a non-blocking manner
    """
    
    def __init__(self, max_history: int = 100):
        self.notification_queue = Queue()
        self.notification_history: List[Notification] = []
        self.max_history = max_history
        self.muted = False
        self.display_callback = None
    
    def notify(self, message: str, priority: str = "normal",
              category: str = "general", task_id: str = None,
              metadata: Dict = None):
        """Add a notification"""
        try:
            priority_enum = NotificationPriority(priority.lower())
        except ValueError:
            priority_enum = NotificationPriority.NORMAL
        
        notification = Notification(
            message=message,
            priority=priority_enum,
            timestamp=time.time(),
            category=category,
            task_id=task_id,
            metadata=metadata or {}
        )
        
        # Add to queue and history
        self.notification_queue.put(notification)
        self.notification_history.append(notification)
        
        # Trim history if needed
        if len(self.notification_history) > self.max_history:
            self.notification_history = self.notification_history[-self.max_history:]
        
        # Display if not muted
        if not self.muted:
            self._display_notification(notification)
    
    def _display_notification(self, notification: Notification):
        """Display a notification"""
        # Format with emoji based on priority
        emoji_map = {
            NotificationPriority.CRITICAL: "",
            NotificationPriority.HIGH: "",
            NotificationPriority.NORMAL: "",
            NotificationPriority.LOW: ""
        }
        
        emoji = emoji_map.get(notification.priority, "")
        timestamp_str = datetime.fromtimestamp(notification.timestamp).strftime("%H:%M:%S")
        
        formatted = f"\n{emoji} [{timestamp_str}] {notification.message}"
        
        # Use callback if set, otherwise print
        if self.display_callback:
            self.display_callback(formatted)
        else:
            print(formatted, flush=True)
    
    def get_pending_notifications(self, limit: int = 10) -> List[Notification]:
        """Get pending notifications from queue"""
        notifications = []
        while not self.notification_queue.empty() and len(notifications) < limit:
            try:
                notifications.append(self.notification_queue.get_nowait())
            except:
                break
        return notifications
    
    def get_recent_notifications(self, limit: int = 10,
                                 priority: str = None,
                                 category: str = None) -> List[Notification]:
        """Get recent notifications from history"""
        filtered = self.notification_history
        
        # Filter by priority
        if priority:
            try:
                priority_enum = NotificationPriority(priority.lower())
                filtered = [n for n in filtered if n.priority == priority_enum]
            except ValueError:
                pass
        
        # Filter by category
        if category:
            filtered = [n for n in filtered if n.category == category]
        
        # Return most recent
        return list(reversed(filtered[-limit:]))
    
    def clear_history(self):
        """Clear notification history"""
        self.notification_history.clear()
        # Clear queue
        while not self.notification_queue.empty():
            try:
                self.notification_queue.get_nowait()
            except:
                break
    
    def mute(self):
        """Mute notifications (still queued, just not displayed)"""
        self.muted = True
    
    def unmute(self):
        """Unmute notifications"""
        self.muted = False
    
    def set_display_callback(self, callback):
        """Set custom display callback"""
        self.display_callback = callback
    
    def format_notification_summary(self, limit: int = 10) -> str:
        """Get formatted summary of recent notifications"""
        recent = self.get_recent_notifications(limit)
        
        if not recent:
            return "No recent notifications"
        
        summary = f" **RECENT NOTIFICATIONS** ({len(recent)})\n\n"
        
        for notif in recent:
            timestamp_str = datetime.fromtimestamp(notif.timestamp).strftime("%H:%M:%S")
            priority_indicator = {
                NotificationPriority.CRITICAL: "",
                NotificationPriority.HIGH: "",
                NotificationPriority.NORMAL: "",
                NotificationPriority.LOW: ""
            }.get(notif.priority, "")
            
            summary += f"{priority_indicator} [{timestamp_str}] {notif.message}\n"
        
        return summary


# Global instance
_notification_system = None

def get_notification_system() -> NotificationSystem:
    """Get or create global notification system"""
    global _notification_system
    if _notification_system is None:
        _notification_system = NotificationSystem()
    return _notification_system
