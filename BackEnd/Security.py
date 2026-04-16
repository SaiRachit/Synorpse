"""
Input Validation & Security
Validates and sanitizes all user inputs to prevent injection attacks
"""
import re
import os
from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger("security")


class InputValidator:
    """Validate and sanitize user inputs"""
    
    # Dangerous patterns that should be blocked
    DANGEROUS_PATTERNS = [
        r"[;&|`$\(\)]",  # Shell command injection
        r"<script",  # XSS attempts
        r"\.\.\/",  # Directory traversal
        r"exec\s*\(",  # Python exec
        r"eval\s*\(",  # Python eval
        r"__import__",  # Dynamic imports
    ]
    
    # Allowed file extensions
    SAFE_FILE_EXTENSIONS = {
        ".pdf", ".docx", ".doc", ".txt", ".xlsx", ".xls", ".pptx", ".ppt",
        ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp",
        ".mp3", ".mp4", ".avi", ".mkv", ".mov",
        ".zip", ".rar", ".7z", ".tar", ".gz"
    }
    
    def __init__(self, config_manager=None):
        self.config = config_manager
        self.enabled = True
        if config_manager:
            self.enabled = config_manager.get("security.enable_input_validation", True)
            safe_exts = config_manager.get("security.allowed_file_extensions")
            if safe_exts:
                self.SAFE_FILE_EXTENSIONS = set(safe_exts)
    
    def validate_command(self, user_input: str) -> tuple[bool, Optional[str]]:
        """
        Validate user command for malicious patterns
        
        Returns:
            (is_valid, error_message) tuple
        """
        if not self.enabled:
            return (True, None)
        
        if not user_input or not user_input.strip():
            return (False, "Empty input")
        
        # Check length
        if len(user_input) > 5000:
            logger.warning(f"Input too long: {len(user_input)} characters")
            return (False, "Input too long (max 5000 characters)")
        
        # Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, user_input, re.IGNORECASE):
                logger.warning(f"Dangerous pattern detected: {pattern}")
                return (False, f"Input contains potentially dangerous pattern")
        
        return (True, None)
    
    def sanitize_file_path(self, file_path: str) -> Optional[str]:
        """
        Sanitize and validate file path
        
        Returns:
            Cleaned absolute path or None if invalid
        """
        if not file_path:
            return None
        
        try:
            # Convert to Path object
            path = Path(file_path).resolve()
            
            # Check if path exists
            if not path.exists():
                logger.debug(f"File path does not exist: {path}")
                return None
            
            # Check if it's actually a file
            if not path.is_file():
                logger.debug(f"Path is not a file: {path}")
                return None
            
            # Check extension
            if path.suffix.lower() not in self.SAFE_FILE_EXTENSIONS:
                logger.warning(f"Unsafe file extension: {path.suffix}")
                return None
            
            # Ensure it's not trying to escape allowed directories
            # (This is Windows-specific check)
            allowed_drives = ["C:", "D:", "E:"]
            if os.name == 'nt':
                drive = path.drive
                if drive and drive not in allowed_drives:
                    logger.warning(f"File on unauthorized drive: {drive}")
                    return None
            
            return str(path)
            
        except Exception as e:
            logger.error(f"Error sanitizing path: {e}")
            return None
    
    def validate_email(self, email: str) -> bool:
        """Validate email address format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    def sanitize_output(self, output: str) -> str:
        """Sanitize output to prevent information leakage"""
        if not output:
            return ""
        
        # Remove any potential sensitive paths
        output = re.sub(r'[A-Z]:\\Users\\[^\\]+', r'C:\Users\[USER]', output)
        
        # Remove any API keys that might have leaked
        output = re.sub(r'([a-zA-Z0-9]{20,})', r'***', output)
        
        return output


class RateLimiter:
    """Rate limiting for API calls and commands"""
    
    def __init__(self, max_requests: int = 60, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = []
    
    def is_allowed(self) -> bool:
        """Check if request is allowed under rate limit"""
        import time
        current_time = time.time()
        
        # Remove old requests outside the window
        self.requests = [req for req in self.requests 
                        if current_time - req < self.window_seconds]
        
        # Check if under limit
        if len(self.requests) < self.max_requests:
            self.requests.append(current_time)
            return True
        
        logger.warning(f"Rate limit exceeded: {len(self.requests)}/{self.max_requests}")
        return False
    
    def get_wait_time(self) -> float:
        """Get time to wait before next allowed request"""
        import time
        if not self.requests:
            return 0.0
        
        oldest_request = min(self.requests)
        current_time = time.time()
        elapsed = current_time - oldest_request
        
        if elapsed >= self.window_seconds:
            return 0.0
        
        return self.window_seconds - elapsed


class AuditLogger:
    """Log all user actions for security audit"""
    
    def __init__(self, log_file: str = "logs/audit.log"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(exist_ok=True)
        
        # Setup audit logger
        self.logger = logging.getLogger("audit")
        handler = logging.FileHandler(self.log_file, encoding='utf-8')
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_command(self, user: str, command: str, result: str = "success") -> None:
        """Log a user command"""
        # Sanitize before logging
        safe_command = command[:100]  # Truncate long commands
        self.logger.info(f"USER={user} | COMMAND={safe_command} | RESULT={result}")
    
    def log_file_access(self, user: str, file_path: str, action: str) -> None:
        """Log file access"""
        self.logger.info(f"USER={user} | FILE_ACCESS | PATH={file_path} | ACTION={action}")
    
    def log_security_event(self, event_type: str, details: str) -> None:
        """Log security-related events"""
        self.logger.warning(f"SECURITY | TYPE={event_type} | DETAILS={details}")


# Global instances
_validator = None
_rate_limiter = None
_audit_logger = None

def get_input_validator() -> InputValidator:
    """Get global input validator"""
    global _validator
    if _validator is None:
        from ConfigManager import get_config
        _validator = InputValidator(get_config())
    return _validator

def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter"""
    global _rate_limiter
    if _rate_limiter is None:
        from ConfigManager import get_config
        config = get_config()
        max_req = config.get("security.rate_limit_requests_per_minute", 60)
        _rate_limiter = RateLimiter(max_requests=max_req, window_seconds=60)
    return _rate_limiter

def get_audit_logger() -> AuditLogger:
    """Get global audit logger"""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
