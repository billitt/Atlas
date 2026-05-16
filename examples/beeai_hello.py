"""Minimal BeeAI hello world — direct Granite chat via Ollama."""

from __future__ import annotations

import asyncio

from beeai_framework.backend.chat import ChatModel
from beeai_framework.backend.message import UserMessage

from services.llm import BEEAI_MODEL_NAME


async def run() -> None:
    llm = ChatModel.from_name(BEEAI_MODEL_NAME)
    response = await llm.create(
        messages=[UserMessage("You are Atlas. In one short sentence, say hello from BeeAI.")],
    )
    text = response.get_text_content()
    print(f"Model: {BEEAI_MODEL_NAME}")
    print(f"BeeAI → Granite: {text}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
