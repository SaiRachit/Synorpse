"""
SemanticNLU.py - Semantic Natural Language Understanding Module
Replaces regex-based intent detection with AI-powered slot extraction
"""
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from groq import Groq
from dotenv import dotenv_values

env_vars = dotenv_values(".env")
GROQ_API_KEY = env_vars.get("GroqAPIKey")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


# Intent definitions with required and optional slots
INTENT_SCHEMAS = {
    "open_app": {
        "description": "Open an application or website",
        "required_slots": ["app_name"],
        "optional_slots": ["new_window"],
        "examples": ["open chrome", "launch spotify", "fire up vs code", "get me into gmail"]
    },
    "close_app": {
        "description": "Close an application",
        "required_slots": ["app_name"],
        "optional_slots": [],
        "examples": ["close chrome", "shut down spotify", "kill notepad"]
    },
    "create_file": {
        "description": "Create a new file or document (Python code, Word doc, PDF, text file)",
        "required_slots": ["file_type", "topic"],
        "optional_slots": ["content", "use_conversation"],
        "examples": [
            "create a python file with fibonacci code",
            "make a word document about AI",
            "create it in a separate python file",
            "write a python script for web scraping",
            "make a pdf report on climate change",
            "create a text file with the summary"
        ]
    },
    "open_file": {
        "description": "Open an EXISTING file or document (NOT for creating new files)",
        "required_slots": ["file_query"],
        "optional_slots": ["temporal_context"],
        "examples": ["open the report pdf", "show me yesterday's notes", "find my presentation"]
    },
    "play_media": {
        "description": "Play music or video",
        "required_slots": ["query"],
        "optional_slots": ["platform"],
        "examples": ["play bohemian rhapsody", "play some jazz", "put on lofi beats"]
    },
    "search_web": {
        "description": "Search the web specifically to open a browser tab with results",
        "required_slots": ["query"],
        "optional_slots": ["engine"],
        "examples": ["google python tutorials", "open google search for best laptops", "search google for movies"]
    },
    "send_email": {
        "description": "Send an email",
        "required_slots": ["recipient"],
        "optional_slots": ["subject", "body", "attachments"],
        "examples": ["email john@test.com about the meeting", "send email to boss"]
    },
    "send_whatsapp": {
        "description": "Send a WhatsApp message",
        "required_slots": ["recipient"],
        "optional_slots": ["message"],
        "examples": ["whatsapp mom saying I'll be late", "message John about dinner"]
    },
    "generate_image": {
        "description": "Generate an AI image",
        "required_slots": ["description"],
        "optional_slots": ["style", "size"],
        "examples": ["generate image of a sunset", "create a picture of a cat", "make an anime style portrait"]
    },
    "search_images": {
        "description": "Search for images online",
        "required_slots": ["query"],
        "optional_slots": [],
        "examples": ["find images of mountains", "show me pictures of cats"]
    },
    "system_control": {
        "description": "Control system settings",
        "required_slots": ["action"],
        "optional_slots": ["value"],
        "examples": ["mute", "volume up", "unmute", "turn off wifi"]
    },
    "general_chat": {
        "description": "General conversation or question",
        "required_slots": [],
        "optional_slots": [],
        "examples": ["how are you", "tell me a joke", "what is python"]
    },
    "realtime_info": {
        "description": "Query requiring a direct, synthesized answer from current web data (news, facts, weather, etc.)",
        "required_slots": ["query"],
        "optional_slots": [],
        "examples": ["weather today", "stock price of apple", "latest news", "who is the current president", "tell me about the recent AI trends"]
    },
    "exit": {
        "description": "End the conversation",
        "required_slots": [],
        "optional_slots": [],
        "examples": ["bye", "exit", "goodbye", "quit"]
    },
    # COMPOSITE WORKFLOWS
    "search_and_share": {
        "description": "Search for information and share results via WhatsApp or email",
        "required_slots": ["search_query", "recipient"],
        "optional_slots": ["platform"],  # whatsapp or email, defaults to whatsapp
        "examples": [
            "find best restaurants and send to myself on whatsapp",
            "search for python tutorials and email them to john@test.com",
            "look up today's news and whatsapp it to mom"
        ]
    },
    "send_file_whatsapp": {
        "description": "Send a file or document via WhatsApp",
        "required_slots": ["file_query", "recipient"],
        "optional_slots": ["message"],
        "examples": [
            "send resume to myself on whatsapp",
            "whatsapp the report pdf to john",
            "send my presentation to boss on whatsapp"
        ]
    },
    # NEW INTENTS
    "youtube_search": {
        "description": "Search YouTube and open search results (NOT play a video)",
        "required_slots": ["query"],
        "optional_slots": [],
        "examples": [
            "youtube search python tutorials",
            "search youtube for cooking videos",
            "find videos about machine learning on youtube"
        ]
    },
    "focus_mode": {
        "description": "Enter focus mode by closing distracting apps",
        "required_slots": [],
        "optional_slots": [],
        "examples": [
            "enter focus mode",
            "remove distractions",
            "focus mode",
            "time to focus",
            "close distracting apps"
        ]
    },
    "read_document": {
        "description": "Find and read/analyze a document to answer questions about it (uses file search)",
        "required_slots": ["file_query"],
        "optional_slots": ["question"],
        "examples": [
            "read my resume",
            "analyze the report pdf",
            "what's in my project notes",
            "summarize the budget spreadsheet",
            "read the contract document",
            "tell me about my presentation"
        ]
    },
    "read_screen": {
        "description": "Capture and analyze what is currently visible on the user's screen",
        "required_slots": [],
        "optional_slots": ["question"],
        "examples": [
            "what's on my screen",
            "read my screen",
            "describe what I'm looking at",
            "what does my screen show",
            "analyze my screen",
            "summarize my screen",
            "where is this",
            "what place is this",
            "identify this location",
            "where are we looking at",
            "what does my screen show specifically",
            "solve the wordle on my screen",
            "what is the answer to this problem on my screen"
        ]
    },
    "recall_action": {
        "description": "Repeat or recall a previous action",
        "required_slots": [],
        "optional_slots": ["action_type"],
        "examples": [
            "do that again",
            "repeat last action",
            "play it again",
            "open that file again",
            "send the same message",
            "search for the same thing"
        ]
    },
    "read_screen_and_share": {
        "description": "Capture screen, analyze it, and share the result/screenshot via WhatsApp or email",
        "required_slots": ["recipient"],
        "optional_slots": ["question", "platform"],
        "examples": [
            "read my screen and send to John on whatsapp",
            "what's on my screen and email it to my boss",
            "share what I'm looking at with mom"
        ]
    },
    "read_screen_and_document": {
        "description": "Capture screen and save the analysis/summary into a new document",
        "required_slots": [],
        "optional_slots": ["file_type", "question"],
        "examples": [
            "summarize my screen in a word document",
            "save what's on my screen to a text file",
            "create a python file from the code on my screen"
        ]
    },
    "read_screen_and_search": {
        "description": "Capture screen and search for more information about what's visible",
        "required_slots": [],
        "optional_slots": ["question"],
        "examples": [
            "read my screen and find more about this on google",
            "what's on my screen? search for it",
            "search the web for the error on my screen"
        ]
    },
    # EXPLICIT SEARCH INTENTS
    "google_search": {
        "description": "Perform a Google web search and open the browser with results",
        "required_slots": ["query"],
        "optional_slots": [],
        "examples": [
            "google search python tutorials",
            "search google for best laptops",
            "google how to make pasta"
        ]
    },
    "play_youtube": {
        "description": "Play a specific video or music on YouTube",
        "required_slots": ["query"],
        "optional_slots": [],
        "examples": [
            "play despacito",
            "play lofi beats",
            "play Bohemian Rhapsody on youtube",
            "put on some jazz"
        ]
    },
    "search_youtube_and_share": {
        "description": "Search YouTube for a video and share the link via WhatsApp or email",
        "required_slots": ["query", "recipient"],
        "optional_slots": ["platform"],
        "examples": [
            "find a video about python and send it to John on whatsapp",
            "search youtube for cooking tutorials and email it to mom@email.com",
            "find a funny video and whatsapp it to myself"
        ]
    },
    "refresh_apps": {
        "description": "Refresh the application cache to discover newly installed apps",
        "required_slots": [],
        "optional_slots": [],
        "examples": [
            "refresh apps",
            "update app list",
            "rescan applications",
            "refresh application cache"
        ]
    },
    "reasoning": {
        "description": "Solve complex logical puzzles, riddles, multi-step reasoning, critical analysis, trick questions, lateral thinking, or any scenario requiring deep thought before answering",
        "required_slots": ["query"],
        "optional_slots": [],
        "examples": [
            "if i have three apples and you take away two how many do you have",
            "solve this riddle",
            "think about this problem",
            "what comes next in this sequence",
            "a man walks into a bar puzzle",
            "how would you approach this",
            "analyze this critically",
            "what's wrong with this argument",
            "solve this logic puzzle",
            "why is this the case",
            "figure this out for me",
            "what's the catch here",
            "how many triangles in this shape"
        ]
    }
}


@dataclass
class NLUResult:
    """Result of semantic NLU classification"""
    intent: str                              # The detected intent
    slots: Dict[str, Any] = field(default_factory=dict)  # Extracted slot values
    confidence: float = 0.0                  # 0.0 - 1.0 confidence score
    missing_slots: List[str] = field(default_factory=list)  # Required slots not filled
    clarification_prompt: Optional[str] = None  # Question to ask if slots missing
    raw_query: str = ""                      # Original user input
    resolved_query: str = ""                 # Query after context resolution
    thought_process: Optional[str] = None     # AI's reasoning for this query
    tool_chain: List[str] = field(default_factory=list) # Proposed sequence of tools
    
    def to_command(self) -> str:
        """Convert NLU result to legacy command format for compatibility"""
        # PRIORITY: If a tool chain is proposed, return it as an 'agentic_chain'
        if self.tool_chain and len(self.tool_chain) > 1:
            import json
            chain_data = {
                'chain': self.tool_chain,
                'thought': self.thought_process,
                'query': self.raw_query
            }
            return f"agentic_chain {json.dumps(chain_data)}"

        if self.intent == "open_app":
            return f"open {self.slots.get('app_name', '')}"
        elif self.intent == "close_app":
            return f"close {self.slots.get('app_name', '')}"
        elif self.intent == "open_file":
            cmd = f"open file {self.slots.get('file_query', '')}"
            if self.slots.get('temporal_context'):
                cmd += f" temporal:{self.slots['temporal_context']}"
            return cmd
        elif self.intent == "play_media":
            return f"play {self.slots.get('query', '')}"
        elif self.intent == "search_web":
            engine = self.slots.get('engine', 'google')
            return f"{engine} search {self.slots.get('query', '')}"
        elif self.intent == "send_email":
            return f"email {self.slots.get('recipient', '')} {self.slots.get('subject', '')} {self.slots.get('body', '')}".strip()
        elif self.intent == "send_whatsapp":
            return f"whatsapp {self.slots.get('recipient', '')} {self.slots.get('message', '')}".strip()
        elif self.intent == "generate_image":
            return f"generate image {self.slots.get('description', '')}"
        elif self.intent == "search_images":
            return f"search images {self.slots.get('query', '')}"
        elif self.intent == "system_control":
            return f"system {self.slots.get('action', '')}"
        elif self.intent == "realtime_info":
            return f"realtime {self.slots.get('query', self.raw_query)}"
        elif self.intent == "exit":
            return "exit"
        # COMPOSITE WORKFLOWS
        elif self.intent == "search_and_share":
            search_query = self.slots.get('search_query', '')
            recipient = self.slots.get('recipient', '')
            platform = self.slots.get('platform', 'whatsapp')
            return f"search_and_share {search_query}|{recipient}|{platform}"
        elif self.intent == "send_file_whatsapp":
            file_query = self.slots.get('file_query', '')
            recipient = self.slots.get('recipient', '')
            message = self.slots.get('message', '')
            return f"send_file_whatsapp {file_query}|{recipient}|{message}"
        # NEW INTENTS
        elif self.intent == "youtube_search":
            return f"youtube search {self.slots.get('query', self.raw_query)}"
        elif self.intent == "google_search":
            return f"google search {self.slots.get('query', self.raw_query)}"
        elif self.intent == "play_youtube":
            return f"play {self.slots.get('query', self.raw_query)}"
        elif self.intent == "focus_mode":
            return "focus_mode"
        elif self.intent == "read_document":
            file_query = self.slots.get('file_query', '')
            question = self.slots.get('question', '')
            return f"read_document {file_query}|{question}".strip()
        elif self.intent == "read_screen":
            question = self.slots.get('question', '')
            return f"read_screen {question}".strip()
        elif self.intent == "recall_action":
            return f"recall_action {self.slots.get('action_type', '')}"
        elif self.intent == "search_youtube_and_share":
            query = self.slots.get('query', '')
            recipient = self.slots.get('recipient', '')
            platform = self.slots.get('platform', 'whatsapp')
            return f"search_youtube_and_share {query}|{recipient}|{platform}"
        elif self.intent == "read_screen_and_share":
            recipient = self.slots.get('recipient', '')
            question = self.slots.get('question', '')
            platform = self.slots.get('platform', 'whatsapp')
            return f"read_screen_and_share {recipient}|{question}|{platform}"
        elif self.intent == "read_screen_and_document":
            file_type = self.slots.get('file_type', 'word')
            question = self.slots.get('question', '')
            return f"read_screen_and_document {file_type}|{question}"
        elif self.intent == "read_screen_and_search":
            question = self.slots.get('question', '')
            return f"read_screen_and_search {question}"
        elif self.intent == "refresh_apps":
            return "refresh_apps"
        elif self.intent == "create_file":
            file_type = self.slots.get('file_type', 'python')
            topic = self.slots.get('topic', '')
            return f"create_file {file_type}|{topic}"
        elif self.intent == "reasoning":
            return f"reasoning {self.slots.get('query', self.raw_query)}"
        else:
            return "general"



class SemanticNLU:
    """
    Semantic Natural Language Understanding using structured AI output.
    Single API call extracts intent + slots + confidence.
    """
    
    def __init__(self):
        self.intent_schemas = INTENT_SCHEMAS
        self.pending_action: Optional[NLUResult] = None
        
        # Build the classification prompt
        self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build the system prompt with all intent definitions"""
        intent_descriptions = []
        for intent_id, schema in self.intent_schemas.items():
            slots_info = f"Required: {schema['required_slots']}" if schema['required_slots'] else "No required slots"
            if schema['optional_slots']:
                slots_info += f", Optional: {schema['optional_slots']}"
            examples = ", ".join([f'"{ex}"' for ex in schema['examples'][:2]])
            intent_descriptions.append(
                f"- {intent_id}: {schema['description']}. {slots_info}. Examples: {examples}"
            )
        
        self.system_prompt = f"""You are a Natural Language Understanding system for a desktop assistant.
Your job is to analyze user queries and extract:
1. The user's intent (what they want to do)
2. Relevant slots/entities (specific values needed to complete the action)
3. Your confidence level (0.0 to 1.0)

AVAILABLE INTENTS:
{chr(10).join(intent_descriptions)}

CRITICAL RULES:
1. Extract ALL relevant information from the query into slots
2. Be flexible with phrasing - "fire up Chrome", "get Chrome going", "launch Chrome" all mean open_app with app_name="chrome"
3. For informal requests like "I need Spotify playing", extract intent=play_media, query="spotify"
4. If required slots are missing, identify them in missing_slots
5. Confidence should reflect how certain you are about the intent AND slot values
6. For general questions about facts, news, or current events, ALWAYS prefer realtime_info over search_web
7. Only use search_web if the user explicitly asks to "google" something or use a "browser" or "search engine"
8. If the user mentions "screen", "monitor", "display", "chrome", "page", "window", or "desktop" (e.g. "on my screen", "solve this on my screen", "what is this location on my screen"), ALWAYS prefer read_screen (or a tool_chain starting with it) over realtime_info or search_web. The user wants you to look at their current monitor.
9. If you identify a specific entity (landmark, company, error code) but need more info to be "outside the box", ALWAYS propose a tool_chain: ["read_screen", "realtime_info"].
10. If the recent context reflects that you just read or analyzed the screen, and the user asks a follow-up like "help me solve it", "what is this?", "explain that", or "find where it is", ALWAYS prefer read_screen.
11. Aggressively route any ambiguity involving visual terms to read_screen chains.
12. Always strive for the BEST and MOST CORRECT answer. If a query requires information not purely on the screen or in a document (e.g. "What place is this?"), propose a chain of tools (e.g. ["read_screen", "realtime_info"]) in the tool_chain field.
13. For any query that looks like a riddle, logic puzzle, or requires "thinking deeply", use the 'reasoning' intent.
14. For trick questions, conditional/counterfactual scenarios ("if I have X and you take Y"), perspective puzzles, lateral thinking problems, or any query where the OBVIOUS answer is likely WRONG, ALWAYS use the 'reasoning' intent. These require careful critical analysis.

OUTPUT FORMAT (JSON only, no other text):
{{
    "intent": "intent_name",
    "slots": {{"slot_name": "value", ...}},
    "thought_process": "Why these tools were chosen",
    "tool_chain": ["tool1", "tool2"],
    "confidence": 0.0-1.0,
    "missing_slots": ["slot1", "slot2"],
    "clarification_prompt": "Question to ask if slots missing or null"
}}"""
        
        return self.system_prompt
    
    def _is_self_referential_query(self, query: str) -> bool:
        """
        Detect if the query is asking about SYNORPSE itself or its creator.
        These should be handled by general_chat, not realtime search.
        """
        query_lower = query.lower()
        
        # Self-referential patterns
        self_patterns = [
            # About identity
            r'\bwho\s+(made|created|built|developed|designed)\s+(you|this|synorpse)',
            r'\bwho\s+(are|is)\s+(you|your\s+creator)',
            r'\bwhat\s+(are|is)\s+(you|your\s+name)',
            r'\bwhat\s+can\s+you\s+do',
            r'\byour\s+(name|creator|developer|maker)',
            r'\btell\s+me\s+about\s+(yourself|you)',
            # About capabilities
            r'\bwhat\s+(are\s+)?your\s+(capabilities|features|functions)',
            r'\bwhat\s+do\s+you\s+do',
            r'\bhow\s+do\s+you\s+work',
            # Creator specific
            r'\bsai\s*rachit',  # Creator's name mentioned
            r'\b(who|your)\s+creator',
            r'\bwho\s+is\s+behind\s+you',
            # Creator's social profiles (follow-up questions)
            r'\bhis\s+(linkedin|github|twitter|instagram|profile|website|email|contact)',
            r'\bher\s+(linkedin|github|twitter|instagram|profile|website|email|contact)',
            r'\b(give|share|send)\s+me\s+his\s+(linkedin|github|twitter)',
            r'\b(do you have|can you give)\s+(his|the)\s+(linkedin|github|twitter)',
            r'\bcreator.{0,10}(linkedin|github|twitter|profile)',
        ]
        
        for pattern in self_patterns:
            if re.search(pattern, query_lower):
                return True
        
        return False
    
    def classify(self, query: str, context: str = None) -> NLUResult:
        """
        Classify a query and extract slots using semantic understanding.
        
        Args:
            query: The user's input
            context: Optional conversation context
            
        Returns:
            NLUResult with intent, slots, confidence, and any missing information
        """
        if not groq_client:
            return NLUResult(
                intent="general_chat",
                confidence=0.5,
                raw_query=query,
                resolved_query=query
            )
        
        # PRIORITY CHECK: Self-referential queries should go to general_chat
        if self._is_self_referential_query(query):
            return NLUResult(
                intent="general_chat",
                confidence=0.95,
                raw_query=query,
                resolved_query=query
            )
        
        # Build the user message
        user_message = f'Analyze this query: "{query}"'
        if context:
            user_message = f"CONTEXT:\n{context}\n\n{user_message}"
        
        try:
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content.strip()
            result_data = json.loads(result_text)
            
            # Build NLUResult from response
            nlu_result = NLUResult(
                intent=result_data.get("intent", "general_chat"),
                slots=result_data.get("slots", {}),
                confidence=float(result_data.get("confidence", 0.5)),
                missing_slots=result_data.get("missing_slots", []),
                clarification_prompt=result_data.get("clarification_prompt"),
                raw_query=query,
                resolved_query=query,
                thought_process=result_data.get("thought_process"),
                tool_chain=result_data.get("tool_chain", [])
            )
            
            # Validate against schema
            nlu_result = self._validate_and_fix(nlu_result)
            
            return nlu_result
            
        except json.JSONDecodeError as e:
            print(f" JSON parse error in SemanticNLU: {e}")
            return NLUResult(
                intent="general_chat",
                confidence=0.3,
                raw_query=query,
                resolved_query=query
            )
        except Exception as e:
            print(f" SemanticNLU classification failed: {e}")
            return NLUResult(
                intent="general_chat",
                confidence=0.3,
                raw_query=query,
                resolved_query=query
            )
    
    def _validate_and_fix(self, result: NLUResult) -> NLUResult:
        """Validate the NLU result and fix common issues"""
        schema = self.intent_schemas.get(result.intent)
        
        if not schema:
            # Unknown intent, default to general_chat
            result.intent = "general_chat"
            result.confidence = min(result.confidence, 0.5)
            return result
        
        # Check for missing required slots
        required = schema.get("required_slots", [])
        missing = []
        
        for slot in required:
            if slot not in result.slots or not result.slots[slot]:
                missing.append(slot)
        
        # IMPORTANT: Override the AI's missing_slots with ONLY truly required ones.
        # The AI sometimes reports optional slots (e.g., email "subject") as missing,
        # which causes unnecessary clarification prompts. We only block on REQUIRED slots.
        result.missing_slots = missing
        
        # Generate clarification prompt if missing required slots
        if result.missing_slots and not result.clarification_prompt:
            result.clarification_prompt = self._generate_clarification(
                result.intent, result.missing_slots
            )
        else:
            result.clarification_prompt = None
        
        return result
    
    def _generate_clarification(self, intent: str, missing_slots: List[str]) -> str:
        """Generate a natural clarification question for missing slots"""
        clarifications = {
            ("send_email", "recipient"): "Who should I send the email to?",
            ("send_email", "subject"): "What's the subject of the email?",
            ("send_email", "body"): "What would you like the email to say?",
            ("send_whatsapp", "recipient"): "Who should I message?",
            ("send_whatsapp", "message"): "What would you like me to say?",
            ("open_app", "app_name"): "Which application would you like me to open?",
            ("open_file", "file_query"): "Which file are you looking for?",
            ("play_media", "query"): "What would you like me to play?",
            ("search_web", "query"): "What would you like me to search for?",
            ("generate_image", "description"): "What kind of image would you like me to create?",
            # Composite workflows
            ("search_and_share", "search_query"): "What would you like me to search for?",
            ("search_and_share", "recipient"): "Who should I send the results to?",
            ("send_file_whatsapp", "file_query"): "Which file would you like me to send?",
            ("send_file_whatsapp", "recipient"): "Who should I send the file to?",
        }
        
        # Try to find a specific clarification
        for slot in missing_slots:
            key = (intent, slot)
            if key in clarifications:
                return clarifications[key]
        
        # Generic fallback
        slot_names = ", ".join(missing_slots)
        return f"I need more information: {slot_names}"
    
    def continue_with_slot(self, slot_value: str, slot_name: str = None) -> Optional[NLUResult]:
        """
        Continue a pending action by filling in a missing slot.
        
        Args:
            slot_value: The value provided by the user
            slot_name: Optional specific slot to fill (auto-detected if not provided)
            
        Returns:
            Updated NLUResult if there was a pending action, None otherwise
        """
        if not self.pending_action:
            return None
        
        result = self.pending_action
        
        # Determine which slot to fill
        if slot_name:
            target_slot = slot_name
        elif result.missing_slots:
            target_slot = result.missing_slots[0]
        else:
            return None
        
        # Fill the slot
        result.slots[target_slot] = slot_value
        
        # Remove from missing slots
        if target_slot in result.missing_slots:
            result.missing_slots.remove(target_slot)
        
        # Update clarification prompt if still missing slots
        if result.missing_slots:
            result.clarification_prompt = self._generate_clarification(
                result.intent, result.missing_slots
            )
        else:
            result.clarification_prompt = None
            result.confidence = max(result.confidence, 0.85)  # Boost confidence
        
        # Clear pending if complete
        if not result.missing_slots:
            self.pending_action = None
        
        return result
    
    def set_pending_action(self, result: NLUResult):
        """Set a pending action for slot filling"""
        self.pending_action = result
    
    def clear_pending_action(self):
        """Clear any pending action"""
        self.pending_action = None
    
    def has_pending_action(self) -> bool:
        """Check if there's a pending action waiting for slot filling"""
        return self.pending_action is not None


# Global instance
_semantic_nlu = None


def get_semantic_nlu() -> SemanticNLU:
    """Get or create the global SemanticNLU instance"""
    global _semantic_nlu
    if _semantic_nlu is None:
        _semantic_nlu = SemanticNLU()
    return _semantic_nlu
