import json
import time
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import Json
from groq import Groq
from dotenv import dotenv_values

env_vars = dotenv_values(".env")
DB_NAME = env_vars.get("DB_NAME", "synorpse_chat")
DB_USER = env_vars.get("DB_USER", "postgres")
DB_PASSWORD = env_vars.get("DB_PASSWORD")
DB_HOST = env_vars.get("DB_HOST", "localhost")
GROQ_API_KEY = env_vars.get("GroqAPIKey")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


class AgentMode(Enum):
    """Agent operational modes"""
    REACTIVE = "reactive"  
    PROACTIVE = "proactive" 
    AUTONOMOUS = "autonomous" 
    SUPERVISED = "supervised"  

class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """Task priority levels"""
    CRITICAL = 5
    HIGH = 4
    MEDIUM = 3
    LOW = 2
    BACKGROUND = 1


@dataclass
class Task:
    """Represents an atomic task the agent can execute"""
    id: str
    description: str
    action_type: str  
    parameters: Dict[str, Any]
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)
    estimated_duration: float = 0.0  
    actual_duration: float = 0.0
    retry_count: int = 0
    max_retries: int = 3
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    requires_confirmation: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Goal:
    """High-level goal that may require multiple tasks"""
    id: str
    description: str
    objective: str
    tasks: List[Task] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    deadline: Optional[datetime] = None
    created_at: float = field(default_factory=time.time)
    success_criteria: List[str] = field(default_factory=list)
    progress: float = 0.0  # 0.0 to 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgenticMemory:
    """Long-term memory for learned patterns and behaviors"""
    
    def __init__(self):
        self._init_db()
        self.pattern_cache = {}
    
    def _init_db(self):
        """Initialize memory tables"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_memory_patterns (
                    id SERIAL PRIMARY KEY,
                    pattern_type VARCHAR(100) NOT NULL,
                    trigger_context JSONB NOT NULL,
                    action_sequence JSONB NOT NULL,
                    success_rate FLOAT DEFAULT 0.0,
                    execution_count INT DEFAULT 0,
                    last_executed TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB DEFAULT '{}'::jsonb
                );
                
                -- User behavior patterns
                CREATE TABLE IF NOT EXISTS agent_memory_behaviors (
                    id SERIAL PRIMARY KEY,
                    behavior_type VARCHAR(100) NOT NULL,
                    time_pattern VARCHAR(50),  -- 'morning', 'afternoon', 'evening'
                    day_pattern VARCHAR(50),   -- 'weekday', 'weekend', 'monday', etc.
                    typical_actions JSONB NOT NULL,
                    frequency FLOAT DEFAULT 0.0,
                    confidence FLOAT DEFAULT 0.0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB DEFAULT '{}'::jsonb
                );
                
                -- Task execution history for learning
                CREATE TABLE IF NOT EXISTS agent_memory_executions (
                    id SERIAL PRIMARY KEY,
                    task_type VARCHAR(100) NOT NULL,
                    context JSONB NOT NULL,
                    execution_plan JSONB NOT NULL,
                    success BOOLEAN NOT NULL,
                    duration FLOAT NOT NULL,
                    error_message TEXT,
                    executed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    metadata JSONB DEFAULT '{}'::jsonb
                );
                
                CREATE INDEX IF NOT EXISTS idx_memory_patterns_type ON agent_memory_patterns(pattern_type);
                CREATE INDEX IF NOT EXISTS idx_memory_behaviors_type ON agent_memory_behaviors(behavior_type);
                CREATE INDEX IF NOT EXISTS idx_memory_executions_type ON agent_memory_executions(task_type);
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" Memory DB init error: {e}")
    
    def learn_pattern(self, trigger_context: Dict, action_sequence: List[str], success: bool):
        """Learn from successful action patterns"""
        try:
            pattern_key = self._hash_context(trigger_context)
            
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                "SELECT id, success_rate, execution_count FROM agent_memory_patterns WHERE pattern_type = %s",
                (pattern_key,)
            )
            existing = cur.fetchone()
            
            if existing:
                pattern_id, success_rate, exec_count = existing
                new_count = exec_count + 1
                new_success_rate = (success_rate * exec_count + (1.0 if success else 0.0)) / new_count
                
                cur.execute(
                    """UPDATE agent_memory_patterns 
                       SET success_rate = %s, execution_count = %s, last_executed = NOW()
                       WHERE id = %s""",
                    (new_success_rate, new_count, pattern_id)
                )
            else:
                cur.execute(
                    """INSERT INTO agent_memory_patterns 
                       (pattern_type, trigger_context, action_sequence, success_rate, execution_count)
                       VALUES (%s, %s, %s, %s, 1)""",
                    (pattern_key, Json(trigger_context), Json(action_sequence), 1.0 if success else 0.0)
                )
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" Pattern learning error: {e}")
    
    def recall_pattern(self, context: Dict) -> Optional[List[str]]:
        """Recall learned action sequence for similar context"""
        try:
            pattern_key = self._hash_context(context)
            
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """SELECT action_sequence, success_rate 
                   FROM agent_memory_patterns 
                   WHERE pattern_type = %s AND success_rate > 0.7
                   ORDER BY success_rate DESC, execution_count DESC
                   LIMIT 1""",
                (pattern_key,)
            )
            result = cur.fetchone()
            conn.close()
            
            if result:
                return result[0]
            return None
        except:
            return None
    
    def _hash_context(self, context: Dict) -> str:
        """Create hash key from context"""
        import hashlib
        context_str = json.dumps(context, sort_keys=True)
        return hashlib.md5(context_str.encode()).hexdigest()[:16]


class TaskPlanner:
    """AI-powered task planning and decomposition"""
    
    def __init__(self, groq_client):
        self.client = groq_client
    
    def decompose_goal(self, goal: str, context: Dict = None) -> List[Task]:
        """
        Decompose high-level goal into executable tasks using AI
        """
        if not self.client:
            return self._fallback_decompose(goal)
        
        try:
            prompt = f"""You are an expert task planner. Decompose this goal into concrete, executable tasks.

Goal: "{goal}"

Context: {json.dumps(context or {}, indent=2)}

Return a JSON array of tasks in this exact format:
[
  {{
    "id": "task_1",
    "description": "Brief task description",
    "action_type": "open|search|send|analyze|generate|close|system",
    "parameters": {{"key": "value"}},
    "priority": "CRITICAL|HIGH|MEDIUM|LOW|BACKGROUND",
    "dependencies": ["task_id_that_must_complete_first"],
    "estimated_duration": 5.0,
    "requires_confirmation": false
  }}
]

Guidelines:
- Break complex goals into 3-7 atomic tasks
- Each task should be independently executable
- Set dependencies for tasks that must run in sequence
- Use realistic time estimates (in seconds)
- Set requires_confirmation=true for risky actions
- action_type must match available automation commands

Example:
Goal: "Research and summarize recent AI developments, then email the summary to john@example.com"
[
  {{
    "id": "task_1",
    "description": "Search for recent AI developments",
    "action_type": "search",
    "parameters": {{"query": "recent AI developments 2025", "source": "realtime"}},
    "priority": "HIGH",
    "dependencies": [],
    "estimated_duration": 3.0,
    "requires_confirmation": false
  }},
  {{
    "id": "task_2",
    "description": "Analyze and summarize search results",
    "action_type": "analyze",
    "parameters": {{"context": "AI developments", "output_format": "summary"}},
    "priority": "HIGH",
    "dependencies": ["task_1"],
    "estimated_duration": 5.0,
    "requires_confirmation": false
  }},
  {{
    "id": "task_3",
    "description": "Send summary email to john@example.com",
    "action_type": "send",
    "parameters": {{"recipient": "john@example.com", "subject": "AI Developments Summary", "content_source": "task_2"}},
    "priority": "MEDIUM",
    "dependencies": ["task_2"],
    "estimated_duration": 2.0,
    "requires_confirmation": true
  }}
]

Now decompose: "{goal}"
"""

            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are a task planning expert. Return ONLY valid JSON array, no markdown."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=2000
            )
            
            result = response.choices[0].message.content.strip()
            
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()
            
            tasks_data = json.loads(result)
            
            tasks = []
            for task_data in tasks_data:
                task = Task(
                    id=task_data['id'],
                    description=task_data['description'],
                    action_type=task_data['action_type'],
                    parameters=task_data['parameters'],
                    priority=TaskPriority[task_data.get('priority', 'MEDIUM')],
                    dependencies=task_data.get('dependencies', []),
                    estimated_duration=task_data.get('estimated_duration', 5.0),
                    requires_confirmation=task_data.get('requires_confirmation', False)
                )
                tasks.append(task)
            
            return tasks
            
        except Exception as e:
            print(f" AI task planning failed: {e}, using fallback")
            return self._fallback_decompose(goal)
    
    def _fallback_decompose(self, goal: str) -> List[Task]:
        """Fallback task decomposition using heuristics"""
        task = Task(
            id="task_1",
            description=goal,
            action_type="general",
            parameters={"goal": goal},
            priority=TaskPriority.MEDIUM
        )
        return [task]
    
    def optimize_task_order(self, tasks: List[Task]) -> List[Task]:
        """
        Optimize task execution order based on dependencies and priorities
        Topological sort with priority weighting
        """
        task_map = {task.id: task for task in tasks}
        in_degree = {task.id: 0 for task in tasks}
        
        for task in tasks:
            for dep in task.dependencies:
                if dep in in_degree:
                    in_degree[task.id] += 1
        
        from heapq import heappush, heappop
        ready_queue = []
        for task in tasks:
            if in_degree[task.id] == 0:
                heappush(ready_queue, (-task.priority.value, task.id))
        
        ordered_tasks = []
        while ready_queue:
            _, task_id = heappop(ready_queue)
            task = task_map[task_id]
            ordered_tasks.append(task)
            
            for other_task in tasks:
                if task_id in other_task.dependencies:
                    in_degree[other_task.id] -= 1
                    if in_degree[other_task.id] == 0:
                        heappush(ready_queue, (-other_task.priority.value, other_task.id))
        
        return ordered_tasks


class AgenticCore:
    """
    Core agentic system - autonomous planning and execution
    """
    
    def __init__(self, mode: AgentMode = AgentMode.PROACTIVE):
        self.mode = mode
        self.memory = AgenticMemory()
        self.planner = TaskPlanner(groq_client)
        self.active_goals: List[Goal] = []
        self.task_queue: List[Task] = []
        self.execution_history: List[Dict] = []
        self._init_db()
    
    def _init_db(self):
        """Initialize agent state tables"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS agent_goals (
                    id VARCHAR(100) PRIMARY KEY,
                    description TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    priority INT NOT NULL,
                    progress FLOAT DEFAULT 0.0,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    deadline TIMESTAMP WITH TIME ZONE,
                    metadata JSONB DEFAULT '{}'::jsonb
                );
                
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    id VARCHAR(100) PRIMARY KEY,
                    goal_id VARCHAR(100),
                    description TEXT NOT NULL,
                    action_type VARCHAR(100) NOT NULL,
                    parameters JSONB NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    priority INT NOT NULL,
                    dependencies JSONB DEFAULT '[]'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP WITH TIME ZONE,
                    completed_at TIMESTAMP WITH TIME ZONE,
                    result TEXT,
                    error TEXT,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    FOREIGN KEY (goal_id) REFERENCES agent_goals(id) ON DELETE CASCADE
                );
                
                CREATE INDEX IF NOT EXISTS idx_agent_goals_status ON agent_goals(status);
                CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON agent_tasks(status);
                CREATE INDEX IF NOT EXISTS idx_agent_tasks_goal ON agent_tasks(goal_id);
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" Agent DB init error: {e}")
    
    def set_mode(self, mode: AgentMode):
        """Change agent operational mode"""
        self.mode = mode
        print(f" Agent mode set to: {mode.value}")
    
    def create_goal(self, description: str, objective: str, 
                   priority: TaskPriority = TaskPriority.MEDIUM,
                   deadline: Optional[datetime] = None) -> Goal:
        """
        Create a new goal and decompose it into tasks
        """
        goal_id = f"goal_{int(time.time() * 1000)}"
        
        goal = Goal(
            id=goal_id,
            description=description,
            objective=objective,
            priority=priority,
            deadline=deadline
        )
        
        print(f" Planning tasks for goal: {description}")
        tasks = self.planner.decompose_goal(objective, context={
            'priority': priority.name,
            'deadline': deadline.isoformat() if deadline else None
        })
        
        tasks = self.planner.optimize_task_order(tasks)
        
        goal.tasks = tasks
        self.active_goals.append(goal)
        self.task_queue.extend(tasks)
        
        self._save_goal(goal)
        
        print(f" Goal created with {len(tasks)} tasks")
        return goal
    
    def execute_next_task(self) -> Optional[Tuple[Task, Any]]:
        """
        Execute the next ready task from queue
        Returns (task, result) or None if no tasks ready
        """
        if not self.task_queue:
            return None
        
        completed_task_ids = {
            task.id for task in self.execution_history 
            if task.get('status') == TaskStatus.COMPLETED.value
        }
        
        for i, task in enumerate(self.task_queue):
            if task.status != TaskStatus.PENDING:
                continue
            
            dependencies_met = all(dep in completed_task_ids for dep in task.dependencies)
            
            if dependencies_met:
                task.status = TaskStatus.IN_PROGRESS
                task.started_at = time.time()
                
                if self.mode == AgentMode.SUPERVISED and task.requires_confirmation:
                    print(f"\n Task requires confirmation:")
                    print(f"   {task.description}")
                    print(f"   Action: {task.action_type}")
                    print(f"   Parameters: {json.dumps(task.parameters, indent=2)}")
                    
                    confirm = input("   Proceed? (yes/no): ").strip().lower()
                    if confirm not in ['yes', 'y']:
                        task.status = TaskStatus.CANCELLED
                        print("    Task cancelled by user")
                        return None
                
                try:
                    result = self._execute_task(task)
                    task.status = TaskStatus.COMPLETED
                    task.result = result
                    task.completed_at = time.time()
                    task.actual_duration = task.completed_at - task.started_at
                    
                    self.memory.learn_pattern(
                        trigger_context={'goal_type': task.action_type},
                        action_sequence=[task.action_type],
                        success=True
                    )
                    
                    self.task_queue.pop(i)
                    
                    self.execution_history.append({
                        'task_id': task.id,
                        'status': TaskStatus.COMPLETED.value,
                        'result': str(result)[:500],
                        'duration': task.actual_duration
                    })
                    
                    self._update_task_status(task)
                    
                    return (task, result)
                    
                except Exception as e:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    task.retry_count += 1
                    
                    if task.retry_count < task.max_retries:
                        print(f" Task failed, retrying ({task.retry_count}/{task.max_retries})")
                        task.status = TaskStatus.PENDING
                        time.sleep(2 ** task.retry_count)  
                    else:
                        print(f" Task failed after {task.max_retries} retries")
                        self.execution_history.append({
                            'task_id': task.id,
                            'status': TaskStatus.FAILED.value,
                            'error': str(e)
                        })
                    
                    self._update_task_status(task)
                    return None
        
        return None
    
    def _execute_task(self, task: Task) -> Any:
        """
        Execute a single task based on its action_type
        This is where tasks get translated to actual automation commands
        """
        print(f" Executing: {task.description}")
        
        action_type = task.action_type
        params = task.parameters
        
        from Automation import Automation
        from RealTimeSearchEngine import RealtimeSearch
        from ChatBot import ChatBot
        import asyncio
        
        if action_type == "open":
            target = params.get('target', '')
            asyncio.run(Automation([f"open {target}"]))
            return f"Opened {target}"
        
        elif action_type == "search":
            query = params.get('query', '')
            source = params.get('source', 'realtime')
            if source == 'realtime':
                result = RealtimeSearch(query)
                return result
            else:
                asyncio.run(Automation([f"google search {query}"]))
                return f"Searched for {query}"
        
        elif action_type == "analyze":
            context = params.get('context', '')
            result = ChatBot(f"Analyze and summarize: {context}")
            return result
        
        elif action_type == "send":
            recipient = params.get('recipient', '')
            content = params.get('content_source', '')
            if content.startswith('task_'):
                for hist in self.execution_history:
                    if hist.get('task_id') == content:
                        content = hist.get('result', '')
                        break
            
            asyncio.run(Automation([f"email {recipient} {content}"]))
            return f"Sent to {recipient}"
        
        elif action_type == "generate":
            prompt = params.get('prompt', '')
            asyncio.run(Automation([f"generate image {prompt}"]))
            return f"Generated image: {prompt}"
        
        elif action_type == "close":
            target = params.get('target', '')
            asyncio.run(Automation([f"close {target}"]))
            return f"Closed {target}"
        
        elif action_type == "play":
            query = params.get('query', '')
            asyncio.run(Automation([f"play {query}"]))
            return f"Playing {query}"
        
        elif action_type == "system":
            command = params.get('command', '')
            asyncio.run(Automation([f"system {command}"]))
            return f"System: {command}"
        
        else:
            return ChatBot(task.description)
    
    def _save_goal(self, goal: Goal):
        """Save goal to database"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """INSERT INTO agent_goals (id, description, objective, status, priority, deadline)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (goal.id, goal.description, goal.objective, goal.status.value,
                 goal.priority.value, goal.deadline)
            )
            
            for task in goal.tasks:
                cur.execute(
                    """INSERT INTO agent_tasks 
                       (id, goal_id, description, action_type, parameters, status, priority, dependencies)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (task.id, goal.id, task.description, task.action_type,
                     Json(task.parameters), task.status.value, task.priority.value,
                     Json(task.dependencies))
                )
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" Error saving goal: {e}")
    
    def _update_task_status(self, task: Task):
        """Update task status in database"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """UPDATE agent_tasks 
                   SET status = %s, started_at = %s, completed_at = %s, result = %s, error = %s
                   WHERE id = %s""",
                (task.status.value,
                 datetime.fromtimestamp(task.started_at) if task.started_at else None,
                 datetime.fromtimestamp(task.completed_at) if task.completed_at else None,
                 str(task.result)[:1000] if task.result else None,
                 task.error,
                 task.id)
            )
            conn.commit()
            conn.close()
        except:
            pass
    
    def get_active_goals(self) -> List[Goal]:
        """Get all active goals"""
        return [g for g in self.active_goals if g.status != TaskStatus.COMPLETED]
    
    def get_goal_progress(self, goal_id: str) -> float:
        """Calculate goal completion progress"""
        goal = next((g for g in self.active_goals if g.id == goal_id), None)
        if not goal or not goal.tasks:
            return 0.0
        
        completed = sum(1 for t in goal.tasks if t.status == TaskStatus.COMPLETED)
        return completed / len(goal.tasks)


_agentic_core = None

def get_agentic_core() -> AgenticCore:
    """Get or create global agentic core"""
    global _agentic_core
    if _agentic_core is None:
        _agentic_core = AgenticCore()
    return _agentic_core