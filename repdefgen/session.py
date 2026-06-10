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

    def send_structured(
        self,
        user_msg: str,
        tool_name: str,
        tool_schema: dict,
        max_tokens: int = 4096,
    ) -> dict:
        """Send a message with a forced tool call; returns the validated tool input.

        The assistant turn is stored in history as plain text (a JSON dump of the
        tool input) so subsequent send() calls see the current state without
        needing tool_result bookkeeping.
        """
        import json

        self._messages.append({"role": "user", "content": user_msg})
        response = self._client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=self._system,
            messages=self._messages,
            tools=[{
                "name": tool_name,
                "description": tool_schema.get("description", ""),
                "input_schema": tool_schema["input_schema"],
            }],
            tool_choice={"type": "tool", "name": tool_name},
        )
        tool_input = next(
            (block.input for block in response.content if block.type == "tool_use"),
            None,
        )
        if tool_input is None:
            raise RuntimeError("Model did not return the expected tool call")
        self._messages.append({
            "role": "assistant",
            "content": json.dumps(tool_input, indent=2),
        })
        return tool_input

    @property
    def history(self) -> list[dict]:
        return list(self._messages)
