import os
import sys
import subprocess
import platform
import json
import time
from difflib import SequenceMatcher
from pathlib import Path

class AppLauncher:
    def __init__(self):
        self.system = platform.system()
        # Set cache path relative to this file
        self.cache_path = Path(__file__).parent.parent / "Data" / "app_cache.json"
        self.cache_path.parent.mkdir(exist_ok=True)
        self.apps = self.load_apps()
    
    def load_apps(self):
        """Load apps from cache or scan if cache doesn't exist/is stale"""
        # Try to load from cache
        if self.cache_path.exists():
            try:
                # Check if cache is recent (less than 7 days old)
                if time.time() - self.cache_path.stat().st_mtime < 7 * 24 * 3600:
                    print("Loading applications from cache...")
                    with open(self.cache_path, 'r') as f:
                        apps = json.load(f)
                        
                        # CRITICAL: If on Windows and no UWP apps in cache, force UWP scan
                        if self.system == "Windows" and not any(str(v).startswith("uwp:") for v in apps.values()):
                            print("Refreshing UWP app list...")
                            uwp_apps = self._get_uwp_apps()
                            apps.update(uwp_apps)
                            # Update cache with UWP apps
                            try:
                                with open(self.cache_path, 'w') as f:
                                    json.dump(apps, f)
                            except:
                                pass
                        
                        return apps
            except Exception as e:
                print(f"Error loading cache: {e}")
        
        # If no cache or invalid, scan
        print("\nScanning for applications (this may take a moment)...")
        apps = self.get_installed_apps()
        
        # Save to cache
        try:
            with open(self.cache_path, 'w') as f:
                json.dump(apps, f)
            print("Application list cached.")
        except Exception as e:
            print(f"Error saving cache: {e}")
            
        return apps
        return apps
    
    def refresh_cache(self):
        """Force refresh the application cache"""
        print("\nUsing FORCE REFRESH on application cache...")
        if self.cache_path.exists():
            try:
                os.remove(self.cache_path)
                print("🗑️ Cleared existing cache.")
            except:
                pass
        
        # Reload (will force scan since cache is gone)
        self.apps = self.load_apps()
        return len(self.apps)
    
    def get_installed_apps(self):
        """Get list of installed applications based on OS"""
        apps = {}
        
        if self.system == "Windows":
            apps = self._get_windows_apps()
            # Merge with UWP apps
            uwp_apps = self._get_uwp_apps()
            apps.update(uwp_apps)
        elif self.system == "Darwin": 
            apps = self._get_macos_apps()
        elif self.system == "Linux":
            apps = self._get_linux_apps()
        
        return apps
    
    def _get_windows_apps(self):
        """Get Windows applications by scanning entire C drive (cached)"""
        apps = {}
        
        print("\nScanning entire C:\\ drive for applications...")
        print("This will take a few minutes, but results will be cached for future runs.\n")
        
        root_path = Path('C:\\')
        
        # optimized skip list to avoid system directories
        skip_dirs = {
            'Windows\\WinSxS',  
            '$Recycle.Bin',
            'System Volume Information',
            'ProgramData\\Package Cache',
            'Windows\\Installer',
            'Windows\\Servicing',
            'Windows\\assembly',
            'Windows\\Microsoft.NET',
            'Downloads', # Skip downloads folder for installers
        }
        
        file_count = 0
        for root, dirs, files in os.walk(root_path, topdown=True):
            # Filtering directories
            dirs[:] = [d for d in dirs if not any(skip in os.path.join(root, d) for skip in skip_dirs)]
            
            for file in files:
                file_lower = file.lower()
                # Skip installers and setup files
                if "installer" in file_lower or "setup" in file_lower:
                    continue
                    
                if file_lower.endswith('.exe') or file_lower.endswith('.lnk'):
                    app_name = file.rsplit('.', 1)[0].lower()
                    full_path = os.path.join(root, file)
                    apps[app_name] = full_path
                    file_count += 1
                    
                    if file_count % 1000 == 0:
                        print(f"Scanned {file_count} executables...", end='\r')
        
        print(f"\nScan complete! Found {len(apps)} unique applications.")
        return apps

    def _get_uwp_apps(self):
        """Get Windows UWP (Store) applications using PowerShell"""
        apps = {}
        try:
            print("Scanning for UWP applications...")
            cmd = 'powershell -Command "Get-StartApps | Select-Object -Property Name, AppID | ConvertTo-Json"'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0:
                try:
                    data = json.loads(result.stdout)
                    # Support both single object and list of objects
                    if isinstance(data, dict):
                        data = [data]
                    
                    for item in data:
                        name = item.get("Name", "")
                        app_id = item.get("AppID", "")
                        if name and app_id:
                            apps[name.lower().strip()] = f"uwp:{app_id.strip()}"
                except json.JSONDecodeError:
                    print("Error decoding UWP app list JSON.")
                
                print(f"Found {len(apps)} UWP applications.")
        except Exception as e:
            print(f"Error scanning UWP apps: {e}")
            
        return apps
    
    def _get_macos_apps(self):
        """Get macOS applications"""
        apps = {}
        locations = ['/Applications', f'{Path.home()}/Applications']
        
        for location in locations:
            if os.path.exists(location):
                for item in os.listdir(location):
                    if item.endswith('.app'):
                        app_name = item.replace('.app', '')
                        apps[app_name.lower()] = os.path.join(location, item)
        
        return apps
    
    def _get_linux_apps(self):
        """Get Linux applications from .desktop files"""
        apps = {}
        locations = [
            '/usr/share/applications',
            f'{Path.home()}/.local/share/applications',
            '/var/lib/snapd/desktop/applications',
            '/var/lib/flatpak/exports/share/applications'
        ]
        
        for location in locations:
            if os.path.exists(location):
                for file in os.listdir(location):
                    if file.endswith('.desktop'):
                        desktop_file = os.path.join(location, file)
                        try:
                            with open(desktop_file, 'r') as f:
                                for line in f:
                                    if line.startswith('Name='):
                                        app_name = line.split('=', 1)[1].strip()
                                        apps[app_name.lower()] = desktop_file
                                        break
                        except:
                            pass
        
        return apps
    
    def fuzzy_match(self, query, threshold=0.6):
        """Find best matching app using fuzzy string matching"""
        query = query.lower()
        matches = []
        
        for app_name, app_path in self.apps.items():
            ratio = SequenceMatcher(None, query, app_name).ratio()
            
            if query in app_name:
                ratio = max(ratio, 0.8)  
            
            if ratio >= threshold:
                matches.append((app_name, app_path, ratio))
        
        matches.sort(key=lambda x: x[2], reverse=True)
        
        return matches
    
    def launch_app(self, app_path):
        """Launch the application based on OS with log suppression"""
        try:
            if self.system == "Windows":
                # Use Popen with shell=True to handle .lnk files and redirect output to DEVNULL
                # Quote path to handle spaces
                if app_path.startswith("uwp:"):
                    app_id = app_path.replace("uwp:", "")
                    subprocess.Popen(f'explorer.exe shell:AppsFolder\\{app_id}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen(f'"{app_path}"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif self.system == "Darwin": 
                subprocess.Popen(['open', app_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif self.system == "Linux":
                if app_path.endswith('.desktop'):
                    with open(app_path, 'r') as f:
                        for line in f:
                            if line.startswith('Exec='):
                                exec_cmd = line.split('=', 1)[1].strip()
                                exec_cmd = exec_cmd.split('%')[0].strip()
                                subprocess.Popen(exec_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                                return True
                else:
                    subprocess.Popen([app_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"Error launching app: {e}")
            return False
    
    def search_and_launch(self, query):
        """Search for app and launch it"""
        print(f"\nSearching for: '{query}'")
        matches = self.fuzzy_match(query)
        
        if not matches:
            print(f"No applications found matching '{query}'")
            return False
        
        print(f"\nFound {len(matches)} match(es):")
        for i, (name, path, score) in enumerate(matches[:10], 1):
            print(f"{i}. {name} (similarity: {score:.2f})")
        
        print(f"\nLaunching best match: {matches[0][0]}")
        return self.launch_app(matches[0][1])

    def refresh_cache(self):
        """Force refresh of the application cache"""
        print("\nRefreshing application cache...")
        if self.cache_path.exists():
            os.remove(self.cache_path)
        self.apps = self.load_apps()
        print("Done.")

def main():
    print("=" * 50)
    print("Universal Application Launcher")
    print("=" * 50)
    
    launcher = AppLauncher()
    print(f"\nDetected OS: {launcher.system}")
    print(f"Loaded {len(launcher.apps)} applications")
    
    while True:
        print("\n" + "-" * 50)
        query = input("\nEnter app name to launch (or 'refresh' to rescanning, 'exit' to quit): ").strip()
        
        if query.lower() in ['exit', 'quit', 'q']:
            print("Goodbye!")
            break
            
        if query.lower() == 'refresh':
            launcher.refresh_cache()
            continue
        
        if query:
            launcher.search_and_launch(query)
        else:
            print("Please enter an app name")

if __name__ == "__main__":
    main()