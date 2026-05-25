"""
LangChainReasoning.py - structured planning for SYNORPSE agent workflows.

This module adds a thin LangChain-backed planner around the existing ReAct
loop. LangChain is optional at runtime: when langchain-groq is unavailable,
the planner falls back to the existing Groq completion callable supplied by
RealTimeSearchEngine.
"""
import json
import re
import warnings
from typing import Any, Awaitable, Callable, Dict, Optional


LANGCHAIN_AVAILABLE = False
_LANGCHAIN_IMPORT_ERROR = None

try:
    warnings.filterwarnings(
        "ignore",
        message="Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.*",
        category=UserWarning,
    )
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_groq import ChatGroq

    LANGCHAIN_AVAILABLE = True
except Exception as exc:  # pragma: no cover - depends on local environment
    ChatPromptTemplate = None
    ChatGroq = None
    _LANGCHAIN_IMPORT_ERROR = exc


PlannerFallback = Callable[..., Awaitable[Any]]


def get_langchain_status() -> Dict[str, Any]:
    """Return runtime status for diagnostics and capability answers."""
    return {
        "available": LANGCHAIN_AVAILABLE,
        "error": str(_LANGCHAIN_IMPORT_ERROR) if _LANGCHAIN_IMPORT_ERROR else None,
    }


class LangChainReasoningPlanner:
    """Structured planner that decides the next action for the existing loop."""

    def __init__(
        self,
        model: str,
        api_key_getter: Callable[[], Optional[str]],
        fallback_call: PlannerFallback,
        temperature: float = 0.2,
    ):
        self.model = model
        self.api_key_getter = api_key_getter
        self.fallback_call = fallback_call
        self.temperature = temperature

    async def plan_next(
        self,
        *,
        goal: str,
        context: Optional[str],
        memory: str,
        trace_context: str,
        actions_desc: str,
        action_names: str,
    ) -> Optional[tuple]:
        """Return (visible_thought, action, action_input), or None on failure."""
        prompt = self._build_prompt(
            goal=goal,
            context=context,
            memory=memory,
            trace_context=trace_context,
            actions_desc=actions_desc,
            action_names=action_names,
        )

        content = await self._call_planner(prompt)
        if not content:
            return None

        try:
            data = self._parse_json(content)
        except Exception:
            return None

        allowed_actions = {name.strip() for name in action_names.split(",") if name.strip()}
        action = str(data.get("action") or "finish").strip()
        if action not in allowed_actions:
            action = "search_knowledge" if "search_knowledge" in allowed_actions else "finish"

        action_input = data.get("action_input")
        if not isinstance(action_input, dict):
            action_input = {}

        visible_thought = str(
            data.get("visible_thought")
            or data.get("thought")
            or "I am choosing the next best step."
        ).strip()

        return visible_thought, action, action_input

    async def _call_planner(self, prompt: str) -> Optional[str]:
        if LANGCHAIN_AVAILABLE:
            api_key = self.api_key_getter()
            if api_key:
                try:
                    try:
                        llm = ChatGroq(
                            groq_api_key=api_key,
                            model=self.model,
                            temperature=self.temperature,
                        )
                    except TypeError:
                        llm = ChatGroq(
                            api_key=api_key,
                            model=self.model,
                            temperature=self.temperature,
                        )
                    chat_prompt = ChatPromptTemplate.from_messages([
                        ("system", "You are a structured agent planner. Return only valid JSON."),
                        ("user", "{prompt}"),
                    ])
                    response = await (chat_prompt | llm).ainvoke({"prompt": prompt})
                    return str(getattr(response, "content", response)).strip()
                except Exception:
                    pass

        try:
            response = await self.fallback_call(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a structured agent planner. Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=1200,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return None

    def _build_prompt(
        self,
        *,
        goal: str,
        context: Optional[str],
        memory: str,
        trace_context: str,
        actions_desc: str,
        action_names: str,
    ) -> str:
        return f"""Plan the next step for this agent workflow.

GOAL:
{goal}

CONTEXT:
{context or "No extra context."}

RELEVANT MEMORY:
{memory or "No relevant prior memory."}

PREVIOUS STEPS:
{trace_context}

AVAILABLE ACTIONS:
{actions_desc}

RULES:
- Choose exactly one action from: {action_names}.
- Observe broadly, but answer narrowly: use context internally and include only what directly helps the user's request.
- Use search for current or unknown facts.
- Use read_screen only when the user explicitly asks about visible screen/display/page/image/window content.
- Use read_document only for an active or uploaded document.
- Use create_file only when the user asks for a file/document/code artifact.
- Use send_message only when the user clearly asks to send/share/email/WhatsApp something.
- Use finish only when the available context, memory, or observations are enough to answer.
- For multi-step tasks, keep a concise plan internally, then choose only the next action now.
- Do not expose hidden chain-of-thought. The visible_thought must be a brief user-safe status update.
- Do not include incidental screen/environment details, trace IDs, tool schemas, weather/date/taskbar/OS details, or speculative user profile guesses unless asked.

Return ONLY JSON:
{{
  "visible_thought": "short user-safe planning update",
  "action": "one action name",
  "action_input": {{}}
}}"""

    @staticmethod
    def _parse_json(content: str) -> Dict[str, Any]:
        text = content.strip()
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0].strip()

        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            text = match.group(0)

        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("Planner output must be a JSON object")
        return data
