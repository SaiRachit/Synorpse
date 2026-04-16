"""
CapabilityRegistry - Central registry of all agent capabilities
Makes the agent self-aware of what it can do and enables intelligent capability selection
"""
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import psycopg2
from psycopg2.extras import Json
from dotenv import dotenv_values

env_vars = dotenv_values(".env")
DB_NAME = env_vars.get("DB_NAME", "synorpse_chat")
DB_USER = env_vars.get("DB_USER", "postgres")
DB_PASSWORD = env_vars.get("DB_PASSWORD")
DB_HOST = env_vars.get("DB_HOST", "localhost")


@dataclass
class Capability:
    """Represents a single capability the agent can perform"""
    id: str
    name: str
    category: str
    description: str
    module: str
    function_name: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    examples: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    can_run_concurrent: bool = True
    requires_confirmation: bool = False
    estimated_duration: str = "fast"  # fast, medium, slow
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CapabilityRegistry:
    """
    Central registry of all agent capabilities
    Provides self-awareness and intelligent capability selection
    """
    
    def __init__(self):
        self.capabilities: Dict[str, Capability] = {}
        self._init_db()
        self._register_core_capabilities()
    
    def _init_db(self):
        """Initialize capability tracking tables"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            # Track capability usage
            cur.execute("""
                CREATE TABLE IF NOT EXISTS capability_usage (
                    id SERIAL PRIMARY KEY,
                    capability_id VARCHAR(100) NOT NULL,
                    used_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT TRUE,
                    execution_time_ms INT,
                    context JSONB DEFAULT '{}'::jsonb,
                    error_message TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_capability_usage_id 
                ON capability_usage(capability_id);
                
                CREATE INDEX IF NOT EXISTS idx_capability_usage_time 
                ON capability_usage(used_at);
            """)
            
            # Track capability combinations (which capabilities are used together)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS capability_combinations (
                    id SERIAL PRIMARY KEY,
                    capability_ids JSONB NOT NULL,
                    used_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    success BOOLEAN DEFAULT TRUE,
                    context JSONB DEFAULT '{}'::jsonb
                );
                
                CREATE INDEX IF NOT EXISTS idx_capability_combinations_time 
                ON capability_combinations(used_at);
            """)
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" CapabilityRegistry DB init warning: {e}")
    
    def _register_core_capabilities(self):
        """Register all core system capabilities"""
        
        # Communication capabilities
        self.register(Capability(
            id="chat",
            name="General Conversation",
            category="communication",
            description="Have natural conversations, answer questions, provide information",
            module="ChatBot",
            function_name="ChatBot",
            examples=[
                "tell me about quantum physics",
                "what's the meaning of life?",
                "explain how AI works"
            ],
            keywords=["chat", "talk", "conversation", "explain", "tell", "what", "how", "why"],
            can_run_concurrent=True,
            estimated_duration="fast"
        ))
        
        self.register(Capability(
            id="send_email",
            name="Send Email",
            category="communication",
            description="Compose and send emails using natural language",
            module="Automation",
            function_name="SendEmail",
            parameters={"query": "string"},
            examples=[
                "send email to john@example.com about meeting tomorrow",
                "email Sarah saying I'll be late"
            ],
            keywords=["email", "send", "mail", "compose"],
            can_run_concurrent=True,
            requires_confirmation=True,
            estimated_duration="medium"
        ))
        
        self.register(Capability(
            id="send_whatsapp",
            name="Send WhatsApp Message",
            category="communication",
            description="Send WhatsApp messages to contacts",
            module="Automation",
            function_name="SendWhatsApp",
            parameters={"query": "string"},
            examples=[
                "send whatsapp to Mom saying I'm on my way",
                "whatsapp John about the project"
            ],
            keywords=["whatsapp", "message", "text"],
            can_run_concurrent=True,
            requires_confirmation=True,
            estimated_duration="medium"
        ))
        
        # Information capabilities
        self.register(Capability(
            id="realtime_search",
            name="Real-time Web Search",
            category="information",
            description="Search the web for current information with AI-powered synthesis",
            module="RealTimeSearchEngine",
            function_name="RealtimeSearch",
            parameters={"query": "string"},
            examples=[
                "search for latest AI news",
                "find information about quantum computing",
                "what's the weather today?"
            ],
            keywords=["search", "find", "look up", "research", "information", "web"],
            can_run_concurrent=True,
            estimated_duration="medium"
        ))
        
        self.register(Capability(
            id="google_search",
            name="Google Search",
            category="information",
            description="Perform Google web search and open results",
            module="Automation",
            function_name="GoogleSearch",
            parameters={"query": "string"},
            examples=[
                "google search python tutorials",
                "search google for best restaurants nearby"
            ],
            keywords=["google", "search"],
            can_run_concurrent=True,
            estimated_duration="fast"
        ))
        
        self.register(Capability(
            id="youtube_search",
            name="YouTube Search",
            category="information",
            description="Search YouTube and open results",
            module="Automation",
            function_name="YouTubeSearch",
            parameters={"query": "string"},
            examples=[
                "search youtube for cooking tutorials",
                "find videos about machine learning"
            ],
            keywords=["youtube", "video", "watch"],
            can_run_concurrent=True,
            estimated_duration="fast"
        ))
        
        self.register(Capability(
            id="play_youtube",
            name="Play YouTube Video",
            category="information",
            description="Play a YouTube video directly",
            module="Automation",
            function_name="PlayYouTube",
            parameters={"query": "string"},
            examples=[
                "play despacito on youtube",
                "play relaxing music"
            ],
            keywords=["play", "youtube", "music", "video"],
            can_run_concurrent=False,
            estimated_duration="fast"
        ))
        
        # Automation capabilities
        self.register(Capability(
            id="open_app",
            name="Open Application",
            category="automation",
            description="Open applications on the system",
            module="Automation",
            function_name="OpenApp",
            parameters={"app": "string"},
            examples=[
                "open notepad",
                "launch chrome",
                "start spotify"
            ],
            keywords=["open", "launch", "start", "run"],
            can_run_concurrent=True,
            estimated_duration="fast"
        ))
        
        self.register(Capability(
            id="close_app",
            name="Close Application",
            category="automation",
            description="Close running applications",
            module="Automation",
            function_name="CloseApp",
            parameters={"app": "string"},
            examples=[
                "close notepad",
                "quit chrome",
                "exit spotify"
            ],
            keywords=["close", "quit", "exit", "stop"],
            can_run_concurrent=True,
            estimated_duration="fast"
        ))
        
        self.register(Capability(
            id="open_file",
            name="Open File",
            category="automation",
            description="Find and open files using fuzzy search",
            module="Automation",
            function_name="OpenFile",
            parameters={"search_term": "string"},
            examples=[
                "open my resume",
                "open project notes",
                "find and open budget spreadsheet"
            ],
            keywords=["open", "file", "document", "find"],
            can_run_concurrent=True,
            estimated_duration="medium"
        ))
        
        self.register(Capability(
            id="system_control",
            name="System Control",
            category="automation",
            description="Control system settings (volume, mute, etc.)",
            module="Automation",
            function_name="System",
            parameters={"command": "string"},
            examples=[
                "mute volume",
                "unmute",
                "volume up",
                "volume down"
            ],
            keywords=["mute", "unmute", "volume", "sound"],
            can_run_concurrent=True,
            estimated_duration="fast"
        ))
        
        # Creation capabilities
        self.register(Capability(
            id="generate_image",
            name="Generate Image",
            category="creation",
            description="Generate images using AI based on text descriptions",
            module="ImageGeneration",
            function_name="LocalImageGenerator.generate_image",
            parameters={"prompt": "string"},
            examples=[
                "generate an image of a sunset over mountains",
                "create a picture of a futuristic city",
                "make an image of a cute robot"
            ],
            keywords=["generate", "create", "make", "image", "picture", "draw"],
            can_run_concurrent=True,
            estimated_duration="slow"
        ))
        
        self.register(Capability(
            id="read_document",
            name="Read Document",
            category="creation",
            description="Read and analyze documents (PDF, DOCX, TXT)",
            module="DocumentReader",
            function_name="DocumentReader",
            parameters={"file_path": "string"},
            examples=[
                "read this document",
                "analyze this PDF",
                "what's in this file?"
            ],
            keywords=["read", "analyze", "document", "pdf", "file"],
            can_run_concurrent=True,
            estimated_duration="medium"
        ))
        
        # Memory capabilities
        self.register(Capability(
            id="remember_pattern",
            name="Learn Pattern",
            category="memory",
            description="Learn and remember user behavior patterns",
            module="ProactiveBehaviors",
            function_name="PatternAnalyzer.record_action",
            examples=[
                "remember this preference",
                "learn my habits"
            ],
            keywords=["remember", "learn", "pattern", "habit"],
            can_run_concurrent=True,
            estimated_duration="fast"
        ))
        
        self.register(Capability(
            id="recall_action",
            name="Recall Previous Action",
            category="memory",
            description="Remember and repeat previous actions",
            module="Automation",
            function_name="get_last_action_of_type",
            examples=[
                "do that again",
                "repeat last action",
                "what did I just do?"
            ],
            keywords=["again", "repeat", "last", "previous"],
            can_run_concurrent=True,
            estimated_duration="fast"
        ))
    
    def register(self, capability: Capability):
        """Register a new capability"""
        self.capabilities[capability.id] = capability
    
    def get_capability(self, capability_id: str) -> Optional[Capability]:
        """Get a specific capability by ID"""
        return self.capabilities.get(capability_id)
    
    def get_all_capabilities(self) -> List[Capability]:
        """Get all registered capabilities"""
        return list(self.capabilities.values())
    
    def get_by_category(self, category: str) -> List[Capability]:
        """Get all capabilities in a category"""
        return [cap for cap in self.capabilities.values() if cap.category == category]
    
    def get_categories(self) -> List[str]:
        """Get all capability categories"""
        return list(set(cap.category for cap in self.capabilities.values()))
    
    def search_capabilities(self, query: str) -> List[Tuple[Capability, float]]:
        """
        Search for capabilities matching a query
        Returns list of (capability, relevance_score) tuples
        """
        query_lower = query.lower()
        results = []
        
        for cap in self.capabilities.values():
            score = 0.0
            
            # Check keywords
            for keyword in cap.keywords:
                if keyword in query_lower:
                    score += 2.0
            
            # Check name and description
            if query_lower in cap.name.lower():
                score += 3.0
            if query_lower in cap.description.lower():
                score += 1.5
            
            # Check examples
            for example in cap.examples:
                if query_lower in example.lower():
                    score += 1.0
            
            if score > 0:
                results.append((cap, score))
        
        # Sort by relevance score
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def get_capability_summary(self) -> str:
        """Get a formatted summary of all capabilities"""
        categories = self.get_categories()
        summary = " **MY CAPABILITIES**\n\n"
        
        category_emojis = {
            "communication": "[COMM]",
            "information": "[INFO]",
            "automation": "[AUTO]",
            "creation": "[CREATE]",
            "memory": "[MEM]"
        }
        
        for category in sorted(categories):
            emoji = category_emojis.get(category, "")
            summary += f"{emoji} **{category.upper()}**\n"
            
            caps = self.get_by_category(category)
            for cap in caps:
                summary += f"   {cap.name}: {cap.description}\n"
            summary += "\n"
        
        return summary
    
    def get_capability_details(self, capability_id: str) -> str:
        """Get detailed information about a capability"""
        cap = self.get_capability(capability_id)
        if not cap:
            return f"Capability '{capability_id}' not found."
        
        details = f"**{cap.name}**\n"
        details += f"Category: {cap.category}\n"
        details += f"Description: {cap.description}\n\n"
        
        if cap.examples:
            details += "Examples:\n"
            for example in cap.examples[:3]:
                details += f"   \"{example}\"\n"
        
        details += f"\nSpeed: {cap.estimated_duration}\n"
        details += f"Can run concurrently: {'Yes' if cap.can_run_concurrent else 'No'}\n"
        
        if cap.requires_confirmation:
            details += " Requires confirmation before execution\n"
        
        return details
    
    def log_capability_usage(self, capability_id: str, success: bool = True, 
                            execution_time_ms: int = 0, context: Dict = None,
                            error_message: str = None):
        """Log capability usage for analytics"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """INSERT INTO capability_usage 
                   (capability_id, success, execution_time_ms, context, error_message)
                   VALUES (%s, %s, %s, %s, %s)""",
                (capability_id, success, execution_time_ms, 
                 Json(context or {}), error_message)
            )
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" Failed to log capability usage: {e}")
    
    def log_capability_combination(self, capability_ids: List[str], 
                                   success: bool = True, context: Dict = None):
        """Log when multiple capabilities are used together"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """INSERT INTO capability_combinations 
                   (capability_ids, success, context)
                   VALUES (%s, %s, %s)""",
                (Json(capability_ids), success, Json(context or {}))
            )
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f" Failed to log capability combination: {e}")
    
    def get_popular_capabilities(self, limit: int = 5) -> List[Tuple[str, int]]:
        """Get most frequently used capabilities"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """SELECT capability_id, COUNT(*) as usage_count
                   FROM capability_usage
                   WHERE used_at > NOW() - INTERVAL '30 days'
                   GROUP BY capability_id
                   ORDER BY usage_count DESC
                   LIMIT %s""",
                (limit,)
            )
            
            results = cur.fetchall()
            conn.close()
            return results
        except:
            return []
    
    def get_common_combinations(self, limit: int = 5) -> List[Tuple[List[str], int]]:
        """Get most common capability combinations"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """SELECT capability_ids, COUNT(*) as combo_count
                   FROM capability_combinations
                   WHERE used_at > NOW() - INTERVAL '30 days'
                   GROUP BY capability_ids
                   ORDER BY combo_count DESC
                   LIMIT %s""",
                (limit,)
            )
            
            results = [(row[0], row[1]) for row in cur.fetchall()]
            conn.close()
            return results
        except:
            return []


# Global instance
_capability_registry = None

def get_capability_registry() -> CapabilityRegistry:
    """Get or create global capability registry"""
    global _capability_registry
    if _capability_registry is None:
        _capability_registry = CapabilityRegistry()
    return _capability_registry
