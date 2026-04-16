"""
Configuration Manager - Centralized configuration management with hot-reload
Manages YAML config files and environment variables
"""
import yaml
import os
from pathlib import Path
from typing import Any, Dict, Optional
from dotenv import dotenv_values
from threading import Lock
import time

class ConfigManager:
    """Singleton configuration manager with hot-reload support"""
    
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self.config_path = Path(__file__).parent.parent / "config.yaml"
            self.env_path = Path(__file__).parent.parent / ".env"
            self._config: Dict[str, Any] = {}
            self._env_vars: Dict[str, str] = {}
            self._last_modified = 0
            self._initialized = True
            self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from YAML and environment variables"""
        try:
            # Load YAML config
            if self.config_path.exists():
                with open(self.config_path, 'r') as f:
                    self._config = yaml.safe_load(f) or {}
                self._last_modified = self.config_path.stat().st_mtime
            else:
                print(f" Config file not found at {self.config_path}, using defaults")
                self._config = self._get_default_config()
            
            # Load environment variables (they override YAML)
            if self.env_path.exists():
                self._env_vars = dotenv_values(str(self.env_path))
            
            # Apply environment overrides
            self._apply_env_overrides()
            
            # Validate configuration
            self._validate_config()
            
        except Exception as e:
            print(f" Error loading config: {e}")
            self._config = self._get_default_config()
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to config"""
        # Database overrides
        if "DB_NAME" in self._env_vars:
            self._config.setdefault("database", {})["name"] = self._env_vars["DB_NAME"]
        if "DB_USER" in self._env_vars:
            self._config.setdefault("database", {})["user"] = self._env_vars["DB_USER"]
        if "DB_PASSWORD" in self._env_vars:
            self._config.setdefault("database", {})["password"] = self._env_vars["DB_PASSWORD"]
        if "DB_HOST" in self._env_vars:
            self._config.setdefault("database", {})["host"] = self._env_vars["DB_HOST"]
        
        # API Keys
        if "GroqAPIKey" in self._env_vars:
            self._config.setdefault("api_keys", {})["groq_api_key"] = self._env_vars["GroqAPIKey"]
        if "GroqAPIKey2" in self._env_vars:
            self._config.setdefault("api_keys", {})["groq_api_key_2"] = self._env_vars["GroqAPIKey2"]
        if "GroqAPIKey3" in self._env_vars:
            self._config.setdefault("api_keys", {})["groq_api_key_3"] = self._env_vars["GroqAPIKey3"]
        if "GoogleAPIKey" in self._env_vars:
            self._config.setdefault("api_keys", {})["google_api_key"] = self._env_vars["GoogleAPIKey"]
        if "GOOGLE_CSE_ID" in self._env_vars:
            self._config.setdefault("api_keys", {})["google_cse_id"] = self._env_vars["GOOGLE_CSE_ID"]
        
        # System settings
        if "Username" in self._env_vars:
            self._config.setdefault("system", {})["username"] = self._env_vars["Username"]
        if "Assistantname" in self._env_vars:
            self._config.setdefault("system", {})["assistant_name"] = self._env_vars["Assistantname"]
    
    def _validate_config(self) -> None:
        """Validate configuration values"""
        # Ensure required sections exist
        required_sections = ["system", "database", "agentic", "logging"]
        for section in required_sections:
            if section not in self._config:
                print(f" Missing config section: {section}, using defaults")
                self._config[section] = self._get_default_config().get(section, {})
        
        # Validate numeric ranges
        if "agentic" in self._config:
            agentic = self._config["agentic"]
            if "suggestion_interval_seconds" in agentic:
                if not (60 <= agentic["suggestion_interval_seconds"] <= 3600):
                    print(" Invalid suggestion_interval, using default 600")
                    agentic["suggestion_interval_seconds"] = 600
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration"""
        return {
            "system": {
                "assistant_name": "Synorpse",
                "username": "User",
                "mode": "supervised"
            },
            "database": {
                "name": "synorpse_chat",
                "user": "postgres",
                "password": "",
                "host": "localhost",
                "port": 5432
            },
            "agentic": {
                "suggestion_interval_seconds": 600,
                "autonomous_loop_interval": 30,
                "max_background_workers": 4,
                "enable_proactive_suggestions": True
            },
            "logging": {
                "level": "INFO",
                "console_output": True,
                "file_output": True,
                "log_dir": "logs"
            },
            "error_handling": {
                "max_retries": 3,
                "retry_delay_seconds": 2,
                "exponential_backoff": True
            }
        }
    
    def reload_if_changed(self) -> bool:
        """Reload config if file has been modified"""
        try:
            if self.config_path.exists():
                current_mtime = self.config_path.stat().st_mtime
                if current_mtime > self._last_modified:
                    print(" Config file changed, reloading...")
                    self.load_config()
                    return True
            return False
        except Exception as e:
            print(f" Error checking config file: {e}")
            return False
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation
        Example: config.get("database.name") returns the database name
        """
        keys = key_path.split(".")
        value = self._config
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        
        return value if value is not None else default
    
    def set(self, key_path: str, value: Any) -> None:
        """
        Set configuration value using dot notation (runtime only, not persisted)
        """
        keys = key_path.split(".")
        config = self._config
        
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        config[keys[-1]] = value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """Get entire configuration section"""
        return self._config.get(section, {})
    
    def get_env(self, key: str, default: str = "") -> str:
        """Get environment variable"""
        return self._env_vars.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """Return full configuration as dictionary"""
        return self._config.copy()


# Global singleton instance
_config_manager = None

def get_config() -> ConfigManager:
    """Get the global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
