"""Claude API Generation Session — maintains full conversation history."""

import os
import anthropic

MODEL = "claude-sonnet-4-6"


class Session:
    def __init__(self, system_prompt: str):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Export it before running repdefgen."
            )
        self._client = anthropic.Anthropic(api_key=api_key)
        self._system = system_prompt
        self._messages: list[dict] = []

    def send(self, user_msg: str, max_tokens: int = 4096) -> str:
        self._messages.append({"role": "user", "content": user_msg})
        response = self._client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=self._system,
            messages=self._messages,
        )
        reply = response.content[0].text
        self._messages.append({"role": "assistant", "content": reply})
        return reply

    @property
    def history(self) -> list[dict]:
        return list(self._messages)
