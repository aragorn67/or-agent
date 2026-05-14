# llm/groq_client.py
"""
Groq LLM client. Groq exposes an OpenAI-compatible Chat Completions API at
https://api.groq.com/openai/v1/chat/completions. This client subclasses
OllamaClient and only overrides _chat — every higher-level method
(classify_problem, extract_parameters, explain_solution, detect_follow_up_intent,
extract_modification_parameters) is built on top of _chat in the base class,
so they work unchanged.
"""
import json
import os
import requests

from .ollama_client import OllamaClient, _strip_thinking, _extract_json_block


class GroqClient(OllamaClient):
    """Groq-hosted LLM, OpenAI-compatible Chat Completions API."""

    BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(self, model: str, api_key: str = None):
        self.model = model
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY not set. Export GROQ_API_KEY or set LLM_BACKEND=ollama."
            )
        # `host` kept for parity with OllamaClient's attribute surface.
        self.host = self.BASE_URL

    def _chat(self, system: str, user: str, json_mode: bool = False) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system.strip()},
                {"role": "user", "content": user.strip()},
            ],
            "temperature": 0,
            "top_p": 0.9,
            "stream": False,
            # Groq's default output cap is low; without this the JSON gets
            # truncated mid-object and json_mode then 400s on validation.
            "max_tokens": 4096,
        }
        # Groq's OpenAI-compat endpoint supports JSON-mode for capable models
        # (Llama 3.x). It returns 400 if the prompt doesn't mention "JSON",
        # but every json_mode call site in this codebase already does.
        # Unlike Ollama's format=json (which breaks qwen3/deepseek-r1 reasoning
        # models — see feedback_qwen3_json_mode), Groq's response_format works
        # fine with the Llama models we use here.
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            resp = requests.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()

            if "choices" not in data or not data["choices"]:
                raise ValueError(f"Invalid response from Groq: {data}")

            content = data["choices"][0].get("message", {}).get("content", "")
            content = _strip_thinking(content)
            if json_mode:
                content = _extract_json_block(content)
            return content

        except requests.exceptions.Timeout:
            raise requests.exceptions.Timeout(
                f"Groq request timed out after 60s (model={self.model})."
            )
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if hasattr(e, "response") else "unknown"
            body = ""
            try:
                body = e.response.text[:500] if hasattr(e, "response") else ""
            except Exception:
                pass
            if status == 401:
                raise requests.exceptions.HTTPError(
                    "Groq returned 401. GROQ_API_KEY is missing or invalid."
                )
            if status == 429:
                raise requests.exceptions.HTTPError(
                    "Groq rate-limited the request (429). Slow down or upgrade tier."
                )
            raise requests.exceptions.HTTPError(f"Groq HTTP {status}: {body or e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Could not parse Groq response: {e}")
