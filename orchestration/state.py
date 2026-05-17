"""LangGraph state schema for Synthesis Agent orchestration."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages

JsonDict = dict[str, Any]


def merge_agent_results(left: list[JsonDict], right: list[JsonDict] | None) -> list[JsonDict]:
    """Reducer for agent result lists.

    LangGraph reducers define how state updates combine across nodes. Phase 4 is
    sequential, but using a reducer now keeps the state ready for later fan-out.
    """
    if right is None:
        return left
    return [*left, *right]


def merge_sources(left: list[JsonDict], right: list[JsonDict] | None) -> list[JsonDict]:
    if right is None:
        return left
    return [*left, *right]


class SynthesisState(TypedDict, total=False):
    """State passed between LangGraph nodes.

    `messages` uses LangGraph's built-in message reducer. `agent_results` and
    `sources` use small custom reducers so each node can append structured data
    without overwriting prior node output.
    """

    messages: Annotated[list, add_messages]
    query: str
    agent_cards: list[JsonDict]
    plan: JsonDict
    agent_results: Annotated[list[JsonDict], merge_agent_results]
    sources: Annotated[list[JsonDict], merge_sources]
    combined_analysis: str
    confidence: str
    briefing: JsonDict
