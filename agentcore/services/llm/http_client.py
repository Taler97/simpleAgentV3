"""纯 HTTP 实现的 LLM 客户端（兼容 OpenAI API 格式）。"""

import json
from typing import Dict, List

import requests


class HTTPLLM:
    """通过 HTTP 请求调用兼容 OpenAI API 格式的 LLM 服务。"""

    def __init__(
        self,
        api_url: str = "https://api.openai.com/v1/chat/completions",
        api_key: str = "",
        model: str = "gpt-4o",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self._api_url = api_url
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

    def generate(self, messages: List[Dict[str, str]]) -> str:
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        resp = requests.post(self._api_url, headers=self._headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"] or ""
