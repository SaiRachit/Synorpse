import sys
import asyncio
import time
from pathlib import Path
from typing import Optional
import logging

backend_path = Path(__file__).parent / "BackEnd"
sys.path.insert(0, str(backend_path))

from ConfigManager import get_config
from LoggingConfig import setup_logging, get_logger, get_performance_logger, timer
from Security import get_input_validator, get_rate_limiter, get_audit_logger
from StatePersistence import get_state_persistence, get_goal_persistence
from SystemAwareness import get_system_awareness
from FileCreator import get_file_creator
from AsyncWrappers import (
    get_async_chatbot, get_async_search, get_async_image_generator,
    get_async_automation, async_retry, async_timeout, CircuitBreaker
)
from CommandHandlers import initialize_command_handlers, get_command_registry

from AgenticCore import (
    get_agentic_core, AgentMode, TaskPriority, TaskStatus
)
from ProactiveBehaviors import (
    get_suggestion_engine, PatternAnalyzer
)
from IntentRouter import get_intent_router_fixed
from ChatBot import init_db as init_chatbot_db, save_message, clear_chat_history
from RealTimeSearchEngine import init_search_db
from Automation import init_automation_db, get_automation_logs
from ImageGeneration import LocalImageGenerator

from CapabilityRegistry import get_capability_registry
from TaskExecutor import get_task_executor, ExecutableTask, TaskPriority as ExecTaskPriority
from ConversationContext import get_conversation_context
from BackgroundTaskManager import get_background_task_manager, TaskPriority as BgTaskPriority
from NotificationSystem import get_notification_system
from CommandChain import get_command_chain_executor, is_chain_command, CommandChainParser
from ChainHandlers import get_chain_handlers
from ReasoningHandlers import get_reasoning_handlers

config = None
logger = None
perf_logger = None
agentic_core = None
suggestion_engine = None
pattern_analyzer = None
intent_router = None
capability_registry = None
task_executor = None
conversation_context = None
background_manager = None
notification_system = None
command_registry = None
chain_executor = None
chain_handlers = None
chain_parser = None
reasoning_handlers = None

input_validator = None
rate_limiter = None
audit_logger = None
state_persistence = None
goal_persistence = None
system_awareness = None
file_creator = None

async_chatbot = None
async_search = None
async_image_gen = None
async_automation = None

chatbot_circuit = CircuitBreaker(failure_threshold=5, timeout=60)
search_circuit = CircuitBreaker(failure_threshold=5, timeout=60)


def initialize_systems():
    """Initialize all agentic systems"""
    global config, logger, perf_logger
    global agentic_core, suggestion_engine, pattern_analyzer, intent_router
    global capability_registry, task_executor, conversation_context
    global background_manager, notification_system, command_registry
    global input_validator, rate_limiter, audit_logger
    global state_persistence, goal_persistence, system_awareness, file_creator
    global async_chatbot, async_search, async_image_gen, async_automation
    global chain_executor, chain_handlers, chain_parser
    global reasoning_handlers
    
    config = get_config()
    
    setup_logging(config)
    logger = get_logger("mainagentic")
    perf_logger = get_performance_logger()
    
    input_validator = get_input_validator()
    rate_limiter = get_rate_limiter()
    audit_logger = get_audit_logger()
    state_persistence = get_state_persistence()
    goal_persistence = get_goal_persistence()
    system_awareness = get_system_awareness()
    
    logger.info("🔧 Initializing Agentic AI Systems...")
    
    with timer("Database Initialization", logger):
        init_chatbot_db()
        init_automation_db()
        init_search_db()
    
    async_chatbot = get_async_chatbot()
    async_search = get_async_search()
    async_image_gen = get_async_image_generator()
    async_automation = get_async_automation()
    
    file_creator = get_file_creator(
        chatbot_func=async_chatbot.query,
        search_func=async_search.search
    )
    
    capability_registry = get_capability_registry()
    task_executor = get_task_executor()
    conversation_context = get_conversation_context()
    background_manager = get_background_task_manager()
    notification_system = get_notification_system()
    
    agentic_core = get_agentic_core()
    suggestion_engine = get_suggestion_engine()
    pattern_analyzer = PatternAnalyzer()
    intent_router = get_intent_router_fixed()
    
    command_registry = initialize_command_handlers(
        agentic_core, capability_registry, task_executor,
        conversation_context, background_manager, notification_system, file_creator
    )
    
    from Automation import PHONEBOOK
    chain_handlers = get_chain_handlers(
        file_creator, None, async_chatbot, async_search,
        async_image_gen, conversation_context, PHONEBOOK
    )
    chain_executor = get_command_chain_executor(chain_handlers.get_handlers_dict())
    chain_parser = CommandChainParser()
    
    reasoning_handlers = get_reasoning_handlers(
        async_search, async_chatbot, async_image_gen,
        async_automation, file_creator, PHONEBOOK
    )
    
    logger.info("✅ Agentic AI Systems Ready (with Unified Reasoning)")
    logger.info(f"   Mode: {agentic_core.mode.value}")
    logger.info(f"   Capabilities: {len(capability_registry.get_all_capabilities())} registered")
    logger.info(f"   Context: Session {conversation_context.current_session.session_id[:8]}...")
    logger.info(f"   Background: {background_manager.max_workers} workers ready")
    
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
        console = Console()
        
        title = Text()
        title.append("🤖 ", style="bold cyan")
        title.append(config.get('system.assistant_name', 'SYNORPSE').upper(), style="bold green")
        title.append(" - AGENTIC AI ASSISTANT", style="bold cyan")
        
        info_text = f"Mode: [bold yellow]{agentic_core.mode.value.upper()}[/bold yellow]\nType [bold cyan]'help'[/bold cyan] for commands"
        
        console.print(Panel(info_text, title=title, border_style="cyan"))
    except ImportError:
        print("=" * 60)
        print(f" {config.get('system.assistant_name', 'SYNORPSE').upper()} - AGENTIC AI ASSISTANT")
        print("=" * 60)
        print(f"Mode: {agentic_core.mode.value.upper()}")
        print("Type 'help' for commands")
        print("=" * 60)


async def execute_autonomous_task(task):
    """Execute a task from the agentic core"""
    try:
        with timer("Autonomous Task Execution", logger):
            result = agentic_core.execute_next_task()
            
            if result:
                task_obj, task_result = result
                logger.info(f"Autonomous task completed: {task_obj.description}")
                
                pattern_analyzer.record_action(
                    task_obj.action_type,
                    task_obj.parameters
                )
                
                return True
            return False
    except Exception as e:
        logger.error(f"Autonomous task failed: {e}", exc_info=True)
        return False


async def check_proactive_suggestions():
    """Check and present proactive suggestions"""
    try:
        suggestions = suggestion_engine.generate_suggestions()
        
        if suggestions:
            for suggestion in suggestions:
                should_execute = suggestion_engine.present_suggestion(suggestion)
                
                if should_execute:
                    goal = agentic_core.create_goal(
                        description=suggestion.action_description,
                        objective=f"Execute {suggestion.action_type} with {suggestion.action_parameters}",
                        priority=TaskPriority(min(suggestion.priority, 5))
                    )
                    
                    await execute_autonomous_task(None)
                    logger.info("Executed proactive suggestion")
                
                break
    except Exception as e:
        logger.warning(f"Proactive suggestion check failed: {e}")


async def execute_with_reasoning(goal: str, context: str = None) -> str:
    """
    Execute a complex goal using the ReAct reasoning loop.
    Used for multi-step tasks, low-confidence intents, or autonomous mode.
    
    Args:
        goal: The user's goal/request
        context: Optional additional context
    
    Returns:
        String response from the reasoning process
    """
    try:
        logger.info(f"🧠 Starting ReAct reasoning for: {goal[:50]}...")
        print("\n💭 Thinking...", end="", flush=True)
        
        def on_thought(thought: str):
            """Callback to display thoughts in real-time"""
            print(f"\n{thought}", flush=True)
        
        with timer(f"Reasoning: {goal[:30]}...", logger):
            response = await async_search.search(
                query=goal,
                on_thought=on_thought,
                context=context
            )
        
        return response
            
    except Exception as e:
        logger.error(f"Reasoning execution failed: {e}", exc_info=True)
        return f"❌ Error during reasoning: {str(e)}"


@async_retry(max_retries=2, base_delay=1.0)
@async_timeout(300)  
async def execute_multi_intent(decisions: list, original_query: str) -> str:
    """Execute multiple intents concurrently using TaskExecutor"""
    from functools import partial
    
    tasks = []
    
    for decision in decisions:
        parts = decision.split(maxsplit=1)
        decision_type = parts[0]
        resolved_query = parts[1] if len(parts) > 1 else original_query
        
        if decision_type == "generate" and "image" in resolved_query:
            image_prompt = resolved_query.replace("image", "", 1).strip()
            
            async def background_image_task(prompt):
                """Runs in background, doesn't block the main loop"""
                import time
                start_time = time.time()
                
                try:
                    print(f"\n🖼️ Starting background image generation: {prompt[:40]}...")
                    
                    image, seed, enhanced_prompt = await async_image_gen.generate(prompt)
                    image_id = await async_image_gen.save_to_db(image, prompt, enhanced_prompt, seed)
                    await async_image_gen.save_to_file(image, prompt, seed)
                    
                    elapsed = time.time() - start_time
                    
                    try:
                        image.show()
                    except:
                        pass
                    
                    print(f"\n✅ 🎨 IMAGE READY! Generated in {elapsed:.1f}s")
                    print(f"   Prompt: {prompt[:50]}{'...' if len(prompt) > 50 else ''}")
                    print(f"   ID: {image_id}, Seed: {seed}")
                    print(f"   The image has been opened for viewing.")
                    print(f"\n>>> Continue typing your next command...\n")
                    
                    conversation_context.add_turn(
                        f"[SYSTEM] Image generation completed for '{prompt[:30]}...'",
                        f"Image successfully generated (ID: {image_id}, Seed: {seed}). The image has been opened for viewing.",
                        intent="generate_image"
                    )
                    
                except Exception as e:
                    print(f"\n❌ Image generation failed: {e}")
                    print(f"\n>>> Continue typing your next command...\n")
                    
                    conversation_context.add_turn(
                        f"[SYSTEM] Image generation failed for '{prompt[:30]}...'",
                        f"Image generation failed: {str(e)}",
                        intent="generate_image"
                    )
            
            asyncio.create_task(background_image_task(image_prompt))
            
            response = f"🎨 Image is generating in background: '{image_prompt}'\n   You can continue chatting. I'll notify you when it's ready!"
            return response
        
        elif decision_type == "realtime":
            async def search_task(query):
                return await search_circuit(async_search.search)(query)
            
            task = task_executor.create_task(
                name=f"Search: {resolved_query[:30]}...",
                capability_id="realtime_search",
                function=search_task,
                args=(resolved_query,),
                priority=ExecTaskPriority.HIGH,
                can_run_concurrent=True
            )
            tasks.append(task)
        
        elif decision_type == "general":
            async def chat_task(query):
                return await chatbot_circuit(async_chatbot.query)(query)
            
            task = task_executor.create_task(
                name=f"Chat: {resolved_query[:30]}...",
                capability_id="chat",
                function=chat_task,
                args=(resolved_query,),
                priority=ExecTaskPriority.MEDIUM,
                can_run_concurrent=True
            )
            tasks.append(task)
        
        elif decision_type in ["open", "close", "play", "google", "youtube", "whatsapp", "email", "system"]:
            async def automation_task(cmd):
                return await async_automation.execute([cmd])
            
            task = task_executor.create_task(
                name=f"{decision_type.title()}: {resolved_query[:30]}...",
                capability_id=decision_type,
                function=automation_task,
                args=(decision,),
                priority=ExecTaskPriority.MEDIUM,
                can_run_concurrent=True
            )
            tasks.append(task)
    
    if tasks:
        results = await task_executor.execute_tasks(tasks, show_progress=True)
        
        response_parts = []
        for result in results:
            if result.status.value == "completed":
                if result.result:
                    response_parts.append(f" {result.name}: {str(result.result)[:100]}")
                else:
                    response_parts.append(f" {result.name}: Completed")
            else:
                response_parts.append(f" {result.name}: {result.error or 'Failed'}")
        
        capability_ids = [t.capability_id for t in tasks]
        capability_registry.log_capability_combination(capability_ids, success=True)
        
        return "\n".join(response_parts)
    
    return "No tasks to execute"


async def process_user_command(user_input: str) -> str:
    """Process user command with agentic capabilities"""
    
    username = config.get("system.username", "User")
    
    is_valid, error_msg = input_validator.validate_command(user_input)
    if not is_valid:
        logger.warning(f"Invalid input: {error_msg}")
        audit_logger.log_security_event("INVALID_INPUT", error_msg)
        return f" Invalid input: {error_msg}"
    
    if not rate_limiter.is_allowed():
        wait_time = rate_limiter.get_wait_time()
        logger.warning("Rate limit exceeded")
        return f" Rate limit exceeded. Please wait {wait_time:.0f} seconds."
    
    audit_logger.log_command(username, user_input[:100])
    
    save_message("user", user_input)
    
  
    if chain_parser and is_chain_command(user_input):
        logger.info("Detected command chain, using chain executor")
        
        conv_turns = []
        try:
            if hasattr(conversation_context, 'get_recent_turns'):
                conv_turns = conversation_context.get_recent_turns(5)
        except:
            pass
        
        with timer(f"Chain Execution: {user_input[:30]}...", logger):
            success, response = await chain_executor.execute_chain(user_input, conv_turns)
        
        save_message("assistant", response)
        conversation_context.add_turn(user_input, response)
        return response
    
    user_lower = user_input.lower()
    if user_lower.startswith('reason:') or user_lower.startswith('think:'):
        goal = user_input.split(':', 1)[1].strip()
        logger.info(f"Explicit reasoning request: {goal[:50]}...")
        
        response = await execute_with_reasoning(goal)
        save_message("assistant", response)
        conversation_context.add_turn(user_input, response)
        return response
    
    if agentic_core.mode == AgentMode.AUTONOMOUS and user_lower.startswith('goal:'):
        goal = user_input.split(':', 1)[1].strip()
        logger.info(f"Autonomous reasoning goal: {goal[:50]}...")
        
        response = await execute_with_reasoning(goal)
        save_message("assistant", response)
        conversation_context.add_turn(user_input, response)
        return response
    
    handled, result = await command_registry.process(user_input)
    if handled:
        save_message("assistant", result)
        conversation_context.add_turn(user_input, result)
        return result
    
    if user_input.lower() == 'clear':
        clear_chat_history()
        return " Chat history cleared"
    
    if user_input.lower() == 'logs':
        logs = get_automation_logs(15)
        if logs:
            response = "\n Recent Automation Logs:\n" + "=" * 80 + "\n"
            for action_type, details, status, metadata, created_at in logs:
                status_emoji = "✅" if status == "success" else "❌"
                response += f"{status_emoji} [{action_type}] {details}\n"
                response += f"   {created_at}\n"
            return response
        return "No logs found"
    
    if user_input.lower() == 'refresh system':
        system_awareness.refresh_all(deep_scan=False)
        return f" System refreshed (quick scan): {len(system_awareness.installed_apps)} apps, {sum(len(v) for v in system_awareness.common_paths.values())} files tracked"
    
    if user_input.lower() in ['refresh system deep', 'deep scan']:
        logger.info("Starting deep C: drive scan - this may take several minutes")
        system_awareness.refresh_all(deep_scan=True)
        total_files = sum(len(v) for v in system_awareness.common_paths.values())
        return f" Deep scan complete: {len(system_awareness.installed_apps)} apps, {total_files} files indexed across C: drive"
    
    with timer(f"Intent Routing: {user_input[:30]}...", logger):
        decisions = intent_router.route(user_input)
    
    if not decisions:
        response = "I couldn't process your request."
        save_message("assistant", response)
        conversation_context.add_turn(user_input, response)
        return response
    
    if len(decisions) > 1:
        logger.info(f"Detected {len(decisions)} tasks - executing concurrently...")
        response = await execute_multi_intent(decisions, user_input)
        save_message("assistant", response)
        conversation_context.add_turn(user_input, response, 
                                     capabilities_used=[d.split()[0] for d in decisions])
        return response
    
    decision = decisions[0]
    
    if decision == "exit":
        return "EXIT_COMMAND"
    
    parts = decision.split(maxsplit=1)
    decision_type = parts[0]
    resolved_query = parts[1] if len(parts) > 1 else user_input
    
    if decision_type == "clarify":
        response = f" {resolved_query}"
        save_message("assistant", response)
        conversation_context.add_turn(user_input, response)
        return response
    
    if decision_type == "confirm":
        if "|" in resolved_query:
            command_part, desc_part = resolved_query.split("|", 1)
            logger.info(f"Auto-confirming: {desc_part}")
            
            decision = command_part.strip()
            
            parts = decision.split(maxsplit=1)
            decision_type = parts[0]
            resolved_query = parts[1] if len(parts) > 1 else user_input
            
            decisions = [decision]
            
        else:
            logger.info(f"Auto-confirming: {resolved_query}")
    
    
    try:
        if decision_type == "generate" and "image" in resolved_query:
            image_prompt = resolved_query.replace("image", "", 1).strip()
            
            async def background_image_task(prompt):
                """Runs in background, doesn't block the main loop"""
                import time
                start_time = time.time()
                
                try:
                    print(f"\n🖼️ Starting background image generation: {prompt[:40]}...")
                    
                    image, seed, enhanced_prompt = await async_image_gen.generate(prompt)
                    image_id = await async_image_gen.save_to_db(image, prompt, enhanced_prompt, seed)
                    await async_image_gen.save_to_file(image, prompt, seed)
                    
                    elapsed = time.time() - start_time
                    
                    try:
                        image.show()
                    except:
                        pass
                    
                    print(f"\n✅ 🎨 IMAGE READY! Generated in {elapsed:.1f}s")
                    print(f"   Prompt: {prompt[:50]}{'...' if len(prompt) > 50 else ''}")
                    print(f"   ID: {image_id}, Seed: {seed}")
                    print(f"   The image has been opened for viewing.")
                    print(f"\n>>> Continue typing your next command...\n")
                    
                    pattern_analyzer.record_action("generate_image", {"prompt": prompt})
                    
                    conversation_context.add_turn(
                        f"[SYSTEM] Image generation completed for '{prompt[:30]}...'",
                        f"Image successfully generated (ID: {image_id}, Seed: {seed}). The image has been opened for viewing.",
                        intent="generate_image"
                    )
                    
                except Exception as e:
                    print(f"\n❌ Image generation failed: {e}")
                    print(f"\n>>> Continue typing your next command...\n")
                    
                    conversation_context.add_turn(
                        f"[SYSTEM] Image generation failed for '{prompt[:30]}...'",
                        f"Image generation failed: {str(e)}",
                        intent="generate_image"
                    )
            
            asyncio.create_task(background_image_task(image_prompt))
            
            response = f"🎨 Image is generating in background: '{image_prompt}'\n   You can continue chatting. I'll notify you when it's ready!"
        
        elif decision_type == "general":
            with timer(f"ChatBot: {resolved_query[:30]}...", logger):
                response = await chatbot_circuit(async_chatbot.query)(resolved_query)
        
        elif decision_type == "realtime":
            with timer(f"RealTime Search: {resolved_query[:30]}...", logger):
                response = await search_circuit(async_search.search)(resolved_query)
        
        elif any(decision.startswith(cmd) for cmd in [
            "open", "open file", "close", "play", "system",
            "google search", "youtube search", "youtube_search", "whatsapp", "email",
            "refresh_apps", "focus_mode", "search_and_email", "search_youtube_and_share",
            "search images", "search_and_share", "send_file_whatsapp", "read_document",
            "recall_action"
        ]):
            with timer(f"Automation: {decision[:30]}...", logger):
                await async_automation.execute(decisions)
            response = "✅ Task completed"
            pattern_analyzer.record_action(decision_type, {"query": resolved_query})

        
        else:
            response = await chatbot_circuit(async_chatbot.query)(user_input)
        
        save_message("assistant", response)
        conversation_context.add_turn(user_input, response)
        return response
        
    except Exception as e:
        logger.error(f"Error processing command: {e}", exc_info=True)
        return f"❌ Error: {str(e)}"


async def autonomous_background_loop():
    """Background loop for autonomous behaviors"""
    last_suggestion_check = time.time()
    suggestion_interval = config.get("agentic.suggestion_interval_seconds", 600)
    loop_interval = config.get("agentic.autonomous_loop_interval", 30)
    
    while True:
        try:
            config.reload_if_changed()
            
            if agentic_core.mode == AgentMode.AUTONOMOUS:
                if agentic_core.task_queue:
                    await execute_autonomous_task(None)
            
            if agentic_core.mode in [AgentMode.PROACTIVE, AgentMode.SUPERVISED]:
                if time.time() - last_suggestion_check > suggestion_interval:
                    await check_proactive_suggestions()
                    last_suggestion_check = time.time()
            
            await asyncio.sleep(loop_interval)
            
        except Exception as e:
            logger.error(f"Background loop error: {e}", exc_info=True)
            await asyncio.sleep(60)


def show_commands():
    """Display available commands"""
    commands = """
=== AGENTIC AI COMMANDS ===

Goal Management:
  create goal: <description> - Create multi-step goal with AI planning
  show goals                 - View active goals and progress
  continue goals             - Execute next tasks in goal queue

Agent Modes:
  set mode autonomous   - Agent acts independently
  set mode proactive    - Agent suggests actions
  set mode supervised   - Agent asks before critical actions
  set mode reactive     - Traditional command-response only

Command Chaining (NEW):
  Chain multiple commands naturally! Examples:
  
  • "Create a Python file with fibonacci code and send it to myself on WhatsApp"
  • "Search for AI trends and create a Word document on this"
  • "Generate an image of a sunset and send it to John"
  • "Create a Word document on this conversation"
  
  Chaining works with:
  - File creation (Python, Word, PDF, Text)
  - WhatsApp messaging with attachments
  - Email with attachments
  - Web search + documentation
  - Image generation + sharing
  
  Tip: Use "and", "then", or "on this" to chain commands!

ReAct Reasoning (NEW):
  For complex tasks that need step-by-step thinking!

  reason: <goal>        - Think step-by-step to achieve a goal
  think: <goal>         - Same as reason:
  goal: <objective>     - (In autonomous mode) Execute with reasoning
  
  Examples:
  • "reason: Find the latest SpaceX news and summarize the key points"
  • "think: Research Python web frameworks and recommend the best one"
  
  The AI will Think → Act → Observe → Repeat until complete!

System Commands:
  help                  - Show this help
  clear                 - Clear chat history
  logs                  - View automation logs
  refresh system        - Quick refresh of installed apps and common folders
  deep scan             - Full C: drive scan (slower, more comprehensive)
  exit/quit             - Exit program

For full capabilities, ask: "What can you do?"
"""
    print(commands)


async def main():
    """Main program loop with agentic capabilities"""
    try:
        import aioconsole
    except ImportError:
        logger.error("aioconsole not installed. Run: pip install aioconsole")
        print("❌ Required package 'aioconsole' not found. Install with: pip install aioconsole")
        return
    
    initialize_systems()
    
    username = config.get("system.username", "User")
    assistant_name = config.get("system.assistant_name", "Synorpse")
    
    background_task = asyncio.create_task(autonomous_background_loop())
    
    try:
        while True:
            try:
                user_input = await aioconsole.ainput(f"\n{username}: ")
                user_input = user_input.strip()
            except EOFError:
                break
            
            if not user_input:
                continue
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print(f"\n{assistant_name}: Goodbye!")
                background_task.cancel()
                break
            
            if user_input.lower() in ['help', 'agentic help', 'agentic commands']:
                show_commands()
                continue
            
            print(f"\n{assistant_name}: ", end="", flush=True)
            
            with timer(f"Total Request Processing", logger):
                response = await process_user_command(user_input)
            
            if response == "EXIT_COMMAND":
                background_task.cancel()
                break
            
            if response:
                print(response)
    
    except KeyboardInterrupt:
        print(f"\n\n{assistant_name}: Goodbye!")
        background_task.cancel()
    
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        print(f"\n❌ Fatal Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())

