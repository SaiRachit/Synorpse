"""
Structured Logging Configuration
Provides comprehensive logging with file rotation, performance tracking, and different log levels
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
import time
from datetime import datetime
import json


class PerformanceLogger:
    """Track and log performance metrics"""
    
    def __init__(self):
        self.metrics = {}
    
    def start_timer(self, operation: str) -> float:
        """Start timing an operation"""
        start_time = time.time()
        self.metrics[operation] = {"start": start_time, "end": None, "duration": None}
        return start_time
    
    def end_timer(self, operation: str) -> float:
        """End timing and calculate duration"""
        if operation in self.metrics:
            end_time = time.time()
            self.metrics[operation]["end"] = end_time
            duration = end_time - self.metrics[operation]["start"]
            self.metrics[operation]["duration"] = duration
            return duration
        return 0.0
    
    def log_metric(self, operation: str, value: float, unit: str = "seconds") -> None:
        """Log a performance metric"""
        logger = get_logger("performance")
        logger.info(f"{operation}: {value:.3f} {unit}")
    
    def get_summary(self) -> dict:
        """Get performance summary"""
        return {
            op: {
                "duration": data["duration"],
                "timestamp": datetime.fromtimestamp(data["start"]).isoformat()
            }
            for op, data in self.metrics.items()
            if data["duration"] is not None
        }


class ContextLogger:
    """Logger with context tracking"""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.context = {}
    
    def add_context(self, **kwargs) -> None:
        """Add context information"""
        self.context.update(kwargs)
    
    def clear_context(self) -> None:
        """Clear context"""
        self.context = {}
    
    def _format_message(self, msg: str) -> str:
        """Format message with context"""
        if self.context:
            context_str = " | ".join([f"{k}={v}" for k, v in self.context.items()])
            return f"{msg} [{context_str}]"
        return msg
    
    def debug(self, msg: str, **kwargs) -> None:
        self.add_context(**kwargs)
        self.logger.debug(self._format_message(msg))
    
    def info(self, msg: str, **kwargs) -> None:
        self.add_context(**kwargs)
        self.logger.info(self._format_message(msg))
    
    def warning(self, msg: str, **kwargs) -> None:
        self.add_context(**kwargs)
        self.logger.warning(self._format_message(msg))
    
    def error(self, msg: str, **kwargs) -> None:
        self.add_context(**kwargs)
        self.logger.error(self._format_message(msg))
    
    def critical(self, msg: str, **kwargs) -> None:
        self.add_context(**kwargs)
        self.logger.critical(self._format_message(msg))


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for console output"""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
        'RESET': '\033[0m'       # Reset
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        record.levelname = f"{log_color}{record.levelname}{self.COLORS['RESET']}"
        return super().format(record)


def setup_logging(config_manager=None) -> None:
    """
    Initialize logging system with configuration
    
    Args:
        config_manager: ConfigManager instance (optional)
    """
    # Get configuration
    if config_manager:
        log_level = config_manager.get("logging.level", "INFO")
        console_output = config_manager.get("logging.console_output", True)
        file_output = config_manager.get("logging.file_output", True)
        log_dir = config_manager.get("logging.log_dir", "logs")
        max_size_mb = config_manager.get("logging.max_log_size_mb", 10)
        backup_count = config_manager.get("logging.backup_count", 5)
    else:
        log_level = "INFO"
        console_output = True
        file_output = True
        log_dir = "logs"
        max_size_mb = 10
        backup_count = 5
    
    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Format strings
    detailed_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    simple_format = '%(levelname)s - %(message)s'
    
    # Console handler
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_formatter = ColoredFormatter(simple_format)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # File handlers (if enabled)
    if file_output:
        # Main log file (all logs)
        main_log_file = log_path / "synorpse.log"
        main_handler = RotatingFileHandler(
            main_log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        main_handler.setLevel(logging.DEBUG)
        main_formatter = logging.Formatter(detailed_format)
        main_handler.setFormatter(main_formatter)
        root_logger.addHandler(main_handler)
        
        # Error log file (errors only)
        error_log_file = log_path / "errors.log"
        error_handler = RotatingFileHandler(
            error_log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(main_formatter)
        root_logger.addHandler(error_handler)
        
        # Performance log file
        perf_log_file = log_path / "performance.log"
        perf_handler = RotatingFileHandler(
            perf_log_file,
            maxBytes=max_size_mb * 1024 * 1024,
            backupCount=backup_count,
            encoding='utf-8'
        )
        perf_handler.setLevel(logging.INFO)
        perf_handler.setFormatter(main_formatter)
        
        # Add performance handler to performance logger
        perf_logger = logging.getLogger("performance")
        perf_logger.addHandler(perf_handler)
        perf_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance by name"""
    return logging.getLogger(name)


def get_context_logger(name: str) -> ContextLogger:
    """Get a context-aware logger"""
    return ContextLogger(get_logger(name))


# Global performance logger
_perf_logger = None

def get_performance_logger() -> PerformanceLogger:
    """Get the global performance logger"""
    global _perf_logger
    if _perf_logger is None:
        _perf_logger = PerformanceLogger()
    return _perf_logger


# Timing context manager
class timer:
    """Context manager for timing operations"""
    
    def __init__(self, operation: str, logger: Optional[logging.Logger] = None):
        self.operation = operation
        self.logger = logger or get_logger("performance")
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, *args):
        duration = time.time() - self.start_time
        self.logger.info(f"{self.operation} completed in {duration:.3f}s")
        
        # Record in performance logger
        perf_logger = get_performance_logger()
        perf_logger.log_metric(self.operation, duration)
