"""
System Awareness Module - Track installed applications and system files
Provides context about what's available on the system for better suggestions
"""
import os
import winreg
from pathlib import Path
from typing import List, Dict, Optional
import logging
from functools import lru_cache
import json

logger = logging.getLogger("system_awareness")


class SystemAwareness:
    """Track and provide information about system applications and files"""
    
    def __init__(self, cache_file: str = "state/system_cache.json"):
        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(exist_ok=True)
        self.installed_apps = {}
        self.common_paths = {}
        self._load_cache()
    
    def _load_cache(self):
        """Load cached system information"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.installed_apps = data.get('installed_apps', {})
                    self.common_paths = data.get('common_paths', {})
                    logger.info(f"Loaded {len(self.installed_apps)} apps from cache")
        except Exception as e:
            logger.warning(f"Could not load cache: {e}")
    
    def _save_cache(self):
        """Save system information to cache"""
        try:
            data = {
                'installed_apps': self.installed_apps,
                'common_paths': self.common_paths
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            logger.debug("System cache saved")
        except Exception as e:
            logger.warning(f"Could not save cache: {e}")
    
    def scan_installed_apps(self) -> Dict[str, str]:
        """
        Scan Windows registry for installed applications
        
        Returns:
            Dict mapping app names to executable paths
        """
        apps = {}
        
        # Registry paths to check
        registry_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        
        for hkey, path in registry_paths:
            try:
                key = winreg.OpenKey(hkey, path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        
                        # Get app name
                        try:
                            app_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        except:
                            continue
                        
                        # Get executable path
                        try:
                            install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                            if install_location and os.path.exists(install_location):
                                apps[app_name.lower()] = install_location
                        except:
                            pass
                        
                        winreg.CloseKey(subkey)
                    except:
                        continue
                
                winreg.CloseKey(key)
            except Exception as e:
                logger.debug(f"Could not access registry path {path}: {e}")
        
        # Add common applications from PATH and standard locations
        common_apps = {
            "notepad": r"C:\Windows\System32\notepad.exe",
            "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "firefox": r"C:\Program Files\Mozilla Firefox\firefox.exe",
            "edge": r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            "vscode": r"C:\Program Files\Microsoft VS Code\Code.exe",
            "notepad++": r"C:\Program Files\Notepad++\notepad++.exe",
        }
        
        for name, path in common_apps.items():
            if os.path.exists(path):
                apps[name] = path
        
        self.installed_apps = apps
        self._save_cache()
        
        logger.info(f"Scanned {len(apps)} installed applications")
        return apps
    
    def find_app(self, query: str) -> Optional[str]:
        """
        Find an installed application by name
        
        Args:
            query: Application name to search for
        
        Returns:
            Path to application or None
        """
        query_lower = query.lower()
        
        # Exact match
        if query_lower in self.installed_apps:
            return self.installed_apps[query_lower]
        
        # Partial match
        for app_name, app_path in self.installed_apps.items():
            if query_lower in app_name or app_name in query_lower:
                return app_path
        
        return None
    
    def scan_common_paths(self, deep_scan: bool = False) -> Dict[str, List[str]]:
        """
        Scan file locations - either common paths or entire C: drive
        
        Args:
            deep_scan: If True, scan entire C: drive (slower but comprehensive)
        
        Returns:
            Dict mapping categories to file paths
        """
        paths = {
            "documents": [],
            "downloads": [],
            "desktop": [],
            "projects": [],
            "programs": [],
            "user_files": []
        }
        
        home = Path.home()
        
        if not deep_scan:
            # Quick scan - just common user folders
            logger.info("Performing quick scan of common folders...")
            
            # Documents
            docs_dir = home / "Documents"
            if docs_dir.exists():
                paths["documents"] = [str(p) for p in docs_dir.glob("*") if p.is_file()][:50]
            
            # Downloads
            downloads_dir = home / "Downloads"
            if downloads_dir.exists():
                paths["downloads"] = [str(p) for p in downloads_dir.glob("*") if p.is_file()][:50]
            
            # Desktop
            desktop_dir = home / "Desktop"
            if desktop_dir.exists():
                paths["desktop"] = [str(p) for p in desktop_dir.glob("*") if p.is_file()][:50]
            
            # Development/Projects (common locations)
            dev_locations = [
                home / "Projects",
                home / "Development",
                home / "Code",
                Path("C:/Developing"),
                Path("D:/Projects"),
            ]
            
            for dev_dir in dev_locations:
                if dev_dir.exists():
                    paths["projects"].extend([str(p) for p in dev_dir.glob("*") if p.is_dir()][:20])
        
        else:
            # Deep scan - entire C: drive
            logger.info("Performing DEEP SCAN of C: drive (this may take a few minutes)...")
            
            # Folders to skip (system/large folders)
            skip_folders = {
                "windows", "windows.old", "$recycle.bin", "system volume information",
                "$windows.~bt", "perflogs", "programdata", "recovery",
                "windows10upgrade", "intel", "nvidia", "amd",
                "msocache", "config.msi", "temp", "tmp",
                # Node modules and other large dev folders
                "node_modules", ".git", ".svn", "__pycache__", ".venv", "venv",
                # Browser caches
                "cache", "caches", "cached", "google", "mozilla", "microsoft edge"
            }
            
            # Extensions to track
            interesting_extensions = {
                # Documents
                ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".md",
                # Code
                ".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".cs", ".go", ".rs",
                ".php", ".rb", ".swift", ".kt", ".ts", ".jsx", ".tsx", ".vue",
                # Data
                ".json", ".xml", ".csv", ".sql", ".db", ".sqlite",
                # Images/Media
                ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".ico",
                ".mp4", ".avi", ".mkv", ".mov", ".mp3", ".wav",
                # Archives
                ".zip", ".rar", ".7z", ".tar", ".gz",
                # Executables
                ".exe", ".msi", ".bat", ".ps1", ".sh"
            }
            
            def should_skip_folder(path: Path) -> bool:
                """Check if folder should be skipped"""
                folder_name = path.name.lower()
                # Skip hidden folders
                if folder_name.startswith('.') and folder_name not in ['.config', '.ssh']:
                    return True
                # Skip system folders
                if folder_name in skip_folders:
                    return True
                # Skip AppData subfolders (too many files)
                if 'appdata' in str(path).lower() and path.name.lower() != 'appdata':
                    return True
                return False
            
            def categorize_file(file_path: Path) -> str:
                """Determine category for a file"""
                path_str = str(file_path).lower()
                
                if "\\documents\\" in path_str:
                    return "documents"
                elif "\\downloads\\" in path_str:
                    return "downloads"
                elif "\\desktop\\" in path_str:
                    return "desktop"
                elif any(dev in path_str for dev in ["\\projects\\", "\\code\\", "\\development\\", "\\developing\\"]):
                    return "projects"
                elif "\\program files" in path_str or "\\program files (x86)\\" in path_str:
                    return "programs"
                else:
                    return "user_files"
            
            # Scan C: drive
            c_drive = Path("C:/")
            file_count = 0
            max_files_per_category = 500  # Limit per category
            
            try:
                for root, dirs, files in os.walk(c_drive):
                    # Skip folders
                    root_path = Path(root)
                    if should_skip_folder(root_path):
                        dirs.clear()  # Don't recurse into this folder
                        continue
                    
                    # Filter dirs in-place to skip unwanted directories
                    dirs[:] = [d for d in dirs if not should_skip_folder(root_path / d)]
                    
                    # Process files
                    for file in files:
                        file_path = root_path / file
                        
                        # Check if interesting extension
                        if file_path.suffix.lower() in interesting_extensions:
                            category = categorize_file(file_path)
                            
                            # Add if under limit
                            if len(paths[category]) < max_files_per_category:
                                try:
                                    # Verify file still exists and is accessible
                                    if file_path.exists() and file_path.is_file():
                                        paths[category].append(str(file_path))
                                        file_count += 1
                                        
                                        # Log progress every 1000 files
                                        if file_count % 1000 == 0:
                                            logger.info(f"Deep scan: {file_count} files indexed...")
                                except:
                                    pass  # Skip inaccessible files
                    
                    # Stop if we've collected enough files
                    if all(len(paths[cat]) >= max_files_per_category for cat in paths):
                        logger.info("Reached file limits for all categories")
                        break
                
                logger.info(f"Deep scan complete: {file_count} total files indexed")
                
            except Exception as e:
                logger.error(f"Error during deep scan: {e}")
        
        self.common_paths = paths
        self._save_cache()
        
        return paths
    
    def get_suggestions_for_query(self, query: str) -> Dict[str, any]:
        """
        Get system-aware suggestions for a query
        
        Args:
            query: User query
        
        Returns:
            Dict with suggestions
        """
        suggestions = {
            "apps": [],
            "files": [],
            "paths": []
        }
        
        query_lower = query.lower()
        
        # Find matching apps
        for app_name, app_path in self.installed_apps.items():
            if any(word in app_name for word in query_lower.split()):
                suggestions["apps"].append({
                    "name": app_name,
                    "path": app_path
                })
        
        # Find matching files in common paths
        for category, file_list in self.common_paths.items():
            for file_path in file_list:
                file_name = Path(file_path).name.lower()
                if any(word in file_name for word in query_lower.split()):
                    suggestions["files"].append({
                        "name": Path(file_path).name,
                        "path": file_path,
                        "category": category
                    })
        
        return suggestions
    
    def refresh_all(self, deep_scan: bool = False):
        """
        Refresh all system information
        
        Args:
            deep_scan: If True, perform deep C: drive scan (slower but comprehensive)
        """
        scan_type = "DEEP" if deep_scan else "quick"
        logger.info(f"Refreshing system awareness ({scan_type} scan)...")
        self.scan_installed_apps()
        self.scan_common_paths(deep_scan=deep_scan)
        logger.info(f"System awareness refreshed ({scan_type} scan complete)")


# Global instance
_system_awareness = None

def get_system_awareness() -> SystemAwareness:
    """Get global system awareness instance"""
    global _system_awareness
    if _system_awareness is None:
        _system_awareness = SystemAwareness()
        # Initial quick scan on first access
        if not _system_awareness.installed_apps:
            _system_awareness.scan_installed_apps()
        if not _system_awareness.common_paths:
            _system_awareness.scan_common_paths(deep_scan=False)  # Quick scan by default
    return _system_awareness
