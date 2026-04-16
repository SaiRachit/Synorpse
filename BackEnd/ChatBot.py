from groq import Groq
import datetime
from dotenv import dotenv_values
import time
import psycopg2
from psycopg2.extras import Json
import re

# Import capabilities documentation
try:
    from SystemCapabilities import format_capabilities_for_system_prompt, get_capabilities_summary
except ImportError:
    format_capabilities_for_system_prompt = lambda: ""
    get_capabilities_summary = lambda: ""

env_vars = dotenv_values(".env")

Username = env_vars.get("Username")
Assistantname = env_vars.get("Assistantname")
DB_NAME = env_vars.get("DB_NAME", "synorpse_chat")
DB_USER = env_vars.get("DB_USER", "postgres")
DB_PASSWORD = env_vars.get("DB_PASSWORD")
DB_HOST = env_vars.get("DB_HOST", "localhost")

# Load all Groq keys for rotation
GROQ_KEYS = [v for k, v in env_vars.items() if "GroqAPIKey" in k and v]
_current_key_index = 0

def get_groq_client():
    """Get the current Groq client based on rotation index"""
    if not GROQ_KEYS:
        return None
    return Groq(api_key=GROQ_KEYS[_current_key_index])

client = get_groq_client()

def rotate_groq_key():
    """Rotate to the next available Groq key"""
    global _current_key_index, client
    if not GROQ_KEYS:
        return
    _current_key_index = (_current_key_index + 1) % len(GROQ_KEYS)
    client = Groq(api_key=GROQ_KEYS[_current_key_index])

def _call_with_retry(**kwargs):
    """Call Groq completion with automatic key rotation on rate limits"""
    last_error = None
    for attempt in range(len(GROQ_KEYS)):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "rate_limit" in err_str:
                rotate_groq_key()
                last_error = e
                continue
            raise
    raise last_error

# Model settings
MODEL_CONVERSATIONAL = "llama-3.3-70b-versatile" # Switched back to 70b to ensure personality guidelines are followed

System = f"""You are {Assistantname}, an advanced AI assistant created by Sai Rachit Singh.

Key guidelines:
- Respond only in English, even if questions are in other languages
- Keep conversations engaging and natural like a friend
- Use current date/time information when relevant
- Format responses with Markdown when appropriate
- Maintain a warm, friendly tone
- If disrespected, firmly request an apology before continuing
- Answer questions directly without mentioning training data or implementation notes
- When asked "what did I just ask you?" or similar questions about previous messages, refer to the ENTIRE conversation history provided to you, not just the immediately previous message
- BE CONTEXT AWARE: If the user asks follow-up questions without full context (like "what about nvidia" after asking about Google stock), understand they're continuing the same topic

About your creator: Sai Rachit Singh was born on June 22, 2006. He is proficient in AI Language processing, NLP, and Deep Learning. Only mention his birthdate or age if specifically asked.

CREATOR'S SOCIAL PROFILES (share these when asked):
- LinkedIn: https://www.linkedin.com/in/sai-rachit-singh-1985b0317/
- GitHub: https://github.com/SaiRachit

When users ask for his LinkedIn, GitHub, or any social profile, provide the link directly.

{format_capabilities_for_system_prompt()}

IMPORTANT: When asked about recent actions (like "what did you just open?", "what file did I open?", "what email did you send?"), you will receive a list of recent automation logs. Use this information to answer accurately about what actions were performed.

WHEN ASKED "WHAT CAN YOU DO?" or similar questions about your capabilities:
- Provide a comprehensive but friendly overview of key features
- Use examples to illustrate capabilities
- Mention command chaining as a powerful feature
- Be enthusiastic about helping!
- Don't just list features - explain how they help the user

CONVERSATIONAL INTELLIGENCE:
- When offering to help with an action, phrase it clearly as a question
- Examples: "Would you like me to open BBC News?", "Shall I search YouTube for that?"
- This allows the user to simply say "yes" or "no" as a follow-up
- Keep offers concise and actionable"""

SystemChatBot = [
    {"role": "system", "content": System}
]

def init_db():
    """Initialize database and create tables"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST
        )
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id SERIAL PRIMARY KEY,
                role VARCHAR(50) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                metadata JSONB DEFAULT '{}'::jsonb
            );
            
            CREATE INDEX IF NOT EXISTS idx_messages_created_at ON chat_messages(created_at);
            CREATE INDEX IF NOT EXISTS idx_messages_role ON chat_messages(role);
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        print(f" Database initialization error: {e}")

def save_message(role, content, metadata=None):
    """Save message with metadata including query classification"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST
        )
        cur = conn.cursor()
        
        cur.execute(
            "INSERT INTO chat_messages (role, content, metadata) VALUES (%s, %s, %s)",
            (role, content, Json(metadata or {}))
        )
        conn.commit()
        conn.close()
    except:
        pass

def get_chat_history(limit=20):
    """Retrieve recent chat history with metadata"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST
        )
        cur = conn.cursor()
        
        cur.execute(
            "SELECT role, content, metadata FROM chat_messages ORDER BY created_at ASC LIMIT %s",
            (limit,)
        )
        messages = [
            {
                "role": role, 
                "content": content,
                "metadata": metadata or {}
            } 
            for role, content, metadata in cur.fetchall()
        ]
        conn.close()
        
        return messages
    except:
        return []

def get_recent_automation_logs(limit=5):
    """Retrieve recent automation logs for context"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST
        )
        cur = conn.cursor()
        
        cur.execute(
            "SELECT action_type, action_details, status, metadata, created_at FROM automation_logs ORDER BY created_at DESC LIMIT %s",
            (limit,)
        )
        logs = cur.fetchall()
        conn.close()
        
        return logs
    except:
        return []

def format_automation_context(logs):
    """Format automation logs into readable context for the AI"""
    if not logs:
        return "No recent automation actions found."
    
    context = "Recent automation actions:\n"
    for action_type, action_details, status, metadata, created_at in logs:
        context += f"- [{action_type}] {action_details} (Status: {status}, Time: {created_at})\n"
        if metadata and isinstance(metadata, dict):
            if 'files_opened' in metadata:
                for file_info in metadata['files_opened']:
                    context += f"  File: {file_info.get('file_name', 'Unknown')}\n"
            elif 'recipient' in metadata:
                context += f"  Recipient: {metadata['recipient']}\n"
            elif 'query' in metadata:
                context += f"  Query: {metadata['query']}\n"
    
    return context

def extract_topic_from_history(history):
    """Extract the main topic/subject from recent conversation"""
    if not history:
        return None
    
    recent_topics = []
    for msg in reversed(history[-5:]):
        if msg['role'] == 'user':
            content = msg.get('content', '')
            metadata = msg.get('metadata', {})
            
            query_type = metadata.get('query_type', '')
            if query_type == 'realtime':
                keywords = ['stock price', 'price of', 'about', 'who is', 'tell me about']
                for keyword in keywords:
                    if keyword in content.lower():
                        parts = content.lower().split(keyword)
                        if len(parts) > 1:
                            topic = parts[1].strip().split()[0:3]
                            recent_topics.append(' '.join(topic))
                            break
    
    return recent_topics[0] if recent_topics else None

def clear_chat_history():
    """Clear chat history to start fresh"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST
        )
        cur = conn.cursor()
        cur.execute("DELETE FROM chat_messages")
        conn.commit()
        conn.close()
    except:
        pass

def get_realtime_information():
    """Get current date and time information"""
    current_date_time = datetime.datetime.now()
    day = current_date_time.strftime("%A")
    date = current_date_time.strftime("%d")
    month = current_date_time.strftime("%B")
    year = current_date_time.strftime("%Y")
    hour = current_date_time.strftime("%H")
    minute = current_date_time.strftime("%M")
    
    return f"""Current real-time information:
Day: {day}
Date: {date} {month} {year}
Time: {hour}:{minute}"""

def clean_response(response):
    """Remove repetitive sentences or phrases"""
    if not response:
        return response
        
    sentences = response.split('. ')
    unique_sentences = []
    seen = set()
    
    for sentence in sentences:
        normalized = sentence.lower().strip()
        if normalized not in seen and len(normalized.split()) > 3:
            unique_sentences.append(sentence)
            seen.add(normalized)
    
    cleaned = '. '.join(unique_sentences)
    return cleaned if cleaned else response

def format_answer(answer):
    """Format answer with proper structure"""
    if not answer:
        return "I didn't generate a proper response. Please try rephrasing your question."
    
    answer = answer.replace("</s>", "").replace("</s", "").strip()
    answer = clean_response(answer)
    
    lines = answer.split('\n')
    non_empty_lines = [line.strip() for line in lines if line.strip()]
    
    return '\n'.join(non_empty_lines)

def is_asking_about_recent_actions(query):
    """Check if the user is asking about recent automation actions"""
    query_lower = query.lower()
    action_keywords = [
        "what did you", "what did i", "what file", "what pdf", "what document",
        "what app", "what application", "what did we", "what was opened",
        "what did you open", "what did you send", "what email", "what message",
        "recent", "just now", "earlier", "before", "last", "previously",
        "again", "same", "that", "repeat", "one more time", "do it again"
    ]
    
    return any(keyword in query_lower for keyword in action_keywords)

def is_asking_about_conversation(query):
    """Check if user is asking about previous conversation"""
    query_lower = query.lower()
    conversation_keywords = [
        "what did i just ask", "what was my question", "what did i say",
        "my previous question", "my last question", "earlier question",
        "what was i asking", "remind me what", "what were we talking"
    ]
    
    return any(keyword in query_lower for keyword in conversation_keywords)

def estimate_tokens(text):
    """Rough estimation of tokens (1 token  0.75 words)"""
    return int(len(text.split()) * 1.33)

def get_dynamic_history_limit(query):
    """Determine how many messages to retrieve based on query type"""
    if is_asking_about_conversation(query):
        return 30  
    elif is_asking_about_recent_actions(query):
        return 20
    else:
        return 15 

def build_context_aware_prompt(query, history):
    """Build a context-aware prompt by analyzing conversation flow"""
    topic = extract_topic_from_history(history)
    
    if topic:
        context_note = f"\n\nCONTEXT NOTE: Recent conversation was about '{topic}'. If the current query seems incomplete or is a follow-up (e.g., 'what about X'), interpret it in relation to this topic."
        return query + context_note
    
    return query

def detect_action_offer(response):
    """
    Detect if the response contains an offer to perform an action.
    Returns a tuple: (has_offer, action_info)
    
    action_info format: {
        'action_type': 'open_website' | 'play_youtube' | 'search_google' | etc.,
        'target': 'what to open/play/search',
        'prompt': 'the question asked to user'
    }
    """
    response_lower = response.lower()
    
    # Pattern 1: "Would you like me to open X?"
    patterns = {
        'open': [
            (r"would you like (?:me to )?open ([^?.!]+)[\?.!]", 'open_website'),
            (r"shall i open ([^?.!]+)[\?.!]", 'open_website'),
            (r"do you want (?:me to )?open ([^?.!]+)[\?.!]", 'open_website'),
        ],
        'play': [
            (r"would you like (?:me to )?play ([^?.!]+)[\?.!]", 'play_youtube'),
            (r"shall i play ([^?.!]+)[\?.!]", 'play_youtube'),
            (r"do you want (?:me to )?play ([^?.!]+)[\?.!]", 'play_youtube'),
        ],
        'search': [
            (r"would you like (?:me to )?search(?: for)? ([^?.!]+)[\?.!]", 'search_google'),
            (r"shall i search(?: for)? ([^?.!]+)[\?.!]", 'search_google'),
            (r"do you want (?:me to )?search(?: for)? ([^?.!]+)[\?.!]", 'search_google'),
        ],
    }
    
    for category, pattern_list in patterns.items():
        for pattern, action_type in pattern_list:
            match = re.search(pattern, response_lower, re.IGNORECASE)
            if match:
                target = match.group(1).strip()
                
                # Find the actual question in the response
                question_patterns = [
                    r"(would you like[^?.!]+[\?.!])",
                    r"(shall i[^?.!]+[\?.!])",
                    r"(do you want[^?.!]+[\?.!])"
                ]
                
                prompt = None
                for q_pattern in question_patterns:
                    q_match = re.search(q_pattern, response, re.IGNORECASE)
                    if q_match:
                        prompt = q_match.group(1).strip()
                        break
                
                if not prompt:
                    prompt = f"Would you like me to {category} {target}?"
                
                # Special handling for YouTube search
                if 'youtube' in response_lower and action_type == 'search_google':
                    action_type = 'search_youtube'
                
                return True, {
                    'action_type': action_type,
                    'target': target,
                    'prompt': prompt
                }
    
    return False, None

def ChatBot(query, query_metadata=None):
    """Main chatbot function with improved context handling"""
    try:
        if not query or not query.strip():
            return "Please provide a valid question or message."
        
        
        history_limit = get_dynamic_history_limit(query)
        context_messages = get_chat_history(limit=history_limit)
        
        messages_for_api = SystemChatBot.copy()
        
        messages_for_api.append({
            "role": "system", 
            "content": get_realtime_information()
        })
        
        if is_asking_about_recent_actions(query):
            automation_logs = get_recent_automation_logs(limit=10)
            automation_context = format_automation_context(automation_logs)
            messages_for_api.append({
                "role": "system",
                "content": f"Automation History Context:\n{automation_context}"
            })
        
        # Check if asking about capabilities
        query_lower = query.lower()
        capability_keywords = [
            "what can you do", "what are you capable", "what are your capabilities",
            "what features", "what can i do", "show me what you can do",
            "list your capabilities", "tell me what you can do", "your abilities"
        ]
        
        if any(keyword in query_lower for keyword in capability_keywords):
            # Inject detailed capabilities
            capabilities = get_capabilities_summary()
            messages_for_api.append({
                "role": "system",
                "content": f"Full Capabilities Reference:\n{capabilities}"
            })
        
        enhanced_query = build_context_aware_prompt(query, context_messages)
        
        for msg in context_messages:
            messages_for_api.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        if enhanced_query != query:
            messages_for_api[-1]["content"] = enhanced_query
        
        total_tokens = sum(estimate_tokens(msg['content']) for msg in messages_for_api)
        
        MAX_CONTEXT_TOKENS = 6000 
        if total_tokens > MAX_CONTEXT_TOKENS:
            system_msgs = [msg for msg in messages_for_api if msg['role'] == 'system']
            user_msgs = [msg for msg in messages_for_api if msg['role'] != 'system']
            
            trimmed_msgs = system_msgs + user_msgs[-10:]
            messages_for_api = trimmed_msgs
        
        try:
            completion = _call_with_retry(
                model=MODEL_CONVERSATIONAL, 
                messages=messages_for_api,
                max_tokens=1024,
                temperature=0.7,  
                top_p=0.9,        
                stream=True,
                stop=None
            )

            answer = ""
            for chunk in completion:
                if chunk.choices[0].delta.content:
                    answer += chunk.choices[0].delta.content
                    
            formatted_answer = format_answer(answer)
            
            if formatted_answer and formatted_answer != query and not formatted_answer.startswith("I didn't generate"):
                # Don't save here - it's handled in Main.py after detecting actions
                # save_message("assistant", formatted_answer)
                return formatted_answer
            else:
                return "I didn't generate a proper response. Please try rephrasing your question."

        except Exception as e:
            if "rate limit" in str(e).lower() or "429" in str(e):
                time.sleep(30)
                return ChatBot(query, query_metadata)
            elif "context length" in str(e).lower():
                conn = psycopg2.connect(
                    dbname=DB_NAME, user=DB_USER, 
                    password=DB_PASSWORD, host=DB_HOST
                )
                cur = conn.cursor()
                cur.execute("DELETE FROM chat_messages WHERE id IN (SELECT id FROM chat_messages ORDER BY created_at LIMIT 10)")
                conn.commit()
                conn.close()
                return ChatBot(query, query_metadata)
            else:
                raise e

    except Exception as e:
        return f"I encountered an error: {str(e)}. Please try again."

def show_commands():
    """Display available commands"""
    commands = """
Available commands:
- 'clear' or 'reset' - Clear chat history
- 'exit' or 'quit' - Exit the program
- Any other input will be treated as a question/message
    """
    print(commands)

def main():
    """Main program loop"""
    print("=" * 60)
    print(f" {Assistantname} Active")
    init_db()
    
    print("Type 'help' for commands or start chatting!")
    print("-" * 60)
    
    while True:
        try:
            user_input = input(f"\n{Username}: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['exit', 'quit']:
                print(f"\n Goodbye! Thanks for chatting with {Assistantname}!")
                break
            elif user_input.lower() in ['clear', 'reset']:
                clear_chat_history()
                print(" Chat history cleared.")
                continue
            elif user_input.lower() in ['help', 'commands']:
                show_commands()
                continue
            
            print(f"\n{Assistantname}: ", end="", flush=True)
            response = ChatBot(user_input)
            print(response)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            continue

if __name__ == "__main__":
    main()