"""
Command Chain System - Enable chaining of multiple commands with context passing
Supports natural language workflows like "create file and send it on whatsapp"
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable, Awaitable
from enum import Enum
import logging
import re
from groq import Groq
from dotenv import dotenv_values

env_vars = dotenv_values(".env")
GROQ_API_KEY = env_vars.get("GroqAPIKey")
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

logger = logging.getLogger(__name__)


class StepType(Enum):
    """Types of workflow steps"""
    CREATE_FILE = "create_file"
    SEND_WHATSAPP = "send_whatsapp"
    SEND_EMAIL = "send_email"
    SEARCH_WEB = "search_web"
    GENERATE_IMAGE = "generate_image"
    READ_SCREEN = "read_screen"
    OPEN_APP = "open_app"
    CHAT = "chat"
    UNKNOWN = "unknown"


@dataclass
class ChainContext:
    """
    Context object that passes data between chain steps
    Stores results from previous steps to be used in subsequent steps
    """
    original_query: str
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    file_paths: List[str] = field(default_factory=list)
    search_results: Optional[str] = None
    image_paths: List[str] = field(default_factory=list)
    recipients: List[str] = field(default_factory=list)
    topic: Optional[str] = None
    screen_analysis: Optional[str] = None
    last_response: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_file(self, file_path: str):
        """Add a file path to context"""
        self.file_paths.append(file_path)
        logger.info(f"Added file to context: {file_path}")
    
    def add_image(self, image_path: str):
        """Add an image path to context"""
        self.image_paths.append(image_path)
        logger.info(f"Added image to context: {image_path}")
    
    def set_search_results(self, results: str):
        """Set search results"""
        self.search_results = results
        logger.info(f"Added search results to context ({len(results)} chars)")
    
    def set_topic(self, topic: str):
        """Set the main topic"""
        self.topic = topic
        logger.info(f"Set topic: {topic}")
    
    def set_screen_analysis(self, analysis: str):
        """Set screen analysis result"""
        self.screen_analysis = analysis
        logger.info(f"Added screen analysis to context ({len(analysis)} chars)")
    
    def get_latest_file(self) -> Optional[str]:
        """Get the most recently created file"""
        return self.file_paths[-1] if self.file_paths else None
    
    def get_latest_image(self) -> Optional[str]:
        """Get the most recently generated image"""
        return self.image_paths[-1] if self.image_paths else None


@dataclass
class WorkflowStep:
    """
    Represents a single step in a command chain
    """
    step_type: StepType
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    depends_on_previous: bool = False
    
    def __repr__(self):
        return f"WorkflowStep({self.step_type.value}: {self.description})"


class CommandChainParser:
    """
    Parse natural language commands into workflow steps
    Uses AI to understand multi-step intents
    """
    
    def __init__(self):
        self.groq_client = groq_client
    
    def is_chain_command(self, query: str) -> bool:
        """
        Detect if a command contains multiple steps
        Look for connecting words like 'and', 'then', 'after'
        """
        # Keywords that suggest chaining
        chain_indicators = [
            r'\band\b.*\b(send|email|whatsapp|share)',
            r'\bthen\b',
            r'\bafter\b.*\b(create|generate|search)',
            r'(create|make|generate).*\band\b.*(send|email|share)',
            r'(search|find).*\band\b.*(create|make|document)',
            r'(read|summarize|analyze).*screen.*\band\b',
            r'\bon my screen\b.*\band\b',
            r'\bon this\b',  # "create a document on this"
        ]
        
        query_lower = query.lower()
        for pattern in chain_indicators:
            if re.search(pattern, query_lower):
                logger.info(f"Detected chain command with pattern: {pattern}")
                return True
        
        return False
    
    def parse_workflow(self, query: str, conversation_context: Optional[List] = None) -> List[WorkflowStep]:
        """
        Parse a natural language query into workflow steps
        
        Args:
            query: Natural language command
            conversation_context: Recent conversation for context
        
        Returns:
            List of WorkflowStep objects
        """
        if not self.groq_client:
            logger.error("Groq client not initialized")
            return []
        
        try:
            # Build context for AI
            context_info = ""
            if conversation_context:
                recent = conversation_context[-3:]  # Last 3 turns
                context_info = "\n".join([
                    f"User: {turn.get('user', '')}\nAssistant: {turn.get('assistant', '')}"
                    for turn in recent
                ])
            
            prompt = f"""Analyze this command and break it into a sequence of workflow steps.

Command: "{query}"

Recent conversation context:
{context_info if context_info else "No recent conversation"}

Your task: Extract ONLY the distinct steps needed. For each step, identify:
1. Step type (create_file, send_whatsapp, send_email, search_web, generate_image, chat, open_app, read_screen)
2. Brief description
3. Key parameters (file_type, topic, recipient, etc.)
4. Whether it depends on output from previous step

IMPORTANT RULES:
- For "send to X" commands, use send_whatsapp by default UNLESS "email" or "mail" is explicitly mentioned
- For "send it to myself" or "send to me", use send_whatsapp with recipient "myself"
- Only use send_email if the user explicitly says "email" or "mail"

Common patterns:
- "create X and send it to Y" = create_file  send_whatsapp (NOT email)
- "search for X and create document on this" = search_web  create_file
- "generate image of X and send to Y" = generate_image  send_whatsapp
- "create a document on this" (with conversation) = chat (gather context)  create_file
- "send to myself" = send_whatsapp with recipient "myself"
- "email to X" = send_email (only when explicitly mentioned)
- "read my screen and send to X" = read_screen  send_whatsapp
- "summarize my screen in a word document" = read_screen  create_file (depends_on_previous: true)
- "what's on my screen and email it to john" = read_screen  send_email (depends_on_previous: true)

Return ONLY valid JSON array of steps, like:
[
  {{"step_type": "create_file", "description": "Create Python file with fibonacci code", "parameters": {{"file_type": "python", "topic": "fibonacci code"}}, "depends_on_previous": false}},
  {{"step_type": "send_whatsapp", "description": "Send file to myself", "parameters": {{"recipient": "myself"}}, "depends_on_previous": true}}
]

Return ONLY the JSON array, no other text."""

            response = self.groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0.3,
                max_tokens=1000
            )
            
            response_text = response.choices[0].message.content.strip()
            logger.info(f"AI workflow analysis: {response_text[:200]}...")
            
            # Extract JSON from response
            import json
            # Try to find JSON array in response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                steps_data = json.loads(json_match.group(0))
            else:
                steps_data = json.loads(response_text)
            
            # Convert to WorkflowStep objects
            steps = []
            for step_data in steps_data:
                try:
                    step_type = StepType(step_data.get("step_type", "unknown"))
                except ValueError:
                    step_type = StepType.UNKNOWN
                
                step = WorkflowStep(
                    step_type=step_type,
                    description=step_data.get("description", ""),
                    parameters=step_data.get("parameters", {}),
                    depends_on_previous=step_data.get("depends_on_previous", False)
                )
                steps.append(step)
            
            logger.info(f"Parsed {len(steps)} workflow steps")
            for i, step in enumerate(steps):
                logger.info(f"  Step {i+1}: {step}")
            
            return steps
            
        except Exception as e:
            logger.error(f"Failed to parse workflow: {e}", exc_info=True)
            return []


class CommandChainExecutor:
    """
    Execute workflow chains by calling appropriate handlers
    Manages context passing between steps
    """
    
    def __init__(self, command_handlers: Dict[str, Callable]):
        """
        Initialize executor with command handlers
        
        Args:
            command_handlers: Dict mapping step types to async handler functions
                Example: {
                    'create_file': file_creator.create_file,
                    'send_whatsapp': automation.send_whatsapp,
                    ...
                }
        """
        self.handlers = command_handlers
        self.parser = CommandChainParser()
    
    async def execute_chain(self, query: str, conversation_context: Optional[List] = None) -> tuple[bool, str]:
        """
        Execute a command chain
        
        Args:
            query: Natural language command
            conversation_context: Recent conversation turns
        
        Returns:
            Tuple of (success, result_message)
        """
        # Parse workflow
        steps = self.parser.parse_workflow(query, conversation_context)
        
        if not steps:
            return False, "Could not parse workflow steps"
        
        # Initialize context
        context = ChainContext(
            original_query=query,
            conversation_history=conversation_context or []
        )
        
        # Execute steps in sequence
        results = []
        for i, step in enumerate(steps):
            logger.info(f"Executing step {i+1}/{len(steps)}: {step.step_type.value}")
            
            try:
                # Get handler for this step type
                handler = self.handlers.get(step.step_type.value)
                
                if not handler:
                    logger.warning(f"No handler for step type: {step.step_type.value}")
                    results.append(f" Step {i+1}: No handler for {step.step_type.value}")
                    continue
                
                # Execute step with context
                result = await self._execute_step(step, context, handler)
                
                if result:
                    results.append(f" Step {i+1}: {step.description} - {result}")
                    context.last_response = result
                else:
                    results.append(f" Step {i+1}: {step.description} - Failed")
                    # Continue anyway, some steps might not be critical
                
            except Exception as e:
                logger.error(f"Step {i+1} failed: {e}", exc_info=True)
                results.append(f" Step {i+1}: {step.description} - Error: {str(e)}")
        
        # Build final response
        success = any("" in r for r in results)
        response = " **Command Chain Execution**\n\n" + "\n".join(results)
        
        return success, response
    
    async def _execute_step(self, step: WorkflowStep, context: ChainContext, handler: Callable) -> Optional[str]:
        """
        Execute a single workflow step
        
        Args:
            step: WorkflowStep to execute
            context: Current chain context
            handler: Handler function for this step type
        
        Returns:
            Result message or None if failed
        """
        # Prepare parameters based on step type and context
        params = step.parameters.copy()
        
        # Add context-based parameters
        if step.step_type == StepType.CREATE_FILE:
            # If topic is "this" or similar, use conversation context
            topic = params.get("topic", "")
            if topic.lower() in ["this", "current topic", "conversation"]:
                if context.search_results:
                    params["content"] = context.search_results
                elif context.conversation_history:
                    params["topic"] = f"Summary of our conversation about {context.topic or 'various topics'}"
            
            # Set topic in context for future steps
            if "topic" in params:
                context.set_topic(params["topic"])
        
        elif step.step_type == StepType.READ_SCREEN:
            # Check if there's a specific question in params
            pass
        
        elif step.step_type == StepType.SEND_WHATSAPP:
            # Add file from context if this step depends on previous
            if step.depends_on_previous and context.file_paths:
                params["file_path"] = context.get_latest_file()
            
            # Auto-populate message from search OR screen results if missing
            if step.depends_on_previous and not params.get("message"):
                if context.screen_analysis:
                    params["message"] = f"Here's what I found on my screen: {context.screen_analysis}"
                elif context.search_results:
                    params["message"] = f"I found this for you: {context.search_results}"
            
            # Handle "myself" recipient
            if params.get("recipient", "").lower() in ["myself", "me"]:
                params["recipient"] = "myself"
        
        elif step.step_type == StepType.SEND_EMAIL:
            # Add file/image from context
            if step.depends_on_previous:
                if context.file_paths:
                    params["file_path"] = context.get_latest_file()
                elif context.image_paths:
                    params["file_path"] = context.get_latest_image()
                
                # Auto-populate message from screen/search results if missing
                if not params.get("message"):
                    if context.screen_analysis:
                        params["message"] = f"Here is the screen analysis: {context.screen_analysis}"
                    elif context.search_results:
                        params["message"] = f"Here are the search results: {context.search_results}"
        
        elif step.step_type == StepType.SEARCH_WEB:
            # Store search results in context
            pass  # Handler will return results
        
        elif step.step_type == StepType.CREATE_FILE:
            # If creating a file from screen analysis
            if step.depends_on_previous and context.screen_analysis and not params.get("content"):
                params["content"] = context.screen_analysis
                if not params.get("topic"):
                    params["topic"] = "Screen Summary"
        
        # Call handler
        try:
            result = await handler(params, context)
            
            # Update context based on result
            if step.step_type == StepType.CREATE_FILE and isinstance(result, dict):
                if result.get("success") and result.get("path"):
                    context.add_file(result["path"])
                    return f"Created {result['path']}"
            
            elif step.step_type == StepType.GENERATE_IMAGE and isinstance(result, dict):
                if result.get("path"):
                    context.add_image(result["path"])
                    return f"Generated image at {result['path']}"
            
            elif step.step_type == StepType.SEARCH_WEB:
                if isinstance(result, str):
                    context.set_search_results(result)
                    return f"Found search results ({len(result)} chars)"
            
            elif step.step_type == StepType.READ_SCREEN:
                if isinstance(result, str):
                    context.set_screen_analysis(result)
                    return f"Analyzed screen ({len(result)} chars)"
            
            # Return string result
            if isinstance(result, str):
                return result
            elif isinstance(result, dict):
                return result.get("message", "Completed")
            else:
                return "Completed"
                
        except Exception as e:
            logger.error(f"Handler execution failed: {e}", exc_info=True)
            return None


# Global instance
_chain_executor = None


def get_command_chain_executor(command_handlers: Optional[Dict] = None):
    """Get or create global CommandChainExecutor instance"""
    global _chain_executor
    if _chain_executor is None and command_handlers:
        _chain_executor = CommandChainExecutor(command_handlers)
    return _chain_executor


def is_chain_command(query: str) -> bool:
    """Quick check if a query is a chain command"""
    parser = CommandChainParser()
    return parser.is_chain_command(query)
