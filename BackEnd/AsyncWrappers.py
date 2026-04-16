"""
Async Wrappers - Convert synchronous backend modules to async
Prevents blocking the event loop during I/O operations
"""
import asyncio
from typing import Any, Optional
from functools import wraps
import time


class AsyncChatBot:
    """Async wrapper for ChatBot module"""
    
    def __init__(self):
        from ChatBot import ChatBot as SyncChatBot
        self._sync_chatbot = SyncChatBot
    
    async def query(self, text: str, query_metadata: Optional[dict] = None) -> str:
        """Execute ChatBot query asynchronously"""
        return await asyncio.to_thread(self._sync_chatbot, text, query_metadata)


class AsyncRealtimeSearch:
    """Async wrapper for RealtimeSearch module"""
    
    def __init__(self):
        from RealTimeSearchEngine import RealtimeSearch
        self._search = RealtimeSearch
    
    async def search(self, query: str, on_thought=None, context=None, force_reasoning=False) -> str:
        """Execute search query asynchronously"""
        return await self._search(query, on_thought=on_thought, context=context, force_reasoning=force_reasoning)


class AsyncImageGenerator:
    """Async wrapper for ImageGeneration module"""
    
    def __init__(self):
        self._generator = None
    
    def _get_generator(self):
        """Lazy load generator"""
        if self._generator is None:
            from ImageGeneration import LocalImageGenerator
            self._generator = LocalImageGenerator()
        return self._generator
    
    async def generate(self, prompt: str, seed: Optional[int] = None) -> tuple:
        """Generate image asynchronously"""
        gen = self._get_generator()
        return await asyncio.to_thread(gen.generate_image, prompt, seed)
    
    async def save_to_db(self, image, original_prompt: str, 
                        enhanced_prompt: str, seed: int) -> int:
        """Save image to database asynchronously"""
        gen = self._get_generator()
        return await asyncio.to_thread(
            gen.save_image_to_db, image, original_prompt, enhanced_prompt, seed
        )
    
    async def save_to_file(self, image, prompt: str, seed: int) -> None:
        """Save image to file asynchronously"""
        gen = self._get_generator()
        return await asyncio.to_thread(gen.save_image_to_file, image, prompt, seed)


class AsyncScreenReader:
    """Async wrapper for ScreenReader module"""
    
    def __init__(self):
        from ScreenReader import analyze_screen
        self._analyze = analyze_screen
    
    async def analyze(self, question: str = "") -> str:
        """Analyze screen asynchronously"""
        return await self._analyze(question)


class AsyncAutomation:
    """Async wrapper ensuring Automation runs properly"""
    
    def __init__(self):
        # Automation is already async, just import it
        pass
    
    async def execute(self, commands: list[str]) -> list:
        """Execute automation commands"""
        from Automation import Automation
        return await Automation(commands)


# Retry decorator with exponential backoff
def async_retry(max_retries: int = 3, base_delay: float = 1.0, 
                exponential_backoff: bool = True):
    """
    Decorator for async functions with retry logic and exponential backoff
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds between retries
        exponential_backoff: Whether to use exponential backoff
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt) if exponential_backoff else base_delay
                        print(f" Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                    else:
                        print(f" All {max_retries + 1} attempts failed")
            
            raise last_exception
        
        return wrapper
    return decorator


# Timeout decorator
def async_timeout(seconds: float):
    """
    Decorator to add timeout to async functions
    
    Args:
        seconds: Timeout in seconds
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Operation timed out after {seconds} seconds")
        
        return wrapper
    return decorator


# Circuit Breaker implementation
class CircuitBreaker:
    """
    Circuit breaker pattern for async operations
    Prevents cascading failures by temporarily disabling failed operations
    """
    
    def __init__(self, failure_threshold: int = 5, timeout: float = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half_open
    
    def is_open(self) -> bool:
        """Check if circuit is open (blocking calls)"""
        if self.state == "open":
            if time.time() - self.last_failure_time >= self.timeout:
                self.state = "half_open"
                return False
            return True
        return False
    
    def record_success(self) -> None:
        """Record successful operation"""
        self.failure_count = 0
        self.state = "closed"
    
    def record_failure(self) -> None:
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            print(f" Circuit breaker opened after {self.failure_count} failures")
    
    def __call__(self, func):
        """Decorator to apply circuit breaker to async functions"""
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if self.is_open():
                raise Exception(f"Circuit breaker is open, operation blocked")
            
            try:
                result = await func(*args, **kwargs)
                self.record_success()
                return result
            except Exception as e:
                self.record_failure()
                raise e
        
        return wrapper


# Global instances
_chatbot = None
_search = None
_image_gen = None
_automation = None
_screen_reader = None

def get_async_chatbot() -> AsyncChatBot:
    """Get async chatbot instance"""
    global _chatbot
    if _chatbot is None:
        _chatbot = AsyncChatBot()
    return _chatbot

def get_async_search() -> AsyncRealtimeSearch:
    """Get async search instance"""
    global _search
    if _search is None:
        _search = AsyncRealtimeSearch()
    return _search

def get_async_image_generator() -> AsyncImageGenerator:
    """Get async image generator instance"""
    global _image_gen
    if _image_gen is None:
        _image_gen = AsyncImageGenerator()
    return _image_gen

def get_async_automation() -> AsyncAutomation:
    """Get async automation instance"""
    global _automation
    if _automation is None:
        _automation = AsyncAutomation()
    return _automation

def get_async_screen_reader() -> AsyncScreenReader:
    """Get async screen reader instance"""
    global _screen_reader
    if _screen_reader is None:
        _screen_reader = AsyncScreenReader()
    return _screen_reader
