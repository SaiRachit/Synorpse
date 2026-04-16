"""
Proactive Behaviors - Makes agent suggest and take actions autonomously
Learns from user patterns and context to anticipate needs
"""
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
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


@dataclass
class ProactiveSuggestion:
    """A proactive action suggestion"""
    action_description: str
    action_type: str
    action_parameters: Dict
    confidence: float  
    reasoning: str
    priority: int  
    context: Dict
    created_at: float


class PatternAnalyzer:
    """Analyzes user behavior patterns for proactive actions"""
    
    def __init__(self):
        self.patterns_cache = {}
        self._init_db()
    
    def _init_db(self):
        """Initialize pattern analysis tables"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS behavior_patterns (
                    id SERIAL PRIMARY KEY,
                    pattern_name VARCHAR(200) NOT NULL,
                    time_of_day VARCHAR(20),  -- morning, afternoon, evening, night
                    day_of_week VARCHAR(20),  -- monday, tuesday, etc.
                    typical_action VARCHAR(100) NOT NULL,
                    action_parameters JSONB DEFAULT '{}'::jsonb,
                    occurrence_count INT DEFAULT 1,
                    last_occurred TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    confidence FLOAT DEFAULT 0.0,
                    metadata JSONB DEFAULT '{}'::jsonb
                );
                
                CREATE INDEX IF NOT EXISTS idx_behavior_time ON behavior_patterns(time_of_day, day_of_week);
                CREATE INDEX IF NOT EXISTS idx_behavior_action ON behavior_patterns(typical_action);
            """)
            conn.commit()
            conn.close()
        except:
            pass
    
    def analyze_current_context(self) -> Dict:
        """Analyze current time/context for pattern matching"""
        now = datetime.now()
        hour = now.hour
        
        if 5 <= hour < 12:
            time_of_day = "morning"
        elif 12 <= hour < 17:
            time_of_day = "afternoon"
        elif 17 <= hour < 21:
            time_of_day = "evening"
        else:
            time_of_day = "night"
        
        day_of_week = now.strftime("%A").lower()
        
        return {
            'time_of_day': time_of_day,
            'day_of_week': day_of_week,
            'hour': hour,
            'is_weekend': day_of_week in ['saturday', 'sunday'],
            'timestamp': now.isoformat()
        }
    
    def record_action(self, action_type: str, parameters: Dict):
        """Record user action for pattern learning"""
        try:
            context = self.analyze_current_context()
            
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """SELECT id, occurrence_count FROM behavior_patterns 
                   WHERE typical_action = %s 
                   AND time_of_day = %s 
                   AND day_of_week = %s
                   LIMIT 1""",
                (action_type, context['time_of_day'], context['day_of_week'])
            )
            existing = cur.fetchone()
            
            if existing:
                pattern_id, count = existing
                new_count = count + 1
                confidence = min(new_count / 10.0, 1.0)  
                
                cur.execute(
                    """UPDATE behavior_patterns 
                       SET occurrence_count = %s, confidence = %s, last_occurred = NOW()
                       WHERE id = %s""",
                    (new_count, confidence, pattern_id)
                )
            else:
                pattern_name = f"{action_type}_{context['time_of_day']}_{context['day_of_week']}"
                cur.execute(
                    """INSERT INTO behavior_patterns 
                       (pattern_name, time_of_day, day_of_week, typical_action, action_parameters, confidence)
                       VALUES (%s, %s, %s, %s, %s, 0.1)""",
                    (pattern_name, context['time_of_day'], context['day_of_week'],
                     action_type, Json(parameters))
                )
            
            conn.commit()
            conn.close()
        except:
            pass
    
    def get_expected_patterns(self) -> List[Tuple[str, Dict, float]]:
        """
        Get patterns expected at current time/context
        Returns list of (action_type, parameters, confidence)
        """
        try:
            context = self.analyze_current_context()
            
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """SELECT typical_action, action_parameters, confidence
                   FROM behavior_patterns
                   WHERE time_of_day = %s 
                   AND day_of_week = %s
                   AND confidence > 0.5
                   ORDER BY confidence DESC, occurrence_count DESC
                   LIMIT 5""",
                (context['time_of_day'], context['day_of_week'])
            )
            
            patterns = cur.fetchall()
            conn.close()
            
            return patterns
        except:
            return []


class ContextMonitor:
    """Monitors system and user context for proactive triggers"""
    
    def __init__(self):
        self.last_check = time.time()
        self.check_interval = 300 
    
    def get_system_context(self) -> Dict:
        """Get current system context"""
        context = {}
        
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute(
                """SELECT action_type, action_details, status, created_at
                   FROM automation_logs
                   WHERE created_at > NOW() - INTERVAL '1 hour'
                   AND status = 'success'
                   ORDER BY created_at DESC
                   LIMIT 10"""
            )
            recent_actions = cur.fetchall()
            context['recent_actions'] = [
                {'type': a[0], 'details': a[1], 'time': a[3]}
                for a in recent_actions
            ]
            
            cur.execute(
                """SELECT DISTINCT metadata->>'app_name' as app
                   FROM automation_logs
                   WHERE action_type = 'open_app'
                   AND status = 'success'
                   AND created_at > NOW() - INTERVAL '30 minutes'"""
            )
            context['open_apps'] = [row[0] for row in cur.fetchall() if row[0]]
            
            cur.execute(
                """SELECT content FROM chat_messages
                   WHERE role = 'user'
                   AND created_at > NOW() - INTERVAL '1 hour'
                   ORDER BY created_at DESC
                   LIMIT 5"""
            )
            context['recent_topics'] = [row[0][:100] for row in cur.fetchall()]
            
            conn.close()
        except:
            pass
        
        return context
    
    def detect_triggers(self, context: Dict) -> List[Dict]:
        """Detect triggers for proactive actions"""
        triggers = []
        
        if context.get('open_apps'):
            triggers.append({
                'type': 'idle_with_apps_open',
                'confidence': 0.6,
                'data': {'apps': context['open_apps']}
            })
        
        recent = context.get('recent_actions', [])
        if len(recent) >= 3:
            action_types = [a['type'] for a in recent[:3]]
            if len(set(action_types)) == 1: 
                triggers.append({
                    'type': 'repetitive_action',
                    'confidence': 0.8,
                    'data': {'action_type': action_types[0]}
                })
        
        return triggers


class ProactiveSuggestionEngine:
    """Generates and manages proactive suggestions"""
    
    def __init__(self):
        self.pattern_analyzer = PatternAnalyzer()
        self.context_monitor = ContextMonitor()
        self.suggestion_history = []
    
    def generate_suggestions(self, force: bool = False) -> List[ProactiveSuggestion]:
        """
        Generate proactive suggestions based on patterns and context
        """
        suggestions = []
        
        if not force and time.time() - self.context_monitor.last_check < self.context_monitor.check_interval:
            return suggestions
        
        self.context_monitor.last_check = time.time()
        
        system_context = self.context_monitor.get_system_context()
        time_context = self.pattern_analyzer.analyze_current_context()
        
        expected_patterns = self.pattern_analyzer.get_expected_patterns()
        
        for action_type, parameters, confidence in expected_patterns:
            if confidence > 0.7:  
                suggestion = self._create_pattern_suggestion(
                    action_type, parameters, confidence, time_context
                )
                if suggestion:
                    suggestions.append(suggestion)
        
        triggers = self.context_monitor.detect_triggers(system_context)
        
        for trigger in triggers:
            if trigger['confidence'] > 0.6:
                suggestion = self._create_trigger_suggestion(
                    trigger, system_context
                )
                if suggestion:
                    suggestions.append(suggestion)
        
        if groq_client and (expected_patterns or triggers):
            ai_suggestions = self._generate_ai_suggestions(
                system_context, time_context, expected_patterns, triggers
            )
            suggestions.extend(ai_suggestions)
        
        suggestions.sort(key=lambda s: (s.priority, s.confidence), reverse=True)
        
        return suggestions[:3]  
    
    def _create_pattern_suggestion(self, action_type: str, parameters: Dict,
                                   confidence: float, context: Dict) -> Optional[ProactiveSuggestion]:
        """Create suggestion from learned pattern"""
        
        action_descriptions = {
            'play': f"Play music (you usually do this {context['time_of_day']})",
            'open': f"Open {parameters.get('target', 'application')}",
            'search': f"Search for {parameters.get('query', 'information')}",
        }
        
        description = action_descriptions.get(action_type, f"Execute {action_type}")
        
        return ProactiveSuggestion(
            action_description=description,
            action_type=action_type,
            action_parameters=parameters,
            confidence=confidence,
            reasoning=f"You typically do this on {context['day_of_week']} {context['time_of_day']}",
            priority=3,
            context=context,
            created_at=time.time()
        )
    
    def _create_trigger_suggestion(self, trigger: Dict, context: Dict) -> Optional[ProactiveSuggestion]:
        """Create suggestion from context trigger"""
        
        if trigger['type'] == 'idle_with_apps_open':
            apps = trigger['data'].get('apps', [])
            if apps:
                return ProactiveSuggestion(
                    action_description=f"Close unused apps: {', '.join(apps[:2])}",
                    action_type='close',
                    action_parameters={'apps': apps},
                    confidence=trigger['confidence'],
                    reasoning="You have apps open but haven't used them recently",
                    priority=2,
                    context=context,
                    created_at=time.time()
                )
        
        elif trigger['type'] == 'repetitive_action':
            action_type = trigger['data'].get('action_type')
            return ProactiveSuggestion(
                action_description=f"Create shortcut for repeated {action_type} action?",
                action_type='create_shortcut',
                action_parameters={'action': action_type},
                confidence=trigger['confidence'],
                reasoning="You've been repeating this action",
                priority=4,
                context=context,
                created_at=time.time()
            )
        
        return None
    
    def _generate_ai_suggestions(self, system_context: Dict, time_context: Dict,
                                patterns: List, triggers: List) -> List[ProactiveSuggestion]:
        """Use AI to generate intelligent suggestions"""
        if not groq_client:
            return []
        
        try:
            prompt = f"""You are a proactive AI assistant. Based on user context, suggest helpful actions.

Current Context:
- Time: {time_context['time_of_day']}, {time_context['day_of_week']}
- Recent actions: {[a['type'] for a in system_context.get('recent_actions', [])][:3]}
- Open apps: {system_context.get('open_apps', [])}
- Recent topics: {system_context.get('recent_topics', [])}

Learned Patterns:
{[f"{p[0]} (confidence: {p[2]:.1%})" for p in patterns[:3]]}

Detected Triggers:
{[t['type'] for t in triggers]}

Generate 1-2 proactive suggestions. Return JSON array:
[
  {{
    "action_description": "Brief user-facing description",
    "action_type": "open|search|play|close|analyze|suggest",
    "action_parameters": {{"key": "value"}},
    "confidence": 0.0-1.0,
    "reasoning": "Why this suggestion makes sense",
    "priority": 1-5
  }}
]

Guidelines:
- Be genuinely helpful, not annoying
- High confidence only for strong patterns
- Consider time of day and user habits
- Don't suggest if already doing
- Make it actionable

Example:
If user searches for news every morning, suggest "Search for today's news" at morning time.

Return ONLY JSON array, no markdown."""

            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "Generate proactive suggestions. Return ONLY JSON array."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            result = response.choices[0].message.content.strip()
            
            # Clean JSON
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()
            
            import json
            suggestions_data = json.loads(result)
            
            suggestions = []
            for data in suggestions_data:
                suggestion = ProactiveSuggestion(
                    action_description=data['action_description'],
                    action_type=data['action_type'],
                    action_parameters=data.get('action_parameters', {}),
                    confidence=data.get('confidence', 0.7),
                    reasoning=data.get('reasoning', ''),
                    priority=data.get('priority', 3),
                    context=time_context,
                    created_at=time.time()
                )
                suggestions.append(suggestion)
            
            return suggestions
            
        except Exception as e:
            print(f" AI suggestion generation failed: {e}")
            return []
    
    def present_suggestion(self, suggestion: ProactiveSuggestion) -> bool:
        """
        Present suggestion to user and return whether to execute
        Returns True if user wants to execute, False otherwise
        """
        print(f"Action: {suggestion.action_description}")
        print(f"Reason: {suggestion.reasoning}")
        print(f"Confidence: {suggestion.confidence:.1%}")
        
        response = input("Execute this action? (yes/no/never): ").strip().lower()
        
        if response == 'never':
            # Learn to avoid this suggestion type
            self._record_rejected_suggestion(suggestion)
            return False
        
        if response in ['yes', 'y']:
            self.suggestion_history.append({
                'suggestion': suggestion,
                'accepted': True,
                'timestamp': time.time()
            })
            return True
        
        self.suggestion_history.append({
            'suggestion': suggestion,
            'accepted': False,
            'timestamp': time.time()
        })
        return False
    
    def _record_rejected_suggestion(self, suggestion: ProactiveSuggestion):
        """Record permanently rejected suggestion types"""
        try:
            conn = psycopg2.connect(
                dbname=DB_NAME, user=DB_USER,
                password=DB_PASSWORD, host=DB_HOST
            )
            cur = conn.cursor()
            
            cur.execute("""
                CREATE TABLE IF NOT EXISTS rejected_suggestions (
                    id SERIAL PRIMARY KEY,
                    action_type VARCHAR(100) NOT NULL,
                    action_parameters JSONB DEFAULT '{}'::jsonb,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cur.execute(
                "INSERT INTO rejected_suggestions (action_type, action_parameters) VALUES (%s, %s)",
                (suggestion.action_type, Json(suggestion.action_parameters))
            )
            
            conn.commit()
            conn.close()
        except:
            pass

_suggestion_engine = None

def get_suggestion_engine() -> ProactiveSuggestionEngine:
    """Get or create global suggestion engine"""
    global _suggestion_engine
    if _suggestion_engine is None:
        _suggestion_engine = ProactiveSuggestionEngine()
    return _suggestion_engine