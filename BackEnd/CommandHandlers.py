"""
Command Handlers - Modular command processing system
Replaces the massive if/elif chains with clean, extensible handlers
"""
from abc import ABC, abstractmethod
from typing import Optional, Any
import logging
from MetaQuery import is_agent_meta_query


class CommandHandler(ABC):
    """Base class for all command handlers"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"handler.{name}")
    
    @abstractmethod
    async def can_handle(self, user_input: str) -> bool:
        """Check if this handler can process the command"""
        pass
    
    @abstractmethod
    async def handle(self, user_input: str, context: dict) -> Any:
        """Process the command and return result"""
        pass
    
    def get_help_text(self) -> str:
        """Return help text for this command"""
        return f"Handler: {self.name}"


class GoalCommandHandler(CommandHandler):
    """Handle goal-related commands"""
    
    def __init__(self, agentic_core):
        super().__init__("goal")
        self.agentic_core = agentic_core
    
    async def can_handle(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(cmd in lower for cmd in [
            "create goal:", "show goals", "continue goals", "goal status"
        ])
    
    async def handle(self, user_input: str, context: dict) -> str:
        from AgenticCore import TaskPriority, TaskStatus
        import time
        
        lower = user_input.lower()
        
        if lower.startswith("create goal:"):
            objective = user_input[12:].strip()
            goal = self.agentic_core.create_goal(
                description=f"User goal: {objective}",
                objective=objective,
                priority=TaskPriority.HIGH
            )
            
            response = f" Goal created with {len(goal.tasks)} tasks:\n"
            for i, task in enumerate(goal.tasks, 1):
                response += f"   {i}. {task.description}\n"
            
            return response
        
        elif lower == "show goals":
            goals = self.agentic_core.get_active_goals()
            if not goals:
                return "No active goals."
            
            response = " Active Goals:\n"
            for goal in goals:
                progress = self.agentic_core.get_goal_progress(goal.id)
                response += f"\n {goal.description}\n"
                response += f"   Progress: {progress:.0%}\n"
                response += f"   Tasks: {len([t for t in goal.tasks if t.status == TaskStatus.COMPLETED])}/{len(goal.tasks)} completed\n"
            
            return response
        
        elif lower == "continue goals":
            # Import here to avoid circular dependency
            from mainagentic import execute_autonomous_task
            
            total_executed = 0
            while True:
                result = await execute_autonomous_task(None)
                if not result:
                    break
                total_executed += 1
                time.sleep(1)
            
            return f" Executed {total_executed} task(s)"
        
        return "Unknown goal command"


class ModeCommandHandler(CommandHandler):
    """Handle agent mode changes"""
    
    def __init__(self, agentic_core):
        super().__init__("mode")
        self.agentic_core = agentic_core
    
    async def can_handle(self, user_input: str) -> bool:
        return user_input.lower().startswith("set mode ")
    
    async def handle(self, user_input: str, context: dict) -> str:
        from AgenticCore import AgentMode
        
        mode_str = user_input.lower().replace("set mode ", "").strip()
        
        mode_map = {
            "autonomous": (AgentMode.AUTONOMOUS, " AUTONOMOUS - I'll take actions independently"),
            "proactive": (AgentMode.PROACTIVE, " PROACTIVE - I'll suggest actions"),
            "supervised": (AgentMode.SUPERVISED, " SUPERVISED - I'll ask before critical actions"),
            "reactive": (AgentMode.REACTIVE, " REACTIVE - I'll only respond to commands")
        }
        
        if mode_str in mode_map:
            mode, message = mode_map[mode_str]
            self.agentic_core.set_mode(mode)
            return f"Agent mode set to {message}"
        
        return f"Unknown mode: {mode_str}"


class CapabilityCommandHandler(CommandHandler):
    """Handle capability-related commands"""
    
    def __init__(self, capability_registry):
        super().__init__("capability")
        self.registry = capability_registry
    
    async def can_handle(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(cmd in lower for cmd in [
            "what can you do", "show capabilities", "list capabilities"
        ])
    
    async def handle(self, user_input: str, context: dict) -> str:
        return self.registry.get_capability_summary()


class TaskCommandHandler(CommandHandler):
    """Handle task management commands"""
    
    def __init__(self, task_executor, background_manager):
        super().__init__("task")
        self.task_executor = task_executor
        self.background_manager = background_manager
    
    async def can_handle(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(cmd in lower for cmd in [
            "what are you doing", "show active tasks", "show tasks",
            "list tasks", "active tasks", "task status", "cancel task",
            "pause tasks", "resume tasks"
        ])
    
    async def handle(self, user_input: str, context: dict) -> str:
        lower = user_input.lower()
        
        if "what are you doing" in lower or "show active tasks" in lower:
            return self.task_executor.get_active_tasks_summary()
        
        elif any(cmd in lower for cmd in ["show tasks", "list tasks", "active tasks"]):
            active = self.background_manager.list_active_tasks()
            if not active:
                return "No active background tasks"
            
            response = f" **ACTIVE BACKGROUND TASKS** ({len(active)})\n\n"
            for task in active:
                state_emoji = "[RUN]" if task['state'] == 'running' else "[PAUSE]"
                response += f"{state_emoji} {task['name']} (ID: {task['id'][:8]}...)\n"
                response += f"   State: {task['state']} | Progress: {task['progress']*100:.0f}%\n"
                if task.get('estimated_remaining'):
                    response += f"   Est. remaining: {task['estimated_remaining']:.0f}s\n"
                response += "\n"
            return response
        
        elif lower.startswith("task status "):
            task_id = user_input[12:].strip()
            status = self.background_manager.get_task_status(task_id)
            if not status:
                return f"Task '{task_id}' not found"
            
            response = f" **TASK STATUS**\n\n"
            response += f"ID: {status['id']}\n"
            response += f"Name: {status['name']}\n"
            response += f"State: {status['state']}\n"
            response += f"Progress: {status['progress']*100:.0f}%\n"
            if status.get('result'):
                response += f"Result: {status['result']}\n"
            if status.get('error'):
                response += f"Error: {status['error']}\n"
            return response
        
        elif lower.startswith("cancel task "):
            task_id = user_input[12:].strip()
            if self.background_manager.cancel_task(task_id):
                return f" Task {task_id[:8]}... cancelled"
            return f" Could not cancel task {task_id}"
        
        elif lower == "pause tasks":
            self.background_manager.pause_all()
            return " Background tasks paused"
        
        elif lower == "resume tasks":
            self.background_manager.resume_all()
            return " Background tasks resumed"
        
        return "Unknown task command"


class NotificationCommandHandler(CommandHandler):
    """Handle notification commands"""
    
    def __init__(self, notification_system):
        super().__init__("notification")
        self.notification_system = notification_system
    
    async def can_handle(self, user_input: str) -> bool:
        lower = user_input.lower()
        return any(cmd in lower for cmd in [
            "show notifications", "notifications", "clear notifications",
            "mute notifications", "unmute notifications"
        ])
    
    async def handle(self, user_input: str, context: dict) -> str:
        lower = user_input.lower()
        
        if "show notifications" in lower or lower == "notifications":
            return self.notification_system.format_notification_summary()
        
        elif "clear notifications" in lower:
            self.notification_system.clear_history()
            return " Notifications cleared"
        
        elif "mute notifications" in lower:
            self.notification_system.mute()
            return " Notifications muted"
        
        elif "unmute notifications" in lower:
            self.notification_system.unmute()
            return " Notifications unmuted"
        
        return "Unknown notification command"


class ConversationCommandHandler(CommandHandler):
    """Handle conversation-related commands"""
    
    def __init__(self, conversation_context):
        super().__init__("conversation")
        self.context = conversation_context
    
    async def can_handle(self, user_input: str) -> bool:
        return "conversation summary" in user_input.lower()
    
    async def handle(self, user_input: str, context: dict) -> str:
        return self.context.get_conversation_summary()


class FileCreationCommandHandler(CommandHandler):
    """Handle file and folder creation commands"""
    
    def __init__(self, file_creator):
        super().__init__("file_creation")
        self.file_creator = file_creator
    
    async def can_handle(self, user_input: str) -> bool:
        import re
        lower = user_input.lower()
        if is_agent_meta_query(lower):
            return False
        
        # Use regex for more flexible matching (handles "create a folder", "make a file", etc.)
        patterns = [
            r'\bcreate\s+(a\s+)?folder\b',
            r'\bmake\s+(a\s+)?folder\b',
            r'\bcreate\s+(a\s+)?file\b',
            r'\bmake\s+(a\s+)?file\b',
            r'\bcreate\s+(a\s+)?python\s+file\b',
            r'\bcreate\s+(a\s+)?word\s+(?:file|document|doc)\b',
            r'\bcreate\s+(a\s+)?(pdf|document)\b',
            r'\bgenerate\s+(a\s+)?file\b',
            r'\bwrite\s+(a\s+)?file\b',
        ]
        
        return any(re.search(pattern, lower) for pattern in patterns)
    
    async def handle(self, user_input: str, context: dict) -> str:
        import re
        from pathlib import Path
        import os
        
        lower = user_input.lower()
        
        # Get actual Windows Desktop path (handles OneDrive redirection)
        def get_real_desktop():
            """Get the actual Desktop path from Windows environment"""
            try:
                # Use Windows environment variable for Desktop
                import ctypes.wintypes
                CSIDL_DESKTOP = 0
                buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
                ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOP, None, 0, buf)
                return buf.value
            except:
                # Fallback to environment variable
                desktop = os.environ.get('USERPROFILE', str(Path.home()))
                # Check if OneDrive Desktop exists
                onedrive_desktop = Path(desktop) / "OneDrive" / "Desktop"
                if onedrive_desktop.exists():
                    return str(onedrive_desktop)
                return str(Path.home() / "Desktop")
        
        # Extract location (desktop, documents, etc.)
        location_map = {
            "desktop": get_real_desktop(),
            "documents": str(Path.home() / "Documents"),
            "downloads": str(Path.home() / "Downloads"),
        }
        
        target_location = None
        for loc_name, loc_path in location_map.items():
            if loc_name in lower:
                target_location = loc_path
                break
        
        if not target_location:
            target_location = get_real_desktop()  # Default to actual desktop
        
        # Handle folder creation
        if "folder" in lower:
            # Extract folder name
            match = re.search(r'create (?:a )?folder (?:named |called )?(.+?)(?:\s+on|\s+in|$)', lower)
            if match:
                folder_name = match.group(1).strip()
                folder_path = Path(target_location) / folder_name
                result = await self.file_creator.create_folder(str(folder_path))
                return result["message"]
            return " Please specify folder name"
        
        # Handle Python file creation
        if "python" in lower or ".py" in lower:
           # Extract description
            desc = lower.replace("create python file", "").replace("on my desktop", "").replace("which has", "").replace("with", "").strip()
            
            if not desc:
                return " Please specify what the Python code should do"
            
            # Generate filename from description
            filename = desc.replace(" ", "_")[:30] + ".py"
            file_path = Path(target_location) / filename
            
            result = await self.file_creator.create_python_file(str(file_path), desc)
            return result["message"]
        
        # Handle Word file creation
        if "word" in lower or "docx" in lower:
            # Extract topic - use regex to remove file type and extra words
            topic = re.sub(r'\b(create|make)\s+(a\s+)?(word\s+)?(file|document|doc)\s+(about\s+)?', '', lower)
            # Also handle "on" instead of "about" (e.g., "word doc on ants")
            topic = re.sub(r'\s+(on|about)\s+', ' ', topic)
            # Remove location references (desktop, documents, downloads)
            topic = re.sub(r'\b(on|in|to)\s+(my\s+)?(desktop|documents|downloads)\b', '', topic)
            topic = re.sub(r'\s+', ' ', topic)  # Collapse multiple spaces
            topic = topic.strip()
            
            if not topic:
                return " Please specify the document topic"
            
            # Generate filename
            filename = topic.replace(" ", "_")[:30] + ".docx"
            file_path = Path(target_location) / filename
            
            result = await self.file_creator.create_word_file(str(file_path), topic, use_web=True)
            return result["message"]
        
        # Handle PDF creation
        if "pdf" in lower:
            # Extract topic - use regex to remove file type and extra words
            topic = re.sub(r'\b(create|make)\s+(a\s+)?(pdf|document)\s+(about\s+)?', '', lower)
            # Remove location references
            topic = re.sub(r'\b(on|in|to)\s+(my\s+)?(desktop|documents|downloads)\b', '', topic)
            topic = re.sub(r'\s+', ' ', topic)  # Collapse multiple spaces
            topic = topic.strip()
            
            if not topic:
                return " Please specify the PDF topic"
            
            # Generate filename
            filename = topic.replace(" ", "_")[:30] + ".pdf"
            file_path = Path(target_location) / filename
            
            result = await self.file_creator.create_pdf_file(str(file_path), topic, use_web=True)
            return result["message"]
        
        return " Please specify file type (python, word, pdf, or folder)"


class CommandRegistry:
    """Registry for all command handlers"""
    
    def __init__(self):
        self.handlers: list[CommandHandler] = []
        self.logger = logging.getLogger("command_registry")
    
    def register(self, handler: CommandHandler) -> None:
        """Register a new command handler"""
        self.handlers.append(handler)
        self.logger.debug(f"Registered handler: {handler.name}")
    
    async def find_handler(self, user_input: str) -> Optional[CommandHandler]:
        """Find the first handler that can process this command"""
        for handler in self.handlers:
            if await handler.can_handle(user_input):
                return handler
        return None
    
    async def process(self, user_input: str, context: dict = None) -> tuple[bool, Any]:
        """
        Process command using appropriate handler
        
        Returns:
            (handled, result) tuple
        """
        context = context or {}
        handler = await self.find_handler(user_input)
        
        if handler:
            self.logger.info(f"Processing with handler: {handler.name}")
            result = await handler.handle(user_input, context)
            return (True, result)
        
        return (False, None)
    
    def get_all_help(self) -> str:
        """Get help text from all handlers"""
        help_text = "Available Commands:\n\n"
        for handler in self.handlers:
            help_text += f" {handler.get_help_text()}\n"
        return help_text


# Global registry instance
_command_registry = None

def get_command_registry() -> CommandRegistry:
    """Get the global command registry"""
    global _command_registry
    if _command_registry is None:
        _command_registry = CommandRegistry()
    return _command_registry


def initialize_command_handlers(agentic_core, capability_registry, task_executor,
                                conversation_context, background_manager,
                                notification_system, file_creator) -> CommandRegistry:
    """Initialize and register all command handlers"""
    registry = get_command_registry()
    
    # Register all handlers
    registry.register(GoalCommandHandler(agentic_core))
    registry.register(ModeCommandHandler(agentic_core))
    registry.register(CapabilityCommandHandler(capability_registry))
    registry.register(TaskCommandHandler(task_executor, background_manager))
    registry.register(NotificationCommandHandler(notification_system))
    registry.register(ConversationCommandHandler(conversation_context))
    registry.register(FileCreationCommandHandler(file_creator))
    
    return registry
