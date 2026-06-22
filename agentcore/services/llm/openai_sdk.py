"""OpenAI SDK 实现的 LLM 客户端。"""

from typing import Any, Dict, List, Optional


class OpenAILLM:
    """使用 OpenAI Python SDK 的 LLM 客户端。"""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str = "",
        base_url: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        from openai import OpenAI

        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._client = OpenAI(api_key=api_key or None, base_url=base_url or None)

    def generate(
        self,
        messages: List[Dict[str, str]],
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        kwargs = dict(
            model=self._model,
            messages=messages,
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        if response_format is not None:
            kwargs["response_format"] = response_format
        resp = self._client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""
