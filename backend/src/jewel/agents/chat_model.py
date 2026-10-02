"""A LangChain chat model over ``OpenAICompatibleChat``, with native tool calls.

``create_agent`` needs a ``BaseChatModel`` that can ``bind_tools``. This adapter keeps
the one HTTP client the project already has (429 retry, Kimi thinking off, no
``temperature``) instead of adding a second SDK. It only translates messages: LangChain
messages to OpenAI-style dicts on the way out, the assistant reply (text and
``tool_calls``) back to an ``AIMessage``.
"""

import json
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage, convert_to_openai_messages
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ConfigDict

from jewel.llm.openai_chat import DEFAULT_MAX_TOKENS, OpenAICompatibleChat


class ToolCallingChat(BaseChatModel):
    """One ``/chat/completions`` call per agent turn. The API key stays on ``client``."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: OpenAICompatibleChat
    max_tokens: int = DEFAULT_MAX_TOKENS  # the answer call keeps the 1024 default

    @property
    def _llm_type(self) -> str:
        return "jewel-openai-compatible"

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        """Send these tools' JSON schemas with every call (``tool_choice`` is not used)."""
        return self.bind(tools=[convert_to_openai_tool(tool) for tool in tools], **kwargs)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        reply = self.client.chat(
            convert_to_openai_messages(messages),
            tools=kwargs.get("tools") or None,
            max_tokens=self.max_tokens,
        )
        return ChatResult(generations=[ChatGeneration(message=assistant_message(reply))])


def assistant_message(reply: dict) -> AIMessage:
    """OpenAI-style assistant dict to ``AIMessage``. Bad tool arguments become invalid calls."""
    tool_calls = []
    invalid_tool_calls = []
    for call in reply.get("tool_calls") or []:
        function = call.get("function") or {}
        raw = function.get("arguments") or "{}"
        try:
            args = json.loads(raw)
            if not isinstance(args, dict):
                raise ValueError("tool arguments must be a JSON object")
        except ValueError as exc:  # json.JSONDecodeError is a ValueError
            invalid_tool_calls.append(
                {"name": function.get("name"), "args": raw, "id": call.get("id"), "error": str(exc)}
            )
            continue
        tool_calls.append({"name": function.get("name") or "", "args": args, "id": call.get("id")})
    content = reply.get("content") or ""
    if not content and not tool_calls and not invalid_tool_calls:
        if reply.get("reasoning_content"):
            raise RuntimeError("kimi returned thinking text and no answer")
        raise RuntimeError("agent model returned an empty answer")
    return AIMessage(content=content, tool_calls=tool_calls, invalid_tool_calls=invalid_tool_calls)
