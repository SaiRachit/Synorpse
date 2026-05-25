"""
IntentRouterFixed.py - Fixed version with better patterns
Fixes: Greetings, Image search, Email detection
"""
import re
import logging
from typing import List, Dict, Optional
from functools import lru_cache
from groq import Groq
from dotenv import dotenv_values
import time
from MetaQuery import is_agent_meta_query

logger = logging.getLogger("IntentRouter")

env_vars = dotenv_values(".env")
GROQ_API_KEY = env_vars.get("GroqAPIKey2")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Import new modules for enhanced functionality
try:
    from CapabilityRegistry import get_capability_registry
    from ConversationContext import get_conversation_context
    from ContextualAliasResolver import get_alias_resolver
    from SemanticNLU import get_semantic_nlu, NLUResult
    capability_registry = get_capability_registry()
    conversation_context = get_conversation_context()
    alias_resolver = get_alias_resolver()
    semantic_nlu = get_semantic_nlu()
except ImportError:
    capability_registry = None
    conversation_context = None
    alias_resolver = None
    semantic_nlu = None


class IntentRouterFixed:
    """
    Fixed intent router with improved pattern matching
    """
    
    # Pre-compiled regex patterns for speed
    PATTERNS = {
        'exit': re.compile(r'\b(exit|quit|bye|goodbye)\b', re.I),
        'open_app': re.compile(r'\bopen\s+(?!file)(?!image)(\w+(?:\s+\w+)?)\b', re.I),
        'open_file': re.compile(r'\bopen\s+(?:the\s+)?file\s+(.+)', re.I),
        # NEW: Create file patterns (before find_file)
        'create_file': re.compile(r'\b(?:create|make|write|generate)\s+(?:a\s+|an\s+)?(?:new\s+)?(python|py|word|doc|docx|pdf|text|txt|markdown|md)?\s*(?:file|document|script|code)?\s*(?:with|about|on|for)?\s*(.+)?', re.I),
        # Stricter find_file: requires 'file/document' OR 'my' to imply local context
        'find_file': re.compile(r'\b(?:find|locate)\s+(?:my\s+|the\s+)?(.+?)(?:\s+(?:file|document|pdf|doc|sheet|presentation|slide))|(?:\b(?:find|search\s+for)\s+my\s+(.+))', re.I),
        'close_app': re.compile(r'\bclose\s+(\w+(?:\s+\w+)?)\b', re.I),
        'play': re.compile(r'\bplay\s+(.+)', re.I),
        'google_search': re.compile(r'\b(?:google\s+search(?:\s+for)?|search\s+google\s+(?:for\s+)?)(.+)', re.I),
        'youtube_search': re.compile(r'\byoutube\s+search\s+(.+)', re.I),
        
        # FIXED: Better image generation patterns
        'generate_image': re.compile(r'\b(?:generate|create|make)\s+(?:an?\s+)?(?:image|picture|photo|pic)\s+(?:of\s+)?(.+)', re.I),
        
        # NEW: Image search patterns (high priority)
        'search_images': re.compile(r'\b(?:find|search|show|get|display)(?:\s+me)?\s+(?:an?\s+)?(?:images?|pictures?|photos?|pics?)\s+(?:of\s+)?(.+)', re.I),
        'search_images_alt': re.compile(r'\b(?:images?|pictures?|photos?)\s+(?:of|for)\s+(.+)', re.I),
        
        # FIXED: Better email pattern (before WhatsApp)
        'email': re.compile(r'\b(?:send|email|mail)\s+(?:an?\s+)?(?:email|mail)\s+to\s+([^\s]+@[^\s]+)(.+)?', re.I),
        'email_simple': re.compile(r'\bemail\s+([^\s]+@[^\s]+)(.+)?', re.I),
        
        # NEW: Search and Share workflow
        'search_and_email': re.compile(r'\bsearch\s+(?:for\s+)?(.+?)\s+and\s+(?:email|send)\s+(?:it|results?)\s+to\s+(.+)', re.I),
        
        # WhatsApp (after email and images) - improved to catch "send a message to X" queries
        'whatsapp': re.compile(r'\b(?:send|whatsapp|message|text)\s+(?:a\s+)?(?:message|whatsapp|text)?\s*(?:to\s+)?(.+?)\s*(?:on\s+whatsapp)?$', re.I),
        
        'system_mute': re.compile(r'\b(mute|silence)\b', re.I),
        'system_unmute': re.compile(r'\b(unmute|unsilence)\b', re.I),
        'system_volume_up': re.compile(r'\bvolume\s+up\b', re.I),
        'system_volume_down': re.compile(r'\bvolume\s+down\b', re.I),
        
        # NEW: Focus mode patterns
        'focus_mode': re.compile(r'\b(?:enter\s+)?focus\s*mode|remove\s+distractions|time\s+to\s+focus|close\s+distracting\s+apps\b', re.I),
        
        # NEW: Screen reading patterns (Higher priority than general document reading)
        'read_screen': re.compile(r'\b(?:read|describe|analyze|summarize|explain|look(?:\s+at)?|check|solve|answer|find|locate|get|show|what|how|where|is|can|identify|scan)\s+.*(?:screen|monitor|display|chrome|browser|desktop|page|window|visual)\b|\bwhat(?:\'?s|\s+is)\s+(?:on|showing\s+on|there\s+on|visible\s+on)\s+(?:my\s+)?screen\b|\bscreen\s+(?:read|capture|analysis)\b|\b(?:what|where|how)(?:\s+[\w\s]+)?\s+(?:do\s+you\s+)?(?:see|view|visible|shortcuts?|answer|result|solve|find|locate|identify)\s+(?:on|in|at|within)\s+(?:my\s+)?(?:screen|monitor|display|chrome|browser|desktop|page|window)\b', re.I),

        # NEW: Read document patterns (uses uploaded file context) - Stricter to avoid screen conflicts
        'read_document': re.compile(r'\b(?:read|analyze|summarize|what\'?s\s+in)\s+(?:my\s+|the\s+)?(?:this\s+|that\s+)?(.+?)\s*(?:file|document|pdf|doc|docx|manual|sheet|presentation|slides?|text\s+file)$|\b(?:read|summarize|analyze)\s+(?:the\s+|this\s+)?(?:uploaded\s+)?(?:file|document|doc)\b', re.I),
        
        # NEW: Recall action patterns
        'recall_action': re.compile(r'\b(?:do\s+(?:that|it)\s+again|repeat\s+(?:last\s+)?(?:action|that)|play\s+it\s+again|(?:open|send|search)\s+(?:that|the\s+same)\s+(?:again|thing))\b', re.I),
        
        # NEW: Refresh apps pattern
        'refresh_apps': re.compile(r'\b(?:refresh|update|rescan)\s+(?:apps?|applications?|app\s+list|application\s+cache)\b', re.I),
        
        # NEW: Search YouTube and share pattern
        'search_youtube_and_share': re.compile(r'\b(?:find|search)\s+(?:a\s+)?(?:video|youtube)\s+(?:about|for)\s+(.+?)\s+and\s+(?:send|share|whatsapp|email)\s+(?:it\s+)?to\s+(.+)', re.I),
        'read_screen_and_share': re.compile(r'\b(?:read|analyze|describe|look\s+at|check)\s+(?:my\s+|the\s+)?screen\s+and\s+(?:share|send|whatsapp|email)\s+(?:it\s+)?to\s+(.+)', re.I),
        'read_screen_and_document': re.compile(r'\b(?:read|analyze|summarize)\s+(?:my\s+|the\s+)?screen\s+(?:in|to)\s+(?:a\s+)?(python|word|text|pdf|markdown)?\s*(?:file|document|report)', re.I),
        'read_screen_and_search': re.compile(r'\b(?:read|analyze|look\s+at)\s+(?:my\s+|the\s+)?screen\s+and\s+(?:search|find|google)\b', re.I),
        'reasoning': re.compile(r'\b(?:solve|think|reason|puzzles?|riddles?|logic|why\s+is|how\s+come|explain\s+logically)\b', re.I),
    }
    
    # Keywords for realtime queries
    REALTIME_INDICATORS = {
        'current', 'now', 'today', 'latest', 'recent', 'price', 'stock',
        'weather', 'news', 'update', 'who is ', 'what is ', 'when is ',
        'current president', 'current ceo', 'right now'
    }
    
    # NEW: Greeting patterns (prevent misclassification)
    GREETING_PATTERN = re.compile(
        r'^(?:hello|hi|hey|good\s+(?:morning|afternoon|evening|night)|greetings|howdy|yo)\b',
        re.I
    )
    
    # Keywords for general queries
    GENERAL_INDICATORS = {
        'how to', 'what are', 'explain', 'tell me about', 'why',
        'define', 'meaning', 'history of', 'tutorial', 'guide'
    }
    
    # NEW: Temporal patterns for file queries
    TEMPORAL_PATTERNS = {
        'yesterday': re.compile(r'\b(yesterday|last day)\b', re.I),
        'this_week': re.compile(r'\b(this week|past week|last week)\b', re.I),
        'today': re.compile(r'\b(today|earlier today)\b', re.I),
        'recently': re.compile(r'\b(recently|recent|lately)\b', re.I),
    }
    
    # NEW: Contextual intent patterns
    CONTEXTUAL_PATTERNS = {
        'want_to_code': re.compile(r'\b(i want to code|i need to code|start coding|time to code)\b', re.I),
        'want_to_browse': re.compile(r'\b(i need to browse|browse the internet|go online|surf the web)\b', re.I),
        'want_music': re.compile(r'\b(play some music|i want music|put on music)\b', re.I),
        'want_to_message': re.compile(r'\b(i need to message|message someone|send a message)\b', re.I),
    }
    
    # Confidence thresholds for semantic NLU
    CONFIDENCE_EXECUTE = 0.85   # Auto-execute if confidence >= this
    CONFIDENCE_CONFIRM = 0.6    # Ask for confirmation if confidence >= this
    
    def __init__(self):
        self.stats = {
            'pattern_matched': 0,
            'ai_classified': 0,
            'semantic_classified': 0,
            'total_queries': 0,
            'avg_response_time': 0,
            'alias_resolved': 0
        }
        self.semantic_nlu = semantic_nlu
    
    def route(self, query: str, context: Dict = None) -> List[str]:
        """
        Main routing function with semantic NLU and multi-intent detection
        Returns list of commands to execute
        """
        start_time = time.time()
        self.stats['total_queries'] += 1

        if is_agent_meta_query(query):
            if self.semantic_nlu:
                self.semantic_nlu.clear_pending_action()
            return [f"reasoning {query}"]
        
        # Step -1: Check for greetings FIRST (highest priority for instant feel)
        if self.GREETING_PATTERN.search(query) and len(query.split()) <= 6:
            return ['general']
        
        # Step 0: Check if we're continuing a pending action (slot filling)
        if self.semantic_nlu and self.semantic_nlu.has_pending_action():
            result = self._handle_slot_filling(query)
            if result:
                elapsed = (time.time() - start_time) * 1000
                self._update_avg_time(elapsed)
                return result
        
        # Step 0.5: Check for composite workflow patterns BEFORE multi-intent split
        if self._is_composite_workflow(query):
            if self.semantic_nlu:
                result = self._semantic_classify(query)
                if result:
                    self.stats['semantic_classified'] += 1
                    elapsed = (time.time() - start_time) * 1000
                    self._update_avg_time(elapsed)
                    return result
        
        # Step 1: Check for multi-intent
        if self._has_multiple_intents(query):
            result = self._parse_multi_intent(query)
            if result:
                self.stats['pattern_matched'] += 1
                elapsed = (time.time() - start_time) * 1000
                self._update_avg_time(elapsed)
                return result
                
        # Step 2: Resolve Context (Aliases & Pronouns)
        resolved_query = query
        
        # 2a: Resolve contextual aliases (e.g., app names)
        if alias_resolver:
            contextual_result = self._handle_contextual_intent(query)
            if contextual_result:
                self.stats['alias_resolved'] += 1
                elapsed = (time.time() - start_time) * 1000
                self._update_avg_time(elapsed)
                return contextual_result
            
            # Resolve aliases in the string
            expanded = alias_resolver.resolve_alias(query)[0]
            if expanded and expanded != query:
                resolved_query = alias_resolver.expand_query(query)
                self.stats['alias_resolved'] += 1

        # 2b: Resolve references using conversation context (pronouns like "it", "this")
        if conversation_context:
            contextualized = conversation_context.resolve_reference(resolved_query)
            if contextualized != resolved_query:
                self.stats['alias_resolved'] += 1
                resolved_query = contextualized
                logger.info(f"Resolved contextual query: '{query}' -> '{resolved_query}'")
        
        # Step 3: Fast pattern matching for simple commands
        if self._is_simple_command(query) or self._is_simple_command(resolved_query):
            result = self._fast_pattern_match(resolved_query)
            if result:
                self.stats['pattern_matched'] += 1
                elapsed = (time.time() - start_time) * 1000
                self._update_avg_time(elapsed)
                return result
        
        # Step 4: Semantic NLU classification
        if self.semantic_nlu:
            result = self._semantic_classify(resolved_query)
            if result:
                self.stats['semantic_classified'] += 1
                elapsed = (time.time() - start_time) * 1000
                self._update_avg_time(elapsed)
                return result
        
        # Step 5: Fallback to fast pattern matching
        result = self._fast_pattern_match(resolved_query)
        if result:
            self.stats['pattern_matched'] += 1
            elapsed = (time.time() - start_time) * 1000
            self._update_avg_time(elapsed)
            return result
        
        # Step 6: Legacy AI classification fallback
        context_str = None
        if conversation_context:
            context_str = conversation_context.get_context_for_ai(include_turns=2)
        
        result = self._classify_with_context(resolved_query, context_str)
        self.stats['ai_classified'] += 1
        elapsed = (time.time() - start_time) * 1000
        self._update_avg_time(elapsed)
        return result
    
    def _is_simple_command(self, query: str) -> bool:
        """
        Check if a query is simple enough to bypass semantic NLU.
        """
        query_lower = query.lower().strip()
        
        # HEURISTIC: Very short queries or specific keywords
        if len(query.split()) <= 4:
            return True
            
        # Screen reading is always considered simple enough for fast trigger
        if "screen" in query_lower or "monitor" in query_lower or "display" in query_lower:
            return True
            
        if "window" in query_lower or "chrome" in query_lower or "browser" in query_lower:
            return True
        
        # EXCEPTION: If it contains question markers, it's NOT simple (needs reasoning)
        if any(q in query_lower for q in ['what', 'where', 'how', 'explain', 'identify', 'why', 'who']):
            return False
            
        # Simple patterns that regex handles efficiently
        simple_starters = [
            'open ', 'close ', 'play ', 'mute', 'unmute', 'volume ',
            'exit', 'quit', 'bye', 'goodbye', 'whatsapp ', 'email ',
            'read ', 'analyze ', 'summarize ', 'what\'s in '
        ]
        
        
        return any(query_lower.startswith(s) for s in simple_starters)
    
    def _is_composite_workflow(self, query: str) -> bool:
        """
        Detect if a query describes a composite workflow that should not be split.
        E.g., "search for X and send to Y"
        """
        query_lower = query.lower()
        
        # Patterns that indicate composite workflows (X and Y as one action)
        composite_patterns = [
            r'.*search.*and.*send.*',
            r'.*find.*and.*whatsapp.*',
            r'.*look up.*and.*email.*',
            r'.*search.*and.*share.*',
            r'.*search.*and.*message.*'
        ]
        
        return any(re.match(pattern, query_lower) for pattern in composite_patterns)

    def _semantic_classify(self, query: str) -> Optional[List[str]]:
        """
        Use SemanticNLU for natural language understanding.
        Handles confidence thresholds and clarification.
        """
        # Get context for the NLU
        context_str = None
        if conversation_context:
            context_str = conversation_context.get_context_for_ai(include_turns=2)
        
        # Classify with semantic NLU
        nlu_result = self.semantic_nlu.classify(query, context_str)
        
        # Handle missing required slots
        if nlu_result.missing_slots:
            self.semantic_nlu.set_pending_action(nlu_result)
            return [f"clarify {nlu_result.clarification_prompt}"]
        
        # High confidence: execute immediately
        # OR: exempt harmless intents (general_chat, greeting) from high thresholds
        if nlu_result.confidence >= self.CONFIDENCE_EXECUTE or nlu_result.intent in ['general_chat', 'greeting']:
            command = nlu_result.to_command()
            return [command]
        
        # Medium confidence: ask for confirmation
        elif nlu_result.confidence >= self.CONFIDENCE_CONFIRM:
            command = nlu_result.to_command()
            self.semantic_nlu.set_pending_action(nlu_result)
            action_desc = f"{nlu_result.intent}: {nlu_result.slots}"
            return [f"confirm {command}|{action_desc}"]
        
        # Low confidence: let it fall through to other classifiers or chat
        return None
    
    def _handle_slot_filling(self, query: str) -> Optional[List[str]]:
        """
        Handle continuation of a pending action by filling missing slots.
        """
        query_lower = query.lower().strip()
        
        # Check for cancellation
        if query_lower in ['cancel', 'nevermind', 'never mind', 'forget it', 'no']:
            self.semantic_nlu.clear_pending_action()
            return ['general']  # Will respond naturally
        
        # Check for confirmation (yes to previous confirm request)
        if query_lower in ['yes', 'yeah', 'yep', 'sure', 'ok', 'okay', 'confirm', 'do it']:
            pending = self.semantic_nlu.pending_action
            if pending and not pending.missing_slots:
                self.semantic_nlu.clear_pending_action()
                return [pending.to_command()]
        
        # Try to fill the missing slot with the user's response
        result = self.semantic_nlu.continue_with_slot(query)
        
        if result:
            # Check if all slots are now filled
            if not result.missing_slots:
                self.semantic_nlu.clear_pending_action()
                return [result.to_command()]
            else:
                # Still missing slots, ask for the next one
                return [f"clarify {result.clarification_prompt}"]
        
        # Couldn't process as slot filling, clear pending and process normally
        self.semantic_nlu.clear_pending_action()
        return None
    
    def _fast_pattern_match(self, query: str) -> Optional[List[str]]:
        """
        Lightning-fast pattern matching with FIXED priorities
        """
        query = query.strip()
        query_lower = query.lower()
        
        # === PRIORITY 0: Greetings (prevent misclassification) ===
        if self.GREETING_PATTERN.search(query) and len(query.split()) <= 6:
            # Short greeting-like query  general
            return ['general']
        
        # === PRIORITY 1: Image GENERATION (before search!) ===
        match = self.PATTERNS['generate_image'].search(query)
        if match:
            description = match.group(1).strip()
            if not description:
                # Fallback: extract everything after "image"
                parts = query.lower().split('image')
                if len(parts) > 1:
                    description = parts[1].strip()
            return [f'generate image {description}']
        
        # === PRIORITY 2: Image search (after generation) ===
        for pattern_name in ['search_images', 'search_images_alt']:
            match = self.PATTERNS[pattern_name].search(query)
            if match:
                search_term = match.group(1).strip()
                # Clean up common words
                search_term = re.sub(r'\b(please|for me|me)\b', '', search_term, flags=re.I).strip()
                return [f'search images {search_term}']
        
        # === PRIORITY 3: Email (before WhatsApp) ===
        for pattern_name in ['email', 'email_simple']:
            if pattern_name in self.PATTERNS:
                match = self.PATTERNS[pattern_name].search(query)
                if match:
                    recipient = match.group(1).strip()
                    content = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else ""
                    return [f'email {recipient} {content}'.strip()]
        
        # === PRIORITY 3.0: Screen Reading (Vision) ===
        # Higher priority than realtime search to avoid misrouting "what is on my screen"
        # BUT: if query ALSO matches reasoning (solve/riddle/puzzle + screen),
        # prefer reasoning — the ReAct loop's visual guard will call read_screen internally
        match = self.PATTERNS['read_screen'].search(query)
        if match:
            if self.PATTERNS['reasoning'].search(query):
                return [f'reasoning {query}']
            return [f'read_screen {query}']

        # === PRIORITY 3.1: Realtime Search Indicators (Before broad patterns) ===
        if any(indicator in query_lower for indicator in self.REALTIME_INDICATORS):
            return ['realtime ' + query]
        
        # Check for exit
        if self.PATTERNS['exit'].search(query):
            return ['exit']
        
        # === PRIORITY 3.5: Search and Email (Compound Workflow) ===
        # Must run BEFORE multi-command split to preserve the workflow
        match = self.PATTERNS['search_and_email'].search(query)
        if match:
            search_query = match.group(1).strip()
            recipient = match.group(2).strip()
            return [f'search_and_email {search_query}|{recipient}']

        # NEW: YouTube and Share
        # Flexible match: "search youtube for X and [share logic] to Y"
        match = re.search(r'\b(?:search|find)\s+(?:youtube|video)\s+(?:for\s+)?(.+?)\s+and\s+(?:share|send|whatsapp|email).+?to\s+(.+)', query, re.I)
        if match:
            video_query = match.group(1).strip()
            recipient = match.group(2).strip()
            # Determine method (default whatsapp)
            method = "whatsapp"
            if "email" in query.lower():
                method = "email"
            return [f'search_youtube_and_share {video_query}|{recipient}|{method}']

        # NEW: Focus Mode / App Management
        if re.search(r'\b(focus mode|i need to focus|close distracting apps)\b', query, re.I):
            return ['focus_mode']

        if re.search(r'\b(focus mode|i need to focus|close distracting apps)\b', query, re.I):
            return ['focus_mode']
            
        # NEW: Refresh/Scan Apps
        if re.search(r'\b(refresh|scan|reload)\s+(?:app|apps|applications|cache)\b', query, re.I):
            return ['refresh_apps']

        # Check for multi-command queries
        if ',' in query or ' and ' in query:
            return self._parse_multi_command(query)
        
        # === PRIORITY 3: Image generation (not search) ===
        match = self.PATTERNS['generate_image'].search(query)
        if match:
            description = match.group(1).strip()
            if not description:
                # Fallback: extract everything after "image"
                parts = query.lower().split('image')
                if len(parts) > 1:
                    description = parts[1].strip()
            return [f'generate image {description}']
        
        # === PRIORITY 4: Other patterns ===
        for intent, pattern in self.PATTERNS.items():
            if intent in ['exit', 'generate_image', 'search_images', 'search_images_alt', 'email', 'email_simple']:
                continue  # Already handled
            
            match = pattern.search(query)
            if match:
                return self._build_command(intent, match, query)
        
        # === PRIORITY 5: Quick classification for general vs realtime ===
        # Check general indicators
        if any(indicator in query_lower for indicator in self.GENERAL_INDICATORS):
            return ['general']
        
        # Question patterns suggest general query
        if re.match(r'^(what|who|where|when|why|how|can|could|would|should|is|are|do|does)', query_lower):
            # But check if it needs realtime info
            if any(word in query_lower for word in ['current', 'now', 'today', 'latest']):
                return ['realtime ' + query]
            return ['general']
        
        return None
    
    def _build_command(self, intent: str, match: re.Match, full_query: str) -> List[str]:
        """Build command from pattern match"""
        
        if intent == 'exit':
            return ['exit']
        
        elif intent == 'open_app':
            app_name = match.group(1).strip()
            return [f'open {app_name}']
        
        elif intent == 'open_file':
            file_name = match.group(1).strip()
            # Check for temporal context
            temporal_key = self._detect_temporal_context(file_name)
            if temporal_key:
                return [f'open file {file_name} temporal:{temporal_key}']
            return [f'open file {file_name}']
        
        elif intent == 'find_file':
            file_name = match.group(1).strip()
            # Check for temporal context
            temporal_key = self._detect_temporal_context(file_name)
            if temporal_key:
                return [f'open file {file_name} temporal:{temporal_key}']
            return [f'open file {file_name}']
        
        elif intent == 'create_file':
            # Extract file type and topic from the regex groups
            file_type = match.group(1) if match.group(1) else 'word'
            topic = match.group(2).strip() if match.group(2) else ''
            
            # Normalize file type
            file_type = file_type.lower() if file_type else 'word'
            if file_type in ['py', 'python']:
                file_type = 'python'
            elif file_type in ['doc', 'docx', 'word']:
                file_type = 'word'
            elif file_type in ['txt', 'text']:
                file_type = 'text'
            elif file_type in ['md', 'markdown']:
                file_type = 'markdown'
            
            return [f'create {file_type} file about {topic}']
        
        elif intent == 'close_app':
            app_name = match.group(1).strip()
            return [f'close {app_name}']
        
        elif intent == 'play':
            song = match.group(1).strip()
            return [f'play {song}']
        
        elif intent == 'google_search':
            query = match.group(1).strip()
            return [f'google search {query}']
        
        elif intent == 'youtube_search':
            query = match.group(1).strip()
            return [f'youtube search {query}']
        
        elif intent == 'whatsapp':
            message_query = match.group(1).strip()
            # Make sure it's not an email
            if '@' in message_query and '.' in message_query:
                return ['general']  # Let AI handle ambiguous cases
            return [f'whatsapp {message_query}']
        
        elif intent.startswith('system_'):
            command = intent.replace('system_', '').replace('_', ' ')
            return [f'system {command}']
        
        elif intent == 'focus_mode':
            return ['focus_mode']
        
        elif intent == 'read_document':
            file_query = match.group(1).strip() if match.groups() else ''
            return [f'read_document {file_query}']
        
        elif intent == 'read_screen':
            return [f'read_screen {full_query}']
        
        elif intent == 'recall_action':
            return ['recall_action']
        
        elif intent == 'refresh_apps':
            return ['refresh_apps']
        
        elif intent == 'search_youtube_and_share':
            query = match.group(1).strip() if match.groups() else ''
            recipient = match.group(2).strip() if len(match.groups()) > 1 else ''
            # Determine platform from recipient
            platform = 'email' if '@' in recipient else 'whatsapp'
            return [f'search_youtube_and_share {query}|{recipient}|{platform}']
        
        elif intent == 'read_screen_and_share':
            recipient = match.group(1).strip() if match.groups() else ''
            # Default platform
            platform = 'email' if '@' in recipient else 'whatsapp'
            return [f'read_screen_and_share {recipient}||{platform}']
            
        elif intent == 'read_screen_and_document':
            file_type = match.group(1).strip() if match.group(1) else 'word'
            return [f'read_screen_and_document {file_type}|']
            
        elif intent == 'read_screen_and_search':
            return [f'read_screen_and_search ']
        
        elif intent == 'reasoning':
            return [f'reasoning {full_query}']
        
        return ['general']
    
    def _has_multiple_intents(self, query: str) -> bool:
        """Check if query contains multiple intents"""
        query_lower = query.lower()
        
        # Conversational patterns that use "and" but are single intents
        conversational_patterns = [
            r'\b(compare|contrast)\s+.*\s+(?:and|vs|versus)\s+',
            r'\b(difference|differences)\s+between\s+.*\s+and\s+',
            r'\b(pros|cons)\s+(?:and|of)\s+',
            r'\b(advantages|disadvantages)\s+(?:and|of)\s+',
            r'\b(similarities|differences)\s+(?:and|between)\s+',
            r'\b(explain|tell|describe|what|how)\s+.*\s+and\s+',
        ]
        
        # Check if query matches conversational patterns
        for pattern in conversational_patterns:
            if re.search(pattern, query_lower):
                return False
        
        # Check for actual multi-command indicators
        # Only split on "and" if there are clear action verbs on both sides
        if ' and ' in query_lower:
            parts = query_lower.split(' and ')
            if len(parts) == 2:
                action_verbs = ['open', 'close', 'play', 'search', 'find', 'create', 
                               'generate', 'send', 'email', 'message', 'whatsapp']
                
                has_action_1 = any(verb in parts[0] for verb in action_verbs)
                has_action_2 = any(verb in parts[1] for verb in action_verbs)
                
                if not (has_action_1 and has_action_2):
                    return False
        
        # Look for other clear multi-intent indicators
        multi_intent_indicators = [' then ', ' also ', ' plus ', ',']
        return any(indicator in query_lower for indicator in multi_intent_indicators)
    
    def _parse_multi_intent(self, query: str) -> Optional[List[str]]:
        """Parse query with multiple intents into separate commands"""
        # Split by common separators
        separators = [',', ' and then ', ' then ', ' and also ', ' also ', ' and ', ' plus ']
        parts = [query]
        
        for sep in separators:
            new_parts = []
            for part in parts:
                if sep in part.lower():
                    # Case-insensitive split
                    import re
                    split_parts = re.split(re.escape(sep), part, flags=re.IGNORECASE)
                    new_parts.extend(split_parts)
                else:
                    new_parts.append(part)
            parts = new_parts
        
        # Route each part separately
        commands = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            
            # Try pattern matching on each part
            result = self._fast_pattern_match(part)
            if result:
                commands.extend(result)
            else:
                # Fallback to AI classification
                result = self._classify_with_context(part)
                commands.extend(result)
        
        return commands if len(commands) > 1 else None
    
    def _parse_multi_command(self, query: str) -> List[str]:
        """Parse queries with multiple commands (legacy method)"""
        return self._parse_multi_intent(query) or ['general']
    
    @lru_cache(maxsize=500)
    def _classify_with_context(self, query: str, context_str: str = None) -> List[str]:
        """AI-powered classification for ambiguous queries"""
        if not groq_client:
            return ['general']
        
        try:
            context_info = f"\nContext: {context_str}" if context_str else ""
            
            prompt = f"""Classify this user query into ONE command type. Return ONLY the command.

Query: "{query}"{context_info}

Commands:
- "general" - conversational/info query
- "realtime QUERY" - needs current info
- "open APP" - open application/website
- "open file FILENAME" - open document
- "close APP" - close application
- "play SONG" - play on YouTube
- "google search QUERY" - Google search
- "youtube search QUERY" - YouTube search
- "generate image DESCRIPTION" - create image (FULL description)
- "search images QUERY" - search Google for images
- "read_screen QUESTION" - capture and analyze the screen
- "whatsapp QUERY" - send WhatsApp
- "email RECIPIENT MESSAGE" - send email
- "system COMMAND" - system control
- "exit" - end conversation

Examples:
"find images of cats"  search images cats
"send email to john@test.com about meeting"  email john@test.com about meeting
"send message to parv on whatsapp hello"  whatsapp parv hello
"whatsapp sarah saying I'll be late"  whatsapp sarah I'll be late
"hello"  general

CRITICAL: If the user mentions "whatsapp", "message", or "text" without an email address (@), ALWAYS prefer "whatsapp" over "email".

Now classify: "{query}"
Return ONLY command."""

            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "Classify queries. Return ONLY command, no explanation."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=150
            )
            
            result = response.choices[0].message.content.strip()
            
            # Validate result
            if any(result.startswith(cmd) for cmd in [
                'general', 'realtime', 'open', 'close', 'play', 
                'google search', 'youtube search', 'generate image', 'search images',
                'whatsapp', 'email', 'system', 'exit', 'read_screen'
            ]):
                return [result]
            else:
                return ['general']
                
        except Exception as e:
            print(f" AI classification failed: {e}")
            return ['general']
    
    def _update_avg_time(self, elapsed_ms: float):
        """Update average response time"""
        total = self.stats['total_queries']
        current_avg = self.stats['avg_response_time']
        self.stats['avg_response_time'] = ((current_avg * (total - 1)) + elapsed_ms) / total
    
    def get_stats(self) -> Dict:
        """Get routing statistics"""
        total = self.stats['total_queries']
        if total == 0:
            return self.stats
        
        return {
            'pattern_match_rate': f"{(self.stats['pattern_matched'] / total * 100):.1f}%",
            'ai_classify_rate': f"{(self.stats['ai_classified'] / total * 100):.1f}%",
            'avg_response_time_ms': f"{self.stats['avg_response_time']:.2f}"
        }
    
    
    def clear_cache(self):
        """Clear LRU cache"""
        self._classify_with_context.cache_clear()
    
    def _handle_contextual_intent(self, query: str) -> Optional[List[str]]:
        """
        Handle high-level contextual intents like 'I want to code'
        Returns command list if matched, None otherwise
        """
        if not alias_resolver:
            return None
        
        query_lower = query.lower()
        
        # Check contextual patterns
        if self.CONTEXTUAL_PATTERNS['want_to_code'].search(query):
            app_name, _ = alias_resolver.resolve_alias("ide")
            if app_name:
                return [f'open {app_name}']
        
        if self.CONTEXTUAL_PATTERNS['want_to_browse'].search(query):
            app_name, _ = alias_resolver.resolve_alias("browser")
            if app_name:
                return [f'open {app_name}']
        
        if self.CONTEXTUAL_PATTERNS['want_music'].search(query):
            app_name, search_query = alias_resolver.resolve_with_context("music")
            if app_name and search_query:
                return [f'play {search_query}']
            elif app_name:
                return [f'open {app_name}']
        
        if self.CONTEXTUAL_PATTERNS['want_to_message'].search(query):
            app_name, _ = alias_resolver.resolve_alias("messaging")
            if app_name:
                return [f'open {app_name}']
        
        return None
    
    def _detect_temporal_context(self, query: str) -> Optional[str]:
        """
        Detect temporal context in file-related queries.
        Returns: 'yesterday', 'this_week', 'today', 'recently', or None
        """
        for time_key, pattern in self.TEMPORAL_PATTERNS.items():
            if pattern.search(query):
                return time_key
        return None

    
    def get_capability_suggestions(self, query: str) -> List[str]:
        """Get capability suggestions based on query"""
        if not capability_registry:
            return []
        
        # Search capabilities
        results = capability_registry.search_capabilities(query)
        
        # Return top 3 capability IDs
        return [cap.id for cap, score in results[:3]]


# Global instance
_intent_router_fixed = None

def get_intent_router_fixed() -> IntentRouterFixed:
    """Get or create global intent router"""
    global _intent_router_fixed
    if _intent_router_fixed is None:
        _intent_router_fixed = IntentRouterFixed()
    return _intent_router_fixed
