"""
ai_assistant.py — wraps Ollama to answer questions about screen content.

Requires local Ollama running: https://ollama.com  (brew install ollama)
Default model: qwen2.5-coder:7b  — change with OLLAMA_MODEL env var.

Model routing (used when multiple models are available):
  coding   → qwen2.5-coder:7b   (best for algorithms, code)
  interview→ llama3.2 / mistral  (best for behavioral, system design)
  quiz     → qwen2.5-coder:1.5b  (fast, simple answers)
  reading  → any small model
  fallback → DEFAULT_MODEL
"""
from __future__ import annotations

import os
import sys

import ollama  # type: ignore[import]

DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")

# Preferred model per content type — first available one wins
MODEL_PREFERENCES: dict[str, list[str]] = {
    "coding":    ["qwen2.5-coder:7b", "qwen2.5-coder:1.5b", "codellama:7b"],
    "interview": ["llama3.2", "mistral:7b", "llama3:8b", "qwen2.5-coder:7b"],
    "quiz":      ["qwen2.5-coder:1.5b", "qwen2.5-coder:7b", "llama3.2"],
    "reading":   ["llama3.2", "qwen2.5-coder:7b", "mistral:7b"],
    "unclear":   [DEFAULT_MODEL],
}

SYSTEM_PROMPT = """You are a silent assistant watching the user's screen.
Your job: give SHORT, ACTIONABLE answers. No intros, no "I see that...", no fluff.

Detect what's on screen and respond in the matching format:

─── CODING TASK / ALGORITHM ───
TYPE: coding
APPROACH: [1 sentence — what algorithm/pattern to use]
CODE:
```
[working solution, minimal, no comments]
```
COMPLEXITY: O(?) time, O(?) space

─── INTERVIEW QUESTION (behavioral/system design) ───
TYPE: interview
ANSWER:
• [point 1]
• [point 2]
• [point 3]

─── MULTIPLE CHOICE / QUIZ ───
TYPE: quiz
ANSWER: [letter]. [reason in ≤10 words]

─── READING / FORM / TEXT ───
TYPE: reading
SUMMARY: [1-2 sentences max]
KEY: [most important fact or action needed]

─── UNCLEAR / NOT A TASK ───
TYPE: unclear
CONTENT: [what you see in ≤15 words]

Rules:
- NEVER write more than 15 lines total
- NEVER explain what the problem is asking (user can read)
- If code: give working code immediately
- Respond in the language of the screen content"""

# Fast classifier prompt — runs on small model first
_CLASSIFY_PROMPT = """Classify screen content in ONE word: coding / interview / quiz / reading / unclear
Respond ONLY with one of those words, nothing else."""


def _detect_type(screen_text: str, available_models: list[str]) -> str:
    """Use a fast small model to classify what's on screen."""
    # Pick smallest available model for classification
    classifier = next(
        (m for m in ["qwen2.5-coder:1.5b", "llama3.2:1b", available_models[0]]
         if m in available_models),
        available_models[0] if available_models else DEFAULT_MODEL
    )
    try:
        resp = ollama.chat(
            model=classifier,
            messages=[
                {"role": "system", "content": _CLASSIFY_PROMPT},
                {"role": "user", "content": screen_text[:800]},  # first 800 chars enough
            ],
            stream=False,
        )
        if isinstance(resp, dict):
            result = resp.get("message", {}).get("content", "")
        else:
            msg = getattr(resp, "message", None)
            result = (getattr(msg, "content", "") or "") if msg else ""
        result = result.strip().lower().split()[0] if result.strip() else "unclear"
        return result if result in MODEL_PREFERENCES else "unclear"
    except Exception:
        return "unclear"


def _pick_model(content_type: str, available_models: list[str], default: str) -> str:
    """Return best available model for the given content type."""
    # Normalize: strip ':latest' suffix for matching
    def norm(name: str) -> str:
        return name.replace(":latest", "")

    normed = {norm(m): m for m in available_models}

    for candidate in MODEL_PREFERENCES.get(content_type, [default]):
        if norm(candidate) in normed:
            return normed[norm(candidate)]
    return default


def ask(
    screen_text: str,
    question: str = "Detect what's on screen and respond in the matching format.",
    model: str = DEFAULT_MODEL,
    stream: bool = True,
    overlay=None,
    output=None,
    auto_route: bool = True,  # enable model routing based on content type
) -> str:
    """Send screen_text + question to Ollama and return the response."""

    # ── Model routing ───────────────────────────────────────────────────────
    used_model = model
    if auto_route:
        available = list_models()
        if len(available) > 1:
            content_type = _detect_type(screen_text, available)
            used_model = _pick_model(content_type, available, model)
            if used_model != model:
                print(f"[router] type={content_type} → {used_model}", file=sys.stderr)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"[SCREEN CONTENT]\n{screen_text}\n\n[QUESTION]\n{question}"},
    ]

    if stream:
        response_chunks = []
        for chunk in ollama.chat(model=used_model, messages=messages, stream=True):
            if isinstance(chunk, dict):
                piece = chunk.get("message", {}).get("content", "")
            else:
                msg = getattr(chunk, "message", None)
                piece = (getattr(msg, "content", "") or "") if msg else ""
            if piece:
                print(piece, end="", flush=True)
                if overlay:
                    overlay.append(piece)
                if output:
                    output.write(piece)
                response_chunks.append(piece)
        print()
        if output:
            output.write("\n")
        return "".join(response_chunks)
    else:
        response = ollama.chat(model=used_model, messages=messages)
        if isinstance(response, dict):
            return response.get("message", {}).get("content", "")
        msg = getattr(response, "message", None)
        return (getattr(msg, "content", "") or "") if msg else ""


def list_models() -> list[str]:
    """Return names of locally available Ollama models."""
    try:
        resp = ollama.list()
        models = resp.get("models") if isinstance(resp, dict) else getattr(resp, "models", [])
        result = []
        for m in models:
            if isinstance(m, dict):
                result.append(m.get("name") or m.get("model", ""))
            else:
                name = getattr(m, "name", None) or getattr(m, "model", "")
                result.append(str(name))
        return [n for n in result if n]
    except Exception:
        return []


