"""Local chat model for graph construction, and the one extraction prompt every model gets.

The user's API key is not used by ``OllamaChat``.
"""

import http.client
import json
import os
import threading
import urllib.request
from urllib.parse import urlparse

from jewel.llm.base import ChatModel
from jewel.llm.openai_chat import OpenAICompatibleChat

OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct"

# num_predict caps output tokens. Up to 20 triples, each with a verbatim quote, plus the
# entity list is well past 512 tokens; a reply cut off mid-JSON yields nothing for the
# chunk. Ollama is only used for extraction, so this budget is extraction-only.
EXTRACT_OPTIONS = {"temperature": 0, "num_predict": 4096}

# The same budget for OpenAI-compatible hosts, passed per call (see ``extract_document``).
EXTRACT_MAX_TOKENS = 4096

# One call per chunk does entity listing, pronoun resolution and triples together. The
# quote rule is enforced again in code: ``parse_extraction`` drops any triple whose quote
# is not an exact substring of the chunk. The worked example cannot leak into a graph:
# its quotes are not in the user's passage, so the same check would drop them.
_EXTRACT_SYSTEM = (
    "You build a knowledge graph from one passage of a user's document. "
    "Return one JSON object and nothing else: no prose and no Markdown code fences. Shape: "
    '{"entities":[{"name":"string","type":"person|organization|place|concept|other"}],'
    '"triples":[{"subject":"string","predicate":"string","object":"string","quote":"string"}]}. '
    "Work in this order. "
    "1. List the entities that appear in the passage: people, organizations, places, and "
    "the concepts the passage is about. Write each name as the passage writes it. "
    "2. Write triples whose subject and object are names from that entity list. The "
    "predicate is a short verb phrase. "
    '3. Resolve pronouns and references such as "she", "it" or "the company" to the name '
    "they refer to in the passage. Never use a pronoun as a subject or object. "
    "4. Every quote is copied verbatim from the passage, character for character, "
    "including any Markdown symbols inside it: the sentence or clause that states the fact. "
    "Do not paraphrase, shorten, correct, or join text from different places. A triple "
    "whose quote is not an exact copy of passage text is discarded. "
    "5. Return at most 20 triples, the facts most central to the passage first. "
    'If the passage states no facts, return {"entities":[],"triples":[]}. '
    "Example passage: "
    '"Ada Lovelace worked with Charles Babbage in London. She wrote the first published '
    'algorithm for his Analytical Engine." '
    "Example output: "
    '{"entities":[{"name":"Ada Lovelace","type":"person"},'
    '{"name":"Charles Babbage","type":"person"},{"name":"London","type":"place"},'
    '{"name":"Analytical Engine","type":"concept"}],'
    '"triples":[{"subject":"Ada Lovelace","predicate":"worked with",'
    '"object":"Charles Babbage",'
    '"quote":"Ada Lovelace worked with Charles Babbage in London."},'
    '{"subject":"Ada Lovelace","predicate":"wrote the first published algorithm for",'
    '"object":"Analytical Engine",'
    '"quote":"She wrote the first published algorithm for his Analytical Engine."}]}. '
    'In the second triple "She" became "Ada Lovelace", but the quote kept the passage\'s '
    "own words."
)


class OllamaChat:
    """One JSON chat completion against a local Ollama server."""

    def __init__(self, model: str | None = None, base_url: str | None = None) -> None:
        self.model = model or os.environ.get("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.base_url = (base_url or os.environ.get("OLLAMA_URL", OLLAMA_URL)).rstrip("/")
        self._conn: http.client.HTTPConnection | None = None
        self._conn_lock = threading.Lock()

    def abort(self) -> None:
        """Close the in-flight request and unload the model so generation stops."""
        with self._conn_lock:
            conn = self._conn
            self._conn = None
        if conn is not None:
            conn.close()
        request = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps({"model": self.model, "keep_alive": 0, "prompt": ""}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                response.read()
        except Exception:
            return

    def complete(self, system: str, user: str) -> str:
        body = json.dumps(
            {
                "model": self.model,
                "stream": False,
                "format": "json",
                "options": EXTRACT_OPTIONS,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            }
        ).encode()
        parsed = urlparse(self.base_url)
        conn = http.client.HTTPConnection(parsed.hostname, parsed.port or 11434, timeout=300)
        with self._conn_lock:
            self._conn = conn
        try:
            conn.request(
                "POST",
                "/api/chat",
                body=body,
                headers={"Content-Type": "application/json"},
            )
            response = conn.getresponse()
            payload = json.loads(response.read().decode())
        except Exception as exc:
            raise RuntimeError("Ollama is not reachable at " + self.base_url) from exc
        finally:
            with self._conn_lock:
                if self._conn is conn:
                    self._conn = None
            conn.close()
        return str(payload["message"]["content"])


def extract_document(chat: ChatModel, text: str) -> str:
    """Ask the extraction model for entities and triples in one passage.

    An API chat gets the larger output budget for this call only; the agent's answer calls
    keep the client default. Ollama already reads its budget from ``EXTRACT_OPTIONS``.
    """
    if isinstance(chat, OpenAICompatibleChat):
        return chat.complete(_EXTRACT_SYSTEM, text, max_tokens=EXTRACT_MAX_TOKENS)
    return chat.complete(_EXTRACT_SYSTEM, text)
