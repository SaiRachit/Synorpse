from AppOpen import AppLauncher
from webbrowser import open as webopen
from dotenv import dotenv_values
from bs4 import BeautifulSoup
from rich import print
from groq import Groq
from fuzzywuzzy import fuzz
from pathlib import Path
import webbrowser
import subprocess
import requests
import keyboard
import asyncio
import platform
import os
import re
import json
import sys
import psycopg2
from psycopg2.extras import Json
import datetime
try:
    import win32com.client
except ImportError:
    win32com = None


def _pywhatkit_search(query):
    from pywhatkit import search
    return search(query)


def _pywhatkit_playonyt(query):
    from pywhatkit import playonyt
    return playonyt(query)

current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Import temporal file search
try:
    from TemporalFileSearch import (
        find_recent_files, 
        find_files_with_temporal_context,
        get_recently_opened_files
    )
except ImportError:
    print("⚠️ Warning: TemporalFileSearch not found")
    find_recent_files = None
    find_files_with_temporal_context = None
    get_recently_opened_files = None
    
try:
    from ConversationContext import get_conversation_context
except ImportError:
    print("⚠️ Warning: ConversationContext not found")
    def get_conversation_context(): return None

try:
    from RealTimeSearchEngine import RealtimeSearch
except ImportError:
    print("⚠️ Warning: RealTimeSearchEngine not found")
    def RealtimeSearch(query):
        return "Search engine not available."



try:
    from WhatsappIntegration import send_whatsapp_desktop, load_phone_numbers
    from MailIntegration import ProfessionalEmailSender
except ImportError:
    print("⚠️ Warning: WhatsappIntegration or MailIntegration not found")
    def load_phone_numbers(path):
        return {}
    def send_whatsapp_desktop(query, phonebook):
        print("❌ WhatsApp integration not available")
        return False
    class ProfessionalEmailSender:
        def __init__(self, api_key):
            pass
        def compose_and_send(self, **kwargs):
            print("❌ Email integration not available")
            return False

# Internet image search utilities
try:
    from InternetImages import search_google_images, show_images
except ImportError:
    print("⚠️ Warning: InternetImages not found")
    def search_google_images(query, num=3):
        print("❌ InternetImages.search_google_images not available")
        return []
    def show_images(urls):
        print("❌ InternetImages.show_images not available")
        return 0

env_vars = dotenv_values(".env")
GoogleAPIKey = env_vars.get("GoogleAPIKey")
GOOGLE_CSE_ID = env_vars.get("GOOGLE_CSE_ID")
SerpAPIKey = env_vars.get("SerpAPIKey")  # Fallback for when Google API reaches limit
YOUTUBE_API_KEY = env_vars.get("YOUTUBE_API_KEY")  # YouTube Data API v3
GroqAPIKey = env_vars.get("GroqAPIKey")
DB_NAME = env_vars.get("DB_NAME", "synorpse_chat")
DB_USER = env_vars.get("DB_USER", "postgres")
DB_PASSWORD = env_vars.get("DB_PASSWORD")
DB_HOST = env_vars.get("DB_HOST", "localhost")


classes = ["zCubwf","hgKElc","LTKOO sY7ric","Z0LcW","gsrt vk_bk FzvWSb YwPhnf","pclqee","tw-Data-text tw-text-small tw-ta",
           "IZ6rdc","O5uR6d LTKOO","vlzY6d","webanswers-webanswers_table__webanswers-table","dDoNo ikb48b gsrt","sXLaOe",
           "LWkfKe","VQF4g","qv3Wpe","kno-redsc","SPZz6b"]

useragent = 'Mozilla/5.0 (WIndows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Like Gecko) Chrome/100.0.4896.75 Safari/537.36'

client = Groq(api_key=GroqAPIKey)

professional_responses = [
    "Your satisfaction is my top priority; feel free to reach out if there's anything else I can help you with.",
    "I'm at your service for any additional questions or support you may need-don't hesitate to ask."
]

messages = []

try:
    PHONEBOOK = load_phone_numbers(r"Data/converted_contacts.csv")
except:
    PHONEBOOK = {}
    print("⚠️ Warning: Could not load phonebook from Data/converted_contacts.csv")

email_sender = None

def get_email_sender():
    global email_sender
    if email_sender is None:
        email_sender = ProfessionalEmailSender(GroqAPIKey)
    return email_sender


def CreateFile(file_type: str, topic: str):
    """
    Create a new file of the specified type with content about the topic.
    This is a synchronous wrapper for file creation functionality.
    
    Args:
        file_type: Type of file (python, word, pdf, text, markdown)
        topic: Subject/content topic for the file
    
    Returns:
        bool: Success status
    """
    try:
        from pathlib import Path
        from FileCreator import get_file_creator
        from AsyncWrappers import get_async_chatbot, get_async_search
        
        print(f"\n📝 Creating {file_type} file about: {topic}")
        
        # Initialize file creator with async wrappers
        async_chatbot = get_async_chatbot()
        async_search = get_async_search()
        file_creator = get_file_creator(
            chatbot_func=async_chatbot.query,
            search_func=async_search.search
        )
        
        # Generate safe filename
        safe_name = "".join(c for c in topic[:30] if c.isalnum() or c in (' ', '_', '-')).strip()
        safe_name = safe_name.replace(' ', '_')
        base_path = Path.home() / "Documents" / safe_name
        
        # Run async file creation synchronously
        import asyncio
        
        async def create_async():
            if file_type in ["python", "py"]:
                return await file_creator.create_python_file(str(base_path), topic)
            elif file_type in ["word", "doc", "docx"]:
                return await file_creator.create_word_file(str(base_path), topic, use_web=True)
            elif file_type == "pdf":
                return await file_creator.create_pdf_file(str(base_path), topic, use_web=True)
            elif file_type in ["text", "txt"]:
                return await file_creator.create_text_file(str(base_path), topic, use_web=True)
            elif file_type in ["markdown", "md"]:
                return await file_creator.create_text_file(str(base_path) + ".md", topic, use_web=True)
            else:
                # Default to word document
                return await file_creator.create_word_file(str(base_path), topic, use_web=True)
        
        # Get or create event loop
        try:
            loop = asyncio.get_running_loop()
            # If we're already in an async context, use run_coroutine_threadsafe
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(create_async(), loop)
            result = future.result(timeout=120)
        except RuntimeError:
            # No running loop, create one
            result = asyncio.run(create_async())
        
        if result and result.get("success"):
            file_path = result.get("path", "unknown")
            print(f"✅ Created file: {file_path}")
            
            log_automation(
                action_type="create_file",
                action_details=f"Created {file_type} file about '{topic}'",
                status="success",
                metadata={"file_type": file_type, "topic": topic, "path": str(file_path)}
            )
            return True
        else:
            error_msg = result.get("message", "Unknown error") if result else "Creation failed"
            print(f"❌ Failed to create file: {error_msg}")
            log_automation(
                action_type="create_file",
                action_details=f"Failed to create {file_type} file about '{topic}'",
                status="failed",
                metadata={"file_type": file_type, "topic": topic, "error": error_msg}
            )
            return False
        
    except Exception as e:
        print(f"❌ Error creating file: {e}")
        import traceback
        traceback.print_exc()
        log_automation(
            action_type="create_file",
            action_details=f"Error creating {file_type} file: {str(e)}",
            status="failed",
            metadata={"file_type": file_type, "topic": topic, "error": str(e)}
        )
        return False


def init_automation_db():
    """Initialize automation logs table"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST
        )
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS automation_logs (
                id SERIAL PRIMARY KEY,
                action_type VARCHAR(100) NOT NULL,
                action_details TEXT NOT NULL,
                status VARCHAR(50) NOT NULL,
                metadata JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_automation_logs_created_at ON automation_logs(created_at);
            CREATE INDEX IF NOT EXISTS idx_automation_logs_action_type ON automation_logs(action_type);
            CREATE INDEX IF NOT EXISTS idx_automation_logs_status ON automation_logs(status);
        """)
        conn.commit()
        conn.close()
    except Exception as e:
        # Keep error logging in the background if needed, but remove direct console print
        # Unless it's critical. But user asked for "no logging.. nothing".
        pass

def log_automation(action_type, action_details, status="success", metadata=None):
    """Log automation action to database"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST
        )
        cur = conn.cursor()
        
        cur.execute(
            "INSERT INTO automation_logs (action_type, action_details, status, metadata) VALUES (%s, %s, %s, %s)",
            (action_type, action_details, status, Json(metadata or {}))
        )
        conn.commit()
        conn.close()
        print(f"📝 Logged: {action_type} - {status}")
    except Exception as e:
        print(f"⚠️ Error logging automation: {e}")

def perform_serpapi_search(query, api_key, num=5):
    """Perform search using SerpAPI as fallback"""
    if not api_key:
        print("⚠️ SerpAPI Key not configured")
        return []
    
    url = "https://serpapi.com/search"
    params = {
        "q": query,
        "api_key": api_key,
        "engine": "google",
        "num": num
    }
    
    try:
        print("🔄 Using SerpAPI fallback...")
        response = requests.get(url, params=params)
        data = response.json()
        
        if "organic_results" in data:
            return [{"title": item.get("title", ""), "snippet": item.get("snippet", ""), "link": item.get("link", "")} 
                    for item in data["organic_results"][:num]]
        
        if "error" in data:
            print(f"❌ SerpAPI Error: {data['error']}")
        
        return []
    except Exception as e:
        print(f"❌ SerpAPI Exception: {e}")
        return []


def perform_google_search(query, api_key, cse_id, num=5):
    """Perform Google Search using Custom Search JSON API with SerpAPI fallback"""
    if not api_key or not cse_id:
        print("⚠️ Google API Key or CSE ID missing, trying SerpAPI...")
        return perform_serpapi_search(query, SerpAPIKey, num)
        
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": query,
        "key": api_key,
        "cx": cse_id,
        "num": num
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if "items" in data:
            # Return list of results with title, link, and snippet
            return [{"title": item["title"], "snippet": item.get("snippet", ""), "link": item["link"]} for item in data["items"]]
        
        if "error" in data:
            error_code = data['error'].get('code', 0)
            error_message = data['error'].get('message', 'Unknown error')
            print(f"❌ Google API Error ({error_code}): {error_message}")
            
            # Rate limit or quota exceeded - use SerpAPI fallback
            if error_code in [429, 403] or 'quota' in error_message.lower() or 'limit' in error_message.lower():
                print("📊 Google quota exceeded, switching to SerpAPI...")
                return perform_serpapi_search(query, SerpAPIKey, num)
            
        return []
    except Exception as e:
        print(f"❌ Google Search Exception: {e}")
        # Try SerpAPI as last resort
        print("🔄 Trying SerpAPI fallback...")
        return perform_serpapi_search(query, SerpAPIKey, num)

def get_automation_logs(limit=20, action_type=None):
    """Retrieve recent automation logs"""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST
        )
        cur = conn.cursor()
        
        if action_type:
            cur.execute(
                "SELECT action_type, action_details, status, metadata, created_at FROM automation_logs WHERE action_type = %s ORDER BY created_at DESC LIMIT %s",
                (action_type, limit)
            )
        else:
            cur.execute(
                "SELECT action_type, action_details, status, metadata, created_at FROM automation_logs ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
        
        logs = cur.fetchall()
        conn.close()
        
        return logs
    except Exception as e:
        print(f"❌ Error retrieving automation logs: {e}")
        return []

def GoogleSearch(Topic):
    """
    Perform a search. If it looks like a general question, use RealtimeSearch.
    Otherwise, open in browser.
    """
    try:
        # If it's a generic "search for..." or a question, use RealtimeSearch first
        if any(q in Topic.lower() for q in ["what", "who", "where", "when", "why", "how", "current", "latest"]):
            print(f"🤖 Using RealTimeSearch for: {Topic}")
            print(RealtimeSearch(Topic))
            return True
            
        # Fallback to browser search
        _pywhatkit_search(Topic)
        log_automation(
            action_type="google_search",
            action_details=f"Searched Google for: {Topic}",
            status="success",
            metadata={"query": Topic}
        )
        return True
    except Exception as e:
        log_automation(
            action_type="google_search",
            action_details=f"Failed to search Google for: {Topic}",
            status="failed",
            metadata={"query": Topic, "error": str(e)}
        )
        return False

def YouTubeSearch(Topic):
    try:
        Url4Search = f"https://www.youtube.com/results?search_query={Topic}"
        webbrowser.open(Url4Search)
        log_automation(
            action_type="youtube_search",
            action_details=f"Searched YouTube for: {Topic}",
            status="success",
            metadata={"query": Topic, "url": Url4Search}
        )
        return True
    except Exception as e:
        log_automation(
            action_type="youtube_search",
            action_details=f"Failed to search YouTube for: {Topic}",
            status="failed",
            metadata={"query": Topic, "error": str(e)}
        )
        return False


# Global storage for last YouTube search results (for "play the first video" functionality)
_last_youtube_results = []


def YouTubeAPISearch(query, max_results=5):
    """
    Search YouTube using the Data API v3 and store results for follow-up commands.
    Returns list of videos with title, url, and video_id.
    """
    global _last_youtube_results
    
    if not YOUTUBE_API_KEY:
        print("⚠️ YOUTUBE_API_KEY not configured, using browser search instead")
        YouTubeSearch(query)
        return []
    
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "part": "snippet",
        "q": query,
        "key": YOUTUBE_API_KEY,
        "type": "video",
        "maxResults": max_results
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if "error" in data:
            error_msg = data['error'].get('message', 'Unknown error')
            print(f"❌ YouTube API Error: {error_msg}")
            # Fallback to browser search
            YouTubeSearch(query)
            return []
        
        videos = []
        if "items" in data:
            for item in data["items"]:
                video_id = item["id"]["videoId"]
                title = item["snippet"]["title"]
                channel = item["snippet"]["channelTitle"]
                videos.append({
                    "title": title,
                    "channel": channel,
                    "video_id": video_id,
                    "url": f"https://www.youtube.com/watch?v={video_id}"
                })
        
        # Store results globally for follow-up commands
        _last_youtube_results = videos
        
        # Print results
        if videos:
            print(f"\n🎬 YouTube Search Results for '{query}':")
            for i, video in enumerate(videos, 1):
                print(f"   {i}. {video['title']}")
                print(f"      📺 {video['channel']} | {video['url']}")
            print()
        
        log_automation(
            action_type="youtube_search",
            action_details=f"Searched YouTube API for: {query}",
            status="success",
            metadata={"query": query, "results_count": len(videos), "videos": videos}
        )
        
        return videos
        
    except Exception as e:
        print(f"❌ YouTube API Exception: {e}")
        # Fallback to browser search
        YouTubeSearch(query)
        return []


def get_last_youtube_results():
    """Get the last YouTube search results for follow-up commands"""
    global _last_youtube_results
    return _last_youtube_results


def play_youtube_by_index(index=1):
    """Play a video from the last search results by index (1-based)"""
    global _last_youtube_results
    
    if not _last_youtube_results:
        print("❌ No recent YouTube search results. Try searching first!")
        return False
    
    if index < 1 or index > len(_last_youtube_results):
        print(f"❌ Invalid video index. Available: 1-{len(_last_youtube_results)}")
        return False
    
    video = _last_youtube_results[index - 1]
    print(f"▶️ Playing: {video['title']}")
    webbrowser.open(video['url'])
    
    log_automation(
        action_type="play_youtube",
        action_details=f"Playing video from search: {video['title']}",
        status="success",
        metadata={"video_id": video['video_id'], "title": video['title'], "url": video['url']}
    )
    return True


def PlayYouTube(query):
    try:
        _pywhatkit_playonyt(query)
        log_automation(
            action_type="play_youtube",
            action_details=f"Playing on YouTube: {query}",
            status="success",
            metadata={"query": query}
        )
        return True
    except Exception as e:
        log_automation(
            action_type="play_youtube",
            action_details=f"Failed to play on YouTube: {query}",
            status="failed",
            metadata={"query": query, "error": str(e)}
        )
        return False

_app_launcher = None

def get_app_launcher():
    """Get or create the AppLauncher instance (singleton pattern)"""
    global _app_launcher
    if _app_launcher is None:
        _app_launcher = AppLauncher()
    return _app_launcher

def Open(query, confidence_threshold=75, max_files=5, search_paths=None):
    """
    Unified open function that cascades through apps → files → web search.
    First searches for applications, then files if no apps found, then web if no files found.
    """
    try:
        # STEP 1: Try to find and open an application
        launcher = get_app_launcher()
        app_matches = launcher.fuzzy_match(query)
        
        if app_matches:
            best_match = app_matches[0]
            
            if launcher.launch_app(best_match[1]):
                log_automation(
                    action_type="open",
                    action_details=f"Opened application: {best_match[0]} (searched for: {query})",
                    status="success",
                    metadata={
                        "query": query,
                        "result_type": "application",
                        "matched_app": best_match[0],
                        "similarity_score": best_match[2]
                    }
                )
                return True
        
        # STEP 2: Try to find and open files
        file_matches = find_documents(query, search_paths)
        
        if file_matches:
            high_confidence_matches = [(path, score) for path, score in file_matches if score >= confidence_threshold]
            
            if high_confidence_matches:
                files_to_open = high_confidence_matches[:max_files]
                opened_count = 0
                opened_files = []
                
                for file_path, score in files_to_open:
                    if open_document(file_path):
                        opened_count += 1
                        opened_files.append({
                            "file_name": os.path.basename(file_path),
                            "file_path": file_path,
                            "confidence": score
                        })
                
                if opened_count > 0:
                    log_automation(
                        action_type="open",
                        action_details=f"Opened {opened_count} file(s) matching: {query}",
                        status="success",
                        metadata={
                            "query": query,
                            "result_type": "files",
                            "files_opened": opened_files
                        }
                    )
                    return True
            else:
                pass
        else:
            pass
        
        # STEP 3: Fall back to RealtimeSearch for synthesis
        answer = RealtimeSearch(query)
        
        if answer and not any(err in answer.lower() for err in ["error", "failed", "couldn't generate"]):
            log_automation(
                action_type="open",
                action_details=f"Resolved query via RealTimeSearch: {query}",
                status="success",
                metadata={
                    "query": query,
                    "result_type": "realtime_search",
                    "answer": answer[:200]
                }
            )
            return True
            
        # STEP 4: Fall back to web search links
        links = perform_google_search(query, GoogleAPIKey, GOOGLE_CSE_ID)
        
        if links:
            # Successfully got results from Google Custom Search API
            first_link = links[0]['link']
            try:
                webbrowser.open(first_link)
                log_automation(
                    action_type="open",
                    action_details=f"Opened website: {first_link} (searched for {query})",
                    status="success",
                    metadata={
                        "query": query,
                        "result_type": "web",
                        "url": first_link
                    }
                )
                return True
            except Exception as e:
                print(f"⚠️ Failed to open web link: {e}")
        
        # Fallback to pywhatkit search if everything else failed
        try:
            _pywhatkit_search(query)  # pywhatkit.search() opens Google search in browser
            log_automation(
                action_type="open",
                action_details=f"Opened Google search for: {query}",
                status="success",
                metadata={
                    "query": query,
                    "result_type": "web_search",
                    "method": "pywhatkit"
                }
            )
            return True
        except Exception as e:
            log_automation(
                action_type="open",
                action_details=f"Failed to open anything for: {query}",
                status="failed",
                metadata={"query": query, "error": str(e)}
            )
            return False
            
    except Exception as e:
        log_automation(
            action_type="open",
            action_details=f"Error in unified open function: {query}",
            status="failed",
            metadata={"query": query, "error": str(e)}
        )
        return False

# Keep OpenApp as a wrapper for backward compatibility
def OpenApp(app):
    """Open an application - now uses the unified Open function"""
    success = Open(app)
    
    # WhatsApp specific fallback for UWP app as a last resort
    if not success and "whatsapp" in app.lower():
        try:
            print("⚠️ Fuzzy match failed for WhatsApp, attempting direct UWP launch...")
            import subprocess
            subprocess.Popen('explorer.exe shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App', 
                           shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception:
            pass
            
    return success
        
def extract_search_term_with_ai(query):
    try:
        prompt = f"""Extract only the core file name or identifier from this search query. Remove any contextual words like file types (pdf, doc, etc.), action words (open, find, attach), articles (the, a, my), and other filler words.

Query: "{query}"

Return ONLY the essential search term, nothing else. No explanations, no extra text.

Examples:
Query: "sih 2025 pdf" → sih 2025
Query: "open the project proposal document" → project proposal
Query: "attach my quarterly report spreadsheet" → quarterly report
Query: "find SIH2025-IDEA-GAMIFIED file" → SIH2025-IDEA-GAMIFIED

Now extract from: "{query}"
"""
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=100
        )
        
        cleaned_term = response.choices[0].message.content.strip()
        
        if not cleaned_term or cleaned_term == query:
            return query
            
        return cleaned_term
        
    except Exception as e:
        return query

def resolve_shortcut(path):
    """Resolve a Windows .lnk shortcut to its target path."""
    if not path.lower().endswith('.lnk') or win32com is None:
        return path
        
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(path)
        return shortcut.Targetpath
    except Exception as e:
        print(f"⚠️ Shortcut resolution failed for {path}: {e}")
        return path


def find_documents(search_term, search_paths=None, extensions=None, use_ai=True):
    """Find documents using fuzzy matching and substring matching with AI-powered context filtering."""
    if extensions is None:
        extensions = ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.txt']
    
    if search_paths is None:
        if platform.system() == "Windows":
            search_paths = [
                os.path.expanduser("~/Documents"),
                os.path.expanduser("~/Desktop"),
                os.path.expanduser("~/Downloads"),
            ]
        else:
            search_paths = [
                os.path.expanduser("~/Documents"),
                os.path.expanduser("~/Desktop"),
                os.path.expanduser("~/Downloads"),
            ]
    
    original_term = search_term
    if use_ai:
        cleaned_term = extract_search_term_with_ai(search_term)
    else:
        cleaned_term = search_term
     
    matches = []
    search_term_lower = cleaned_term.lower()
    
    # NEW: Also search in Application indexing (AppLauncher)
    # This ensures that if it's found as an "application" (often a shortcut), we can find the target file
    try:
        launcher = get_app_launcher()
        app_matches = launcher.fuzzy_match(cleaned_term)
        for name, path, score in app_matches:
            # Resolve potential shortcuts
            target_path = resolve_shortcut(path)
            
            # If it's a file that exists and matches our extension filter (or we don't have one)
            if os.path.isfile(target_path):
                if not extensions or any(target_path.lower().endswith(ext) for ext in extensions):
                    matches.append((target_path, score * 100)) # Scale score to 100
    except Exception as e:
        print(f"⚠️ Error searching AppLauncher cache: {e}")

    for search_path in search_paths:
        if not os.path.exists(search_path):
            continue
            
        for root, dirs, files in os.walk(search_path):
            for file in files:
                if not any(file.lower().endswith(ext) for ext in extensions):
                    continue
                
                file_path = os.path.join(root, file)
                file_name = os.path.splitext(file)[0].lower()
                
                fuzzy_score = fuzz.partial_ratio(search_term_lower, file_name)
                
                if search_term_lower in file_name:
                    substring_bonus = 20
                else:
                    substring_bonus = 0
                
                confidence = min(fuzzy_score + substring_bonus, 100)
                
                # STRICTOR RELEVANCE: Penalty for missing unique keywords
                # If a word longer than 3 chars in query is completely missing from filename
                query_words = [w for w in search_term_lower.split() if len(w) > 3]
                for word in query_words:
                    if word not in file_name:
                        confidence -= 30
                
                if confidence >= 70:
                    matches.append((file_path, confidence))
    
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches


def open_document(file_path):
    """Open a document using the default application."""
    try:
        if platform.system() == "Windows":
            os.startfile(file_path)
        elif platform.system() == "Darwin": 
            subprocess.run(["open", file_path], check=True)
        else: 
            subprocess.run(["xdg-open", file_path], check=True)
        return True
    except Exception as e:
        print(f"Failed to open {file_path}: {e}")
        return False

def OpenFile(search_term, confidence_threshold=75, max_files=5, search_paths=None):
    """Search for and open documents - now uses the unified Open function"""
    return Open(search_term, confidence_threshold, max_files, search_paths)



def CloseApp(app):
    """Close an application - Note: This functionality requires platform-specific implementation"""
    if "chrome" in app.lower():
        log_automation(
            action_type="close_app",
            action_details=f"Skipped closing Chrome (protected)",
            status="skipped",
            metadata={"app_name": app}
        )
        return True
    else:
        try:
            system = platform.system()
            
            if system == "Windows":
                subprocess.run(["taskkill", "/IM", f"{app}.exe", "/F"], check=True, capture_output=True)
            elif system == "Darwin":  # macOS
                subprocess.run(["pkill", "-x", app], check=True, capture_output=True)
            else:  # Linux
                subprocess.run(["pkill", app], check=True, capture_output=True)
            
            log_automation(
                action_type="close_app",
                action_details=f"Closed application: {app}",
                status="success",
                metadata={"app_name": app}
            )
            return True
        except subprocess.CalledProcessError:
            print(f"⚠️ Application '{app}' may not be running or name doesn't match")
            log_automation(
                action_type="close_app",
                action_details=f"Failed to close application: {app} (not running or name mismatch)",
                status="failed",
                metadata={"app_name": app}
            )
            return False
        except Exception as e:
            log_automation(
                action_type="close_app",
                action_details=f"Failed to close application: {app}",
                status="failed",
                metadata={"app_name": app, "error": str(e)}
            )
            return False

def System(command):
    def mute():
        keyboard.press_and_release("volume mute")

    def unmute():
        keyboard.press_and_release("volume mute")

    def volume_up():
        keyboard.press_and_release("volume up")

    def volume_down():
        keyboard.press_and_release("volume down")

    try:
        if command == "mute":
            mute()
        elif command == "unmute":
            unmute()
        elif command == "volume up":
            volume_up()
        elif command == "volume down":
            volume_down()
        
        log_automation(
            action_type="system_control",
            action_details=f"System command executed: {command}",
            status="success",
            metadata={"command": command}
        )
        return True
    except Exception as e:
        log_automation(
            action_type="system_control",
            action_details=f"Failed to execute system command: {command}",
            status="failed",
            metadata={"command": command, "error": str(e)}
        )
        return False

def SendWhatsApp(query):
    """
    Send WhatsApp message using natural language query.
    Example: "send message to John saying hello"
    """
    if not PHONEBOOK:
        print("❌ No contacts loaded")
        log_automation(
            action_type="whatsapp_message",
            action_details="Failed to send WhatsApp message: No contacts loaded",
            status="failed",
            metadata={"query": query}
        )
        return False
    
    try:
        success = send_whatsapp_desktop(query, PHONEBOOK)
        
        if success:
            log_automation(
                action_type="whatsapp_message",
                action_details=f"Sent WhatsApp message: {query}",
                status="success",
                metadata={"query": query}
            )
        else:
            log_automation(
                action_type="whatsapp_message",
                action_details=f"Failed to send WhatsApp message: {query}",
                status="failed",
                metadata={"query": query}
            )
        
        return success
    except Exception as e:
        log_automation(
            action_type="whatsapp_message",
            action_details=f"Error sending WhatsApp message: {query}",
            status="failed",
            metadata={"query": query, "error": str(e)}
        )
        return False


def extract_email_context_with_ai(query):
    """
    Use AI to extract email components from natural language query.
    Returns: dict with recipient, subject_context, and potential_attachments
    """
    try:
        prompt = f"""Analyze this email query and extract:
1. Recipient email address
2. Main context/subject (what the email is about)
3. Any file/document names mentioned that should be attached (return empty if none)

Query: "{query}"

Return ONLY a JSON object in this exact format:
{{
    "recipient": "email@example.com or empty",
    "context": "main subject/context",
    "attachment_search_terms": ["term1", "term2"] or []
}}

Examples:
Query: "send email to john@test.com about quarterly report attach Q4 report"
{{"recipient": "john@test.com", "context": "quarterly report", "attachment_search_terms": ["Q4 report"]}}

Query: "email sarah@company.com project update include sih 2025 pdf and budget spreadsheet"
{{"recipient": "sarah@company.com", "context": "project update", "attachment_search_terms": ["sih 2025 pdf", "budget spreadsheet"]}}

Query: "email boss@work.com meeting tomorrow"
{{"recipient": "boss@work.com", "context": "meeting tomorrow", "attachment_search_terms": []}}

Query: "send mail to client@business.com with the proposal document"
{{"recipient": "client@business.com", "context": "proposal", "attachment_search_terms": ["proposal document"]}}

Now analyze: "{query}"
"""
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=300
        )
        
        result = response.choices[0].message.content.strip()
        
        result = result.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(result)
        
        return parsed
        
    except Exception as e:
        print(f"⚠️ AI extraction failed: {e}")
        return None


def SendEmail(query):
    """
    Send email using natural language query with AI-powered context and attachment detection.
    """
    try:
        sender = get_email_sender()
        
        print("🤖 Analyzing email query with AI...")
        email_info = extract_email_context_with_ai(query)
        
        if not email_info:
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, query)
            
            if not emails:
                print("❌ No valid email address found in query")
                log_automation(
                    action_type="email",
                    action_details="Failed to send email: No valid email address found",
                    status="failed",
                    metadata={"query": query}
                )
                return False
            
            recipient = emails[0]
            context = query
            attachment_search_terms = []
            
            attachment_keywords = ["attach", "include", "with", "send", "file", "document"]
            if any(keyword in query.lower() for keyword in attachment_keywords):
                words = query.split()
                for i, word in enumerate(words):
                    if word.lower() in attachment_keywords and i + 1 < len(words):
                        potential_term = " ".join(words[i+1:])
                        potential_term = re.sub(email_pattern, '', potential_term).strip()
                        if potential_term:
                            attachment_search_terms = [potential_term]
                            break
        else:
            recipient = email_info.get("recipient", "")
            context = email_info.get("context", query)
            attachment_search_terms = email_info.get("attachment_search_terms", [])
        
        if not recipient:
            print("❌ No valid email address found in query")
            log_automation(
                action_type="email",
                action_details="Failed to send email: No valid email address found",
                status="failed",
                metadata={"query": query}
            )
            return False
        
        attachments = []
        
        if attachment_search_terms:
            print(f"🔍 AI identified {len(attachment_search_terms)} potential attachment(s)")
            
            for search_term in attachment_search_terms:
                print(f"🔍 Searching for files matching '{search_term}'...")
                
                matches = find_documents(search_term, use_ai=True)
                
                if not matches:
                    print(f"❌ No files found matching '{search_term}'")
                    continue
                
                high_confidence_matches = [(path, score) for path, score in matches if score >= 75]
                
                if not high_confidence_matches:
                    print(f"❌ No files with confidence >= 75% for '{search_term}'")
                    print("📋 Top matches found:")
                    for path, score in matches[:3]:
                        print(f"  - {os.path.basename(path)} (confidence: {score}%)")
                    continue
                
                best_match = high_confidence_matches[0]
                print(f"📂 Found: {os.path.basename(best_match[0])} (confidence: {best_match[1]}%)")
                attachments.append(best_match[0])
        
        print(f"\n📧 Preparing email to {recipient}...")
        print(f"📝 Context: {context}")
        
        if attachments:
            print(f"📎 Attachments ({len(attachments)}):")
            for attachment in attachments:
                print(f"  ✓ {os.path.basename(attachment)}")
        else:
            print("📎 No attachments")
        
        attachment_path = attachments[0] if attachments else None
        
        if len(attachments) > 1:
            print(f"\n⚠️ Note: Found {len(attachments)} files, but attaching only the first one: {os.path.basename(attachments[0])}")
            print("   (Multiple attachments require email sender modification)")
        
        success = sender.compose_and_send(
            recipient_email=recipient,
            context=context,
            attachment_path=attachment_path,
            preview=False
        )
        
        if success:
            log_automation(
                action_type="email",
                action_details=f"Sent email to {recipient} about: {context}",
                status="success",
                metadata={
                    "recipient": recipient,
                    "context": context,
                    "attachments": [os.path.basename(a) for a in attachments] if attachments else [],
                    "query": query
                }
            )
        else:
            log_automation(
                action_type="email",
                action_details=f"Failed to send email to {recipient}",
                status="failed",
                metadata={
                    "recipient": recipient,
                    "context": context,
                    "query": query
                }
            )
        
        return success

    except Exception as e:
        print(f"❌ Error sending email: {e}")
        log_automation(
            action_type="email",
            action_details=f"Error sending email: {str(e)}",
            status="failed",
            metadata={"query": query, "error": str(e)}
        )
        import traceback
        traceback.print_exc()
        return False

def SearchAndEmail(command: str):
    """
    Execute composite workflow: Search Google -> Email results
    Command format: "search_query|recipient"
    """
    try:
        if "|" not in command:
            print("❌ Invalid SearchAndEmail command format (expected query|recipient)")
            return False
            
        parts = command.split('|', 1)
        search_query = parts[0].strip()
        recipient = parts[1].strip()
        
        print(f"\n🔍 Executing Search-and-Email workflow...")
        print(f"1. Searching for: '{search_query}'")
        
        # 1. Perform Search
        links = perform_google_search(search_query, GoogleAPIKey, GOOGLE_CSE_ID)
        
        if not links:
            print(f"❌ No results found for '{search_query}'")
            return False
            
        print(f"✅ Found {len(links)} results.")
        
        # 2. Send Email
        print(f"2. Emailing results to: {recipient}")
        
        # Initialize sender
        sender = ProfessionalEmailSender(GroqAPIKey)
        
        success = sender.compose_and_send(
            recipient_email=recipient,
            context=f"Search results for '{search_query}'",
            search_results=links,
            preview=False 
        )
        
        if success:
            log_automation(
                action_type="search_and_email",
                action_details=f"Emailed search results for '{search_query}' to {recipient}",
                status="success"
            )
        return success
        
    except Exception as e:
        print(f"❌ SearchAndEmail Error: {e}")
        return False

def SearchYouTubeAndShare(command: str):
    """
    Search YouTube and share the link
    Command: query|recipient|method
    """
    try:
        parts = command.split('|')
        if len(parts) < 3: return False
        
        query = parts[0].strip()
        recipient = parts[1].strip()
        method = parts[2].strip().lower()
        
        print(f"\n🎥 Searching YouTube for: '{query}'")
        
        # Use Google Search restricted to YouTube for better accuracy/URL extraction
        links = perform_google_search(f"site:youtube.com {query}", GoogleAPIKey, GOOGLE_CSE_ID)
        
        video_link = None
        for link in links:
            if "youtube.com/watch" in link or "youtu.be/" in link:
                video_link = link
                break
        
        if not video_link:
            print("❌ No video found.")
            return False
            
        print(f"✅ Found video: {video_link}")
        
        message = f"Check this out: {video_link}"
        
        if method == "whatsapp":
            print(f"📱 Sending via WhatsApp to {recipient}...")
            # We use send_whatsapp_desktop directly to bypass IntentRouter
            # Need to load phonebook locally or assume send_whatsapp_desktop handles it?
            # send_whatsapp_desktop requires phonebook arg.
            # We should load it here or default it.
            phonebook = load_phone_numbers(r"Data/converted_contacts.csv")
            return send_whatsapp_desktop(f"send {message} to {recipient}", phonebook)
            
        elif method == "email":
            print(f"📧 Sending via Email to {recipient}...")
            sender = ProfessionalEmailSender(GroqAPIKey)
            return sender.compose_and_send(
                recipient_email=recipient,
                context=f"Sharing video: {query}",
                additional_instructions=f"Include this link: {video_link}",
                preview=False
            )
            
        return True
    except Exception as e:
        print(f"❌ YouTube Share Error: {e}")
        return False

def FocusMode():
    """Close distracting apps"""
    distractions = ["discord", "steam", "spotify", "netflix", "instagram"]
    
    closed_count = 0
    
    # Use subprocess to kill common processes for robustness
    # This avoids circular dependency or import issues if CloseApp is not easily callable
    
    # We will use subprocess to kill common processes for robustness
    # This avoids circular dependency or import issues if CloseApp is not easily callable
    for app in distractions:
        try:
            subprocess.run(f"taskkill /f /im {app}.exe", shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
            # We don't verify closure to keep it fast
        except: pass
        
    return True


def ReadDocument(file_query: str):
    """
    Find and read a document to answer questions about it.
    Uses the same file search mechanics as OpenFile.
    
    Args:
        file_query: Search term to find the document
    
    Returns:
        str: Document content or analysis
    """
    try:
        # Split query by | for question support (from SemanticNLU)
        question = ""
        if "|" in file_query:
            file_query, question = file_query.split("|", 1)
            file_query = file_query.strip()
            question = question.strip()

        # Step 1: Force use of contextually uploaded file
        # We NO LONGER search the disk for files to avoid conflicts with Screen Reading.
        ctx = get_conversation_context()
        file_path = ctx.get_active_file() if ctx else None
        
        if not file_path or not os.path.exists(file_path):
            print(f"❌ No active document found in context.")
            return "I don't have an active document to read. Please **upload a file** using the paperclip 📎 icon in the chat header first."
        
        print(f"✅ Reading active document: {os.path.basename(file_path)}")

        # Step 2: Read and process the document
        from DocumentReader import DocumentReader
        try:
            reader = DocumentReader()
            if reader.read(file_path):
                content = reader.document_content
                
                log_automation(
                    action_type="read_document",
                    action_details=f"Read uploaded document: {os.path.basename(file_path)}",
                    status="success",
                    metadata={"file_path": file_path, "content_length": len(content) if content else 0}
                )
                
                # If a specific question was asked
                if question and question.lower() not in ["summarize", "analyze", "read", ""]:
                    print(f"❓ Asking question: {question}")
                    answer = reader.ask_question(question)
                    return f"**Document**: {os.path.basename(file_path)}\n**Question**: {question}\n\n**Answer**:\n{answer}"
                else:
                    # Default: return a summary
                    print(f"📊 Generating summary...")
                    summary = reader.get_document_summary()
                    return f"**Document**: {os.path.basename(file_path)}\n\n**Summary**:\n{summary}"
            else:
                print(f"❌ Could not read document content")
                return f"I found the file '{os.path.basename(file_path)}' but couldn't read its content."
                
        except Exception as e:
            print(f"❌ Error reading document: {e}")
            return f"Error reading document: {str(e)}"
        
    except Exception as e:
        print(f"❌ ReadDocument Error: {e}")
        import traceback
        traceback.print_exc()
        log_automation(
            action_type="read_document",
            action_details=f"Error reading document: {str(e)}",
            status="failed",
            metadata={"file_query": file_query, "error": str(e)}
        )
        return f"Error: {str(e)}"


def RecallAction():
    """
    Recall and repeat the last successful action.
    Uses the automation history to determine what to repeat.
    
    Returns:
        bool: Success status
    """
    try:
        print("\n🔄 Recalling last action...")
        
        # Get recent automation logs
        logs = get_automation_logs(limit=5)
        
        if not logs:
            print("❌ No recent actions to recall")
            return False
        
        # Find the most recent successful action that can be repeated
        for log in logs:
            action_type, action_details, status, metadata, created_at = log
            
            if status != "success":
                continue
            
            # Reconstruct and execute the action
            if action_type == "play_youtube":
                query = metadata.get('query')
                if query:
                    print(f"🔄 Replaying: {query}")
                    return PlayYouTube(query)
            
            elif action_type == "open_file":
                search_term = metadata.get('search_term')
                if search_term:
                    print(f"🔄 Reopening: {search_term}")
                    return OpenFile(search_term)
            
            elif action_type == "open_app":
                app_name = metadata.get('app_name')
                if app_name:
                    print(f"🔄 Reopening: {app_name}")
                    return OpenApp(app_name)
            
            elif action_type == "google_search":
                query = metadata.get('query')
                if query:
                    print(f"🔄 Re-searching: {query}")
                    return GoogleSearch(query)
            
            elif action_type == "youtube_search":
                query = metadata.get('query')
                if query:
                    print(f"🔄 Re-searching YouTube: {query}")
                    return YouTubeSearch(query)
            
            elif action_type == "whatsapp_message":
                query = metadata.get('query')
                if query:
                    print(f"🔄 Re-sending WhatsApp")
                    return SendWhatsApp(query)
            
            elif action_type == "email":
                recipient = metadata.get('recipient')
                context = metadata.get('context')
                if recipient and context:
                    print(f"🔄 Re-sending email to {recipient}")
                    return SendEmail(f"{context} to {recipient}")
        
        print("❌ No repeatable action found in recent history")
        return False
        
    except Exception as e:
        print(f"❌ RecallAction Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def RefreshApps():
    """Force refresh of application cache"""
    try:
        from AppOpen import AppLauncher
        launcher = AppLauncher()
        count = launcher.refresh_cache()
        print(f"✅ App cache refreshed! Found {count} apps.")
        return True
    except Exception as e:
        print(f"❌ Error refreshing apps: {e}")
        return False


def SearchAndShare(command: str):
    """
    Composite workflow: Search for information and share via WhatsApp or Email.
    Command format: "search_query|recipient|platform"
    Platform: "whatsapp" (default) or "email"
    """
    try:
        parts = command.split("|")
        if len(parts) < 2:
            print("❌ Invalid SearchAndShare format (expected query|recipient|platform)")
            return False
        
        search_query = parts[0].strip()
        recipient = parts[1].strip()
        platform = parts[2].strip().lower() if len(parts) > 2 else "whatsapp"
        
        print(f"\n🔍 Search and Share Workflow")
        print(f"   Query: '{search_query}'")
        print(f"   Recipient: {recipient}")
        print(f"   Platform: {platform}")
        
        # Step 1: Perform search using RealTimeSearch engine to get a synthesized answer
        print(f"\n1️⃣ Finding and synthesizing answer for: '{search_query}'...")
        from RealTimeSearchEngine import RealtimeSearch
        
        # Get synthesized answer
        answer = RealtimeSearch(search_query)
        
        if not answer or "Search error" in answer or "failed" in answer.lower():
            print("🔄 RealTimeSearch failed, falling back to basic link search...")
            search_results = perform_google_search(search_query, GoogleAPIKey, GOOGLE_CSE_ID)
            
            if not search_results:
                print("❌ No search results found.")
                return False
                
            # Format link results
            formatted_content = f"🔍 Search Results for: {search_query}\n\n"
            for i, result in enumerate(search_results[:5], 1):
                formatted_content += f"{i}. {result.get('title')}\n   🔗 {result.get('link')}\n\n"
        else:
            # Format the synthesized answer
            formatted_content = f"🤖 SYNORPSE Intelligence Support\nTopic: {search_query}\n{'-'*30}\n\n{answer}"
        
        print(f"✅ Information synthesized successfully.")
        
        # Step 2: Send via chosen platform
        if platform == "whatsapp":
            print(f"\n2️⃣ Sending via WhatsApp to {recipient}...")
            phonebook = load_phone_numbers(r"Data/converted_contacts.csv")
            
            # Import WhatsApp functions directly
            from WhatsappIntegration import resolve_alias, open_whatsapp_desktop, send_whatsapp_message
            
            # Resolve the contact
            contact = resolve_alias(recipient, phonebook)
            if not contact:
                print(f"❌ Could not find contact: {recipient}")
                return False
            
            # Open WhatsApp and send
            if not open_whatsapp_desktop():
                print("❌ Failed to open WhatsApp")
                return False
            
            success = send_whatsapp_message(contact, formatted_content)
            
        elif platform == "email":
            print(f"\n2️⃣ Sending via Email to {recipient}...")
            sender = get_email_sender()
            success = sender.compose_and_send(
                recipient_email=recipient,
                context=f"Intel Report: {search_query}",
                additional_instructions=formatted_content,
                preview=False
            )
        else:
            print(f"❌ Unknown platform: {platform}")
            return False
        
        if success:
            log_automation(
                action_type="search_and_share",
                action_details=f"Synthesized '{search_query}' and shared via {platform} to {recipient}",
                status="success",
                metadata={"query": search_query, "recipient": recipient, "platform": platform}
            )
            print(f"\n✅ Synthesized report shared successfully!")
        else:
            log_automation(
                action_type="search_and_share",
                action_details=f"Failed to share synthesized results via {platform}",
                status="failed",
                metadata={"query": search_query, "recipient": recipient, "platform": platform}
            )
            
        return success
        
    except Exception as e:
        print(f"❌ SearchAndShare Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def SendFileWhatsApp(command: str):
    """
    Send a file via WhatsApp.
    Command format: "file_query|recipient|message"
    """
    try:
        parts = command.split('|')
        if len(parts) < 2: return False
        
        file_query = parts[0].strip()
        recipient = parts[1].strip()
        message = parts[2].strip() if len(parts) > 2 else ""
        
        # 1. Find the file
        matches = find_documents(file_query, use_ai=True)
        if not matches:
            print(f"❌ No files found matching '{file_query}'")
            return False
            
        file_path = matches[0][0]
        
        # 2. Send via WhatsApp
        phonebook = load_phone_numbers(r"Data/converted_contacts.csv")
        from WhatsappIntegration import resolve_alias, open_whatsapp_desktop, send_whatsapp_file
        
        contact = resolve_alias(recipient, phonebook)
        if not contact: return False
        
        if not open_whatsapp_desktop(): return False
        
        return send_whatsapp_file(contact, file_path, message)
        
    except Exception as e:
        print(f"❌ SendFileWhatsApp error: {e}")
        return False

async def ReadScreenAndShare(command: str):
    """
    Composite: Capture screen -> Analyze -> Share via WhatsApp/Email
    Format: recipient|question|platform
    """
    try:
        parts = command.split('|')
        recipient = parts[0].strip()
        question = parts[1].strip() if len(parts) > 1 else ""
        platform = parts[2].strip().lower() if len(parts) > 2 else "whatsapp"
        
        print(f"\n🖥️ Composite: Read Screen and Share")
        
        # 1. Capture and analyze screen
        from ScreenReader import analyze_screen
        analysis = await analyze_screen(question)
        
        if not analysis or "Failed" in analysis:
            return "Failed to analyze screen for sharing."
            
        # 2. Share
        if platform == "whatsapp":
            phonebook = load_phone_numbers(r"Data/converted_contacts.csv")
            from WhatsappIntegration import resolve_alias, open_whatsapp_desktop, send_whatsapp_message
            contact = resolve_alias(recipient, phonebook)
            if contact and open_whatsapp_desktop():
                send_whatsapp_message(contact, analysis)
                return f"Analyzed screen and sent to {recipient} on WhatsApp."
        elif platform == "email":
            sender = get_email_sender()
            success = sender.compose_and_send(
                recipient_email=recipient,
                context="Screen Analysis Share",
                additional_instructions=analysis,
                preview=False
            )
            if success:
                return f"Analyzed screen and emailed to {recipient}."
                
        return "Analyzed screen but failed to share."
    except Exception as e:
        print(f"❌ ReadScreenAndShare error: {e}")
        return f"Error: {e}"

async def ReadScreenAndDocument(command: str):
    """
    Composite: Capture screen -> Analyze -> Create Document
    Format: file_type|question
    """
    try:
        parts = command.split('|')
        file_type = parts[0].strip() or "word"
        question = parts[1].strip() if len(parts) > 1 else ""
        
        # 1. Capture and analyze screen
        from ScreenReader import analyze_screen
        analysis = await analyze_screen(question)
        
        # 2. Create file
        return await asyncio.to_thread(CreateFile, file_type, f"Screen Analysis: {question or 'Summary'}", content=analysis)
    except Exception as e:
        return f"Error: {e}"

async def ReadScreenAndSearch(command: str):
    """
    Composite: Capture screen -> Analyze -> Search for more info
    Format: question
    """
    try:
        question = command.strip()
        # 1. Analyze
        from ScreenReader import analyze_screen
        analysis = await analyze_screen(question)
        
        # 2. Search (synthesized)
        from RealTimeSearchEngine import RealtimeSearch
        return await asyncio.to_thread(RealtimeSearch, f"Tell me more about this: {analysis[:500]}")
    except Exception as e:
        return f"Error: {e}"
    try:
        parts = command.split("|")
        if len(parts) < 2:
            print("❌ Invalid SendFileWhatsApp format (expected file_query|recipient|message)")
            return False
        
        file_query = parts[0].strip()
        recipient = parts[1].strip()
        message = parts[2].strip() if len(parts) > 2 else f"Here's the file: {file_query}"
        
        print(f"\n📎 Send File via WhatsApp")
        print(f"   File: '{file_query}'")
        print(f"   Recipient: {recipient}")
        print(f"   Message: {message[:50]}...")
        
        # Step 1: Find the file
        print(f"\n1️⃣ Searching for file: '{file_query}'...")
        
        # NEW: Prioritize AppLauncher database matches (same as the Open command)
        # This ensures that if "open resume" finds a specific shortcut, "send resume" finds the target of that shortcut.
        file_path = None
        
        try:
            launcher = get_app_launcher()
            app_matches = launcher.fuzzy_match(file_query)
            
            if app_matches:
                # We check matches for actual files
                for app_name, path, score in app_matches:
                    resolved_path = resolve_shortcut(path)
                    
                    # If it's an actual file (not just a directory or missing file), use it
                    if os.path.isfile(resolved_path):
                        # Filter for common document types to avoid sending .exe by mistake
                        doc_extensions = ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.txt', '.png', '.jpg', '.jpeg']
                        if any(resolved_path.lower().endswith(ext) for ext in doc_extensions):
                            file_path = resolved_path
                            print(f"✅ Found via indexed shorthand: {os.path.basename(file_path)} (confidence: {score*100:.0f}%)")
                            break
        except Exception as e:
            print(f"⚠️ App index check failed: {e}")

        # Fallback to general file search if no appropriate indexed match
        if not file_path:
            try:
                from TemporalFileSearch import find_files_with_temporal_context
                matches = find_files_with_temporal_context(file_query, None)
            except ImportError:
                matches = find_documents(file_query, use_ai=True)
            
            if not matches:
                print(f"❌ No files found matching '{file_query}'")
                return False
            
            # Get best match
            if isinstance(matches[0], tuple):
                file_path = matches[0][0]
                confidence = matches[0][1] if len(matches[0]) > 1 else 100
            else:
                file_path = matches[0]
                confidence = 100
                
            print(f"✅ Found via folder search: {os.path.basename(file_path)} (confidence: {confidence}%)")
        
        # Step 2: Send via WhatsApp
        print(f"\n2️⃣ Sending via WhatsApp to {recipient}...")
        
        phonebook = load_phone_numbers(r"Data/converted_contacts.csv")
        
        # Import WhatsApp functions directly
        from WhatsappIntegration import resolve_alias, open_whatsapp_desktop, send_whatsapp_message
        
        # Resolve the contact
        contact = resolve_alias(recipient, phonebook)
        if not contact:
            print(f"❌ Could not find contact: {recipient}")
            return False
        
        # Open WhatsApp and send with file attachment
        if not open_whatsapp_desktop():
            print("❌ Failed to open WhatsApp")
            return False
        
        success = send_whatsapp_message(contact, message, file_path)
        
        if success:
            log_automation(
                action_type="send_file_whatsapp",
                action_details=f"Sent file '{os.path.basename(file_path)}' to {recipient} via WhatsApp",
                status="success",
                metadata={"file": os.path.basename(file_path), "recipient": recipient}
            )
            print(f"\n✅ File sent successfully!")
        else:
            log_automation(
                action_type="send_file_whatsapp",
                action_details=f"Failed to send file to {recipient}",
                status="failed",
                metadata={"file_query": file_query, "recipient": recipient}
            )
            
        return success
        
    except Exception as e:
        print(f"❌ SendFileWhatsApp Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def SearchAndShowImages(query, num=2):
    """Helper: search images via InternetImages and display them."""
    try:
        urls = search_google_images(query, num=num)
        if urls:
            show_images(urls)
        return urls
    except Exception as e:
        print(f"✗ SearchAndShowImages error: {e}")
        return []


async def TranslateAndExecute(commands: list[str]):
    funcs = []
    
    for command in commands:
        if command == "refresh_apps":
             fun = asyncio.to_thread(RefreshApps)
             funcs.append(fun)
             continue
             
        # Check for search_and_email workflow
        if command.startswith("search_and_email "):
             query = command.removeprefix("search_and_email ")
             fun = asyncio.to_thread(SearchAndEmail, query)
             funcs.append(fun)
             continue
             
        # Check for search_youtube_and_share
        if command.startswith("search_youtube_and_share "):
             parts = command.removeprefix("search_youtube_and_share ")
             fun = asyncio.to_thread(SearchYouTubeAndShare, parts)
             funcs.append(fun)
             continue

        # Check for image search
        if command.startswith("search images "):
             query = command.removeprefix("search images ")
             fun = asyncio.to_thread(SearchAndShowImages, query)
             funcs.append(fun)
             continue
        
        # Check for search_and_share (new composite workflow)
        if command.startswith("search_and_share "):
             parts = command.removeprefix("search_and_share ")
             fun = asyncio.to_thread(SearchAndShare, parts)
             funcs.append(fun)
             continue
        
        # Check for send_file_whatsapp (new composite workflow)
        if command.startswith("send_file_whatsapp "):
             parts = command.removeprefix("send_file_whatsapp ")
             fun = asyncio.to_thread(SendFileWhatsApp, parts)
             funcs.append(fun)
             continue
             
        # Check for focus mode
        if command == "focus_mode":
             fun = asyncio.to_thread(FocusMode)
             funcs.append(fun)
             continue

        # Use enhanced file operations for temporal support
        if command.startswith("open file "):
            if "open it" in command:
                pass
            else:
                query = command.removeprefix("open file ").strip()
                # Check if temporal context is present
                if 'temporal:' in query:
                    from EnhancedFileOperations import open_file_with_temporal_context
                    fun = asyncio.to_thread(open_file_with_temporal_context, query)
                else:
                    fun = asyncio.to_thread(OpenFile, query)
                funcs.append(fun)
        
        elif command.startswith("open "):
            query = command.removeprefix("open ").strip()
            # Use OpenApp for general open commands
            fun = asyncio.to_thread(OpenApp, query)
            funcs.append(fun)

        # NEW: Handle file creation commands
        elif command.startswith("create "):
            # Parse "create python file about fibonacci code" format
            parts = command.removeprefix("create ").strip()
            # Extract file type and topic
            file_type = "word"
            topic = parts
            
            if " file about " in parts:
                file_type_part, topic = parts.split(" file about ", 1)
                file_type = file_type_part.strip()
            elif " file " in parts:
                file_type_part, topic = parts.split(" file ", 1)
                file_type = file_type_part.strip()
            
            fun = asyncio.to_thread(CreateFile, file_type, topic)
            funcs.append(fun)
        
        elif command.startswith("general "):
            pass
        elif command.startswith("realtime "):
            pass

        elif command.startswith("close "):
            fun = asyncio.to_thread(CloseApp, command.removeprefix("close "))
            funcs.append(fun)
        
        elif command.startswith("play "):
            fun = asyncio.to_thread(PlayYouTube, command.removeprefix("play "))
            funcs.append(fun)

        elif command.startswith("google search "):
            fun = asyncio.to_thread(GoogleSearch, command.removeprefix("google search "))
            funcs.append(fun)
        
        elif command.startswith("youtube search "):
            fun = asyncio.to_thread(YouTubeAPISearch, command.removeprefix("youtube search "))
            funcs.append(fun)
        
        # Handle "play the first video" / "play first video" / "play video 1" etc
        elif any(phrase in command.lower() for phrase in ["play the first", "play first", "play 1st", "play video 1"]):
            fun = asyncio.to_thread(play_youtube_by_index, 1)
            funcs.append(fun)
        elif any(phrase in command.lower() for phrase in ["play the second", "play second", "play 2nd", "play video 2"]):
            fun = asyncio.to_thread(play_youtube_by_index, 2)
            funcs.append(fun)
        elif any(phrase in command.lower() for phrase in ["play the third", "play third", "play 3rd", "play video 3"]):
            fun = asyncio.to_thread(play_youtube_by_index, 3)
            funcs.append(fun)
        
        elif command.startswith("system "):
            fun = asyncio.to_thread(System, command.removeprefix("system "))
            funcs.append(fun)
        
        elif command.startswith("whatsapp "):
            query = command.removeprefix("whatsapp ")
            fun = asyncio.to_thread(SendWhatsApp, query)
            funcs.append(fun)
        
        elif command.startswith("email "):
            query = command.removeprefix("email ")
            fun = asyncio.to_thread(SendEmail, query)
            funcs.append(fun)
        
        # NEW: Focus mode handler
        elif command == "focus_mode":
            fun = asyncio.to_thread(FocusMode)
            funcs.append(fun)
        
        # NEW: Read document handler (uses file search)
        elif command.startswith("read_document "):
            file_query = command.removeprefix("read_document ").strip()
            fun = asyncio.to_thread(ReadDocument, file_query)
            funcs.append(fun)
        
        # NEW: Recall action handler
        elif command == "recall_action":
            fun = asyncio.to_thread(RecallAction)
            funcs.append(fun)
            
        # COMPOSITE HANDLERS
        elif command.startswith("search_and_share "):
            fun = asyncio.to_thread(SearchAndShare, command.removeprefix("search_and_share "))
            funcs.append(fun)
            
        elif command.startswith("search_and_email "):
            fun = asyncio.to_thread(SearchAndEmail, command.removeprefix("search_and_email "))
            funcs.append(fun)
            
        elif command.startswith("search_youtube_and_share "):
            fun = asyncio.to_thread(SearchYouTubeAndShare, command.removeprefix("search_youtube_and_share "))
            funcs.append(fun)
            
        elif command.startswith("send_file_whatsapp "):
            fun = asyncio.to_thread(SendFileWhatsApp, command.removeprefix("send_file_whatsapp "))
            funcs.append(fun)
            
        elif command.startswith("read_screen_and_share "):
            fun = ReadScreenAndShare(command.removeprefix("read_screen_and_share "))
            funcs.append(fun)
            
        elif command.startswith("read_screen_and_document "):
            fun = ReadScreenAndDocument(command.removeprefix("read_screen_and_document "))
            funcs.append(fun)
            
        elif command.startswith("read_screen_and_search "):
            fun = ReadScreenAndSearch(command.removeprefix("read_screen_and_search "))
            funcs.append(fun)

        elif command.startswith("read_screen"):
            # Simple read screen (not composite)
            from ScreenReader import analyze_screen
            question = command.removeprefix("read_screen").strip()
            fun = analyze_screen(question)
            funcs.append(fun)

        else:
            print(f"No function found for {command}")

    results = await asyncio.gather(*funcs)

    for result in results:
        if isinstance(result, str):
            yield result
        else:
            yield result

async def Automation(commands: list[str]):
    results = []
    async for result in TranslateAndExecute(commands):
        if result:
            # Unpack JSON if present for clean terminal/widget output
            msg = str(result)
            if msg.strip().startswith('{') and msg.strip().endswith('}'):
                try:
                    import json as _json
                    parsed = _json.loads(msg)
                    if 'analysis' in parsed:
                        msg = parsed['analysis']
                    elif 'response' in parsed:
                        msg = parsed['response']
                except:
                    pass
            print(msg) # Print clean message for stdout capture
            results.append(result)
    return results


def get_recent_automation_context(limit=10):
    """
    Get recent automation logs formatted for AI context understanding.
    Returns a string summary of recent actions.
    """
    try:
        logs = get_automation_logs(limit=limit)
        
        if not logs:
            return "No recent automation history available."
        
        context_parts = ["Recent automation history:"]
        
        for log in logs:
            action_type, action_details, status, metadata, created_at = log
            
            time_diff = datetime.datetime.now(datetime.timezone.utc) - created_at
            
            if time_diff.total_seconds() < 60:
                time_str = "just now"
            elif time_diff.total_seconds() < 3600:
                minutes = int(time_diff.total_seconds() / 60)
                time_str = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
            elif time_diff.total_seconds() < 86400:
                hours = int(time_diff.total_seconds() / 3600)
                time_str = f"{hours} hour{'s' if hours > 1 else ''} ago"
            else:
                days = int(time_diff.total_seconds() / 86400)
                time_str = f"{days} day{'s' if days > 1 else ''} ago"
            
            if action_type == "play_youtube":
                query = metadata.get('query', 'unknown')
                context_parts.append(f"- {time_str}: Played '{query}' on YouTube ({status})")
            
            elif action_type == "open_file":
                search_term = metadata.get('search_term', 'unknown')
                files = metadata.get('files_opened', [])
                if files:
                    file_names = [f['file_name'] for f in files]
                    context_parts.append(f"- {time_str}: Opened file(s) '{', '.join(file_names)}' (searched for: {search_term})")
                else:
                    context_parts.append(f"- {time_str}: Failed to find file matching '{search_term}'")
            
            elif action_type == "open_app":
                app_name = metadata.get('app_name', 'unknown')
                context_parts.append(f"- {time_str}: Opened application '{app_name}' ({status})")
            
            elif action_type == "google_search":
                query = metadata.get('query', 'unknown')
                context_parts.append(f"- {time_str}: Searched Google for '{query}' ({status})")
            
            elif action_type == "youtube_search":
                query = metadata.get('query', 'unknown')
                context_parts.append(f"- {time_str}: Searched YouTube for '{query}' ({status})")
            
            elif action_type == "whatsapp_message":
                query = metadata.get('query', 'unknown')
                context_parts.append(f"- {time_str}: Sent WhatsApp message ({status})")
            
            elif action_type == "email":
                recipient = metadata.get('recipient', 'unknown')
                context = metadata.get('context', 'unknown')
                context_parts.append(f"- {time_str}: Sent email to {recipient} about '{context}' ({status})")
            
            elif action_type == "close_app":
                app_name = metadata.get('app_name', 'unknown')
                context_parts.append(f"- {time_str}: Closed application '{app_name}' ({status})")
            
            elif action_type == "system_control":
                command = metadata.get('command', 'unknown')
                context_parts.append(f"- {time_str}: System command '{command}' ({status})")
            
            else:
                context_parts.append(f"- {time_str}: {action_details} ({status})")
        
        return "\n".join(context_parts)
    
    except Exception as e:
        print(f"⚠️ Error getting automation context: {e}")
        return "Unable to retrieve automation history."


def get_last_action_of_type(action_type):
    """
    Get the most recent action of a specific type.
    Useful for "do it again" or "repeat that" commands.
    """
    try:
        logs = get_automation_logs(limit=1, action_type=action_type)
        
        if not logs:
            return None
        
        action_type, action_details, status, metadata, created_at = logs[0]
        
        return {
            'action_type': action_type,
            'action_details': action_details,
            'status': status,
            'metadata': metadata,
            'created_at': created_at
        }
    
    except Exception as e:
        print(f"⚠️ Error getting last action: {e}")
        return None


def build_ai_prompt_with_context(user_query, context_limit=10):
    """
    Build an AI prompt that includes automation context.
    This helps the AI understand references to previous actions.
    """
    automation_context = get_recent_automation_context(limit=context_limit)
    
    prompt = f"""You are an intelligent automation assistant. You have access to the user's recent automation history to understand context and references.

{automation_context}

Current user query: "{user_query}"

Based on the automation history above, interpret the user's query. If the user refers to previous actions (like "play it again", "open that file again", "send another message", etc.), identify what they're referring to and provide the appropriate command.

If the query is a new action (not referencing history), process it normally.

Your response should be one or more automation commands in this format:
- play [song/video name]
- open [app/website name]
- open file [file name]
- google search [query]
- youtube search [query]
- close [app name]
- system [mute/unmute/volume up/volume down]
- whatsapp [message query]
- email [email query]
- general [for conversational responses]
- realtime [for web search queries]

Examples:
User: "play it again" (after playing "Imagine Dragons" recently)
Response: play Imagine Dragons

User: "open that file again" (after opening "project_proposal.pdf")
Response: open file project proposal

User: "search for the same thing on YouTube" (after Google search for "python tutorials")
Response: youtube search python tutorials

Now process the current query considering the automation history."""

    return prompt


def extract_referenced_action(user_query):
    """
    Detect if user is referencing a previous action and return the relevant details.
    """
    reference_keywords = {
        'play': ['again', 'same', 'that', 'repeat', 'same song', 'same video'],
        'open': ['again', 'same', 'that', 'that file', 'that app'],
        'search': ['again', 'same', 'same thing', 'that'],
        'send': ['again', 'another', 'same'],
    }
    
    query_lower = user_query.lower()
    
    if any(keyword in query_lower for keyword in ['play', 'song', 'video', 'music']):
        if any(ref in query_lower for ref in reference_keywords['play']):
            last_play = get_last_action_of_type('play_youtube')
            if last_play and last_play['status'] == 'success':
                query = last_play['metadata'].get('query')
                print(f"🔄 Detected reference to previous play: '{query}'")
                return f"play {query}"
    
    if any(keyword in query_lower for keyword in ['open', 'file', 'document']):
        if any(ref in query_lower for ref in reference_keywords['open']):
            last_file = get_last_action_of_type('open_file')
            if last_file and last_file['status'] == 'success':
                files_opened = last_file['metadata'].get('files_opened', [])
                if files_opened:
                    file_name = files_opened[0]['file_name']
                    print(f"🔄 Detected reference to previous file: '{file_name}'")
                    return f"open file {file_name}"
    
    if 'search' in query_lower:
        if any(ref in query_lower for ref in reference_keywords['search']):
            last_google = get_last_action_of_type('google_search')
            last_youtube = get_last_action_of_type('youtube_search')
            
            last_search = None
            if last_google and last_youtube:
                last_search = last_google if last_google['created_at'] > last_youtube['created_at'] else last_youtube
            elif last_google:
                last_search = last_google
            elif last_youtube:
                last_search = last_youtube
            
            if last_search and last_search['status'] == 'success':
                query = last_search['metadata'].get('query')
                search_type = 'youtube search' if last_search['action_type'] == 'youtube_search' else 'google search'
                print(f"🔄 Detected reference to previous search: '{query}'")
                return f"{search_type} {query}"
    
    return None


async def ProcessQueryWithContext(user_query):
    """
    Process user query with automation context awareness.
    This should be called before your main AI command extraction.
    """
    referenced_command = extract_referenced_action(user_query)
    
    if referenced_command:
        print(f"✅ Resolved reference: '{user_query}' → '{referenced_command}'")
        await Automation([referenced_command])
        return True
    
    prompt = build_ai_prompt_with_context(user_query)
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        
        ai_response = response.choices[0].message.content.strip()
        print(f"🤖 AI interpreted query as: {ai_response}")
        
        commands = [line.strip() for line in ai_response.split('\n') if line.strip()]
        await Automation(commands)
        return True
        
    except Exception as e:
        print(f"❌ Error processing query with context: {e}")
        return False

if __name__ == "__main__":
    init_automation_db()
    asyncio.run(Automation(["open python tutorial"]))
