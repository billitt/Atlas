"""Minimal LangGraph hello world — single node graph calling Granite via Ollama."""

from __future__ import annotations

from typing import Annotated

from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from services.llm import OLLAMA_CHAT_MODEL, get_chat_ollama


class State(TypedDict):
    messages: Annotated[list, add_messages]


def chatbot(state: State) -> dict:
    llm = get_chat_ollama()
    reply = llm.invoke(state["messages"])
    return {"messages": [reply]}


def build_graph():
    graph = StateGraph(State)
    graph.add_node("chatbot", chatbot)
    graph.add_edge(START, "chatbot")
    graph.add_edge("chatbot", END)
    return graph.compile()


def main() -> None:
    app = build_graph()
    prompt = "You are Atlas. In one short sentence, say hello from LangGraph."
    result = app.invoke({"messages": [("user", prompt)]})
    last = result["messages"][-1]
    content = getattr(last, "content", last)
    print(f"Model: {OLLAMA_CHAT_MODEL}")
    print(f"LangGraph -> Granite: {content}")


if __name__ == "__main__":
    main()
