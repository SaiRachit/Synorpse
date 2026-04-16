"""
BackgroundTaskManager - Non-blocking task execution system
Allows tasks to run in background while user continues working
"""
import asyncio
import threading
import time
import uuid
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future
from queue import Queue, PriorityQueue
import psycopg2
from psycopg2.extras import Json
from dotenv import dotenv_values

env_vars = dotenv_values(".env")
DB_NAME = env_vars.get("DB_NAME", "synorpse_chat")
DB_USER = env_vars.get("DB_USER", "postgres")
DB_PASSWORD = env_vars.get("DB_PASSWORD")
DB_HOST = env_vars.get("DB_HOST", "localhost")


class TaskState(Enum):
    """Background task states"""
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    BACKGROUND = 1


@dataclass
class BackgroundTask:
    """Represents a background task"""
    id: str
    name: str
    function: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    state: TaskState = TaskState.QUEUED
    progress: float = 0.0  # 0.0 to 1.0
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    estimated_duration: Optional[float] = None
    callback: Optional[Callable] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __lt__(self, other):
        """For priority queue comparison"""
        return self.priority.value > other.priority.value  # Higher priority first


class BackgroundTaskManager:
    """
    Manages background task execution without blocking the main thread
    Provides non-blocking task submission, progress tracking, and notifications
    """
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks: Dict[str, BackgroundTask] = {}
        self.task_queue = PriorityQueue()
        self.notification_queue = Queue()
        self.running = True
        self.paused = False
        
        # Start background worker thread
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        
        self._init_db()
    
    def _init_db(self):
        """Initialize background task tracking tables"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS background_tasks (
                    id VARCHAR(100) PRIMARY KEY,
                    name VARCHAR(200) NOT NULL,
                    priority INT DEFAULT 3,
                    state VARCHAR(20) NOT NULL,
                    progress FLOAT DEFAULT 0.0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP WITH TIME ZONE,
                    completed_at TIMESTAMP WITH TIME ZONE,
                    execution_time_ms INT,
                    success BOOLEAN,
                    error_message TEXT,
                    metadata JSONB DEFAULT '{}'::jsonb
                );
                
                CREATE INDEX IF NOT EXISTS idx_background_tasks_state 
                ON background_tasks(state);
                
                CREATE INDEX IF NOT EXISTS idx_background_tasks_created 
                ON background_tasks(created_at);
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" BackgroundTaskManager DB init warning: {e}")
    
    def submit_task(self, name: str, function: Callable, 
                   args: tuple = (), kwargs: Dict = None,
                   priority: TaskPriority = TaskPriority.MEDIUM,
                   callback: Callable = None,
                   estimated_duration: float = None) -> str:
        """
        Submit a task for background execution
        Returns task_id immediately without blocking
        """
        task_id = f"bg_{uuid.uuid4().hex[:12]}"
        
        task = BackgroundTask(
            id=task_id,
            name=name,
            function=function,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            callback=callback,
            estimated_duration=estimated_duration
        )
        
        self.tasks[task_id] = task
        self.task_queue.put(task)
        
        # Log task creation
        self._log_task(task)
        
        # Notify user
        self._add_notification(
            f" Task queued: {name} (ID: {task_id[:8]}...)",
            priority="normal"
        )
        
        return task_id
    
    def _worker_loop(self):
        """Background worker that processes task queue"""
        while self.running:
            try:
                if self.paused:
                    time.sleep(0.5)
                    continue
                
                # Get next task from queue (blocks with timeout)
                try:
                    task = self.task_queue.get(timeout=1.0)
                except:
                    continue
                
                # Execute task
                self._execute_task(task)
                
            except Exception as e:
                print(f" Worker loop error: {e}")
                time.sleep(1)
    
    def _execute_task(self, task: BackgroundTask):
        """Execute a single background task"""
        task.state = TaskState.RUNNING
        task.started_at = time.time()
        
        self._add_notification(
            f" Started: {task.name}",
            priority="low"
        )
        
        try:
            # Submit to thread pool
            future = self.executor.submit(task.function, *task.args, **task.kwargs)
            
            # Wait for completion
            result = future.result()
            
            task.result = result
            task.state = TaskState.COMPLETED
            task.completed_at = time.time()
            task.progress = 1.0
            
            # Execute callback if provided
            if task.callback:
                try:
                    task.callback(task)
                except Exception as e:
                    print(f" Callback error: {e}")
            
            # Notify completion
            execution_time = task.completed_at - task.started_at
            self._add_notification(
                f" Completed: {task.name} ({execution_time:.1f}s)",
                priority="high"
            )
            
            # Log completion
            self._log_task(task, success=True)
            
        except Exception as e:
            task.error = str(e)
            task.state = TaskState.FAILED
            task.completed_at = time.time()
            
            self._add_notification(
                f" Failed: {task.name} - {str(e)[:50]}",
                priority="high"
            )
            
            # Log failure
            self._log_task(task, success=False, error=str(e))
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get current status of a task"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        status = {
            "id": task.id,
            "name": task.name,
            "state": task.state.value,
            "progress": task.progress,
            "priority": task.priority.value,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at
        }
        
        if task.state == TaskState.COMPLETED:
            status["result"] = str(task.result)[:200] if task.result else None
        elif task.state == TaskState.FAILED:
            status["error"] = task.error
        
        if task.estimated_duration:
            status["estimated_duration"] = task.estimated_duration
            if task.started_at and task.state == TaskState.RUNNING:
                elapsed = time.time() - task.started_at
                status["estimated_remaining"] = max(0, task.estimated_duration - elapsed)
        
        return status
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a queued or running task"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.state in [TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED]:
            return False
        
        task.state = TaskState.CANCELLED
        task.completed_at = time.time()
        
        self._add_notification(
            f" Cancelled: {task.name}",
            priority="normal"
        )
        
        return True
    
    def pause_all(self):
        """Pause all background task execution"""
        self.paused = True
        self._add_notification(
            " Background tasks paused",
            priority="normal"
        )
    
    def resume_all(self):
        """Resume background task execution"""
        self.paused = False
        self._add_notification(
            " Background tasks resumed",
            priority="normal"
        )
    
    def list_active_tasks(self) -> List[Dict]:
        """Get all active (queued or running) tasks"""
        active = []
        for task in self.tasks.values():
            if task.state in [TaskState.QUEUED, TaskState.RUNNING]:
                active.append(self.get_task_status(task.id))
        
        # Sort by priority and created time
        active.sort(key=lambda t: (t.get("priority", 3), t.get("created_at", 0)), reverse=True)
        return active
    
    def list_recent_tasks(self, limit: int = 10) -> List[Dict]:
        """Get recently completed/failed tasks"""
        recent = []
        for task in self.tasks.values():
            if task.state in [TaskState.COMPLETED, TaskState.FAILED]:
                recent.append(self.get_task_status(task.id))
        
        # Sort by completion time
        recent.sort(key=lambda t: t.get("completed_at", 0), reverse=True)
        return recent[:limit]
    
    def get_result(self, task_id: str) -> Any:
        """Get result of a completed task"""
        task = self.tasks.get(task_id)
        if not task or task.state != TaskState.COMPLETED:
            return None
        return task.result
    
    def get_notifications(self, limit: int = 10) -> List[Dict]:
        """Get recent notifications"""
        notifications = []
        while not self.notification_queue.empty() and len(notifications) < limit:
            try:
                notifications.append(self.notification_queue.get_nowait())
            except:
                break
        return notifications
    
    def _add_notification(self, message: str, priority: str = "normal"):
        """Add notification to queue"""
        notification = {
            "message": message,
            "priority": priority,
            "timestamp": time.time()
        }
        self.notification_queue.put(notification)
    
    def _log_task(self, task: BackgroundTask, success: bool = None, error: str = None):
        """Log task to database"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            execution_time_ms = None
            if task.started_at and task.completed_at:
                execution_time_ms = int((task.completed_at - task.started_at) * 1000)
            
            cur.execute(
                """INSERT INTO background_tasks 
                   (id, name, priority, state, progress, started_at, completed_at,
                    execution_time_ms, success, error_message, metadata)
                   VALUES (%s, %s, %s, %s, %s, 
                           to_timestamp(%s), to_timestamp(%s), %s, %s, %s, %s)
                   ON CONFLICT (id) DO UPDATE SET
                   state = EXCLUDED.state,
                   progress = EXCLUDED.progress,
                   started_at = EXCLUDED.started_at,
                   completed_at = EXCLUDED.completed_at,
                   execution_time_ms = EXCLUDED.execution_time_ms,
                   success = EXCLUDED.success,
                   error_message = EXCLUDED.error_message""",
                (task.id, task.name, task.priority.value, task.state.value,
                 task.progress, task.started_at, task.completed_at,
                 execution_time_ms, success, error, Json(task.metadata))
            )
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" Failed to log background task: {e}")
    
    def get_stats(self) -> Dict:
        """Get task execution statistics"""
        total = len(self.tasks)
        queued = sum(1 for t in self.tasks.values() if t.state == TaskState.QUEUED)
        running = sum(1 for t in self.tasks.values() if t.state == TaskState.RUNNING)
        completed = sum(1 for t in self.tasks.values() if t.state == TaskState.COMPLETED)
        failed = sum(1 for t in self.tasks.values() if t.state == TaskState.FAILED)
        
        return {
            "total_tasks": total,
            "queued": queued,
            "running": running,
            "completed": completed,
            "failed": failed,
            "success_rate": f"{(completed / max(total, 1) * 100):.1f}%",
            "paused": self.paused
        }
    
    def shutdown(self):
        """Shutdown the background task manager"""
        self.running = False
        self.executor.shutdown(wait=True)


# Global instance
_background_task_manager = None

def get_background_task_manager() -> BackgroundTaskManager:
    """Get or create global background task manager"""
    global _background_task_manager
    if _background_task_manager is None:
        _background_task_manager = BackgroundTaskManager()
    return _background_task_manager
