"""
ContextualAliasResolver.py - Resolve contextual references to actual applications
Maps user-friendly terms like "my code editor" to actual app names like "Visual Studio Code"
"""
import json
import os
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from fuzzywuzzy import fuzz

class ContextualAliasResolver:
    """Resolves contextual aliases to actual application names"""
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # Default to Data/app_aliases.json
            base_dir = Path(__file__).parent.parent
            config_path = base_dir / "Data" / "app_aliases.json"
        
        self.config_path = config_path
        self.aliases = self._load_aliases()
        self.user_preferences = {}  # Track user's preferred apps
    
    def _load_aliases(self) -> Dict:
        """Load alias configuration from JSON file"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            else:
                print(f" Alias config not found at {self.config_path}, using defaults")
                return self._get_default_aliases()
        except Exception as e:
            print(f" Error loading aliases: {e}, using defaults")
            return self._get_default_aliases()
    
    def _get_default_aliases(self) -> Dict:
        """Default aliases if config file not found"""
        return {
            "ide": {
                "aliases": ["ide", "code editor", "my code editor"],
                "default_app": "Visual Studio Code",
                "alternatives": ["vscode", "code"]
            },
            "browser": {
                "aliases": ["browser", "web browser", "internet"],
                "default_app": "Google Chrome",
                "alternatives": ["chrome"]
            }
        }
    
    def resolve_alias(self, query: str) -> Tuple[Optional[str], bool]:
        """
        Resolve a query to an actual application name.
        Returns: (app_name, is_alias_match)
        - app_name: The resolved application name, or None if no match
        - is_alias_match: True if matched via alias, False otherwise
        """
        import re
        query_lower = query.lower().strip()
        
        # Check each category for alias matches
        for category, config in self.aliases.items():
            aliases = config.get("aliases", [])
            
            # Exact alias match with word boundaries (prevents 'ide' matching 'video')
            for alias in aliases:
                # Use word boundary regex to match whole words only
                pattern = r'\b' + re.escape(alias.lower()) + r'\b'
                if re.search(pattern, query_lower):
                    # Check if user has a preference for this category
                    if category in self.user_preferences:
                        return self.user_preferences[category], True
                    
                    # Return default app
                    return config.get("default_app"), True
            
            # Fuzzy match on aliases (only for multi-word aliases to avoid false positives)
            for alias in aliases:
                if len(alias.split()) > 1:  # Only fuzzy match multi-word aliases
                    similarity = fuzz.partial_ratio(alias.lower(), query_lower)
                    if similarity >= 90:  # Higher threshold for fuzzy
                        if category in self.user_preferences:
                            return self.user_preferences[category], True
                        return config.get("default_app"), True
        
        return None, False
    
    def resolve_with_context(self, query: str, context: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Resolve query with additional context.
        Returns: (app_name, search_query)
        - app_name: The application to open
        - search_query: Optional search query to execute (for music, news, etc.)
        """
        query_lower = query.lower().strip()
        
        # Check for special categories that need search queries
        for category, config in self.aliases.items():
            aliases = config.get("aliases", [])
            
            for alias in aliases:
                if alias.lower() in query_lower:
                    app_name = config.get("default_app")
                    search_query = config.get("search_query")
                    
                    # If user has preference, use it
                    if category in self.user_preferences:
                        app_name = self.user_preferences[category]
                    
                    return app_name, search_query
        
        return None, None
    
    def set_user_preference(self, category: str, app_name: str):
        """Set user's preferred app for a category"""
        if category in self.aliases:
            self.user_preferences[category] = app_name
            print(f" Set preference: {category}  {app_name}")
    
    def get_category_for_app(self, app_name: str) -> Optional[str]:
        """Get the category for a given app name"""
        app_lower = app_name.lower()
        
        for category, config in self.aliases.items():
            # Check default app
            if config.get("default_app", "").lower() == app_lower:
                return category
            
            # Check alternatives
            alternatives = config.get("alternatives", [])
            if any(alt.lower() == app_lower for alt in alternatives):
                return category
        
        return None
    
    def expand_query(self, query: str) -> str:
        """
        Expand a query by resolving aliases.
        Example: "open my code editor"  "open Visual Studio Code"
        """
        import re
        app_name, is_alias = self.resolve_alias(query)
        
        if is_alias and app_name:
            query_lower = query.lower()
            
            # For "open" or "close" commands, replace everything after the command with just the app name
            # This handles "open the ide on my system" -> "open Visual Studio Code"
            if query_lower.startswith("open "):
                return f"open {app_name}"
            elif query_lower.startswith("close "):
                return f"close {app_name}"
            else:
                # For other cases, find which alias matched and replace it using word boundaries
                for category, config in self.aliases.items():
                    for alias in config.get("aliases", []):
                        # Use word boundary regex to match whole words only
                        pattern = r'\b' + re.escape(alias.lower()) + r'\b'
                        if re.search(pattern, query_lower):
                            # Replace the alias with the app name using regex
                            expanded = re.sub(pattern, app_name.lower(), query_lower)
                            return expanded
        
        return query
    
    def get_all_aliases(self) -> Dict[str, List[str]]:
        """Get all aliases mapped to their default apps"""
        result = {}
        for category, config in self.aliases.items():
            app_name = config.get("default_app")
            aliases = config.get("aliases", [])
            result[app_name] = aliases
        return result
    
    def reload_config(self):
        """Reload alias configuration from file"""
        self.aliases = self._load_aliases()
        print(" Alias configuration reloaded")


# Global instance
_alias_resolver = None

def get_alias_resolver() -> ContextualAliasResolver:
    """Get or create global alias resolver"""
    global _alias_resolver
    if _alias_resolver is None:
        _alias_resolver = ContextualAliasResolver()
    return _alias_resolver


# Convenience functions
def resolve_contextual_alias(query: str) -> Tuple[Optional[str], bool]:
    """Resolve a contextual alias in a query"""
    resolver = get_alias_resolver()
    return resolver.resolve_alias(query)

def expand_query_with_aliases(query: str) -> str:
    """Expand query by resolving aliases"""
    resolver = get_alias_resolver()
    return resolver.expand_query(query)
