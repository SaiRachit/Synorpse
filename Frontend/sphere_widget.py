import sys
import ctypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

import os
import asyncio
import threading
import logging
import time
import json as _json
from pathlib import Path
import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── DPI & GPU Acceleration Settings (MUST be set before any Qt imports) ──
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ.pop("QT_AUTO_SCREEN_SCALE_FACTOR", None)
os.environ["QT_SCALE_FACTOR_ROUNDING_POLICY"] = "PassThrough"

# Force Chromium (inside QWebEngineView) to use the dedicated GPU (RTX 4060)
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join([
    "--enable-gpu-rasterization",
    "--enable-zero-copy",
    "--enable-native-gpu-memory-buffers",
    "--enable-accelerated-2d-canvas",
    "--enable-gpu-compositing",
    "--ignore-gpu-blocklist",
])

from PyQt6.QtCore import (
    Qt, QUrl, QObject, pyqtSlot, pyqtSignal, QSize
)
from PyQt6.QtGui import QRegion, QColor
from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineSettings, QWebEnginePage
from PyQt6.QtWebChannel import QWebChannel

# ------------------------------------------------------------------
# Suppress ALL logging — user wants zero noise
# ------------------------------------------------------------------
logging.disable(logging.CRITICAL)  # Kill every log level globally
logging.basicConfig(level=logging.CRITICAL)
for noisy in [
    "mainagentic", "handler.", "urllib3", "groq", "httpx",
    "httpcore", "asyncio", "PIL", "selenium", "werkzeug",
    "requests", "filelock", "charset_normalizer", "h11",
    "root", "", "automation", "Automation",
]:
    lg = logging.getLogger(noisy)
    lg.setLevel(logging.CRITICAL)
    lg.propagate = False
    lg.handlers = []

import builtins
_real_print = builtins.print  # Keep a ref to the real print

def _silent_print(*a, **kw):
    pass  # Silence all backend prints

# ------------------------------------------------------------------
# Path setup — make BackEnd importable
# ------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_PATH = PROJECT_ROOT / "BackEnd"
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(BACKEND_PATH))

# Also set working directory so .env and Data/ paths resolve
os.chdir(str(PROJECT_ROOT))

# ------------------------------------------------------------------
# Import all backend modules (mirrors mainagentic.py imports)
# ------------------------------------------------------------------
BACKEND_AVAILABLE = False

# Core
config = None
intent_router = None
command_registry = None

# Async wrappers
async_chatbot = None
async_search = None
async_image_gen = None
async_automation = None

# Agentic systems
agentic_core = None
suggestion_engine = None
pattern_analyzer = None
capability_registry = None
task_executor = None
conversation_context = None
background_manager = None
notification_system = None

# Security
input_validator = None
rate_limiter = None
audit_logger = None

# Persistence & awareness
state_persistence = None
goal_persistence = None
system_awareness = None
file_creator = None

# Chain & Reasoning
chain_executor = None
chain_handlers = None
chain_parser = None
reasoning_handlers = None

# Circuit breakers
chatbot_circuit = None
search_circuit = None

# Screen context cache for follow-up questions
import time as _time
_last_screen_context = {"data": None, "query": None, "timestamp": 0}

CHAT_TIMEOUT_SECONDS = 75
REASONING_TIMEOUT_SECONDS = 120
SCREEN_TIMEOUT_SECONDS = 45
PROCESS_TIMEOUT_SECONDS = 150

try:
    from ConfigManager import get_config
    from LoggingConfig import setup_logging, get_logger, get_performance_logger, timer
    from Security import get_input_validator, get_rate_limiter, get_audit_logger
    from StatePersistence import get_state_persistence, get_goal_persistence
    from SystemAwareness import get_system_awareness
    from FileCreator import get_file_creator
    from ScreenReader import analyze_screen
    from AsyncWrappers import (
        get_async_chatbot, get_async_search, get_async_image_generator,
        get_async_automation, CircuitBreaker
    )
    from CommandHandlers import initialize_command_handlers, get_command_registry
    from AgenticCore import get_agentic_core, AgentMode, TaskPriority, TaskStatus
    from ProactiveBehaviors import get_suggestion_engine, PatternAnalyzer
    from IntentRouter import get_intent_router_fixed
    from ChatBot import init_db as init_chatbot_db, save_message, clear_chat_history
    from RealTimeSearchEngine import init_search_db, get_reasoning_trace, format_trace_for_user
    from Automation import init_automation_db, get_automation_logs
    from CapabilityRegistry import get_capability_registry
    from TaskExecutor import get_task_executor, ExecutableTask, TaskPriority as ExecTaskPriority
    from ConversationContext import get_conversation_context
    from BackgroundTaskManager import get_background_task_manager
    from NotificationSystem import get_notification_system
    from CommandChain import get_command_chain_executor, is_chain_command, CommandChainParser
    from ChainHandlers import get_chain_handlers
    from ReasoningHandlers import get_reasoning_handlers
    from MetaQuery import is_agent_meta_query

    BACKEND_AVAILABLE = True
except Exception as e:
    print(f"⚠️ Backend import failed: {e}")


def initialize_systems():
    """Initialize all agentic systems — mirrors mainagentic.initialize_systems()"""
    global config, intent_router, command_registry
    global async_chatbot, async_search, async_image_gen, async_automation
    global agentic_core, suggestion_engine, pattern_analyzer
    global capability_registry, task_executor, conversation_context
    global background_manager, notification_system
    global input_validator, rate_limiter, audit_logger
    global state_persistence, goal_persistence, system_awareness, file_creator
    global chain_executor, chain_handlers, chain_parser
    global reasoning_engine, reasoning_handlers
    global chatbot_circuit, search_circuit

    if not BACKEND_AVAILABLE:
        return False

    try:
        config = get_config()

        # Logging — minimal, suppress noise
        setup_logging(config)
        logger = get_logger("sphere_widget")
        logger.setLevel(logging.WARNING)

        # Security
        input_validator = get_input_validator()
        rate_limiter = get_rate_limiter()
        audit_logger = get_audit_logger()
        state_persistence = get_state_persistence()
        goal_persistence = get_goal_persistence()
        system_awareness = get_system_awareness()

        # Databases
        init_chatbot_db()
        init_automation_db()
        init_search_db()

        # Async wrappers
        async_chatbot = get_async_chatbot()
        async_search = get_async_search()
        async_image_gen = get_async_image_generator()
        async_automation = get_async_automation()

        # Circuit breakers
        chatbot_circuit = CircuitBreaker(failure_threshold=5, timeout=60)
        search_circuit = CircuitBreaker(failure_threshold=5, timeout=60)

        # File creator
        file_creator = get_file_creator(
            chatbot_func=async_chatbot.query,
            search_func=async_search.search
        )

        # Agentic modules
        capability_registry = get_capability_registry()
        task_executor = get_task_executor()
        conversation_context = get_conversation_context()
        background_manager = get_background_task_manager()
        notification_system = get_notification_system()

        agentic_core = get_agentic_core()
        suggestion_engine = get_suggestion_engine()
        pattern_analyzer = PatternAnalyzer()
        intent_router = get_intent_router_fixed()

        # Command registry
        command_registry = initialize_command_handlers(
            agentic_core, capability_registry, task_executor,
            conversation_context, background_manager, notification_system, file_creator
        )

        # Chain system
        from Automation import PHONEBOOK
        chain_handlers = get_chain_handlers(
            file_creator, None, async_chatbot, async_search,
            async_image_gen, conversation_context, PHONEBOOK
        )
        chain_executor = get_command_chain_executor(chain_handlers.get_handlers_dict())
        chain_parser = CommandChainParser()

        # Reasoning engine
        from DocumentReader import DocumentReader as DocReader
        doc_reader = DocReader()
        reasoning_handlers = get_reasoning_handlers(
            async_search, async_chatbot, async_image_gen,
            async_automation, file_creator, analyze_screen,
            document_reader=doc_reader, conversation_context=conversation_context,
            phonebook=PHONEBOOK
        )

        # Set autonomous mode by default for critical thinking
        if agentic_core:
            agentic_core.mode = AgentMode.AUTONOMOUS

        # After init is done, silence all print() calls from backend
        builtins.print = _silent_print

        return True

    except Exception as e:
        _real_print(f"⚠️ System initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False


# ------------------------------------------------------------------
# Async event loop running in a background thread
# ------------------------------------------------------------------
_async_loop = None
_async_thread = None


def _start_async_loop():
    """Start a dedicated asyncio event loop in a background thread."""
    global _async_loop, _async_thread

    _async_loop = asyncio.new_event_loop()

    def run():
        asyncio.set_event_loop(_async_loop)
        _async_loop.run_forever()

    _async_thread = threading.Thread(target=run, daemon=True)
    _async_thread.start()


def run_async(coro):
    """Submit a coroutine to the background async loop and return a Future."""
    if _async_loop is None:
        _start_async_loop()
    return asyncio.run_coroutine_threadsafe(coro, _async_loop)


# ------------------------------------------------------------------
# The full process_user_command — mirrors mainagentic.py exactly
# ------------------------------------------------------------------

# Maps intent types → sphere animation states
INTENT_STATE_MAP = {
    'general': 'processing',
    'realtime': 'searching',
    'google search': 'searching',
    'youtube search': 'searching',
    'youtube_search': 'searching',
    'generate': 'generating',
    'open': 'automation',
    'open file': 'automation',
    'close': 'automation',
    'play': 'automation',
    'system': 'automation',
    'refresh_apps': 'automation',
    'focus_mode': 'automation',
    'whatsapp': 'messaging',
    'email': 'messaging',
    'search_and_email': 'messaging',
    'search_and_share': 'messaging',
    'send_file_whatsapp': 'messaging',
    'search_youtube_and_share': 'messaging',
    'create_file': 'file_creation',
    'read_screen': 'analyzing',
    'read_screen_and_share': 'analyzing',
    'read_screen_and_document': 'analyzing',
    'read_screen_and_search': 'analyzing',
    'search images': 'searching',
    'reasoning': 'processing',
}


# ------------------------------------------------------------------
# Critical-thinking heuristic: detect queries needing reasoning
# ------------------------------------------------------------------
import re as _re_module

_CRITICAL_THINKING_PATTERNS = [
    # Trick questions & perspective puzzles
    _re_module.compile(r'\bif\s+(?:i|you|he|she|we|they)\s+(?:have|had|has)\b.*\b(?:take|give|remove|add|lose|eat)\b', _re_module.I),
    # Riddles & puzzles
    _re_module.compile(r'\b(?:riddle|puzzle|brainteaser|brain\s*teaser|trick\s*question)\b', _re_module.I),
    _re_module.compile(r'\b(?:what\s+has|what\s+am\s+i|what\s+gets|what\s+can)\b.*\bbut\b', _re_module.I),
    # Solve anything (broadened)
    _re_module.compile(r'\b(?:solve|figure\s+out|work\s+out)\b.*\b(?:this|the|my|it|that|riddle|puzzle|problem|equation|question)\b', _re_module.I),
    # Logic & sequences
    _re_module.compile(r'\b(?:what\s+comes\s+next|next\s+in\s+(?:the\s+)?(?:sequence|series|pattern))\b', _re_module.I),
    _re_module.compile(r'\b(?:how\s+many|how\s+much)\b.*\b(?:if|when|after|before)\b', _re_module.I),
    # Critical analysis
    _re_module.compile(r'\b(?:what.?s\s+wrong\s+with|find\s+the\s+(?:error|flaw|mistake)|analyze\s+(?:this|critically))\b', _re_module.I),
    _re_module.compile(r'\b(?:think\s+(?:about|through|deeply))\b', _re_module.I),
    # Counterfactual / hypothetical
    _re_module.compile(r'\b(?:what\s+(?:would|could|should)\s+happen\s+if)\b', _re_module.I),
    # Screen-based reasoning (GeoGuesser, wordle, etc.)
    _re_module.compile(r'\b(?:solve|figure\s+out|identify|find|guess|help|check)\b.*\b(?:screen|see|looking\s+at|display|view)\b', _re_module.I),
    _re_module.compile(r'\b(?:where\s+is\s+this|what\s+(?:place|location|country|city)\s+is\s+this)\b', _re_module.I),
    _re_module.compile(r'\b(?:riddle|puzzle|brainteaser|question)\b.*\b(?:screen|display|here)\b', _re_module.I),
]

def _needs_critical_thinking(query: str) -> bool:
    """Detect if a query needs the autonomous reasoning loop."""
    return any(p.search(query) for p in _CRITICAL_THINKING_PATTERNS)


async def _await_with_timeout(coro, seconds: int, label: str):
    """Prevent model/network stalls from leaving the UI in a thinking state."""
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        return (
            f"I got stuck waiting on {label}. Please try again with a smaller request, "
            "or ask me to continue from the last screen/context."
        )


def _recent_screen_context(max_age_seconds: int = 300) -> str:
    """Return cached screen analysis if it is still fresh."""
    if not _last_screen_context["data"]:
        return ""
    if _time.time() - _last_screen_context["timestamp"] > max_age_seconds:
        return ""
    return str(_last_screen_context["data"])


def _is_screen_followup_request(query: str) -> bool:
    """Detect follow-ups that refer to the previously analyzed screen."""
    if not _recent_screen_context():
        return False
    q = query.lower().strip()
    followup_terms = [
        "this", "that", "it", "the code", "code", "solution", "solve",
        "implement", "write", "give me", "fix", "explain", "continue"
    ]
    return any(term in q for term in followup_terms)


async def execute_with_reasoning(goal, context=None, on_thought=None):
    """Execute using the unified ReAct loop directly."""
    try:
        reasoning_context = context or ""
        if conversation_context:
            try:
                recent_context = conversation_context.get_context_for_ai(include_turns=5)
                if recent_context:
                    reasoning_context = f"{reasoning_context}\n\nSESSION CONTEXT:\n{recent_context}".strip()
            except Exception:
                pass

        from RealTimeSearchEngine import run_reasoning_loop
        result = await _await_with_timeout(
            run_reasoning_loop(
                goal,
                on_thought=on_thought,
                context=reasoning_context
            ),
            REASONING_TIMEOUT_SECONDS,
            "the reasoning engine"
        )

        if isinstance(result, str):
            return result

        # run_reasoning_loop now returns a dict; simple search returns a string
        if isinstance(result, dict):
            answer = result.get("answer") or "I finished the reasoning loop but did not produce an answer."
            return answer
        return str(result)
    except Exception as e:
        return f"❌ Error during reasoning: {str(e)}"


# ------------------------------------------------------------------
# Trace retrieval — "how did you get that answer?"
# ------------------------------------------------------------------
import re as _re_trace

_TRACE_REQUEST_PATTERNS = [
    _re_trace.compile(r'\b(?:how\s+did\s+you\s+(?:get|arrive|come\s+up|reach|figure|find|know|work))', _re_trace.I),
    _re_trace.compile(r'\b(?:show|tell|explain|give)\s+(?:me\s+)?(?:your|the)?\s*(?:thinking|thought|reasoning|process|trace|steps)', _re_trace.I),
    _re_trace.compile(r'\b(?:what\s+was\s+your\s+(?:thought|thinking|reasoning)\s*(?:process)?)', _re_trace.I),
    _re_trace.compile(r'\b(?:walk\s+me\s+through|break\s+(?:it\s+)?down)', _re_trace.I),
]

def _is_asking_for_trace(query: str) -> bool:
    """Detect if user is asking about the thinking process behind an answer."""
    return any(p.search(query) for p in _TRACE_REQUEST_PATTERNS)


async def execute_multi_intent(decisions, original_query):
    """Execute multiple intents concurrently using TaskExecutor."""
    tasks = []

    for decision in decisions:
        parts = decision.split(maxsplit=1)
        decision_type = parts[0]
        resolved_query = parts[1] if len(parts) > 1 else original_query

        if decision_type == "generate" and "image" in resolved_query:
            image_prompt = resolved_query.replace("image", "", 1).strip()
            try:
                image, seed, enhanced_prompt = await async_image_gen.generate(image_prompt)
                image_id = await async_image_gen.save_to_db(image, image_prompt, enhanced_prompt, seed)
                await async_image_gen.save_to_file(image, image_prompt, seed)
                try:
                    image.show()
                except:
                    pass
                return f"🎨 Image generated! Prompt: '{image_prompt}' (ID: {image_id}, Seed: {seed}). The image has been opened."
            except Exception as e:
                return f"❌ Image generation failed: {e}"

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
        results = await task_executor.execute_tasks(tasks, show_progress=False)
        response_parts = []
        for result in results:
            if result.status.value == "completed":
                if result.result:
                    response_parts.append(str(result.result))
                else:
                    response_parts.append(f"✅ {result.name}: Completed")
            else:
                response_parts.append(f"❌ {result.name}: {result.error or 'Failed'}")
        return "\n".join(response_parts)

    return "No tasks to execute"


async def process_user_command(user_input, state_callback=None, thinking_callback=None, visibility_callback=None):
    """
    Full command processing pipeline — mirrors mainagentic.process_user_command().
    
    Args:
        user_input: The user's message text
        state_callback: callable(state_str) to update sphere animation
        thinking_callback: callable(thought_str) for reasoning thoughts
    
    Returns:
        Response string
    """
    username = config.get("system.username", "User") if config else "User"

    # --- Input validation ---
    if input_validator:
        is_valid, error_msg = input_validator.validate_command(user_input)
        if not is_valid:
            return f"⚠️ Invalid input: {error_msg}"

    if rate_limiter and not rate_limiter.is_allowed():
        wait_time = rate_limiter.get_wait_time()
        return f"⏳ Rate limit exceeded. Please wait {wait_time:.0f} seconds."

    if audit_logger:
        audit_logger.log_command(username, user_input[:100])

    save_message("user", user_input)

    # Meta/workflow questions should explain planning, not trigger tools that
    # happen to be mentioned inside the question.
    if is_agent_meta_query(user_input):
        try:
            from SemanticNLU import get_semantic_nlu
            get_semantic_nlu().clear_pending_action()
        except Exception:
            pass
        if state_callback:
            state_callback('processing')
        response = await execute_with_reasoning(user_input, on_thought=thinking_callback)
        save_message("assistant", response)
        if conversation_context:
            conversation_context.add_turn(user_input, response)
        return response

    # --- 1. Command chains ("create file and send on whatsapp") ---
    if chain_parser and is_chain_command(user_input):
        if state_callback:
            state_callback('processing')

        conv_turns = []
        try:
            if hasattr(conversation_context, 'get_recent_turns'):
                conv_turns = conversation_context.get_recent_turns(5)
        except:
            pass

        success, response = await chain_executor.execute_chain(user_input, conv_turns)
        save_message("assistant", response)
        if conversation_context:
            conversation_context.add_turn(user_input, response)
        return response

    # --- 2. Explicit reasoning ("reason:" or "think:") ---
    user_lower = user_input.lower()
    if user_lower.startswith('reason:') or user_lower.startswith('think:'):
        goal = user_input.split(':', 1)[1].strip()
        if state_callback:
            state_callback('processing')

        def on_thought(thought):
            if thinking_callback:
                thinking_callback(thought)

        response = await execute_with_reasoning(goal, on_thought=on_thought)
        save_message("assistant", response)
        if conversation_context:
            conversation_context.add_turn(user_input, response)
        return response

    # --- 3. Autonomous goal ---
    if agentic_core and agentic_core.mode == AgentMode.AUTONOMOUS and user_lower.startswith('goal:'):
        goal = user_input.split(':', 1)[1].strip()
        if state_callback:
            state_callback('processing')
        response = await execute_with_reasoning(goal)
        save_message("assistant", response)
        if conversation_context:
            conversation_context.add_turn(user_input, response)
        return response

    # --- 4. Command registry (goals, mode, tasks, etc) ---
    if command_registry:
        handled, result = await command_registry.process(user_input)
        if handled:
            save_message("assistant", result)
            if conversation_context:
                conversation_context.add_turn(user_input, result)
            return result

    # --- 5. Built-in commands ---
    if user_input.lower() == 'clear':
        clear_chat_history()
        return "✅ Chat history cleared"

    if user_input.lower() in [
        'show reasoning', 'last reasoning', 'reasoning trace',
        'how did you reason', 'show trace'
    ]:
        return format_trace_for_user(get_reasoning_trace())

    if user_input.lower() == 'logs':
        logs = get_automation_logs(15)
        if logs:
            response = "📋 Recent Automation Logs:\n"
            for action_type, details, status, metadata, created_at in logs:
                emoji = "✅" if status == "success" else "❌"
                response += f"{emoji} [{action_type}] {details}\n"
            return response
        return "No logs found"

    if user_input.lower() == 'refresh system':
        system_awareness.refresh_all(deep_scan=False)
        return f"✅ System refreshed: {len(system_awareness.installed_apps)} apps tracked"

    if user_input.lower() in ['refresh system deep', 'deep scan']:
        system_awareness.refresh_all(deep_scan=True)
        total_files = sum(len(v) for v in system_awareness.common_paths.values())
        return f"✅ Deep scan complete: {len(system_awareness.installed_apps)} apps, {total_files} files indexed"

    # --- 5.5 Trace retrieval: "how did you get that answer?" ---
    if _is_asking_for_trace(user_input):
        try:
            trace_data = get_reasoning_trace()  # Gets most recent
            response = format_trace_for_user(trace_data)
            save_message("assistant", response)
            if conversation_context:
                conversation_context.add_turn(user_input, response)
            return response
        except Exception:
            pass  # Fall through to normal processing

    # --- 5.55 Follow-up to the last screen analysis ---
    # Example: user first asks "look at my screen", then "give me the code".
    if _is_screen_followup_request(user_input):
        if state_callback:
            state_callback('processing')

        screen_ctx = _recent_screen_context()
        context = (
            "RECENT SCREEN ANALYSIS:\n"
            f"{screen_ctx[:3000]}\n\n"
            "Use this as the visual context for the user's follow-up. "
            "Answer only the follow-up request; do not repeat unrelated screen details."
        )

        response = await execute_with_reasoning(user_input, context=context, on_thought=thinking_callback)
        save_message("assistant", response)
        if conversation_context:
            conversation_context.add_turn(user_input, response)
        return response

    # --- 5.6 Auto-route critical thinking queries through reasoning ---
    is_critical = _needs_critical_thinking(user_input)
    
    # Fallback/Manual detection for screen reasoning
    user_lower = user_input.lower()
    if not is_critical:
        if any(kw in user_lower for kw in ["riddle", "puzzle", "brainteaser", "solve this"]) and \
           any(kw in user_lower for kw in ["screen", "display", "see", "here"]):
            is_critical = True

    # Persistent debug logging
    try:
        with open("routing_debug.log", "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.datetime.now()}] Query: '{user_input}'\n")
            f.write(f"Is Critical: {is_critical}\n")
    except:
        pass

    if is_critical:
        if state_callback:
            state_callback('processing')

        def on_thought(thought):
            if thinking_callback:
                thinking_callback(thought)

        # Front-load screen analysis if the query is screen-related
        context = ""
        if any(w in user_lower for w in ["screen", "see", "display", "looking at", "show", "here", "this"]):
            if thinking_callback:
                thinking_callback(" Analyzing your screen first...")
            try:
                screen_data = await _await_with_timeout(
                    analyze_screen(user_input),
                    SCREEN_TIMEOUT_SECONDS,
                    "screen analysis"
                )
                if screen_data:
                    context = f"INITIAL SCREEN ANALYSIS:\n{screen_data}\n\nUse this data to solve the user's request."
                    # Cache for follow-up questions
                    _last_screen_context["data"] = screen_data
                    _last_screen_context["query"] = user_input
                    _last_screen_context["timestamp"] = _time.time()
                    # Log success
                    try:
                        with open("routing_debug.log", "a", encoding="utf-8") as f:
                            f.write(f"Screen data captured: {len(screen_data)} chars\n")
                    except:
                        pass
            except Exception as e:
                # Screen pre-analysis failed — the reasoning loop's visual guard
                # will still force a read_screen action as fallback
                try:
                    with open("routing_debug.log", "a", encoding="utf-8") as f:
                        f.write(f"Screen error: {e}\n")
                except:
                    pass

        response = await execute_with_reasoning(user_input, context=context, on_thought=on_thought)
        save_message("assistant", response)
        if conversation_context:
            conversation_context.add_turn(user_input, response)
        return response

    # --- 6. Intent routing ---
    decisions = await asyncio.to_thread(intent_router.route, user_input)

    if not decisions:
        response = "I couldn't process your request."
        save_message("assistant", response)
        if conversation_context:
            conversation_context.add_turn(user_input, response)
        return response

    # --- 7. Multi-intent ---
    if len(decisions) > 1:
        if state_callback:
            state_callback('processing')
        response = await execute_multi_intent(decisions, user_input)
        save_message("assistant", response)
        if conversation_context:
            conversation_context.add_turn(user_input, response,
                                         capabilities_used=[d.split()[0] for d in decisions])
        return response

    # --- 8. Single intent ---
    decision = decisions[0]

    if decision == "exit":
        return "Goodbye! 👋"

    parts = decision.split(maxsplit=1)
    decision_type = parts[0]
    resolved_query = parts[1] if len(parts) > 1 else user_input

    # Set sphere animation state
    sphere_state = INTENT_STATE_MAP.get(decision_type, 'processing')
    if state_callback:
        state_callback(sphere_state)

    # Handle clarify
    if decision_type == "clarify":
        response = f"❓ {resolved_query}"
        save_message("assistant", response)
        if conversation_context:
            conversation_context.add_turn(user_input, response)
        return response

    # Handle Agentic Chain (Autonomous Tool Chaining)
    if decision_type == "agentic_chain":
        if state_callback:
            state_callback('analyzing')
            
        try:
            chain_data = _json.loads(resolved_query)
            goal = chain_data.get('query', user_input)
            thought = chain_data.get('thought', "")
            
            if thinking_callback and thought:
                thinking_callback(thought)
                
            # Pass full conversation context for follow-up accuracy
            history = conversation_context.get_recent_context() if conversation_context else None
            response = await execute_with_reasoning(goal, context=history, on_thought=thinking_callback)
            save_message("assistant", response)
            if conversation_context:
                conversation_context.add_turn(user_input, response)
            return response
        except Exception as e:
            # Fallback to general processing if chain parsing fails
            pass

    # Handle explicit reasoning intent
    if decision_type == "reasoning":
        if state_callback:
            state_callback('processing')
            
        def on_thought(thought):
            if thinking_callback:
                thinking_callback(thought)
                
        # Use existing conversation history for context
        history = conversation_context.get_recent_context() if conversation_context else None
        response = await execute_with_reasoning(resolved_query, context=history, on_thought=on_thought)
        save_message("assistant", response)
        if conversation_context:
            conversation_context.add_turn(user_input, response)
        return response

    # Handle confirm — auto-confirm and re-parse
    if decision_type == "confirm":
        if "|" in resolved_query:
            command_part, desc_part = resolved_query.split("|", 1)
            decision = command_part.strip()
            parts = decision.split(maxsplit=1)
            decision_type = parts[0]
            resolved_query = parts[1] if len(parts) > 1 else user_input
            decisions = [decision]
            # Update sphere state for the real action
            sphere_state = INTENT_STATE_MAP.get(decision_type, 'processing')
            if state_callback:
                state_callback(sphere_state)

    try:
        # --- Image generation ---
        if decision_type == "generate" and "image" in resolved_query:
            image_prompt = resolved_query.replace("image", "", 1).strip()
            if state_callback:
                state_callback('generating')

            try:
                image, seed, enhanced_prompt = await async_image_gen.generate(image_prompt)
                image_id = await async_image_gen.save_to_db(image, image_prompt, enhanced_prompt, seed)
                await async_image_gen.save_to_file(image, image_prompt, seed)
                try:
                    image.show()
                except:
                    pass

                if pattern_analyzer:
                    pattern_analyzer.record_action("generate_image", {"prompt": image_prompt})

                if conversation_context:
                    conversation_context.add_turn(
                        user_input,
                        f"Image generated (ID: {image_id}, Seed: {seed})",
                        intent="generate_image"
                    )

                response = f"🎨 Image generated!\nPrompt: '{image_prompt}'\nID: {image_id} | Seed: {seed}\nThe image has been opened for viewing."

            except Exception as e:
                response = f"❌ Image generation failed: {e}"

        # --- General chat ---
        elif decision_type == "general":
            # Inject recent screen context for follow-up questions
            screen_ctx = _recent_screen_context()
            if screen_ctx:
                augmented_query = (
                    f"[CONTEXT: The user was just looking at their screen. "
                    f"Here is what was on screen: {screen_ctx[:2000]}]\n\n"
                    f"User's follow-up question: {resolved_query}"
                )
                response = await _await_with_timeout(
                    chatbot_circuit(async_chatbot.query)(augmented_query),
                    CHAT_TIMEOUT_SECONDS,
                    "chat response"
                )
            else:
                response = await _await_with_timeout(
                    chatbot_circuit(async_chatbot.query)(resolved_query),
                    CHAT_TIMEOUT_SECONDS,
                    "chat response"
                )

        # --- Realtime search ---
        elif decision_type == "realtime":
            response = await _await_with_timeout(
                search_circuit(async_search.search)(resolved_query),
                REASONING_TIMEOUT_SECONDS,
                "real-time search"
            )

        # --- File creation (handle both NLU and regex formats) ---
        elif decision_type == "create_file" or (decision.startswith("create ") and "file" in decision):
            if state_callback:
                state_callback('file_creation')

            # Parse NLU format: "create_file python|fibonacci code"
            if decision_type == "create_file":
                if "|" in resolved_query:
                    file_type, topic = resolved_query.split("|", 1)
                else:
                    file_type = "word"
                    topic = resolved_query
            # Parse regex format: "create python file about fibonacci code"
            else:
                create_text = decision.removeprefix("create ").strip()
                file_type = "word"
                topic = create_text
                if " file about " in create_text:
                    file_type, topic = create_text.split(" file about ", 1)
                elif " file " in create_text:
                    file_type, topic = create_text.split(" file ", 1)

            file_type = file_type.strip().lower()
            topic = topic.strip()

            from Automation import CreateFile
            success = await asyncio.to_thread(CreateFile, file_type, topic)
            if success:
                response = f"📝 Created {file_type} file about: {topic}"
            else:
                response = f"❌ Failed to create {file_type} file about: {topic}"

            if pattern_analyzer:
                pattern_analyzer.record_action("create_file", {"file_type": file_type, "topic": topic})

        # --- Automation commands ---
        elif any(decision.startswith(cmd) for cmd in [
            "open", "open file", "close", "play", "system",
            "google search", "youtube search", "youtube_search", "whatsapp", "email",
            "refresh_apps", "focus_mode", "search_and_email", "search_youtube_and_share",
            "search images", "search_and_share", "send_file_whatsapp", "read_document",
            "read_screen", "read_screen_and_share", "read_screen_and_document", 
            "read_screen_and_search", "recall_action"
        ]):
            # Capture stdout so output appears in chat, not just CLI
            import io, re as _re, contextlib
            capture = io.StringIO()
            
            # Temporarily restore real print and redirect stdout/stderr
            builtins.print = _real_print
            with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                try:
                    await async_automation.execute(decisions)
                finally:
                    builtins.print = _silent_print  # Re-silence

            captured = capture.getvalue().strip()
            # Strip ANSI color codes
            captured = _re.sub(r'\x1b\[[0-9;]*m', '', captured)
            # Strip rich markup tags like [bold], [/bold], etc.
            captured = _re.sub(r'\[/?[\w\s#]+\]', '', captured)

            # Filter out log/status noise but KEEP content (links, search items)
            log_prefixes = (
                '📝 Logged:', '⚠️ Error logging', '🔄 Resolved alias',
                'INFO -', 'DEBUG -', 'WARNING -', 'ERROR -',
                '✅ Automation logging', '✅ All agentic systems',
                '✅ Chat history cleared', 'Loaded 59 apps',
                'Step ', 'Generating ', 'Processing ', 'Thinking...',
                'Thought:', 'Observation:', 'Action:', 'Final Answer:',
                '🧠 ', '💭 ', '🔧 ', '📋 ', '✅ ', '❌ '
            )
            
            lines = captured.split('\n')
            clean_lines = []
            for line in lines:
                s = line.strip()
                if not s: continue
                # Skip known log noise
                if any(s.startswith(p) for p in log_prefixes):
                    continue
                # Skip very short lines that are likely just noise/separator artifacts after filtering
                if len(s) < 2 and not s[0].isalnum():
                    continue
                clean_lines.append(line)
            
            captured = '\n'.join(clean_lines).strip()

            # Unwrap nested JSON from ScreenReader if present
            captured_test = captured.strip()
            if captured_test.startswith('{') and captured_test.endswith('}'):
                try:
                    parsed_captured = _json.loads(captured_test)
                    if 'analysis' in parsed_captured:
                        captured = parsed_captured['analysis']
                    elif 'response' in parsed_captured:
                        captured = parsed_captured['response']
                except:
                    pass

            # Format as JSON for structured display
            json_response = _json.dumps({
                "type": decision_type,
                "query": resolved_query,
                "response": captured if captured else f"Completed your request to {decision_type.replace('_', ' ').title()}",
                "status": "success" if captured else "completed"
            })
            response = json_response

            if pattern_analyzer:
                pattern_analyzer.record_action(decision_type, {"query": resolved_query})

        # --- Fallback to chatbot ---
        else:
            # Check if recent screen analysis is available for follow-up context
            screen_ctx = _recent_screen_context()
            if screen_ctx:
                augmented_query = (
                    f"[CONTEXT: The user was just looking at their screen. "
                    f"Here is what was on screen: {screen_ctx[:2000]}]\n\n"
                    f"User's follow-up question: {user_input}"
                )
                response = await _await_with_timeout(
                    chatbot_circuit(async_chatbot.query)(augmented_query),
                    CHAT_TIMEOUT_SECONDS,
                    "chat response"
                )
            else:
                response = await _await_with_timeout(
                    chatbot_circuit(async_chatbot.query)(user_input),
                    CHAT_TIMEOUT_SECONDS,
                    "chat response"
                )

        save_message("assistant", response)
        if conversation_context:
            conversation_context.add_turn(user_input, response)
        return response

    except Exception as e:
        return f"❌ Error: {str(e)}"


# ------------------------------------------------------------------
# Bridge: Python ↔ JavaScript via QWebChannel
# ------------------------------------------------------------------
class PythonBridge(QObject):
    """
    Exposed to JavaScript as `bridge`.
    JS calls bridge.receiveMessage(text) → full pipeline → JS callback.
    JS calls bridge.clearHistory() → clears backend chat history.
    """
    responseReady = pyqtSignal(str)
    errorOccurred = pyqtSignal(str)
    stateChanged = pyqtSignal(str)
    thinkingUpdate = pyqtSignal(str)
    visibilityRequested = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

    @pyqtSlot(str)
    def receiveMessage(self, text):
        """Called from JavaScript when user sends a message."""
        threading.Thread(
            target=self._process_message,
            args=(text,),
            daemon=True
        ).start()

    @pyqtSlot()
    def clearHistory(self):
        """Called from JavaScript when user clicks the clear button."""
        try:
            if BACKEND_AVAILABLE:
                clear_chat_history()
                if conversation_context:
                    # Reset active file on history clear
                    conversation_context.set_active_file(None)
                print("✅ Chat history and file metadata cleared via sphere widget")
        except Exception as e:
            print(f"⚠️ Failed to clear history: {e}")

    @pyqtSlot()
    def uploadDocument(self):
        """Open a file dialog and upload a document for analysis."""
        window = self.parent()
        if not window: return

        file_path, _ = QFileDialog.getOpenFileName(
            window,
            "Select Document",
            "",
            "Documents (*.pdf *.docx *.txt *.py *.md);;All Files (*)"
        )

        if file_path:
            # 1. Store in context
            if conversation_context:
                conversation_context.set_active_file(file_path)
            
            # 2. Inform user (No auto-summary)
            file_name = Path(file_path).name
            self.responseReady.emit(f"📎 **{file_name}** is now active and ready for your questions.")
            
            # 3. Background pre-reading (Indexing)
            def index_file():
                try:
                    from DocumentReader import DocumentReader
                    reader = DocumentReader()
                    reader.read(file_path)
                    print(f"✅ Background indexing complete for: {file_name}")
                except Exception as e:
                    print(f"⚠️ Background indexing failed: {e}")

            threading.Thread(
                target=index_file,
                daemon=True
            ).start()

    def _process_message(self, text):
        """Process message using the full pipeline in the async loop."""
        try:
            if not BACKEND_AVAILABLE:
                self.responseReady.emit(
                    "Running in **standalone mode**. "
                    "Backend modules are not available."
                )
                return

            def state_cb(state):
                self.stateChanged.emit(state)

            def thinking_cb(thought):
                pass
            
            def visibility_cb(visible):
                self.visibilityRequested.emit(visible)

            # Submit to the async event loop
            future = run_async(
                process_user_command(text, state_callback=state_cb, thinking_callback=thinking_cb, visibility_callback=visibility_cb)
            )

            # Wait for result, but don't let backend/model stalls keep the UI spinning.
            response = future.result(timeout=PROCESS_TIMEOUT_SECONDS)

            if response:
                self.responseReady.emit(str(response))
            else:
                self.responseReady.emit("I couldn't process that request.")

        except TimeoutError:
            try:
                future.cancel()
            except Exception:
                pass
            self.errorOccurred.emit(
                "I got stuck waiting for the backend. Please try again, or ask a narrower follow-up."
            )
        except Exception as e:
            _real_print(f"❌ Error processing message: {e}")
            self.errorOccurred.emit(str(e))

    @pyqtSlot()
    def expandWindow(self):
        """Called from JS when chat panel opens — expand window to show chat."""
        window = self.parent()
        if window and hasattr(window, '_expand'):
            window._expand()

    @pyqtSlot()
    def collapseWindow(self):
        """Called from JS when chat panel closes — shrink window to sphere only."""
        window = self.parent()
        if window and hasattr(window, '_collapse'):
            window._collapse()

    @pyqtSlot()
    def quitApp(self):
        """Called from JS context menu — cleanly exit the application."""
        QApplication.instance().quit()


# ------------------------------------------------------------------
# Custom WebEngine page to suppress console noise
# ------------------------------------------------------------------
class SilentWebPage(QWebEnginePage):
    def javaScriptConsoleMessage(self, level, message, lineNumber, sourceID):
        if level == QWebEnginePage.JavaScriptConsoleMessageLevel.ErrorMessageLevel:
            print(f"[JS Error] {message} (line {lineNumber})")


# ------------------------------------------------------------------
# Main Sphere Window
# ------------------------------------------------------------------
class SphereWindow(QMainWindow):
    """Transparent, frameless, always-on-top overlay with sphere + chat."""

    EXPANDED_SIZE = QSize(420, 640)
    COLLAPSED_SIZE = QSize(96, 96)   # Fit the sphere closely so no box shows around it

    def __init__(self):
        super().__init__()
        self._drag_pos = None
        self._is_expanded = False

        self._setup_window()
        self._setup_webview()
        self._setup_bridge()
        self._position_top_right()

    def _setup_window(self):
        self.setWindowTitle("SYNORPSE")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(self.COLLAPSED_SIZE)  # Start collapsed — only the sphere

    def _setup_webview(self):
        self.webview = QWebEngineView(self)
        page = SilentWebPage(self.webview)
        self.webview.setPage(page)

        self.webview.setStyleSheet("background: transparent;")
        # Ensure the webview paints transparently and doesn't draw its own background
        try:
            self.webview.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            self.webview.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
            self.webview.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        except Exception:
            pass
        # Prefer an explicit transparent QColor (fixes differing behavior across PyQt/Qt versions)
        try:
            page.setBackgroundColor(QColor(0, 0, 0, 0))
        except Exception:
            try:
                page.setBackgroundColor(Qt.GlobalColor.transparent)
            except Exception:
                pass

        settings = self.webview.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessFileUrls, True
        )
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True
        )

        self.webview.resize(self.size())

        html_path = Path(__file__).parent / "sphere.html"
        self.webview.setUrl(QUrl.fromLocalFile(str(html_path)))

    def _setup_bridge(self):
        self._bridge = PythonBridge(self)
        self._bridge.visibilityRequested.connect(self.setVisible)
        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self._bridge)
        self.webview.page().setWebChannel(self._channel)

        self._bridge.responseReady.connect(self._send_response_to_js)
        self._bridge.errorOccurred.connect(self._send_error_to_js)
        self._bridge.stateChanged.connect(self._send_state_to_js)
        self._bridge.thinkingUpdate.connect(self._send_thinking_to_js)

    def _send_response_to_js(self, text):
        safe = _json.dumps(text)
        self.webview.page().runJavaScript(f'onAssistantResponse({safe});')

    def _send_error_to_js(self, text):
        safe = _json.dumps(text)
        self.webview.page().runJavaScript(f'onAssistantError({safe});')

    def _send_state_to_js(self, state):
        self.webview.page().runJavaScript(f'setSphereState("{state}");')

    def _send_thinking_to_js(self, thought):
        safe = _json.dumps(thought)
        self.webview.page().runJavaScript(f'onThinkingUpdate({safe});')

    def _position_top_right(self):
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.right() - self.width() - 12
            y = geo.top() + 12
            self.move(x, y)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "webview"):
            self.webview.resize(self.size())
        self._update_window_mask()

    def _update_window_mask(self):
        if self._is_expanded:
            self.clearMask()
            try:
                # Also clear any mask on the webview when expanded
                if hasattr(self, 'webview'):
                    self.webview.clearMask()
            except Exception:
                pass
            return

        # Apply an elliptical mask to the main window and the webview so
        # the QWebEngine native surface doesn't show a rectangular border.
        ellipse = QRegion(self.rect(), QRegion.RegionType.Ellipse)
        self.setMask(ellipse)
        try:
            if hasattr(self, 'webview'):
                self.webview.setMask(QRegion(self.webview.rect(), QRegion.RegionType.Ellipse))
        except Exception:
            pass

    def _expand(self):
        """Expand window to show the full chat panel."""
        if self._is_expanded:
            return
        self._is_expanded = True
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.right() - self.EXPANDED_SIZE.width() - 12
            y = geo.top() + 12
            self.move(x, y)
        self.resize(self.EXPANDED_SIZE)
        self._update_window_mask()

    def _collapse(self):
        """Collapse window to just the sphere — frees area below for other apps."""
        if not self._is_expanded:
            return
        self._is_expanded = False
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            x = geo.right() - self.COLLAPSED_SIZE.width() - 12
            y = geo.top() + 12
            self.move(x, y)
        self.resize(self.COLLAPSED_SIZE)
        self._update_window_mask()


# ------------------------------------------------------------------
# Missing functions from mainagentic.py — adapted for widget
# ------------------------------------------------------------------

async def execute_autonomous_task(task):
    """Execute a queued task from the agentic core."""
    try:
        if not task or not hasattr(task, 'description'):
            return
        _real_print(f"[Autonomous] Executing task: {task.description}")
        response = await process_user_command(task.description)
        if agentic_core:
            agentic_core.complete_task(task.id, str(response))
    except Exception as e:
        _real_print(f"[Autonomous] Task failed: {e}")
        if agentic_core:
            agentic_core.fail_task(task.id, str(e))


async def check_proactive_suggestions():
    """Check for proactive suggestions from the suggestion engine."""
    if not suggestion_engine or not pattern_analyzer:
        return
    try:
        suggestions = suggestion_engine.get_suggestions(
            pattern_analyzer.get_patterns()
        )
        if suggestions:
            _real_print(f"[Proactive] {len(suggestions)} suggestions available")
    except Exception:
        pass


async def autonomous_background_loop():
    """Persistent background loop for autonomous behaviors."""
    while True:
        try:
            await asyncio.sleep(60)  # Check every 60 seconds

            # Check for pending autonomous tasks
            if agentic_core and agentic_core.mode == AgentMode.AUTONOMOUS:
                pending = agentic_core.get_pending_tasks()
                if pending:
                    for task in pending[:1]:  # One at a time
                        await execute_autonomous_task(task)

            # Check for proactive suggestions
            await check_proactive_suggestions()

        except asyncio.CancelledError:
            break
        except Exception:
            pass


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------
def main():
    app = QApplication(sys.argv)
    app.setApplicationName("SYNORPSE")

    # Initialize the async event loop
    _start_async_loop()

    # Initialize all backend systems
    initialize_systems()

    # Start autonomous background loop in the async event loop
    if BACKEND_AVAILABLE and _async_loop:
        asyncio.run_coroutine_threadsafe(autonomous_background_loop(), _async_loop)

    window = SphereWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
