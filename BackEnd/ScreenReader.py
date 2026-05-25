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


def is_task_identification_request(question: str) -> bool:
    """Detect screen prompts asking what the user is working on."""
    import re
    q_lower = (question or "").lower().strip()
    patterns = [
        r'\bwhat\s+(?:am\s+i|task\s+am\s+i)\s+(?:working\s+on|doing)\b',
        r'\bexplain\s+what\s+task\s+i\s+am\s+(?:currently\s+)?working\s+on\b',
        r'\blook\s+at\s+(?:my\s+|the\s+)?screen\s+and\s+explain\s+what\s+task\b',
        r'\bwhat\s+is\s+(?:my\s+)?current\s+task\b',
        r'\bwhat\s+problem\s+am\s+i\s+(?:solving|working\s+on)\b',
    ]
    return any(re.search(pattern, q_lower) for pattern in patterns)


def get_screen_answer_instructions(question: str) -> str:
    """Style instructions tuned to the user's actual screen request."""
    if is_task_identification_request(question):
        return (
            "Answer in 2-4 short bullets. Identify only the main task, the platform/app if visible, "
            "the programming language if visible, and one useful next step. "
            "Do not mention weather, date/time, taskbar icons, OS, language settings, or speculative user profile details. "
            "Do not say 'based on the image content'."
        )

    return (
        "Answer the user's screen question directly and concisely. Include only details relevant to the request. "
        "Do not mention weather, date/time, taskbar icons, OS, language settings, or background UI unless the user asks. "
        "Avoid guessing demographics, skill level, or motivations."
    )


async def analyze_screen(question: str = "") -> str:
    """
    Capture the screen and ask the Groq Vision model about it.
    """
    if not groq_client:
        return "❌ Screen reader unavailable — GroqScreenReader API key not configured."

    prompt = question.strip() if question.strip() else DEFAULT_QUESTION
    answer_instructions = get_screen_answer_instructions(prompt)

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
        max_answer_tokens = 350 if is_task_identification_request(prompt) else 700

        # 2. Send to vision model
        response = await groq_client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are Synorpse, a desktop assistant with vision capabilities. "
                        "You have been provided with a screenshot of the user's primary monitor. "
                        "Analyze the image content to answer the user's request accurately and concisely. "
                        "Do not say you cannot see the screen — the image is attached below."
                    )
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"User Prompt: {prompt}\n\n"
                                f"Response style: {answer_instructions}\n\n"
                                "Task: Use the screenshot to answer the user's request. "
                                "Name important visible entities only when they are relevant to the request. "
                                "For location-identification tasks, describe visual clues. "
                                "For coding/problem-solving tasks, focus on the problem, language, visible code state, and next step."
                            ),
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
            max_tokens=max_answer_tokens,
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
