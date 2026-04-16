"""
ai_assistant.py — wraps Ollama to answer questions about screen content.

Requires local Ollama running: https://ollama.com  (brew install ollama)
Default model: llama3.2  — change with --model flag or OLLAMA_MODEL env var.
"""
from __future__ import annotations

import os
import sys
from typing import Iterator

import ollama  # type: ignore[import]

DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

SYSTEM_PROMPT = """You are a concise, helpful assistant.
The user will share text currently visible on their screen.
Answer only based on what is shown. Be brief and direct.
If the screen content is unclear or unrelated to the question, say so."""


def ask(
    screen_text: str,
    question: str = "Summarize what's on screen and highlight anything important.",
    model: str = DEFAULT_MODEL,
    stream: bool = True,
    overlay=None,   # optional OverlayWindow
    output=None,    # optional MultiOutput (TCP + BT)
) -> str:
    """Send screen_text + question to Ollama and return the response."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"[SCREEN CONTENT]\n{screen_text}\n\n[QUESTION]\n{question}",
        },
    ]

    if stream:
        response_chunks = []
        for chunk in ollama.chat(model=model, messages=messages, stream=True):
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
        # Send newline to external output after response
        if output:
            output.write("\n")
        return "".join(response_chunks)
    else:
        response = ollama.chat(model=model, messages=messages)
        if isinstance(response, dict):
            return response.get("message", {}).get("content", "")
        msg = getattr(response, "message", None)
        return (getattr(msg, "content", "") or "") if msg else ""
    """Send screen_text + question to Ollama and return the response."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"[SCREEN CONTENT]\n{screen_text}\n\n[QUESTION]\n{question}",
        },
    ]

    if stream:
        response_chunks = []
        for chunk in ollama.chat(model=model, messages=messages, stream=True):
            if isinstance(chunk, dict):
                piece = chunk.get("message", {}).get("content", "")
            else:
                msg = getattr(chunk, "message", None)
                piece = (getattr(msg, "content", "") or "") if msg else ""
            if piece:
                print(piece, end="", flush=True)
                if overlay:
                    overlay.append(piece)
                response_chunks.append(piece)
        print()
        return "".join(response_chunks)
    else:
        response = ollama.chat(model=model, messages=messages)
        if isinstance(response, dict):
            return response.get("message", {}).get("content", "")
        msg = getattr(response, "message", None)
        return (getattr(msg, "content", "") or "") if msg else ""


def list_models() -> list[str]:
    """Return names of locally available Ollama models."""
    try:
        resp = ollama.list()
        # resp is a ListResponse object with .models attribute (list of Model objects)
        models = resp.get("models") if isinstance(resp, dict) else getattr(resp, "models", [])
        result = []
        for m in models:
            if isinstance(m, dict):
                result.append(m.get("name") or m.get("model", ""))
            else:
                name = getattr(m, "name", None) or getattr(m, "model", "")
                result.append(str(name))
        return [n for n in result if n]
    except Exception as e:
        return []

