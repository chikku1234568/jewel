"""A scripted LangChain chat model for agent tests. It never leaves the process."""

from collections.abc import Callable
from itertools import count
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

_ids = count()


def call(name: str, **arguments: Any) -> AIMessage:
    """A reply that asks for one tool."""
    return calls((name, arguments))


def calls(*requests: tuple[str, dict]) -> AIMessage:
    """A reply that asks for several tools in one turn."""
    tool_calls = [
        {"name": name, "args": args, "id": f"call-{next(_ids)}"} for name, args in requests
    ]
    return AIMessage(content="", tool_calls=tool_calls)


class Turn:
    """What the model was given on one call."""

    def __init__(self, messages: list[BaseMessage], tools: list[dict]) -> None:
        self.messages = messages
        self.tools = tools

    @property
    def tool_names(self) -> list[str]:
        return [tool["function"]["name"] for tool in self.tools]

    @property
    def tool_results(self) -> int:
        return sum(isinstance(message, ToolMessage) for message in self.messages)

    @property
    def observations(self) -> list[str]:
        return [str(m.content) for m in self.messages if isinstance(m, ToolMessage)]

    @property
    def text(self) -> str:
        """Everything the model could read on this call, tool schemas included."""
        return "\n".join([str(m.content) for m in self.messages] + [str(self.tools)])


class ScriptedChat(BaseChatModel):
    """``script(turn)`` returns the next reply; every turn is kept in ``turns``."""

    script: Callable[[Turn], AIMessage]
    turns: list[Turn] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self.bind(tools=[convert_to_openai_tool(tool) for tool in tools], **kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        turn = Turn(list(messages), list(kwargs.get("tools") or []))
        self.turns.append(turn)
        return ChatResult(generations=[ChatGeneration(message=self.script(turn))])
