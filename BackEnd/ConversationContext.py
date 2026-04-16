"""
ConversationContext - Manages conversation history and context awareness
Enables the agent to maintain coherent multi-turn conversations
"""
import time
import json
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import Json
from dotenv import dotenv_values

env_vars = dotenv_values(".env")
DB_NAME = env_vars.get("DB_NAME", "synorpse_chat")
DB_USER = env_vars.get("DB_USER", "postgres")
DB_PASSWORD = env_vars.get("DB_PASSWORD")
DB_HOST = env_vars.get("DB_HOST", "localhost")


@dataclass
class ConversationTurn:
    """Represents a single turn in the conversation"""
    id: str
    user_message: str
    assistant_response: str
    timestamp: float
    intent: Optional[str] = None
    capabilities_used: List[str] = field(default_factory=list)
    entities: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionContext:
    """Current session context"""
    session_id: str
    started_at: float
    current_topic: Optional[str] = None
    active_goals: List[str] = field(default_factory=list)
    user_preferences: Dict[str, Any] = field(default_factory=dict)
    recent_entities: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[ConversationTurn] = field(default_factory=list)
    last_query_pattern: Optional[Dict[str, str]] = None
    last_user_query: Optional[str] = None
    active_file: Optional[str] = None


class ConversationContext:
    """
    Manages conversation context and history
    Provides context-aware understanding for multi-turn conversations
    """
    
    def __init__(self, context_window: int = 10):
        self.context_window = context_window  # Number of recent turns to keep in memory
        self.current_session: Optional[SessionContext] = None
        self._init_db()
        self._start_new_session()
    
    def _init_db(self):
        """Initialize conversation context tables"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            # Conversation turns table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversation_turns (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(100) NOT NULL,
                    user_message TEXT NOT NULL,
                    assistant_response TEXT NOT NULL,
                    intent VARCHAR(100),
                    capabilities_used JSONB DEFAULT '[]'::jsonb,
                    entities JSONB DEFAULT '{}'::jsonb,
                    metadata JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_conversation_turns_session 
                ON conversation_turns(session_id);
                
                CREATE INDEX IF NOT EXISTS idx_conversation_turns_time 
                ON conversation_turns(created_at);
            """)
            
            # User preferences table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id SERIAL PRIMARY KEY,
                    preference_key VARCHAR(100) UNIQUE NOT NULL,
                    preference_value JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Session metadata table
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(100) UNIQUE NOT NULL,
                    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP WITH TIME ZONE,
                    turn_count INT DEFAULT 0,
                    metadata JSONB DEFAULT '{}'::jsonb
                );
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" ConversationContext DB init warning: {e}")
    
    def _start_new_session(self):
        """Start a new conversation session"""
        session_id = f"session_{int(time.time() * 1000)}"
        self.current_session = SessionContext(
            session_id=session_id,
            started_at=time.time()
        )
        
        # Log session start
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """INSERT INTO conversation_sessions (session_id)
                   VALUES (%s)""",
                (session_id,)
            )
            
            conn.commit()
            conn.close()
        except:
            pass
    
    def add_turn(self, user_message: str, assistant_response: str,
                 intent: str = None, capabilities_used: List[str] = None,
                 entities: Dict = None):
        """Add a conversation turn to the context"""
        turn_id = f"turn_{int(time.time() * 1000)}"
        
        turn = ConversationTurn(
            id=turn_id,
            user_message=user_message,
            assistant_response=assistant_response,
            timestamp=time.time(),
            intent=intent,
            capabilities_used=capabilities_used or [],
            entities=entities or {}
        )
        
        # Add to session history
        self.current_session.conversation_history.append(turn)
        
        # Keep only recent turns in memory
        if len(self.current_session.conversation_history) > self.context_window:
            self.current_session.conversation_history = \
                self.current_session.conversation_history[-self.context_window:]
        
        # Update recent entities
        if entities:
            self.current_session.recent_entities.update(entities)
        
        # Extract and store query pattern from user message
        pattern = self._extract_query_pattern(user_message)
        if pattern:
            self.current_session.last_query_pattern = pattern
        
        # Store last user query
        self.current_session.last_user_query = user_message
        
        # Save to database
        self._save_turn_to_db(turn)
    
    def _save_turn_to_db(self, turn: ConversationTurn):
        """Save conversation turn to database"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """INSERT INTO conversation_turns 
                   (session_id, user_message, assistant_response, intent, 
                    capabilities_used, entities, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (self.current_session.session_id, turn.user_message,
                 turn.assistant_response, turn.intent,
                 Json(turn.capabilities_used), Json(turn.entities),
                 Json(turn.metadata))
            )
            
            # Update session turn count
            cur.execute(
                """UPDATE conversation_sessions 
                   SET turn_count = turn_count + 1
                   WHERE session_id = %s""",
                (self.current_session.session_id,)
            )
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" Failed to save conversation turn: {e}")
    
    def get_recent_context(self, num_turns: int = 5) -> str:
        """Get recent conversation context as formatted string"""
        recent_turns = self.current_session.conversation_history[-num_turns:]
        
        if not recent_turns:
            return "No recent conversation history."
        
        context = "Recent conversation:\n"
        for turn in recent_turns:
            context += f"User: {turn.user_message}\n"
            context += f"Assistant: {turn.assistant_response}\n\n"
        
        return context
    
    def get_last_user_message(self) -> Optional[str]:
        """Get the last user message"""
        if self.current_session.conversation_history:
            return self.current_session.conversation_history[-1].user_message
        return None
    
    def get_last_assistant_response(self) -> Optional[str]:
        """Get the last assistant response"""
        if self.current_session.conversation_history:
            return self.current_session.conversation_history[-1].assistant_response
        return None
    
    def get_last_intent(self) -> Optional[str]:
        """Get the intent from the last turn"""
        if self.current_session.conversation_history:
            return self.current_session.conversation_history[-1].intent
        return None
    
    def get_recent_entities(self) -> Dict[str, Any]:
        """Get recently mentioned entities"""
        return self.current_session.recent_entities.copy()
    
    def resolve_reference(self, query: str) -> str:
        """
        Resolve references in query using context
        Handles both explicit pronouns and implicit follow-up queries
        E.g., "that" -> last mentioned entity, "what about google" -> "stock price of google"
        """
        query_lower = query.lower().strip()
        
        # Check if this is a follow-up query (implicit context)
        if self._is_follow_up_query(query):
            expanded = self._expand_follow_up_query(query)
            if expanded and expanded != query:
                return expanded
        
        # Pronouns that might reference previous context (explicit)
        reference_words = ["it", "that", "this", "them", "those", "these"]
        
        has_reference = any(word in query_lower.split() for word in reference_words)
        
        if not has_reference:
            return query
        
        # Try to resolve from recent entities
        entities = self.get_recent_entities()
        
        # Get last topic/subject
        last_message = self.get_last_user_message()
        if last_message:
            # Simple resolution: append context
            resolved = f"{query} (referring to: {last_message})"
            return resolved
        
        return query
    
    def infer_intent_from_context(self, query: str) -> Optional[str]:
        """
        Infer intent using conversation context
        Helps with follow-up questions
        """
        query_lower = query.lower()
        
        # Check for follow-up patterns
        follow_up_patterns = [
            "what about", "how about", "and", "also",
            "more", "another", "again", "same"
        ]
        
        is_follow_up = any(pattern in query_lower for pattern in follow_up_patterns)
        
        if is_follow_up and self.current_session.conversation_history:
            # Use last intent as context
            last_intent = self.get_last_intent()
            if last_intent:
                return last_intent
        
        return None
    
    def get_conversation_summary(self) -> str:
        """Get a summary of the current conversation"""
        if not self.current_session.conversation_history:
            return "No conversation yet."
        
        turn_count = len(self.current_session.conversation_history)
        duration = time.time() - self.current_session.started_at
        
        # Get unique capabilities used
        all_capabilities = []
        for turn in self.current_session.conversation_history:
            all_capabilities.extend(turn.capabilities_used)
        unique_capabilities = list(set(all_capabilities))
        
        summary = f" **CONVERSATION SUMMARY**\n\n"
        summary += f"Session: {self.current_session.session_id}\n"
        summary += f"Duration: {duration/60:.1f} minutes\n"
        summary += f"Turns: {turn_count}\n"
        
        if unique_capabilities:
            summary += f"Capabilities used: {', '.join(unique_capabilities)}\n"
        
        if self.current_session.current_topic:
            summary += f"Current topic: {self.current_session.current_topic}\n"
        
        return summary
    
    def set_preference(self, key: str, value: Any):
        """Set a user preference"""
        self.current_session.user_preferences[key] = value
        
        # Save to database
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """INSERT INTO user_preferences (preference_key, preference_value)
                   VALUES (%s, %s)
                   ON CONFLICT (preference_key) 
                   DO UPDATE SET preference_value = EXCLUDED.preference_value,
                                 updated_at = CURRENT_TIMESTAMP""",
                (key, Json(value))
            )
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" Failed to save preference: {e}")
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference"""
        # Check session cache first
        if key in self.current_session.user_preferences:
            return self.current_session.user_preferences[key]
        
        # Load from database
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """SELECT preference_value FROM user_preferences
                   WHERE preference_key = %s""",
                (key,)
            )
            
            result = cur.fetchone()
            conn.close()
            
            if result:
                value = result[0]
                self.current_session.user_preferences[key] = value
                return value
        except:
            pass
        
        return default
    
    def extract_entities(self, text: str) -> Dict[str, Any]:
        """
        Extract entities from text
        Simple implementation - can be enhanced with NER
        """
        entities = {}
        
        # Extract potential file names
        if any(ext in text.lower() for ext in ['.pdf', '.docx', '.txt', '.xlsx']):
            # Simple extraction
            words = text.split()
            for word in words:
                if any(ext in word.lower() for ext in ['.pdf', '.docx', '.txt', '.xlsx']):
                    entities['file'] = word
        
        # Extract potential app names
        common_apps = ['notepad', 'chrome', 'spotify', 'excel', 'word', 'vscode']
        for app in common_apps:
            if app in text.lower():
                entities['app'] = app
        
        # Extract potential email addresses
        import re
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, text)
        if emails:
            entities['email'] = emails[0]
        
        return entities
    
    def update_topic(self, topic: str):
        """Update the current conversation topic"""
        self.current_session.current_topic = topic
    
    def add_goal(self, goal: str):
        """Add an active goal to the session"""
        if goal not in self.current_session.active_goals:
            self.current_session.active_goals.append(goal)
    
    def remove_goal(self, goal: str):
        """Remove a completed goal"""
        if goal in self.current_session.active_goals:
            self.current_session.active_goals.remove(goal)
    
    def get_active_goals(self) -> List[str]:
        """Get currently active goals"""
        return self.current_session.active_goals.copy()
    
    def set_active_file(self, file_path: str):
        """Set the active file for the session"""
        self.current_session.active_file = file_path
    
    def get_active_file(self) -> Optional[str]:
        """Get the active file for the session"""
        return self.current_session.active_file
    
    def clear_context(self):
        """Clear current session context and start fresh"""
        self._start_new_session()
    
    def get_context_for_ai(self, include_turns: int = 3) -> str:
        """
        Get formatted context string for AI prompts
        """
        context_parts = []
        
        # Recent conversation
        if self.current_session.conversation_history:
            recent = self.current_session.conversation_history[-include_turns:]
            context_parts.append("Recent conversation:")
            for turn in recent:
                context_parts.append(f"User: {turn.user_message}")
                context_parts.append(f"Assistant: {turn.assistant_response}")
        
        # Active goals
        if self.current_session.active_goals:
            context_parts.append(f"\nActive goals: {', '.join(self.current_session.active_goals)}")
        
        # Current topic
        if self.current_session.current_topic:
            context_parts.append(f"Current topic: {self.current_session.current_topic}")
        
        # Recent entities
        if self.current_session.recent_entities:
            context_parts.append(f"Recent entities: {self.current_session.recent_entities}")
        
        return "\n".join(context_parts)
    
    def _extract_query_pattern(self, query: str) -> Optional[Dict[str, str]]:
        """
        Extract the query pattern/template from a user query.
        Returns: {"type": "stock_price", "template": "stock price of {entity}", "entity": "nvidia"}
        """
        import re
        
        query_lower = query.lower().strip()
        
        # Define patterns for different query types
        patterns = {
            "stock_price": [
                (r'(?:what is |what\'s )?(?:the )?(?:latest |current )?(?:stock )?price (?:of |for )?(.+?)(?:\s+stock)?$', 'stock price of {entity}'),
                (r'(.+?) (?:stock|share) price', 'stock price of {entity}'),
                (r'how much is (.+?) (?:stock|trading|worth)', 'stock price of {entity}'),
                (r'(?:stock|share) (?:price )?(?:of |for )?(.+)', 'stock price of {entity}')
            ],
            "weather": [
                (r'(?:what is |what\'s )?(?:the )?weather (?:in |at |for )?(.+)', 'weather in {entity}'),
                (r'(?:what is |what\'s )?(?:the )?temperature (?:in |at )?(.+)', 'temperature in {entity}'),
                (r'how (?:hot|cold|warm) is it in (.+)', 'weather in {entity}')
            ],
            "news": [
                (r'(?:latest |recent )?news (?:about |on |for )?(.+)', 'news about {entity}'),
                (r'what\'?s happening (?:with |in )?(.+)', 'news about {entity}'),
                (r'updates? (?:on |about )?(.+)', 'news about {entity}')
            ],
            "info": [
                (r'who is (.+)', 'who is {entity}'),
                (r'what is (.+)', 'what is {entity}'),
                (r'tell me about (.+)', 'tell me about {entity}')
            ]
        }
        
        # Try to match each pattern
        for pattern_type, pattern_list in patterns.items():
            for regex, template in pattern_list:
                match = re.search(regex, query_lower)
                if match:
                    entity = match.group(1).strip()
                    # Clean up entity
                    entity = re.sub(r'\s+', ' ', entity)
                    return {
                        "type": pattern_type,
                        "template": template,
                        "entity": entity
                    }
        
        return None
    
    def _is_follow_up_query(self, query: str) -> bool:
        """
        Detect if a query is a follow-up to the previous query.
        Indicators: "what about X", "how about X", "and X", short queries, etc.
        """
        import re
        
        query_lower = query.lower().strip()
        
        if not self.current_session.last_query_pattern:
            return False
            
        # CRITICAL: If query starts with an action command, it's NOT a follow-up
        action_starters = ['open', 'play', 'send', 'generate', 'show', 'whatsapp', 'email', 'create', 'find', 'locate', 'search']
        if any(query_lower.startswith(s) for s in action_starters):
            return False
        
        # Explicit follow-up indicators
        follow_up_patterns = [
            r'^(?:what|how) about (.+)',
            r'^(?:and |also )?(.+?)(?:\s+too)?$',
            r'^how about (.+)',
            r'^what about (.+)',
            r'^and (.+)',
        ]
        
        for pattern in follow_up_patterns:
            if re.match(pattern, query_lower):
                return True
        
        # Short queries (1-3 words) might be follow-ups if recent context exists
        word_count = len(query.split())
        if word_count <= 3 and self.current_session.last_user_query:
            # Check if it's not a complete question
            if not any(query_lower.startswith(q) for q in ['what', 'who', 'where', 'when', 'why', 'how', 'is', 'are', 'do', 'does']):
                return True
        
        return False
    
    def _expand_follow_up_query(self, query: str) -> str:
        """
        Expand a follow-up query using the last query pattern.
        E.g., "what about google" + last pattern "stock price of {entity}" -> "stock price of google"
        """
        import re
        
        query_lower = query.lower().strip()
        last_pattern = self.current_session.last_query_pattern
        
        if not last_pattern:
            return query
        
        # Extract the entity from the follow-up query
        entity = None
        
        # Try explicit follow-up patterns
        follow_up_extractions = [
            r'^(?:what|how) about (.+)',
            r'^and (.+)',
            r'^(.+?)(?:\s+too)?$'
        ]
        
        for pattern in follow_up_extractions:
            match = re.match(pattern, query_lower)
            if match:
                entity = match.group(1).strip()
                break
        
        if not entity:
            # For very short queries, use the whole query as entity
            if len(query.split()) <= 3:
                entity = query.strip()
        
        if entity:
            # Clean up entity
            entity = re.sub(r'\s+', ' ', entity)
            
            # Expand using the template
            expanded = last_pattern["template"].format(entity=entity)
            
            # Add "latest" or "current" prefix for certain types
            if last_pattern["type"] in ["stock_price", "weather", "news"]:
                if "latest" not in expanded and "current" not in expanded:
                    expanded = f"latest {expanded}"
            
            return expanded
        
        return query


# Global instance
_conversation_context = None

def get_conversation_context() -> ConversationContext:
    """Get or create global conversation context"""
    global _conversation_context
    if _conversation_context is None:
        _conversation_context = ConversationContext()
    return _conversation_context
