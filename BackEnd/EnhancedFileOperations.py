"""
EnhancedFileOperations.py - Enhanced file operations with temporal support
Wraps existing file operations with temporal context awareness
"""
import os
from typing import Optional, List, Tuple

def open_file_with_temporal_context(
    search_term: str,
    confidence_threshold: int = 75,
    max_files: int = 5,
    search_paths: Optional[List[str]] = None
) -> bool:
    """
    Enhanced file opening with temporal context support.
    Handles queries like "file from yesterday", "document this week", etc.
    
    Args:
        search_term: File search term, may include "temporal:key" suffix
        confidence_threshold: Minimum confidence score
        max_files: Maximum files to open
        search_paths: Directories to search
    
    Returns:
        True if files were opened successfully
    """
    from Automation import Open, open_document, log_automation
    
    # Check if temporal context is specified
    temporal_key = None
    if 'temporal:' in search_term:
        parts = search_term.split('temporal:')
        search_term = parts[0].strip()
        temporal_key = parts[1].strip()
        print(f" Temporal context: {temporal_key}")
    
    # Try temporal search if context provided
    if temporal_key:
        try:
            from TemporalFileSearch import find_files_with_temporal_context
            
            print(f" Searching for '{search_term}' from {temporal_key}...")
            
            matches = find_files_with_temporal_context(
                search_term=search_term,
                temporal_key=temporal_key,
                search_paths=search_paths,
                confidence_threshold=confidence_threshold
            )
            
            if matches:
                files_to_open = matches[:max_files]
                
                print(f" Found {len(matches)} file(s):")
                for path, score in files_to_open:
                    print(f"   {os.path.basename(path)} ({score:.0f}%)")
                
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
                    print(f" Opened {opened_count} file(s)")
                    log_automation(
                        action_type="open_file",
                        action_details=f"Opened {opened_count} file(s): {search_term} ({temporal_key})",
                        status="success",
                        metadata={
                            "search_term": search_term,
                            "temporal_context": temporal_key,
                            "files_opened": opened_files
                        }
                    )
                    return True
            else:
                print(f" No files found for '{search_term}' from {temporal_key}")
        
        except ImportError:
            print(" Temporal search not available, using regular search")
    
    # Fall back to regular Open function
    return Open(search_term, confidence_threshold, max_files, search_paths)
