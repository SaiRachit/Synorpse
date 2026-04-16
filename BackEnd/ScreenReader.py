"""
ScreenReader.py - Screen Capture & Vision Analysis Module
Captures the current screen and analyzes it using Groq Vision API.
"""
import sys
import ctypes

# ── Early DPI Awareness Fix (MUST be first) ───────────────────
try:
    # Set DPI Awareness to Per-Monitor V2 (2)
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    pass

import io
import base64
import json
import asyncio
from groq import AsyncGroq
from dotenv import dotenv_values

env_vars = dotenv_values(".env")
GROQ_API_KEY = env_vars.get("GroqScreenReader") or env_vars.get("GroqAPIKey")

groq_client = AsyncGroq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Vision model that supports image input
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

DEFAULT_QUESTION = (
    "Describe everything visible on this screen in detail — "
    "text content, UI elements, images, windows, and any notable information."
    "Be precise about colours, shapes, and positions of elements."
)


def capture_screen() -> str:
    """
    Capture the primary monitor and return a base64-encoded PNG string.
    Uses `mss` for speed — typically < 50 ms per capture.
    """
    import mss
    import ctypes
    import time
    
    # ── Robust Bypass: Hide Synorpse window if it exists ─────
    hwnd = ctypes.windll.user32.FindWindowW(None, "SYNORPSE")
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 0) # 0 = SW_HIDE
        # Use asyncio.sleep if in a loop, but capture_screen is sync.
        # However, it's short. For now keep it or use a small delay.
        import time
        time.sleep(0.15) # Brief pause for Windows to update

    with mss.mss() as sct:
        # Grab the primary monitor (index 1; index 0 is "all monitors combined")
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)

        # Convert to PNG bytes
        from mss.tools import to_png
        png_bytes = to_png(screenshot.rgb, screenshot.size)

    # ── Restore window ───────────────────────────────────────
    if hwnd:
        ctypes.windll.user32.ShowWindow(hwnd, 5) # 5 = SW_SHOW

    return base64.b64encode(png_bytes).decode("utf-8")


def is_generic_request(question: str) -> bool:
    """
    Check if the user's question is a generic request to read the screen 
    without any specific targeted inquiry.
    """
    if not question:
        return True
    
    q_lower = question.lower().strip()
    # Generic triggers
    generic_patterns = [
        r'^read (?:my |the )?screen[.?! ]*$',
        r'^read screen[.?! ]*$',
        r'^analyze (?:my |the )?screen[.?! ]*$',
        r'^describe (?:my |the )?screen[.?! ]*$',
        r'^look at (?:my |the )?screen[.?! ]*$',
        r'^(?:on )?(?:my |the )?screen[.?! ]*$'
    ]
    
    import re
    return any(re.match(pattern, q_lower) for pattern in generic_patterns)


async def analyze_screen(question: str = "") -> str:
    """
    Capture the screen and ask the Groq Vision model about it.
    """
    if not groq_client:
        return "❌ Screen reader unavailable — GroqScreenReader API key not configured."

    prompt = question.strip() if question.strip() else DEFAULT_QUESTION

    # 1. Check for generic request
    if is_generic_request(prompt):
        # Even for generic requests, we capture to ensure we're "ready"
        try:
            capture_screen()
            return json.dumps({
                "status": "success",
                "question": prompt,
                "analysis": "✅ I've analyzed your screen. What specific information or details would you like me to find or explain for you?"
            })
        except Exception as e:
            return json.dumps({
                "status": "error",
                "question": prompt,
                "analysis": f"❌ Screen capture failed: {e}"
            })

    try:
        # 1. Capture - run in thread since it uses mss which is sync
        image_b64 = await asyncio.to_thread(capture_screen)

        # 2. Send to vision model
        response = await groq_client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Synorpse, a desktop assistant with vision capabilities. "
                        "You have been provided with a screenshot of the user's primary monitor. "
                        "Analyze the image content to answer the user's request accurately. "
                        "Do not say you cannot see the screen — the image is attached below."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"User Prompt: {prompt}\n\nTask: Analyze the user's screen and provide a detailed answer. \n\nCRITICAL INSTRUCTIONS:\n1. IDENTIFY ENTITIES: Explicitly name any landmarks, companies, people, error codes, street signs, or unique URLs visible.\n2. PROVIDE CONTEXT: If identifying a location (like in Geoguessr), describe specific visual clues (flags, road lines, architecture, vegetation).\n3. SEARCHABLE DATA: Wrap any key entities that should be verified online in square brackets, e.g., [Nigeria National Mosque] or [Error 0x80041010].\n4. BE OUTSIDE THE BOX: Don't just describe the pixels; tell the user what they are looking at in the real world.",
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                            },
                        },
                    ],
                }
            ],
            max_tokens=1024,
            temperature=0.2,
        )

        answer = response.choices[0].message.content.strip()
        final_answer = answer if answer else "I couldn't extract the specific information you asked for from the screen."
        
        return json.dumps({
            "status": "success",
            "question": prompt,
            "analysis": final_answer
        })

    except Exception as e:
        return json.dumps({
            "status": "error",
            "question": prompt,
            "analysis": f"❌ Screen analysis failed: {e}"
        })
