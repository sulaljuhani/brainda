"""Adapter implementations for connecting to different LLM providers."""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
import structlog
from tenacity import AsyncRetrying, RetryError, retry_if_exception_type, stop_after_attempt, wait_exponential
from common.circuit_breaker import get_circuit_breaker, CircuitBreakerOpen

logger = structlog.get_logger()

# Timeout configurations (in seconds)
DEFAULT_HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "30"))
LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))

try:  # pragma: no cover - optional dependency loaded at runtime
    import tiktoken
except Exception:  # pragma: no cover - defensive guard if library missing
    tiktoken = None  # type: ignore


class LLMAdapterError(RuntimeError):
    """Raised when an adapter cannot fulfil a request."""


class BaseLLMAdapter(ABC):
    """Base interface for all LLM adapters."""

    retry_attempts: int = 3

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """Generate a completion for the given prompt."""

    @abstractmethod
    async def complete_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream a completion for the given prompt."""

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Estimate token count for the given text."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""

    async def complete_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """
        Generate a completion with tool calling support.
        Returns a dict with:
        - 'type': 'text' or 'tool_calls'
        - 'content': text content (if type='text')
        - 'tool_calls': list of tool calls (if type='tool_calls')
        """
        # Default implementation: fall back to simple completion
        content = await self.complete(prompt, temperature, max_tokens, system_prompt, **kwargs)
        return {"type": "text", "content": content}

    async def _retry(self, func, *args: Any, **kwargs: Any):
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                return await func(*args, **kwargs)
        raise LLMAdapterError("Failed to execute LLM request")


def _count_tokens_with_tiktoken(model: str, text: str) -> int:
    if not tiktoken:
        return max(1, len(text) // 4)
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


class DummyLLMAdapter(BaseLLMAdapter):
    """Fallback adapter that simply echoes a placeholder response."""

    def __init__(self):
        self._model = os.getenv("LLM_MODEL", "placeholder-model")

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        logger.warning(
            "llm_adapter_placeholder_used",
            model=self._model,
        )
        return "Retrieval results are ready, but no LLM adapter is configured to draft an answer."

    async def complete_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        yield await self.complete(prompt, temperature, max_tokens, system_prompt, **kwargs)

    def count_tokens(self, text: str) -> int:
        return _count_tokens_with_tiktoken(self._model, text)

    @property
    def model_name(self) -> str:
        return self._model


class OpenAIAdapter(BaseLLMAdapter):
    """Adapter for the OpenAI Chat Completions API."""

    def __init__(self):
        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError as exc:  # pragma: no cover - import guard
            raise LLMAdapterError("openai package is required for OpenAI backend") from exc

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMAdapterError("OPENAI_API_KEY is required for OpenAI backend")

        base_url = os.getenv("OPENAI_BASE_URL")
        self._model = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=LLM_TIMEOUT,
        )
        self._circuit_breaker = get_circuit_breaker("openai")

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async def _call():
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return response

        try:
            # Wrap in circuit breaker to prevent runaway costs
            response = await self._circuit_breaker.call(self._retry, _call)
        except CircuitBreakerOpen as exc:
            logger.error("openai_circuit_breaker_open", error=str(exc))
            raise LLMAdapterError(str(exc)) from exc
        except RetryError as exc:  # pragma: no cover - defensive
            raise LLMAdapterError("OpenAI completion failed") from exc
        message = response.choices[0].message.content or ""
        return message.strip()

    async def complete_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                stream = await self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                    **kwargs,
                )
                async for chunk in stream:  # type: ignore[attr-defined]
                    delta = chunk.choices[0].delta.content if chunk.choices else None
                    if delta:
                        yield delta
                return

    def count_tokens(self, text: str) -> int:
        return _count_tokens_with_tiktoken(self._model, text)

    @property
    def model_name(self) -> str:
        return self._model

    async def complete_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Generate a completion with tool calling support using OpenAI's native tools."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        async def _call():
            return await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=tools,
                tool_choice="auto",
                **kwargs,
            )

        try:
            response = await self._retry(_call)
        except RetryError as exc:
            raise LLMAdapterError("OpenAI completion with tools failed") from exc

        message = response.choices[0].message

        # Check if the model wants to call tools
        if message.tool_calls:
            tool_calls = []
            for tool_call in message.tool_calls:
                tool_calls.append({
                    "id": tool_call.id,
                    "name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments),
                })
            return {"type": "tool_calls", "tool_calls": tool_calls}

        # Otherwise return text response
        content = message.content or ""
        return {"type": "text", "content": content.strip()}


class AnthropicAdapter(BaseLLMAdapter):
    """Adapter for the Anthropic Messages API."""

    def __init__(self):
        try:
            from anthropic import AsyncAnthropic  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise LLMAdapterError("anthropic package is required for Anthropic backend") from exc

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMAdapterError("ANTHROPIC_API_KEY is required for Anthropic backend")

        self._model = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
        self._client = AsyncAnthropic(api_key=api_key)
        self._default_max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS", "1024"))

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        max_output_tokens = max_tokens or self._default_max_tokens

        async def _call():
            return await self._client.messages.create(
                model=self._model,
                temperature=temperature,
                max_tokens=max_output_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )

        try:
            response = await self._retry(_call)
        except RetryError as exc:  # pragma: no cover
            raise LLMAdapterError("Anthropic completion failed") from exc

        parts = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return "".join(parts).strip()

    async def complete_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        max_output_tokens = max_tokens or self._default_max_tokens

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(Exception),
            reraise=True,
        ):
            with attempt:
                stream = await self._client.messages.create(
                    model=self._model,
                    temperature=temperature,
                    max_tokens=max_output_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                    stream=True,
                    **kwargs,
                )
                async for event in stream:  # type: ignore[attr-defined]
                    delta = getattr(event, "delta", None)
                    if delta and getattr(delta, "text", None):
                        yield delta.text
                return

    def count_tokens(self, text: str) -> int:
        return _count_tokens_with_tiktoken(self._model, text)

    @property
    def model_name(self) -> str:
        return self._model

    async def complete_with_tools(
        self,
        prompt: str,
        tools: list[dict],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> dict:
        """Generate a completion with tool calling support using Anthropic's native tools."""
        max_output_tokens = max_tokens or self._default_max_tokens

        # Convert OpenAI-style tools to Anthropic format
        anthropic_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                anthropic_tools.append({
                    "name": func.get("name"),
                    "description": func.get("description"),
                    "input_schema": func.get("parameters", {}),
                })

        async def _call():
            return await self._client.messages.create(
                model=self._model,
                temperature=temperature,
                max_tokens=max_output_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": prompt}],
                tools=anthropic_tools,
                **kwargs,
            )

        try:
            response = await self._retry(_call)
        except RetryError as exc:
            raise LLMAdapterError("Anthropic completion with tools failed") from exc

        # Check if the model wants to call tools
        tool_uses = [block for block in response.content if getattr(block, "type", None) == "tool_use"]
        if tool_uses:
            tool_calls = []
            for tool_use in tool_uses:
                tool_calls.append({
                    "id": tool_use.id,
                    "name": tool_use.name,
                    "arguments": tool_use.input,
                })
            return {"type": "tool_calls", "tool_calls": tool_calls}

        # Otherwise return text response
        parts = []
        for block in response.content:
            text = getattr(block, "text", None)
            if text:
                parts.append(text)
        return {"type": "text", "content": "".join(parts).strip()}


class OllamaAdapter(BaseLLMAdapter):
    """Adapter for local or remote Ollama deployments."""

    def __init__(self):
        base_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        self._model = os.getenv("OLLAMA_MODEL", "llama3")
        self._client = httpx.AsyncClient(base_url=base_url, timeout=30.0)

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if system_prompt:
            payload["system"] = system_prompt
        payload.update(kwargs)

        async def _call():
            response = await self._client.post("/api/generate", json=payload)
            response.raise_for_status()
            return response.json()

        try:
            data = await self._retry(_call)
        except RetryError as exc:  # pragma: no cover
            raise LLMAdapterError("Ollama completion failed") from exc

        return data.get("response", "").strip()

    async def complete_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        payload: Dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "stream": True,
            "options": {"temperature": temperature},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if system_prompt:
            payload["system"] = system_prompt
        payload.update(kwargs)

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        ):
            with attempt:
                async with self._client.stream("POST", "/api/generate", json=payload) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        chunk = data.get("response")
                        if chunk:
                            yield chunk
                return

    def count_tokens(self, text: str) -> int:
        return _count_tokens_with_tiktoken(self._model, text)

    @property
    def model_name(self) -> str:
        return self._model


class CustomLLMAdapter(BaseLLMAdapter):
    """Adapter for arbitrary OpenAI-compatible chat completion APIs."""

    def __init__(self):
        url = os.getenv("CUSTOM_LLM_URL")
        if not url:
            raise LLMAdapterError("CUSTOM_LLM_URL is required for custom backend")

        self._url = url
        self._model = os.getenv("CUSTOM_LLM_MODEL", "custom-model")
        headers_env = os.getenv("CUSTOM_LLM_HEADERS", "{}")
        try:
            extra_headers = json.loads(headers_env)
        except json.JSONDecodeError as exc:
            raise LLMAdapterError("CUSTOM_LLM_HEADERS must be valid JSON") from exc

        api_key = os.getenv("CUSTOM_LLM_API_KEY")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        headers.update(extra_headers)

        self._headers = headers
        self._client = httpx.AsyncClient(timeout=30.0)

    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": self._build_messages(prompt, system_prompt),
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        async def _call():
            response = await self._client.post(self._url, headers=self._headers, json=payload)
            response.raise_for_status()
            return response.json()

        try:
            data = await self._retry(_call)
        except RetryError as exc:  # pragma: no cover
            raise LLMAdapterError("Custom LLM completion failed") from exc

        return self._extract_message_content(data)

    async def complete_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        payload: Dict[str, Any] = {
            "model": self._model,
            "messages": self._build_messages(prompt, system_prompt),
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        payload.update(kwargs)

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        ):
            with attempt:
                async with self._client.stream(
                    "POST", self._url, headers=self._headers, json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        payload_str = line.split("data:", 1)[1].strip()
                        if payload_str in ("", "[DONE]"):
                            continue
                        try:
                            data = json.loads(payload_str)
                        except json.JSONDecodeError:
                            continue
                        delta = data.get("choices", [{}])[0].get("delta", {}).get("content")
                        if delta:
                            yield delta
                return

    def count_tokens(self, text: str) -> int:
        return _count_tokens_with_tiktoken(self._model, text)

    @property
    def model_name(self) -> str:
        return self._model

    def _build_messages(self, prompt: str, system_prompt: Optional[str]):
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages

    def _extract_message_content(self, data: Dict[str, Any]) -> str:
        choices = data.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content)
        return str(content).strip()


@lru_cache(maxsize=4)
def _build_adapter(backend: str) -> BaseLLMAdapter:
    logger.info("llm_adapter_selected", backend=backend)

    if backend == "openai":
        return OpenAIAdapter()
    if backend == "anthropic":
        return AnthropicAdapter()
    if backend == "ollama":
        return OllamaAdapter()
    if backend == "custom":
        return CustomLLMAdapter()
    if backend not in {"dummy", "none"}:
        logger.warning("llm_adapter_unknown_backend", backend=backend)
    return DummyLLMAdapter()


def get_llm_adapter() -> BaseLLMAdapter:
    """Return a cached adapter instance for the configured backend."""

    backend = os.getenv("LLM_BACKEND", "dummy").lower()
    return _build_adapter(backend)


def build_adapter_from_config(provider: str, model_name: str, config: Dict[str, Any], temperature: float = 0.7, max_tokens: Optional[int] = None) -> BaseLLMAdapter:
    """Build an LLM adapter from configuration dictionary.

    This is used for dynamically creating adapters from database-stored model configurations.

    Args:
        provider: The provider type (openai, anthropic, ollama, custom)
        model_name: The model identifier
        config: Configuration dictionary with provider-specific settings
        temperature: Default temperature for requests
        max_tokens: Default max tokens for requests

    Returns:
        BaseLLMAdapter instance configured for the model
    """
    logger.info("building_adapter_from_config", provider=provider, model_name=model_name)

    if provider == "openai":
        return _build_openai_adapter_from_config(model_name, config, temperature, max_tokens)
    elif provider == "anthropic":
        return _build_anthropic_adapter_from_config(model_name, config, temperature, max_tokens)
    elif provider == "ollama":
        return _build_ollama_adapter_from_config(model_name, config, temperature, max_tokens)
    elif provider == "custom":
        return _build_custom_adapter_from_config(model_name, config, temperature, max_tokens)
    else:
        logger.warning("unknown_provider_for_dynamic_adapter", provider=provider)
        return DummyLLMAdapter()


def _build_openai_adapter_from_config(model_name: str, config: Dict[str, Any], temperature: float, max_tokens: Optional[int]) -> BaseLLMAdapter:
    """Build OpenAI adapter from config."""
    try:
        from openai import AsyncOpenAI
    except ImportError as exc:
        raise LLMAdapterError("openai package is required for OpenAI backend") from exc

    api_key = config.get("api_key")
    if not api_key:
        raise LLMAdapterError("api_key is required in config for OpenAI adapter")

    base_url = config.get("base_url")

    # Create a custom adapter instance
    adapter = OpenAIAdapter.__new__(OpenAIAdapter)
    adapter._model = model_name
    adapter._client = AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=LLM_TIMEOUT,
    )
    adapter._circuit_breaker = get_circuit_breaker("openai")
    adapter.retry_attempts = 3

    return adapter


def _build_anthropic_adapter_from_config(model_name: str, config: Dict[str, Any], temperature: float, max_tokens: Optional[int]) -> BaseLLMAdapter:
    """Build Anthropic adapter from config."""
    try:
        from anthropic import AsyncAnthropic
    except ImportError as exc:
        raise LLMAdapterError("anthropic package is required for Anthropic backend") from exc

    api_key = config.get("api_key")
    if not api_key:
        raise LLMAdapterError("api_key is required in config for Anthropic adapter")

    # Create a custom adapter instance
    adapter = AnthropicAdapter.__new__(AnthropicAdapter)
    adapter._model = model_name
    adapter._client = AsyncAnthropic(api_key=api_key)
    adapter._default_max_tokens = max_tokens or int(os.getenv("ANTHROPIC_MAX_TOKENS", "1024"))
    adapter.retry_attempts = 3

    return adapter


def _build_ollama_adapter_from_config(model_name: str, config: Dict[str, Any], temperature: float, max_tokens: Optional[int]) -> BaseLLMAdapter:
    """Build Ollama adapter from config."""
    base_url = config.get("base_url", "http://ollama:11434")

    # Create a custom adapter instance
    adapter = OllamaAdapter.__new__(OllamaAdapter)
    adapter._model = model_name
    adapter._client = httpx.AsyncClient(base_url=base_url, timeout=30.0)
    adapter.retry_attempts = 3

    return adapter


def _build_custom_adapter_from_config(model_name: str, config: Dict[str, Any], temperature: float, max_tokens: Optional[int]) -> BaseLLMAdapter:
    """Build custom adapter from config."""
    url = config.get("url") or config.get("base_url")
    if not url:
        raise LLMAdapterError("url or base_url is required in config for custom adapter")

    api_key = config.get("api_key")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    # Merge any additional headers from config
    extra_headers = config.get("headers", {})
    headers.update(extra_headers)

    # Create a custom adapter instance
    adapter = CustomLLMAdapter.__new__(CustomLLMAdapter)
    adapter._url = url
    adapter._model = model_name
    adapter._headers = headers
    adapter._client = httpx.AsyncClient(timeout=30.0)
    adapter.retry_attempts = 3

    return adapter

