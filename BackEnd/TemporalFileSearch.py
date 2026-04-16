"""
TemporalFileSearch.py - Enhanced file search with temporal filtering
Supports queries like "files from yesterday", "documents this week", etc.
"""
import os
import time
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
import platform

def get_time_filter(temporal_key: str) -> Optional[float]:
    """
    Convert temporal key to Unix timestamp for filtering.
    Returns the minimum modification time (files modified after this time).
    """
    now = time.time()
    
    if temporal_key == 'yesterday':
        # Files modified in the last 24 hours
        return now - (24 * 3600)
    
    elif temporal_key == 'this_week':
        # Files modified in the last 7 days
        return now - (7 * 24 * 3600)
    
    elif temporal_key == 'today':
        # Files modified today (since midnight)
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return today_start.timestamp()
    
    elif temporal_key == 'recently':
        # Files modified in the last 3 days
        return now - (3 * 24 * 3600)
    
    return None


def find_recent_files(
    temporal_key: str,
    search_paths: Optional[List[str]] = None,
    extensions: Optional[List[str]] = None,
    max_results: int = 20
) -> List[Tuple[str, float, float]]:
    """
    Find files based on temporal filter.
    
    Args:
        temporal_key: 'yesterday', 'this_week', 'today', 'recently'
        search_paths: Directories to search (default: Documents, Desktop, Downloads)
        extensions: File extensions to include (default: common document types)
        max_results: Maximum number of results to return
    
    Returns:
        List of (file_path, modification_time, confidence_score) tuples
        Sorted by modification time (most recent first)
    """
    if extensions is None:
        extensions = ['.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', 
                     '.txt', '.py', '.js', '.html', '.css', '.json', '.md']
    
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
    
    # Get time filter
    min_time = get_time_filter(temporal_key)
    if min_time is None:
        return []
    
    matches = []
    
    for search_path in search_paths:
        if not os.path.exists(search_path):
            continue
        
        for root, dirs, files in os.walk(search_path):
            for file in files:
                # Check extension
                if not any(file.lower().endswith(ext) for ext in extensions):
                    continue
                
                file_path = os.path.join(root, file)
                
                try:
                    # Get modification time
                    mod_time = os.path.getmtime(file_path)
                    
                    # Filter by time
                    if mod_time >= min_time:
                        # Calculate confidence based on how recent the file is
                        # More recent = higher confidence
                        time_diff = time.time() - mod_time
                        max_time_diff = time.time() - min_time
                        
                        if max_time_diff > 0:
                            # Confidence: 100 for just modified, decreasing to 60 for oldest in range
                            confidence = 100 - (40 * (time_diff / max_time_diff))
                        else:
                            confidence = 100
                        
                        matches.append((file_path, mod_time, confidence))
                
                except (OSError, PermissionError):
                    continue
    
    # Sort by modification time (most recent first)
    matches.sort(key=lambda x: x[1], reverse=True)
    
    return matches[:max_results]


def find_files_with_temporal_context(
    search_term: str,
    temporal_key: Optional[str] = None,
    search_paths: Optional[List[str]] = None,
    extensions: Optional[List[str]] = None,
    confidence_threshold: int = 60
) -> List[Tuple[str, float]]:
    """
    Find files matching search term with optional temporal filtering.
    Combines fuzzy matching with temporal filtering.
    
    Args:
        search_term: Text to search for in filenames
        temporal_key: Optional temporal filter ('yesterday', 'this_week', etc.)
        search_paths: Directories to search
        extensions: File extensions to include
        confidence_threshold: Minimum confidence score
    
    Returns:
        List of (file_path, confidence_score) tuples
    """
    from fuzzywuzzy import fuzz
    
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
    
    # Get time filter if temporal context provided
    min_time = None
    if temporal_key:
        min_time = get_time_filter(temporal_key)
    
    matches = []
    search_term_lower = search_term.lower()
    
    for search_path in search_paths:
        if not os.path.exists(search_path):
            continue
        
        for root, dirs, files in os.walk(search_path):
            for file in files:
                if not any(file.lower().endswith(ext) for ext in extensions):
                    continue
                
                file_path = os.path.join(root, file)
                file_name = os.path.splitext(file)[0].lower()
                
                try:
                    # Check temporal filter first
                    if min_time is not None:
                        mod_time = os.path.getmtime(file_path)
                        if mod_time < min_time:
                            continue  # Skip files outside temporal range
                    
                    # Fuzzy match on filename
                    fuzzy_score = fuzz.partial_ratio(search_term_lower, file_name)
                    
                    # Substring bonus
                    if search_term_lower in file_name:
                        substring_bonus = 20
                    else:
                        substring_bonus = 0
                    
                    confidence = min(fuzzy_score + substring_bonus, 100)
                    
                    if confidence >= confidence_threshold:
                        matches.append((file_path, confidence))
                
                except (OSError, PermissionError):
                    continue
    
    # Sort by confidence
    matches.sort(key=lambda x: x[1], reverse=True)
    
    return matches


def get_recently_opened_files(limit: int = 10) -> List[Tuple[str, str, float]]:
    """
    Get recently opened files from automation logs.
    
    Args:
        limit: Maximum number of files to return
    
    Returns:
        List of (file_path, file_name, timestamp) tuples
    """
    try:
        from Automation import get_automation_logs
        
        logs = get_automation_logs(limit=limit * 2, action_type='open')
        
        recent_files = []
        seen_files = set()
        
        for action_type, action_details, status, metadata, created_at in logs:
            if status != 'success':
                continue
            
            # Extract file information from metadata
            result_type = metadata.get('result_type')
            
            if result_type == 'files':
                files_opened = metadata.get('files_opened', [])
                for file_info in files_opened:
                    file_path = file_info.get('file_path')
                    file_name = file_info.get('file_name')
                    
                    if file_path and file_path not in seen_files:
                        seen_files.add(file_path)
                        recent_files.append((file_path, file_name, created_at.timestamp()))
                        
                        if len(recent_files) >= limit:
                            break
            
            if len(recent_files) >= limit:
                break
        
        return recent_files
    
    except Exception as e:
        print(f" Error getting recently opened files: {e}")
        return []
