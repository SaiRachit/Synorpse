"""
TaskExecutor - Concurrent task execution framework
Enables running multiple independent tasks simultaneously with dependency management
"""
import asyncio
import time
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
import psycopg2
from psycopg2.extras import Json
from dotenv import dotenv_values

env_vars = dotenv_values(".env")
DB_NAME = env_vars.get("DB_NAME", "synorpse_chat")
DB_USER = env_vars.get("DB_USER", "postgres")
DB_PASSWORD = env_vars.get("DB_PASSWORD")
DB_HOST = env_vars.get("DB_HOST", "localhost")


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    BACKGROUND = 1


@dataclass
class ExecutableTask:
    """Represents a task that can be executed"""
    id: str
    name: str
    capability_id: str
    function: Callable
    args: Tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    can_run_concurrent: bool = True
    requires_confirmation: bool = False
    dependencies: List[str] = field(default_factory=list)
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskGroup:
    """Group of related tasks"""
    id: str
    name: str
    tasks: List[ExecutableTask] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)


class TaskExecutor:
    """
    Executes multiple tasks concurrently with dependency management
    Handles parallel execution, resource conflicts, and error isolation
    """
    
    def __init__(self):
        self.active_tasks: Dict[str, ExecutableTask] = {}
        self.task_groups: Dict[str, TaskGroup] = {}
        self.resource_locks: Dict[str, asyncio.Lock] = {}
        self._init_db()
    
    def _init_db(self):
        """Initialize task execution tracking tables"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS task_executions (
                    id SERIAL PRIMARY KEY,
                    task_id VARCHAR(100) NOT NULL,
                    task_name VARCHAR(200) NOT NULL,
                    capability_id VARCHAR(100),
                    status VARCHAR(20) NOT NULL,
                    priority INT DEFAULT 3,
                    started_at TIMESTAMP WITH TIME ZONE,
                    completed_at TIMESTAMP WITH TIME ZONE,
                    execution_time_ms INT,
                    success BOOLEAN,
                    error_message TEXT,
                    metadata JSONB DEFAULT '{}'::jsonb
                );
                
                CREATE INDEX IF NOT EXISTS idx_task_executions_id 
                ON task_executions(task_id);
                
                CREATE INDEX IF NOT EXISTS idx_task_executions_status 
                ON task_executions(status);
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" TaskExecutor DB init warning: {e}")
    
    def create_task(self, name: str, capability_id: str, function: Callable,
                   args: Tuple = (), kwargs: Dict = None,
                   priority: TaskPriority = TaskPriority.MEDIUM,
                   can_run_concurrent: bool = True,
                   requires_confirmation: bool = False,
                   dependencies: List[str] = None) -> ExecutableTask:
        """Create a new executable task"""
        task_id = f"task_{int(time.time() * 1000)}_{len(self.active_tasks)}"
        
        task = ExecutableTask(
            id=task_id,
            name=name,
            capability_id=capability_id,
            function=function,
            args=args,
            kwargs=kwargs or {},
            priority=priority,
            can_run_concurrent=can_run_concurrent,
            requires_confirmation=requires_confirmation,
            dependencies=dependencies or []
        )
        
        return task
    
    def detect_resource_conflicts(self, tasks: List[ExecutableTask]) -> List[Tuple[str, str]]:
        """
        Detect resource conflicts between tasks
        Returns list of (task1_id, task2_id) conflict pairs
        """
        conflicts = []
        
        for i, task1 in enumerate(tasks):
            for task2 in tasks[i+1:]:
                # Check if tasks conflict (e.g., opening and closing same app)
                if self._tasks_conflict(task1, task2):
                    conflicts.append((task1.id, task2.id))
        
        return conflicts
    
    def _tasks_conflict(self, task1: ExecutableTask, task2: ExecutableTask) -> bool:
        """Check if two tasks have resource conflicts"""
        # Same capability on same resource
        if task1.capability_id == task2.capability_id:
            # Check if operating on same target
            target1 = task1.kwargs.get('app') or task1.kwargs.get('target')
            target2 = task2.kwargs.get('app') or task2.kwargs.get('target')
            
            if target1 and target2 and target1.lower() == target2.lower():
                return True
        
        # Open vs Close conflicts
        if task1.capability_id == "open_app" and task2.capability_id == "close_app":
            app1 = task1.kwargs.get('app', '').lower()
            app2 = task2.kwargs.get('app', '').lower()
            if app1 == app2:
                return True
        
        return False
    
    def build_execution_plan(self, tasks: List[ExecutableTask]) -> Dict[str, List[ExecutableTask]]:
        """
        Build execution plan organizing tasks into parallel batches
        Returns dict of {batch_id: [tasks]} where tasks in same batch can run concurrently
        """
        plan = {}
        remaining_tasks = tasks.copy()
        batch_num = 0
        
        while remaining_tasks:
            batch = []
            batch_id = f"batch_{batch_num}"
            
            # Find tasks that can run in this batch
            for task in remaining_tasks[:]:
                # Check if dependencies are satisfied
                deps_satisfied = all(
                    dep_id not in [t.id for t in remaining_tasks]
                    for dep_id in task.dependencies
                )
                
                if not deps_satisfied:
                    continue
                
                # Check if task can run concurrently with current batch
                can_add = True
                if not task.can_run_concurrent and batch:
                    can_add = False
                
                # Check for conflicts with batch tasks
                for batch_task in batch:
                    if self._tasks_conflict(task, batch_task):
                        can_add = False
                        break
                
                if can_add:
                    batch.append(task)
                    remaining_tasks.remove(task)
                    
                    # If task can't run concurrently, don't add more to this batch
                    if not task.can_run_concurrent:
                        break
            
            if batch:
                plan[batch_id] = batch
                batch_num += 1
            else:
                # Deadlock or circular dependency - force add one task
                if remaining_tasks:
                    plan[f"batch_{batch_num}"] = [remaining_tasks.pop(0)]
                    batch_num += 1
        
        return plan
    
    async def execute_task(self, task: ExecutableTask) -> ExecutableTask:
        """Execute a single task"""
        task.status = TaskStatus.RUNNING
        task.start_time = time.time()
        self.active_tasks[task.id] = task
        
        try:
            # Check if function is async
            if asyncio.iscoroutinefunction(task.function):
                result = await task.function(*task.args, **task.kwargs)
            else:
                # Run sync function in executor to avoid blocking
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    None, 
                    lambda: task.function(*task.args, **task.kwargs)
                )
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.end_time = time.time()
            
            # Log successful execution
            self._log_task_execution(task, success=True)
            
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            task.end_time = time.time()
            
            # Log failed execution
            self._log_task_execution(task, success=False, error=str(e))
            pass
        
        finally:
            # Remove from active tasks
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]
        
        return task
    
    async def execute_batch(self, tasks: List[ExecutableTask], 
                           show_progress: bool = True) -> List[ExecutableTask]:
        """Execute a batch of tasks concurrently"""
        if show_progress and len(tasks) > 1:
            if tasks:
                pass
        
        # Execute all tasks concurrently
        results = await asyncio.gather(
            *[self.execute_task(task) for task in tasks],
            return_exceptions=True
        )
        
        # Handle any exceptions from gather
        completed_tasks = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                tasks[i].status = TaskStatus.FAILED
                tasks[i].error = str(result)
            completed_tasks.append(tasks[i])
        
        return completed_tasks
    
    async def execute_plan(self, execution_plan: Dict[str, List[ExecutableTask]],
                          show_progress: bool = True) -> Dict[str, List[ExecutableTask]]:
        """Execute the full execution plan batch by batch"""
        results = {}
        
        for batch_id, batch_tasks in execution_plan.items():
            if show_progress:
                pass
            
            completed = await self.execute_batch(batch_tasks, show_progress)
            results[batch_id] = completed
            
            # Check if any critical tasks failed
            failed_critical = [
                t for t in completed 
                if t.status == TaskStatus.FAILED and t.priority == TaskPriority.CRITICAL
            ]
            
            if failed_critical:
                # Mark remaining tasks as cancelled
                for remaining_batch in list(execution_plan.keys())[list(execution_plan.keys()).index(batch_id)+1:]:
                    for task in execution_plan[remaining_batch]:
                        task.status = TaskStatus.CANCELLED
                    results[remaining_batch] = execution_plan[remaining_batch]
                break
        
        return results
    
    async def execute_tasks(self, tasks: List[ExecutableTask],
                           show_progress: bool = True) -> List[ExecutableTask]:
        """
        Main entry point: Execute multiple tasks with automatic parallelization
        """
        if not tasks:
            return []
        
        # Single task - execute directly
        if len(tasks) == 1:
            result = await self.execute_task(tasks[0])
            return [result]
        
        # Multiple tasks - build execution plan
        if show_progress:
            pass
        
        # Detect conflicts
        conflicts = self.detect_resource_conflicts(tasks)
        if conflicts and show_progress:
            pass
        
        # Build execution plan
        execution_plan = self.build_execution_plan(tasks)
        
        if show_progress:
            pass
        
        # Execute plan
        results_by_batch = await self.execute_plan(execution_plan, show_progress)
        
        # Flatten results
        all_results = []
        for batch_results in results_by_batch.values():
            all_results.extend(batch_results)
        
        # Summary
        if show_progress:
            completed = sum(1 for t in all_results if t.status == TaskStatus.COMPLETED)
            failed = sum(1 for t in all_results if t.status == TaskStatus.FAILED)
            pass
        
        return all_results
    
    def get_active_tasks(self) -> List[ExecutableTask]:
        """Get currently running tasks"""
        return list(self.active_tasks.values())
    
    def get_active_tasks_summary(self) -> str:
        """Get summary of currently running tasks"""
        active = self.get_active_tasks()
        if not active:
            return "No tasks currently running"
        
        summary = f" **ACTIVE TASKS** ({len(active)})\n\n"
        for task in active:
            elapsed = time.time() - (task.start_time or time.time())
            summary += f" {task.name} (running for {elapsed:.1f}s)\n"
        
        return summary
    
    def _log_task_execution(self, task: ExecutableTask, success: bool, error: str = None):
        """Log task execution to database"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            execution_time_ms = None
            if task.start_time and task.end_time:
                execution_time_ms = int((task.end_time - task.start_time) * 1000)
            
            cur.execute(
                """INSERT INTO task_executions 
                   (task_id, task_name, capability_id, status, priority,
                    started_at, completed_at, execution_time_ms, success, error_message, metadata)
                   VALUES (%s, %s, %s, %s, %s, 
                           to_timestamp(%s), to_timestamp(%s), %s, %s, %s, %s)""",
                (task.id, task.name, task.capability_id, task.status.value,
                 task.priority.value, task.start_time, task.end_time,
                 execution_time_ms, success, error, Json(task.metadata))
            )
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" Failed to log task execution: {e}")
    
    def create_task_group(self, name: str, tasks: List[ExecutableTask]) -> TaskGroup:
        """Create a group of related tasks"""
        group_id = f"group_{int(time.time() * 1000)}"
        group = TaskGroup(
            id=group_id,
            name=name,
            tasks=tasks
        )
        self.task_groups[group_id] = group
        return group
    
    async def execute_task_group(self, group: TaskGroup, 
                                 show_progress: bool = True) -> TaskGroup:
        """Execute all tasks in a group"""
        if show_progress:
            print(f"\n Task Group: {group.name}")
        
        group.status = TaskStatus.RUNNING
        results = await self.execute_tasks(group.tasks, show_progress)
        
        # Update group status
        if all(t.status == TaskStatus.COMPLETED for t in results):
            group.status = TaskStatus.COMPLETED
        elif any(t.status == TaskStatus.FAILED for t in results):
            group.status = TaskStatus.FAILED
        else:
            group.status = TaskStatus.COMPLETED
        
        return group


# Global instance
_task_executor = None

def get_task_executor() -> TaskExecutor:
    """Get or create global task executor"""
    global _task_executor
    if _task_executor is None:
        _task_executor = TaskExecutor()
    return _task_executor
