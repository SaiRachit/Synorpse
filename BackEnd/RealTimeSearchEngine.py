import requests
from groq import Groq, AsyncGroq
import datetime
from dotenv import dotenv_values
import psycopg2
from psycopg2.extras import Json
from bs4 import BeautifulSoup
import re
import json
import time
import sys
import asyncio
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum

env_vars = dotenv_values(".env")

# Collect ALL Groq keys for rotation
GROQ_KEYS = [
    env_vars.get("GroqScreenReader"),
    env_vars.get("GroqAPIKey"),
    env_vars.get("GroqAPIKey2"),
    env_vars.get("GroqAPIKey3"),
    env_vars.get("GroqAPIKeyDoc"),
    env_vars.get("GroqAPIKeyImage"),
    env_vars.get("GroqConversationManager")
]
GROQ_KEYS = [k for k in GROQ_KEYS if k] # Filter out missing keys

Username = env_vars.get("Username")
Assistantname = env_vars.get("Assistantname")
DB_NAME = env_vars.get("DB_NAME", "synorpse_chat")
DB_USER = env_vars.get("DB_USER", "postgres")
DB_PASSWORD = env_vars.get("DB_PASSWORD")
DB_HOST = env_vars.get("DB_HOST", "localhost")

# Global clients for rotation
_current_key_index = 0
client = Groq(api_key=GROQ_KEYS[0]) if GROQ_KEYS else None
async_client = AsyncGroq(api_key=GROQ_KEYS[0]) if GROQ_KEYS else None

def rotate_groq_key():
    """Rotate to the next available Groq key"""
    global _current_key_index, client, async_client
    if not GROQ_KEYS:
        return
    _current_key_index = (_current_key_index + 1) % len(GROQ_KEYS)
    client = Groq(api_key=GROQ_KEYS[_current_key_index])
    async_client = AsyncGroq(api_key=GROQ_KEYS[_current_key_index])

def _call_with_retry(**kwargs):
    """Call a sync Groq completion with automatic key rotation on rate limits."""
    last_error = None
    for attempt in range(len(GROQ_KEYS)):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str:
                rotate_groq_key()
                last_error = e
                continue
            raise  # Non-rate-limit error, don't retry
    raise last_error  # All keys exhausted

async def _async_call_with_retry(**kwargs):
    """Call an async Groq completion with automatic key rotation on rate limits."""
    last_error = None
    for attempt in range(len(GROQ_KEYS)):
        try:
            return await async_client.chat.completions.create(**kwargs)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "rate_limit" in err_str:
                rotate_groq_key()
                last_error = e
                continue
            raise
    raise last_error

# Model choices — heavy model for answer generation, light model for evaluation/orchestration
MODEL_HEAVY = "llama-3.3-70b-versatile"   # Quality answers
MODEL_LIGHT = "llama-3.1-8b-instant"       # Evaluation, orchestration, fact-checking

class ReasoningState(Enum):
    """Current state of the reasoning loop"""
    THINKING = "thinking"
    ACTING = "acting"
    OBSERVING = "observing"
    COMPLETE = "complete"
    FAILED = "failed"

@dataclass
class ThoughtStep:
    """A single thought-action-observation cycle"""
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict[str, Any]] = None
    observation: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

@dataclass
class ReasoningTrace:
    """Complete trace of reasoning for a task"""
    goal: str
    steps: List[ThoughtStep] = field(default_factory=list)
    final_answer: Optional[str] = None
    success: bool = False
    total_time: float = 0.0
    
    def add_step(self, step: ThoughtStep):
        self.steps.append(step)
    
    def get_context(self) -> str:
        """Format trace as context for the LLM"""
        lines = [f"Goal: {self.goal}\n"]
        total_steps = len(self.steps)
        for i, step in enumerate(self.steps):
            lines.append(f"Step {i+1}:")
            lines.append(f"  Thought: {step.thought}")
            if step.action:
                lines.append(f"  Action: {step.action}")
                if step.action_input:
                    lines.append(f"  Input: {json.dumps(step.action_input)}")
            
            if step.observation:
                limit = 1500 if i == total_steps - 1 else 200
                lines.append(f"  Observation: {step.observation[:limit]}...")
            lines.append("")
        return "\n".join(lines)

def init_search_db():
    """Initialize search cache and reasoning traces tables"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST
        )
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS search_cache (
                id SERIAL PRIMARY KEY,
                query_hash VARCHAR(32) UNIQUE NOT NULL,
                query TEXT NOT NULL,
                results TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_search_query_hash ON search_cache(query_hash);
            CREATE INDEX IF NOT EXISTS idx_search_created_at ON search_cache(created_at);

            CREATE TABLE IF NOT EXISTS reasoning_traces (
                id SERIAL PRIMARY KEY,
                trace_id VARCHAR(36) UNIQUE NOT NULL,
                goal TEXT NOT NULL,
                steps JSONB NOT NULL DEFAULT '[]',
                final_answer TEXT,
                verified BOOLEAN DEFAULT FALSE,
                confidence INTEGER DEFAULT 0,
                total_time FLOAT DEFAULT 0.0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_trace_id ON reasoning_traces(trace_id);
            CREATE INDEX IF NOT EXISTS idx_trace_created ON reasoning_traces(created_at);
        """)
        conn.commit()
        conn.close()
    except:
        pass

def get_query_hash(query):
    """Generate hash for query"""
    import hashlib
    return hashlib.md5(query.lower().strip().encode()).hexdigest()

def get_cached_search(query):
    """Get cached search results (24 hour expiry)"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST
        )
        cur = conn.cursor()
        
        query_hash = get_query_hash(query)
        
        cur.execute(
            """SELECT results, created_at FROM search_cache 
               WHERE query_hash = %s 
               AND created_at > NOW() - INTERVAL '24 hours'""",
            (query_hash,)
        )
        result = cur.fetchone()
        conn.close()
        
        if result:
            return result[0]
        return None
    except:
        return None

def cache_search(query, results):
    """Save search results to cache"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST
        )
        cur = conn.cursor()
        
        query_hash = get_query_hash(query)
        
        cur.execute(
            """INSERT INTO search_cache (query_hash, query, results) 
               VALUES (%s, %s, %s)
               ON CONFLICT (query_hash) 
               DO UPDATE SET results = EXCLUDED.results, created_at = NOW()""",
            (query_hash, query, results)
        )
        conn.commit()
        conn.close()
    except:
        pass

def scrape_webpage(url, max_length=3000):
    """Scrape webpage content"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']):
            element.decompose()
        
        main_content = None
        for tag in ['article', 'main', 'div[class*="content"]']:
            main_content = soup.find(tag.split('[')[0])
            if main_content:
                break
        
        if not main_content:
            main_content = soup.find('body')
        
        if not main_content:
            return None
        
        text = main_content.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        if len(text) > max_length:
            text = text[:max_length] + "..."
        
        return text
    except:
        return None

def DuckDuckGoSearch(query):
    """Perform DuckDuckGo search"""
    try:
        url = "https://html.duckduckgo.com/html/"
        params = {"q": query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        response = requests.post(url, data=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            text = response.text
            results = []
            parts = text.split('result__a')
            
            for i, part in enumerate(parts[1:6]):
                try:
                    link_start = part.find('href="') + 6
                    link_end = part.find('"', link_start)
                    link = part[link_start:link_end]
                    
                    title_start = part.find('>') + 1
                    title_end = part.find('</a>')
                    title = part[title_start:title_end].strip()
                    
                    snippet_part = parts[i+1] if i+1 < len(parts) else part
                    snippet_start = snippet_part.find('result__snippet')
                    snippet_text = snippet_part[snippet_start:snippet_start+300] if snippet_start > 0 else ""
                    snippet = snippet_text.split('>')[1].split('<')[0].strip() if '>' in snippet_text else "No description"
                    
                    if link and title and not link.startswith('//duckduckgo.com'):
                        results.append({
                            "title": title.replace('&amp;', '&'),
                            "snippet": snippet.replace('&amp;', '&'),
                            "link": link
                        })
                except:
                    continue
            
            return results if results else None
        return None
    except:
        return None

def DuckDuckGoSearchWithScraping(query, num_pages=3):
    """Search and scrape web pages"""
    try:
        results = DuckDuckGoSearch(query)
        if not results:
            return None
        
        scraped_content = f"Web search results for '{query}':\n\n"
        
        for i, result in enumerate(results[:num_pages], 1):
            url = result['link']
            content = scrape_webpage(url)
            
            if content:
                scraped_content += f"=== Source {i}: {result['title']} ===\n"
                scraped_content += f"URL: {url}\n"
                scraped_content += f"Content:\n{content}\n\n"
            else:
                scraped_content += f"=== Source {i}: {result['title']} ===\n"
                scraped_content += f"URL: {url}\n"
                scraped_content += f"Description: {result['snippet']}\n\n"
            
            scraped_content += "=" * 80 + "\n\n"
        
        return scraped_content
    except:
        return None

def get_current_datetime_info():
    """Get current date and time"""
    current_date_time = datetime.datetime.now()
    day = current_date_time.strftime("%A")
    date = current_date_time.strftime("%B %d, %Y")
    time = current_date_time.strftime("%H:%M")
    
    return f"""Current date and time:
Today is {day}, {date}
Current time: {time}

The search results provided are current and up-to-date."""

def requires_links_in_response(query):
    """
    Analyze query to determine if the user is asking for links/URLs.
    Returns True if links should be included in the response.
    """
    query_lower = query.lower()
    
    # Direct link requests
    link_keywords = [
        "link", "url", "website", "site", "webpage",
        "linkedin", "twitter", "instagram", "facebook", "github",
        "profile", "page", "account", "handle",
        "where can i find", "where to find", "how to access",
        "do you have", "can you give me", "share the",
        "send me", "give me the link", "provide the link"
    ]
    
    # Profile/social media requests
    profile_patterns = [
        "his linkedin", "her linkedin", "their linkedin",
        "his twitter", "her twitter", "their twitter", 
        "his github", "her github", "their github",
        "his profile", "her profile", "their profile",
        "his website", "her website", "their website",
        "contact info", "contact details", "social media"
    ]
    
    # Check for direct link keywords
    if any(keyword in query_lower for keyword in link_keywords):
        return True
    
    # Check for profile patterns
    if any(pattern in query_lower for pattern in profile_patterns):
        return True
    
    return False


def extract_relevant_urls(search_results, query):
    """
    Extract URLs from search results that are relevant to the query.
    Returns a list of (title, url) tuples.
    """
    urls = []
    query_lower = query.lower()
    
    # Parse the search results for URLs
    lines = search_results.split('\n')
    current_title = ""
    
    for line in lines:
        if line.startswith("=== Source"):
            # Extract title
            try:
                current_title = line.split(": ", 1)[1].replace(" ===", "").strip()
            except:
                current_title = "Source"
        elif line.startswith("URL: "):
            url = line.replace("URL: ", "").strip()
            if url and current_title:
                # Prioritize social media profiles
                social_domains = ["linkedin.com", "twitter.com", "github.com", 
                                 "facebook.com", "instagram.com"]
                is_social = any(domain in url.lower() for domain in social_domains)
                
                # Check relevance
                if is_social or any(term in url.lower() for term in query_lower.split()):
                    urls.append((current_title, url))
    
    return urls[:3]  # Return top 3 relevant URLs


def generate_candidate_answer(prompt, search_results, temperature=0.3):
    """Generate a single candidate answer with optional links"""
    
    # Check if this query requires links
    include_links = requires_links_in_response(prompt)
    
    if include_links:
        # Extract relevant URLs for link requests
        relevant_urls = extract_relevant_urls(search_results, prompt)
        
        search_system = f"""You are {Assistantname}, an AI assistant with real-time search capabilities.

CRITICAL INSTRUCTIONS:
- The user is asking for a link/URL/profile
- Provide a helpful response AND include the relevant link(s)
- Format links clearly, for example: "Here's the LinkedIn profile: [URL]"
- If you found the requested profile/link, share it directly
- If no relevant link was found, say so politely and suggest alternatives
- Be conversational and helpful

{get_current_datetime_info()}

RELEVANT URLS FOUND:
{chr(10).join([f"- {title}: {url}" for title, url in relevant_urls]) if relevant_urls else "No specific URLs found for this request."}

CURRENT WEB DATA:
{search_results}"""

        user_prompt = f"The user asked: {prompt}\n\nProvide a helpful response with relevant links if available."
    else:
        # Standard response without links
        search_system = f"""You are {Assistantname}, an AI assistant with real-time search capabilities.

CRITICAL INSTRUCTIONS:
- Provide ONLY the direct answer to the user's question
- DO NOT include any URLs, links, or source citations
- DO NOT mention where the information came from
- DO NOT say "according to" or "based on the sources"
- Give a natural, conversational response as if you inherently know this information
- Focus on answering exactly what was asked - nothing more, nothing less
- Be concise but complete
- If asked about current events, news, prices, or time-sensitive data, provide the LATEST information from the search results

{get_current_datetime_info()}

CURRENT WEB DATA:
{search_results}"""

        user_prompt = f"Answer this directly without any sources or links: {prompt}"

    messages = [
        {"role": "system", "content": search_system},
        {"role": "user", "content": user_prompt}
    ]

    completion = _call_with_retry(
        model=MODEL_HEAVY,
        messages=messages,
        temperature=temperature,
        max_tokens=1024,
        top_p=0.9,
        stream=False,
        stop=None
    )

    answer = completion.choices[0].message.content.strip()
    return answer.replace("</s>", "").replace("</s", "")

def evaluate_answer_reliability(prompt, answer, search_results):
    """Evaluate the reliability and accuracy of an answer"""
    evaluation_prompt = f"""You are an expert fact-checker. Evaluate the following answer for reliability and accuracy.

ORIGINAL QUESTION: {prompt}

ANSWER TO EVALUATE:
{answer}

SOURCE DATA:
{search_results[:2000]}

Provide a JSON response with:
{{
    "reliability_score": <0-100>,
    "factual_accuracy": <0-100>,
    "relevance": <0-100>,
    "completeness": <0-100>,
    "issues": ["list any factual errors or concerns"],
    "overall_quality": <0-100>
}}

Scoring criteria:
- reliability_score: How trustworthy is this answer based on sources?
- factual_accuracy: Are all facts correct and verifiable?
- relevance: Does it directly answer the question?
- completeness: Is the answer sufficiently detailed?
- overall_quality: Average of all scores

Be strict in your evaluation. Only give high scores to excellent answers."""

    try:
        completion = _call_with_retry(
            model=MODEL_LIGHT,
            messages=[
                {"role": "system", "content": "You are a strict fact-checker. Respond ONLY with valid JSON."},
                {"role": "user", "content": evaluation_prompt}
            ],
            temperature=0.1,
            max_tokens=512,
            stream=False
        )
        
        result = completion.choices[0].message.content.strip()
        
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0].strip()
        elif "```" in result:
            result = result.split("```")[1].split("```")[0].strip()
        
        evaluation = json.loads(result)
        return evaluation
    except:
        return {
            "reliability_score": 50,
            "factual_accuracy": 50,
            "relevance": 50,
            "completeness": 50,
            "issues": [],
            "overall_quality": 50
        }

def select_best_answer(candidates_with_scores):
    """Select the best answer from candidates based on scores"""
    if not candidates_with_scores:
        return None
    
    sorted_candidates = sorted(
        candidates_with_scores, 
        key=lambda x: x['evaluation']['overall_quality'], 
        reverse=True
    )
    
    best = sorted_candidates[0]
    return best['answer']


# ------------------------------------------------------------------
# Reasoning Trace Persistence
# ------------------------------------------------------------------
_last_trace_id = None  # Track the most recent trace for "how did you get that?"

def save_reasoning_trace(trace: ReasoningTrace, verified: bool = False, confidence: int = 0) -> str:
    """Persist a ReasoningTrace to the database. Returns the trace_id."""
    global _last_trace_id
    trace_id = str(uuid.uuid4())
    _last_trace_id = trace_id

    steps_json = []
    for step in trace.steps:
        steps_json.append({
            "thought": step.thought,
            "action": step.action,
            "action_input": step.action_input,
            "observation": step.observation,
            "timestamp": step.timestamp
        })

    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER,
            password=DB_PASSWORD, host=DB_HOST
        )
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO reasoning_traces
               (trace_id, goal, steps, final_answer, verified, confidence, total_time)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (trace_id, trace.goal, Json(steps_json),
             trace.final_answer, verified, confidence, trace.total_time)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"⚠️ Failed to save reasoning trace: {e}", file=sys.stderr)

    return trace_id


def get_reasoning_trace(trace_id: str = None) -> Optional[dict]:
    """
    Retrieve a stored reasoning trace.
    If no trace_id given, returns the most recent trace.
    """
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME, user=DB_USER,
            password=DB_PASSWORD, host=DB_HOST
        )
        cur = conn.cursor()

        if trace_id:
            cur.execute(
                """SELECT trace_id, goal, steps, final_answer, verified, confidence, total_time, created_at
                   FROM reasoning_traces WHERE trace_id = %s""",
                (trace_id,)
            )
        else:
            # Get the most recent trace
            cur.execute(
                """SELECT trace_id, goal, steps, final_answer, verified, confidence, total_time, created_at
                   FROM reasoning_traces ORDER BY created_at DESC LIMIT 1"""
            )

        row = cur.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "trace_id": row[0],
            "goal": row[1],
            "steps": row[2],
            "final_answer": row[3],
            "verified": row[4],
            "confidence": row[5],
            "total_time": row[6],
            "created_at": str(row[7])
        }
    except Exception as e:
        print(f"⚠️ Failed to retrieve reasoning trace: {e}", file=sys.stderr)
        return None


def format_trace_for_user(trace_data: dict) -> str:
    """Format a reasoning trace into a human-readable summary for the frontend."""
    if not trace_data:
        return "I don't have a recorded thinking process for that."

    lines = [f"**🧠 How I arrived at the answer:**\n"]
    lines.append(f"**Goal:** {trace_data['goal']}\n")

    steps = trace_data.get("steps", [])
    for i, step in enumerate(steps, 1):
        lines.append(f"**Step {i}:**")
        lines.append(f"  💭 *Thought:* {step.get('thought', 'N/A')}")
        if step.get("action") and step["action"] != "finish":
            lines.append(f"  🔧 *Action:* {step['action']}")
            if step.get("observation"):
                obs = step["observation"]
                if len(obs) > 300:
                    obs = obs[:300] + "..."
                lines.append(f"  👁️ *Result:* {obs}")
        lines.append("")

    confidence = trace_data.get("confidence", 0)
    verified = "✅ Yes" if trace_data.get("verified") else "⚠️ Not fully verified"
    lines.append(f"**Confidence:** {confidence}/100 | **Verified:** {verified}")
    lines.append(f"**Total time:** {trace_data.get('total_time', 0):.1f}s")

    return "\n".join(lines)


# ------------------------------------------------------------------
# Knowledge Query — replaces ChatBot for the reasoning loop
# ------------------------------------------------------------------
async def knowledge_query(question: str) -> str:
    """
    Answer a knowledge question using search + LLM.
    This replaces the ChatBot dependency in the reasoning loop.
    Does a quick web search and generates a single verified answer.
    """
    try:
        # Quick search for supporting data
        search_results = await asyncio.to_thread(DuckDuckGoSearchWithScraping, question, num_pages=2)
        
        if not search_results:
            # Fallback: use LLM knowledge directly without web data
            if not client:
                return "Unable to answer — no API keys available."
            completion = _call_with_retry(
                model=MODEL_HEAVY,
                messages=[
                    {"role": "system", "content": f"You are {Assistantname}, a knowledgeable AI. Answer concisely and accurately."},
                    {"role": "user", "content": question}
                ],
                temperature=0.3,
                max_tokens=1024
            )
            return completion.choices[0].message.content.strip()

        # Generate answer backed by search data
        answer = generate_candidate_answer(question, search_results, temperature=0.2)
        return answer if answer else "I couldn't find a reliable answer."
    except Exception as e:
        return f"Knowledge query error: {str(e)}"

async def RealtimeSearch(prompt, on_thought: Optional[Callable[[str], None]] = None, context: Optional[str] = None, force_reasoning: bool = False):
    """
    Main search function with integrated reasoning (ReAct) loop.
    Decides based on query complexity whether to use simple search or full reasoning.
    
    Args:
        force_reasoning: When True, bypasses _needs_reasoning() heuristic entirely
                         and goes straight to the full ReAct reasoning loop.
    """
    try:
        if not prompt or not prompt.strip():
            return "Please provide a valid query."

        # Detect if deep reasoning is needed:
        # 1. force_reasoning=True bypasses the heuristic entirely (set by intent router)
        # 2. _needs_reasoning() checks regex patterns for complex queries
        # 3. on_thought callback presence implies reasoning was requested
        requires_reasoning = force_reasoning or _needs_reasoning(prompt) or (on_thought is not None)
        
        if requires_reasoning:
            result = await run_reasoning_loop(prompt, on_thought=on_thought, context=context)
            # Extract answer string; trace is persisted in DB for later retrieval
            if isinstance(result, dict):
                return result.get("answer", str(result))
            return result

        # Legacy search path for simple queries
        return await _simple_realtime_search(prompt)
        
    except Exception as e:
        return f"Search error: {str(e)}"

def _needs_reasoning(query: str) -> bool:
    """Heuristic to detect if a query needs the autonomous reasoning loop."""
    patterns = [
        r'\bif\s+(?:i|you|he|she|we|they)\s+(?:have|had|has)\b.*\b(?:take|give|remove|add|lose|eat)\b',
        r'\b(?:riddle|puzzle|brainteaser|brain\s*teaser|trick\s*question)\b',
        r'\b(?:what\s+has|what\s+am\s+i|what\s+gets|what\s+can)\b.*\bbut\b',
        r'\b(?:solve|figure\s+out|work\s+out)\b.*\b(?:this|the|my|it|that|riddle|puzzle|problem|equation|question)\b',
        r'\b(?:what\s+comes\s+next|next\s+in\s+(?:the\s+)?(?:sequence|series|pattern))\b',
        r'\b(?:how\s+many|how\s+much)\b.*\b(?:if|when|after|before)\b',
        r'\b(?:what.?s\s+wrong\s+with|find\s+the\s+(?:error|flaw|mistake)|analyze\s+(?:this|critically))\b',
        r'\b(?:solve|figure\s+out|identify|find|guess)\b.*\b(?:screen|see|looking\s+at|display)\b',
        r'\b(?:where\s+is\s+this|what\s+(?:place|location|country|city)\s+is\s+this)\b'
    ]
    return any(re.search(p, query, re.I) for p in patterns)

async def _simple_realtime_search(prompt):
    """The original search-then-generate-best-answer logic"""
    cached_results = get_cached_search(prompt)
    if cached_results:
        search_results = cached_results
    else:
        # Use asyncio.to_thread for blocking requests
        search_results = await asyncio.to_thread(DuckDuckGoSearchWithScraping, prompt, num_pages=3)
        
        if not search_results:
            return "Search failed. Please try again or rephrase your query."
        
        cache_search(prompt, search_results)
    
    candidates = []
    temperatures = [0.2, 0.3, 0.4]
    
    for temp in temperatures:
        # Use asyncio.to_thread for blocking client calls if necessary, 
        # but here we can just call it (ideally migrate generate_candidate_answer to async)
        answer = generate_candidate_answer(prompt, search_results, temperature=temp)
        if answer and len(answer.strip()) >= 10:
            candidates.append(answer)
    
    if not candidates:
        return "Couldn't generate a proper response."
    
    unique_candidates = []
    for candidate in candidates:
        is_duplicate = False
        for existing in unique_candidates:
            if len(set(candidate.split()) & set(existing.split())) / max(len(candidate.split()), len(existing.split())) > 0.8:
                is_duplicate = True
                break
        if not is_duplicate:
            unique_candidates.append(candidate)
    
    candidates_with_scores = []
    for answer in unique_candidates:
        evaluation = evaluate_answer_reliability(prompt, answer, search_results)
        candidates_with_scores.append({
            'answer': answer,
            'evaluation': evaluation
        })
    
    best_answer = select_best_answer(candidates_with_scores)
    if not best_answer:
        return "Couldn't generate a reliable response."
    
    return best_answer.strip()

async def run_reasoning_loop(goal: str, context: str = None, 
                           on_thought: Callable[[str], None] = None) -> dict:
    """
    Execute a reasoning loop for a complex goal.
    Returns dict: {answer, trace_id, verified, confidence}
    """
    from ReasoningHandlers import get_reasoning_handlers
    
    handlers_obj = get_reasoning_handlers()
    if not handlers_obj:
        return {"answer": "Reasoning handlers not initialized.", "trace_id": None, "verified": False, "confidence": 0}
    
    handlers = handlers_obj.get_handlers_dict()
    start_time = time.time()
    trace = ReasoningTrace(goal=goal)
    
    state = ReasoningState.THINKING
    step_count = 0
    MAX_STEPS = 10
    last_search_results = None  # Keep track for verification
    
    while state not in [ReasoningState.COMPLETE, ReasoningState.FAILED]:
        if step_count >= MAX_STEPS:
            trace.final_answer = "I've reached my step limit. Here's what I found so far."
            break
        
        step_count += 1
        
        # THINK
        thought_result = await _think_react(goal, trace, context, handlers)
        
        if not thought_result:
            # Retry with key rotation
            rotate_groq_key()
            thought_result = await _think_react(goal, trace, context, handlers)
            
            if not thought_result:
                return {"answer": "I encountered an error while thinking. Please check your connection.",
                        "trace_id": None, "verified": False, "confidence": 0}

        thought, action, action_input = thought_result
        step = ThoughtStep(thought=thought, action=action, action_input=action_input)
        
        if on_thought:
            on_thought(f" {thought}")
        
        # --- Hard guard: prevent premature finishing ---
        _goal_lower = goal.lower()
        _is_screen_goal = any(w in _goal_lower for w in ["screen", "display", "looking at", "see on my", "on my monitor"])
        # Check if we have a screen observation in steps OR in the initial context
        _has_screen_observation = any(
            s.action == "read_screen" and s.observation for s in trace.steps
        ) or (context and "SCREEN" in context.upper())
        
        if action == "finish":
            # BLOCK: Screen-related goal but haven't read the screen yet
            if _is_screen_goal and not _has_screen_observation and "read_screen" in handlers:
                action = "read_screen"
                action_input = {"query": goal}
                step = ThoughtStep(
                    thought="[Auto-corrected] Must read the screen before answering.",
                    action=action, action_input=action_input
                )
                if on_thought:
                    on_thought(" Reading your screen first...")
            # BLOCK: First step — must gather info before finishing (unless context provided)
            elif step_count == 1 and not (context and len(context) > 100):
                action = "search" if "search" in handlers else "search_knowledge"
                action_input = {"query": goal} if action == "search" else {"question": goal}
                step = ThoughtStep(
                    thought="[Auto-corrected] Gathering information before answering.",
                    action=action, action_input=action_input
                )
            else:
                # Legitimate finish — accept it
                final_answer = action_input.get("answer", "") if isinstance(action_input, dict) else ""
                
                # If empty/generic answer but we have screen data, force a real solve
                _generic_answers = ["task completed", "task completed.", ""]
                if (not final_answer or final_answer.strip().lower() in _generic_answers) and _has_screen_observation:
                    # Get screen data
                    screen_data = None
                    for s in trace.steps:
                        if s.action == "read_screen" and s.observation:
                            screen_data = s.observation
                            break
                    if not screen_data and context and "SCREEN" in context.upper():
                        screen_data = context
                    
                    if screen_data:
                        if on_thought:
                            on_thought(" Solving based on screen analysis...")
                        try:
                            solve_prompt = f"""You are looking at the user's screen. Analyze what you see and help them step by step.

USER'S REQUEST: {goal}

SCREEN CONTENT:
{screen_data[:3000]}

IMPORTANT: Walk the user through your reasoning:
1. First, describe what you observe on their screen (game state, puzzle, riddle text, etc.)
2. Analyze the key details (e.g., which letters are correct/wrong, what clues are given)
3. Explain your reasoning process
4. Give your recommendation or answer

Be specific about what you see — reference colors, positions, letters, numbers, or any visual details. Think WITH the user, not just AT them."""
                            
                            solve_response = await _async_call_with_retry(
                                model=MODEL_LIGHT,
                                messages=[
                                    {"role": "system", "content": "You are an intelligent screen companion. You can see the user's screen and help them solve puzzles, games, and problems by thinking through them step by step. Always reference specific visual details from the screen data."},
                                    {"role": "user", "content": solve_prompt}
                                ],
                                temperature=0.4,
                                max_tokens=1500
                            )
                            final_answer = solve_response.choices[0].message.content.strip()
                        except Exception:
                            final_answer = f"Based on screen analysis: {screen_data[:500]}"
                
                if not final_answer:
                    final_answer = "Task completed."
                    
                trace.final_answer = final_answer
                trace.success = True
                break
        
        # --- Hard guard: prevent duplicate read_screen calls ---
        # If LLM requests read_screen but screen data already exists,
        # force-finish by directly solving the goal with existing screen data.
        if action == "read_screen" and _has_screen_observation:
            # Collect existing screen data
            existing_screen = None
            for s in trace.steps:
                if s.action == "read_screen" and s.observation:
                    existing_screen = s.observation
                    break
            if not existing_screen and context and "SCREEN" in context.upper():
                existing_screen = context
            
            if existing_screen:
                if on_thought:
                    on_thought(" Screen already analyzed — solving now...")
                
                # Direct LLM call to produce the final answer from screen data
                try:
                    solve_prompt = f"""You are looking at the user's screen. Analyze what you see and help them step by step.

USER'S REQUEST: {goal}

SCREEN CONTENT:
{existing_screen[:3000]}

IMPORTANT: Walk the user through your reasoning:
1. First, describe what you observe on their screen (game state, puzzle, riddle text, etc.)
2. Analyze the key details (e.g., which letters are correct/wrong, what clues are given)
3. Explain your reasoning process
4. Give your recommendation or answer

Be specific about what you see — reference colors, positions, letters, numbers, or any visual details. Think WITH the user, not just AT them."""
                    
                    solve_response = await _async_call_with_retry(
                        model=MODEL_LIGHT,
                        messages=[
                            {"role": "system", "content": "You are an intelligent screen companion. You can see the user's screen and help them solve puzzles, games, and problems by thinking through them step by step. Always reference specific visual details from the screen data."},
                            {"role": "user", "content": solve_prompt}
                        ],
                        temperature=0.4,
                        max_tokens=1500
                    )
                    final_answer = solve_response.choices[0].message.content.strip()
                except Exception:
                    final_answer = f"Based on screen analysis: {existing_screen[:500]}"
                
                trace.final_answer = final_answer
                trace.success = True
                step.observation = "[Forced finish — screen data already available]"
                trace.add_step(step)
                break
        
        # ACT
        state = ReasoningState.ACTING
        handler = handlers.get(action)
        if not handler:
            observation = f"Error: No handler for action '{action}'"
        else:
            try:
                result = await handler(action_input)
                observation = result.get("message", str(result)) if isinstance(result, dict) else str(result)
                # Track search results for verification
                if action in ("search", "search_knowledge"):
                    last_search_results = observation
            except Exception as e:
                observation = f"Error executing {action}: {str(e)}"
        
        step.observation = observation
        trace.add_step(step)
        state = ReasoningState.THINKING
        await asyncio.sleep(0.5)
    
    trace.total_time = time.time() - start_time
    
    # --- Answer Verification ---
    verified = False
    confidence = 0
    if trace.final_answer:
        # Screen-based goals with screen observations: skip web verification
        # (DuckDuckGo can't verify answers derived from visual screen analysis)
        _goal_lower = goal.lower()
        _is_screen_goal = any(w in _goal_lower for w in ["screen", "display", "looking at", "see on my", "on my monitor"])
        _has_screen_obs = any(
            s.action == "read_screen" and s.observation for s in trace.steps
        ) or (context and "SCREEN" in context.upper())
        
        if _is_screen_goal and _has_screen_obs:
            # Trust the visual observation — web search can't verify this
            confidence = 75
            verified = True
        else:
            try:
                # Get search data for verification (use last search or do a quick one)
                verify_data = last_search_results
                if not verify_data:
                    verify_data = await asyncio.to_thread(DuckDuckGoSearchWithScraping, goal, num_pages=2)
                
                if verify_data:
                    evaluation = await asyncio.to_thread(
                        evaluate_answer_reliability, goal, trace.final_answer, verify_data
                    )
                    confidence = evaluation.get("overall_quality", 50)
                    verified = confidence >= 60
                    
                    # If low confidence, try to improve with one more search pass
                    if not verified and confidence < 40:
                        if on_thought:
                            on_thought(" Low confidence — cross-checking answer...")
                        improved = generate_candidate_answer(goal, verify_data, temperature=0.2)
                        if improved:
                            re_eval = await asyncio.to_thread(
                                evaluate_answer_reliability, goal, improved, verify_data
                            )
                            if re_eval.get("overall_quality", 0) > confidence:
                                trace.final_answer = improved
                                confidence = re_eval["overall_quality"]
                                verified = confidence >= 60
                else:
                    confidence = 50  # Can't verify without data
            except Exception as e:
                print(f"⚠️ Verification error: {e}", file=sys.stderr)
                confidence = 50
    
    # --- Persist Trace (silently — only shown when user asks) ---
    trace_id = save_reasoning_trace(trace, verified=verified, confidence=confidence)
    
    return {
        "answer": trace.final_answer,
        "trace_id": trace_id,
        "verified": verified,
        "confidence": confidence
    }

async def _think_react(goal: str, trace: ReasoningTrace, context: str, handlers: Dict) -> Optional[tuple]:
    """Internal ReAct thinking logic"""
    if not async_client:
        return None
    
    # Available actions description
    AVAILABLE_ACTIONS_DESC = {
        "search": "Search the web for current information. Input: {query: string}",
        "search_knowledge": "Answer a knowledge question using search-backed AI reasoning. Input: {question: string}",
        "create_file": "Create a document or code file. Input: {file_type: string, topic: string}",
        "send_message": "Send via WhatsApp or email. Input: {recipient: string, message: string, method: 'whatsapp'|'email'}",
        "open_app": "Open an application. Input: {app_name: string}",
        "generate_image": "Generate an AI image. Input: {prompt: string}",
        "read_screen": "Capture and analyze the current screen content. Input: {query: string}",
        "read_document": "Read and query the active/uploaded document. Input: {query: string}",
        "finish": "Complete the task with a CONCISE, direct final answer. Input: {answer: string}"
    }
    
    actions_desc = "\n".join([f"- {name}: {AVAILABLE_ACTIONS_DESC[name]}" for name in handlers if name in AVAILABLE_ACTIONS_DESC])
    trace_context = trace.get_context() if trace.steps else "No previous steps."
    
    prompt = f"""You are an autonomous Critical Thinking Engine.
GOAL: {goal}
{f"CONTEXT: {context}" if context else ""}
PREVIOUS STEPS:
{trace_context}
AVAILABLE ACTIONS:
{actions_desc}

CRITICAL RULES:
1. If the goal mentions "screen", "display", "looking at", "see", or "on my screen", you MUST use "read_screen" FIRST before anything else — UNLESS the CONTEXT already contains screen analysis data (e.g. "INITIAL SCREEN ANALYSIS").
2. NEVER use "finish" as your first action UNLESS the CONTEXT already provides sufficient information to answer the goal directly.
3. Your final answer in "finish" MUST be based on the observations from previous steps or from the CONTEXT — do NOT give generic/placeholder answers.
4. If you already have observations from previous steps, use them to formulate a specific, accurate answer.
5. Keep answers concise and direct — give the actual answer, not instructions telling the user what to do.
6. If the CONTEXT already contains screen analysis with enough data to answer the goal, proceed directly to "finish" with the answer. Do NOT re-read the screen or search the web.

OUTPUT FORMAT (JSON only):
{{
    "thought": "Brief strategic reasoning",
    "action": "action_name",
    "action_input": {{"key": "value"}}
}}
Return ONLY valid JSON."""

    try:
        response = await _async_call_with_retry(
            model=MODEL_LIGHT,
            messages=[
                {"role": "system", "content": "You are a reasoning agent. Output only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1024
        )
        content = response.choices[0].message.content.strip()
        if "```json" in content: content = content.split("```json")[-1].split("```")[0].strip()
        elif "```" in content: content = content.split("```")[-1].split("```")[0].strip()
        
        result = json.loads(content)
        return (result.get("thought", ""), result.get("action", "finish"), result.get("action_input", {}))
    except Exception as e:
        print(f"⚠️ Reasoning Error: {e}", file=sys.stderr)
        return None

init_search_db()