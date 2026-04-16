import pyautogui
import pyperclip
import time
import csv
import json
import re
import difflib
from groq import Groq
import logging
from dotenv import dotenv_values
env_vars = dotenv_values(".env")

logging.basicConfig(level=logging.CRITICAL)
logger = logging.getLogger(__name__)

client = Groq(api_key=env_vars.get("GroqAPIKey"))

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5


def _clipboard_type(text, interval=None):
    """Type text using clipboard paste — works in UWP/Electron apps like WhatsApp Desktop."""
    old_clipboard = ""
    try:
        old_clipboard = pyperclip.paste()
    except Exception:
        pass
    pyperclip.copy(text)
    time.sleep(0.05)
    pyautogui.hotkey("ctrl", "v")
    time.sleep(0.15)
    # Restore old clipboard
    try:
        pyperclip.copy(old_clipboard)
    except Exception:
        pass

def load_phone_numbers(filepath: str) -> list[dict]:
    phonebook = []
    try:
        with open(filepath, mode='r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                alias = row["Alias"].strip().lower()
                name = row["Name"].strip()
                phone = re.sub(r"[^\d+]", "", row["Phone"].strip())

                if not phone or "E+" in phone.upper():
                    continue
                
                if phone.startswith("+91"):
                    pass
                elif phone.startswith("91") and len(phone) >= 12:
                    phone = "+91" + phone[2:]
                elif phone.startswith("0"):
                    phone = "+91" + phone[1:]
                elif phone.isdigit() and len(phone) == 10:
                    phone = "+91" + phone
                else:
                    continue

                phonebook.append({"alias": alias, "name": name, "phone": phone})
        
        return phonebook
    except:
        return []

def generate_message(query: str, max_retries: int = 2):
    prompt = f"""Extract 3 things from this WhatsApp command:
1. "recipient": Name of the person
2. "message": The message to send
3. "attachment": Any file mentioned to send (or null if none)

Query: "{query}"

For attachment: if user says "send my resume", attachment="resume".
If user says "send this file", and provided no name, assume context implies a file.

Respond ONLY with valid JSON in this exact format:
{{"recipient": "name", "message": "msg", "attachment": "search_term_or_null"}}

Do not include any other text."""

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            raw = response.choices[0].message.content.strip()
            
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                raw = json_match.group(0)
            
            data = json.loads(raw)
            
            recipient = data.get("recipient", "").lower().strip()
            message = data.get("message", "").strip()
            attachment = data.get("attachment")
            
            if attachment and attachment.lower() == "null":
                attachment = None
                
            if recipient and message:
                return recipient, message, attachment
            
        except:
            pass
    
    return None, None, None

def open_whatsapp_desktop():
    try:
        pyautogui.press("win")
        time.sleep(0.7)
        _clipboard_type("WhatsApp")
        time.sleep(0.7)
        pyautogui.press("enter")
        time.sleep(3.0)  # WhatsApp Desktop needs more time to fully load
        return True
    except:
        return False

def resolve_alias(recipient: str, phonebook: list[dict]) -> dict | None:
    recipient = recipient.lower().strip()
    
    # Handle self-messaging (WhatsApp "You")
    if recipient in ["me", "myself", "self", "i"]:
        return {"alias": "me", "name": "You", "phone": "You"}
    
    for entry in phonebook:
        if entry["alias"] == recipient:
            return entry
    
    for entry in phonebook:
        alias = entry["alias"]
        if recipient in alias or alias in recipient:
            return entry
    
    for entry in phonebook:
        alias_words = entry["alias"].split()
        for word in alias_words:
            if len(word) >= 3:
                matches = difflib.get_close_matches(recipient, [word], n=1, cutoff=0.8)
                if matches:
                    return entry
    
    aliases = [entry["alias"] for entry in phonebook]
    best_match = difflib.get_close_matches(recipient, aliases, n=1, cutoff=0.7)
    
    if best_match:
        for entry in phonebook:
            if entry["alias"] == best_match[0]:
                return entry
    
    return None

import subprocess
import os

def copy_file_to_clipboard(file_path):
    """Copy a file to the clipboard using PowerShell"""
    try:
        if not os.path.exists(file_path):
            return False
            
        # Use PowerShell to set clipboard
        cmd = f'powershell -command "Set-Clipboard -Path \'{file_path}\'"'
        subprocess.run(cmd, shell=True, check=True)
        return True
    except Exception as e:
        pass
        return False

def send_whatsapp_message(contact: dict, message: str, file_path: str = None):
    try:
        raw_number = contact["phone"]
        
        # Handle special case: sending to yourself
        if raw_number in ["You", "you", "ME", "Me", "me"]:
            pyautogui.hotkey("ctrl", "n")  # New chat shortcut
            time.sleep(0.8)
            _clipboard_type("You")
            time.sleep(0.5)
            pyautogui.press("enter")
            time.sleep(0.8)
        else:
            # Normal contact search
            if raw_number.startswith("+91"):
                search_number = raw_number[3:]
            else:
                search_number = raw_number
            
            pyautogui.hotkey("ctrl", "f")
            time.sleep(0.4)
            pyautogui.hotkey("ctrl", "a")
            time.sleep(0.2)

            _clipboard_type(search_number)
            time.sleep(0.5)  # Wait for search results to populate
            
            pyautogui.press("tab")
            time.sleep(0.15)
            pyautogui.press("tab")
            time.sleep(0.15)
            pyautogui.press("enter")
            time.sleep(0.5)
        
        # Handle file attachment if provided
        if file_path:
            if copy_file_to_clipboard(file_path):
                time.sleep(0.5)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(1.5)  # Wait for file preview to load
            else:
                message += f"\n[Failed to attach file: {os.path.basename(file_path)}]"
        
        # Send message text using clipboard paste (pyautogui.write fails in UWP apps)
        if message:
            lines = message.split('\n')
            for i, line in enumerate(lines):
                _clipboard_type(line)
                if i < len(lines) - 1:
                    pyautogui.hotkey("shift", "enter")
                    time.sleep(0.2)
        
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(1.5)
        
        pyautogui.hotkey("alt", "f4")
        return True
        
    except Exception as e:
        pass
        return False
    
# Import file search capabilities
try:
    from TemporalFileSearch import find_files_with_temporal_context
except ImportError:
    find_files_with_temporal_context = None

def send_whatsapp_desktop(query: str, phonebook: list[dict], file_path: str = None):
    # Unpack 3 values now
    recipient, message, attachment_query = generate_message(query)
    
    # Valid if we have recipient AND (message OR attachment)
    if not recipient or (not message and not attachment_query):
        return False
    
    # Resolve attachment if query provided but no direct path
    if attachment_query and not file_path:
        print(f" Looking for attachment: '{attachment_query}'")
        
        # Check for temporal context
        temporal_key = None
        search_term = attachment_query
        
        # Simple temporal extraction
        if "yesterday" in attachment_query.lower():
            temporal_key = "yesterday"
            search_term = attachment_query.lower().replace("yesterday", "").strip()
        elif "today" in attachment_query.lower():
            temporal_key = "today"
            search_term = attachment_query.lower().replace("today", "").strip()
            
        if find_files_with_temporal_context:
            # Use robust search (with or without temporal filter)
            matches = find_files_with_temporal_context(search_term, temporal_key)
            if matches:
                file_path = matches[0][0]
                print(f" Found file: {os.path.basename(file_path)}")
        else:
            # Fallback (legacy)
            # For now, if no temporal context, we just warn or skip if not an absolute path
            if os.path.exists(attachment_query):
                file_path = attachment_query
            else:
                # Try simple fuzzy search if we can access the file index (not easily accessible here without huge import)
                # Ideally, we should move file search logic to a shared utility
                print(f" Could not resolve file '{attachment_query}'. Sending text only.")

    print(f" Sending to: {recipient}")
    print(f" Message: {message}")
    if file_path:
        print(f" Attachment: {os.path.basename(file_path)}")
    
    if not open_whatsapp_desktop():
        return False
    
    contact = resolve_alias(recipient, phonebook)
    if not contact:
        pyautogui.hotkey("alt", "f4")
        return False
    
    return send_whatsapp_message(contact, message, file_path)

if __name__ == "__main__":
    phonebook = load_phone_numbers(r"Data/converted_contacts.csv")
    
    if not phonebook:
        print(" No contacts loaded")
        exit(1)
    
    query = ""
    success = send_whatsapp_desktop(query, phonebook)
    
    if not success:
        print(" Failed to send message")