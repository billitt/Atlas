"""Verify Ollama is running and Granite 4.1 8B responds."""

from __future__ import annotations

import sys

from services.llm import OLLAMA_BASE_URL, OLLAMA_CHAT_MODEL, list_models, ollama_generate


def main() -> None:
    print(f"Ollama base URL: {OLLAMA_BASE_URL}")
    print(f"Expected model:  {OLLAMA_CHAT_MODEL}")
    print()

    try:
        models = list_models()
    except Exception as exc:
        print(f"FAIL: Cannot reach Ollama at {OLLAMA_BASE_URL}")
        print(f"      {exc}")
        print()
        print("Install Ollama: https://ollama.com/download")
        print("Then pull Granite: ollama pull ibm/granite4.1:8b")
        sys.exit(1)

    print("Available models:")
    for name in models:
        marker = (
            " <-- configured"
            if name == OLLAMA_CHAT_MODEL or name.startswith(OLLAMA_CHAT_MODEL)
            else ""
        )
        print(f"  - {name}{marker}")

    if not any(m == OLLAMA_CHAT_MODEL or m.startswith(f"{OLLAMA_CHAT_MODEL}") for m in models):
        print()
        print(f"WARN: {OLLAMA_CHAT_MODEL} not found. Pull it with:")
        print(f"      ollama pull {OLLAMA_CHAT_MODEL}")
        sys.exit(1)

    print()
    print("Sending test prompt to Granite...")
    reply = ollama_generate("Reply with exactly: Atlas Phase 0 OK")
    print(f"Response: {reply.strip()}")
    print()
    print("PASS: Ollama + Granite are responding.")


if __name__ == "__main__":
    main()
