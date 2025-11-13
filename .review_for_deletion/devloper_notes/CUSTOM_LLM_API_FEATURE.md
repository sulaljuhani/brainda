# Custom LLM API Integration Feature

**Status**: 🔴 **Not Implemented** (only placeholder exists)
**Priority**: High
**Complexity**: Medium
**Estimated Effort**: 2-3 days

---

## Current State

### What Exists
- **LLM Adapter Interface**: `app/api/adapters/llm_adapter.py` defines the basic pattern
- **RAG Integration**: `app/api/services/rag_service.py` already uses LLM adapter for question answering
- **Environment Variables**: `.env.example` mentions `LLM_BACKEND` and `OLLAMA_URL`, but not implemented
- **Dummy Implementation**: `DummyLLMAdapter` returns placeholder text instead of real LLM responses

### What's Missing
- ❌ No actual LLM provider implementations (OpenAI, Anthropic, Ollama, etc.)
- ❌ No custom API endpoint support
- ❌ No adapter factory/registry pattern
- ❌ No streaming support for responses
- ❌ No error handling and retry logic
- ❌ No token counting or rate limiting
- ❌ No model selection per request
- ❌ No prompt caching or optimization

---

## Feature Requirements

### 1. Core LLM Adapter Interface

The adapter should support:

```python
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, AsyncGenerator

class BaseLLMAdapter(ABC):
    """Base interface for all LLM adapters."""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> str:
        """Generate a completion for the given prompt."""
        pass

    @abstractmethod
    async def complete_stream(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream a completion for the given prompt."""
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Estimate token count for the given text."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        pass
```

### 2. Adapter Implementations Needed

#### A. OpenAI Adapter
```python
class OpenAIAdapter(BaseLLMAdapter):
    """
    Environment Variables:
    - LLM_BACKEND=openai
    - OPENAI_API_KEY=sk-...
    - OPENAI_MODEL=gpt-4-turbo (optional, default: gpt-3.5-turbo)
    - OPENAI_BASE_URL=https://api.openai.com/v1 (optional)
    """
    pass
```

**Dependencies**: `openai>=1.0.0`

#### B. Anthropic Adapter
```python
class AnthropicAdapter(BaseLLMAdapter):
    """
    Environment Variables:
    - LLM_BACKEND=anthropic
    - ANTHROPIC_API_KEY=sk-ant-...
    - ANTHROPIC_MODEL=claude-3-5-sonnet-20241022 (optional)
    """
    pass
```

**Dependencies**: `anthropic>=0.18.0`

#### C. Ollama Adapter
```python
class OllamaAdapter(BaseLLMAdapter):
    """
    Environment Variables:
    - LLM_BACKEND=ollama
    - OLLAMA_URL=http://ollama:11434
    - OLLAMA_MODEL=llama3 (optional, default: llama3)
    """
    pass
```

**Dependencies**: `httpx` (already in project)

#### D. Custom API Adapter
```python
class CustomAPIAdapter(BaseLLMAdapter):
    """
    Supports any OpenAI-compatible API endpoint.

    Environment Variables:
    - LLM_BACKEND=custom
    - CUSTOM_LLM_URL=https://your-api.com/v1/chat/completions
    - CUSTOM_LLM_API_KEY=your-key (optional)
    - CUSTOM_LLM_MODEL=your-model-name
    - CUSTOM_LLM_HEADERS={"X-Custom": "value"} (optional, JSON)
    """
    pass
```

**API Format**: Should accept OpenAI-compatible requests:
```json
POST /v1/chat/completions
{
  "model": "your-model",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ],
  "temperature": 0.7,
  "max_tokens": 1000
}
```

### 3. Adapter Factory Pattern

```python
# app/api/adapters/llm_adapter.py

def get_llm_adapter() -> BaseLLMAdapter:
    """
    Factory function to create the appropriate LLM adapter
    based on environment configuration.
    """
    backend = os.getenv("LLM_BACKEND", "dummy").lower()

    adapters = {
        "openai": OpenAIAdapter,
        "anthropic": AnthropicAdapter,
        "ollama": OllamaAdapter,
        "custom": CustomAPIAdapter,
        "dummy": DummyLLMAdapter,
    }

    adapter_class = adapters.get(backend)
    if not adapter_class:
        logger.warning(f"Unknown LLM backend: {backend}, using dummy")
        return DummyLLMAdapter()

    try:
        return adapter_class()
    except Exception as e:
        logger.error(f"Failed to initialize {backend} adapter: {e}")
        return DummyLLMAdapter()
```

### 4. Enhanced Features

#### A. Retry Logic with Exponential Backoff
```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

class BaseRetryAdapter(BaseLLMAdapter):
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, TimeoutError))
    )
    async def complete(self, prompt: str, **kwargs) -> str:
        return await self._complete_impl(prompt, **kwargs)
```

#### B. Rate Limiting
```python
import asyncio
from datetime import datetime, timedelta

class RateLimitedAdapter(BaseLLMAdapter):
    def __init__(self, base_adapter: BaseLLMAdapter, requests_per_minute: int):
        self.base_adapter = base_adapter
        self.requests_per_minute = requests_per_minute
        self.request_times = []

    async def complete(self, prompt: str, **kwargs) -> str:
        await self._wait_if_rate_limited()
        self.request_times.append(datetime.now())
        return await self.base_adapter.complete(prompt, **kwargs)

    async def _wait_if_rate_limited(self):
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)
        self.request_times = [t for t in self.request_times if t > one_minute_ago]

        if len(self.request_times) >= self.requests_per_minute:
            wait_time = (self.request_times[0] - one_minute_ago).total_seconds()
            await asyncio.sleep(wait_time)
```

#### C. Prompt Caching
```python
from functools import lru_cache
import hashlib

class CachedAdapter(BaseLLMAdapter):
    def __init__(self, base_adapter: BaseLLMAdapter, cache_size: int = 100):
        self.base_adapter = base_adapter
        self.cache = {}
        self.cache_size = cache_size

    async def complete(self, prompt: str, **kwargs) -> str:
        cache_key = self._make_cache_key(prompt, kwargs)

        if cache_key in self.cache:
            logger.info("llm_cache_hit", cache_key=cache_key[:16])
            return self.cache[cache_key]

        response = await self.base_adapter.complete(prompt, **kwargs)

        if len(self.cache) >= self.cache_size:
            # Remove oldest entry (FIFO)
            self.cache.pop(next(iter(self.cache)))

        self.cache[cache_key] = response
        return response

    def _make_cache_key(self, prompt: str, kwargs: dict) -> str:
        data = f"{prompt}:{sorted(kwargs.items())}"
        return hashlib.sha256(data.encode()).hexdigest()
```

### 5. Environment Variable Configuration

Update `.env.example`:

```bash
# LLM Configuration
# Choose backend: openai, anthropic, ollama, custom, dummy
LLM_BACKEND=openai

# OpenAI Configuration (if LLM_BACKEND=openai)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-3.5-turbo
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MAX_TOKENS=2000
OPENAI_TEMPERATURE=0.7

# Anthropic Configuration (if LLM_BACKEND=anthropic)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-sonnet-20241022
ANTHROPIC_MAX_TOKENS=4096

# Ollama Configuration (if LLM_BACKEND=ollama)
OLLAMA_URL=http://ollama:11434
OLLAMA_MODEL=llama3

# Custom API Configuration (if LLM_BACKEND=custom)
CUSTOM_LLM_URL=https://your-api.com/v1/chat/completions
CUSTOM_LLM_API_KEY=your-key
CUSTOM_LLM_MODEL=your-model-name
CUSTOM_LLM_HEADERS={}  # Optional JSON object
CUSTOM_LLM_TIMEOUT=60
CUSTOM_LLM_MAX_TOKENS=2000

# LLM Features
LLM_ENABLE_CACHING=true
LLM_CACHE_SIZE=100
LLM_ENABLE_RETRY=true
LLM_MAX_RETRIES=3
LLM_RATE_LIMIT_RPM=60  # Requests per minute
```

### 6. Metrics and Monitoring

Add Prometheus metrics for LLM operations:

```python
# app/api/metrics.py

from prometheus_client import Counter, Histogram, Gauge

llm_requests_total = Counter(
    "llm_requests_total",
    "Total LLM API requests",
    ["backend", "model", "status"]
)

llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration",
    ["backend", "model"]
)

llm_tokens_used_total = Counter(
    "llm_tokens_used_total",
    "Total tokens consumed",
    ["backend", "model", "type"]  # type: prompt/completion
)

llm_cache_hits_total = Counter(
    "llm_cache_hits_total",
    "LLM cache hits",
    ["backend"]
)

llm_errors_total = Counter(
    "llm_errors_total",
    "LLM API errors",
    ["backend", "error_type"]
)
```

---

## Implementation Plan

### Phase 1: Core Infrastructure (Day 1)
1. ✅ Define `BaseLLMAdapter` interface
2. ✅ Update factory pattern in `get_llm_adapter()`
3. ✅ Add comprehensive error handling
4. ✅ Add basic logging and metrics
5. ✅ Update `.env.example` with all configuration options

### Phase 2: Provider Implementations (Day 2)
1. ✅ Implement `OpenAIAdapter` with streaming support
2. ✅ Implement `AnthropicAdapter` with streaming support
3. ✅ Implement `OllamaAdapter`
4. ✅ Implement `CustomAPIAdapter` for generic endpoints
5. ✅ Add token counting for each provider
6. ✅ Add unit tests for each adapter

### Phase 3: Enhanced Features (Day 3)
1. ✅ Add retry logic with exponential backoff
2. ✅ Implement prompt caching
3. ✅ Add rate limiting
4. ✅ Add streaming endpoint to API
5. ✅ Update RAG service to support streaming
6. ✅ Add integration tests

### Phase 4: Documentation (Day 3)
1. ✅ Update README.md with LLM configuration examples
2. ✅ Add API documentation for streaming endpoint
3. ✅ Create troubleshooting guide
4. ✅ Add example configurations for each provider

---

## Testing Requirements

### Unit Tests
```python
# tests/test_llm_adapters.py

import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_openai_adapter_complete():
    with patch("openai.AsyncOpenAI") as mock_client:
        mock_client.return_value.chat.completions.create = AsyncMock(
            return_value=MockCompletion(content="Test response")
        )

        adapter = OpenAIAdapter()
        response = await adapter.complete("Test prompt")

        assert response == "Test response"
        assert adapter.count_tokens("Test prompt") > 0

@pytest.mark.asyncio
async def test_custom_api_adapter():
    with patch("httpx.AsyncClient.post") as mock_post:
        mock_post.return_value.json.return_value = {
            "choices": [{"message": {"content": "Custom response"}}]
        }

        adapter = CustomAPIAdapter()
        response = await adapter.complete("Test prompt")

        assert response == "Custom response"
```

### Integration Tests
```python
# tests/integration/test_rag_with_llm.py

@pytest.mark.asyncio
async def test_rag_with_real_llm():
    """Test RAG service with actual LLM (requires API key)."""
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("No OpenAI API key available")

    vector_service = VectorService()
    llm_adapter = get_llm_adapter()
    rag_service = RAGService(vector_service, llm_adapter)

    result = await rag_service.answer_question(
        query="What is the capital of France?",
        user_id=test_user_id
    )

    assert "Paris" in result["answer"]
    assert len(result["citations"]) > 0
```

---

## Security Considerations

1. **API Key Management**
   - ✅ Never commit API keys to git
   - ✅ Use environment variables only
   - ✅ Validate keys on startup
   - ✅ Rotate keys regularly
   - ✅ Use separate keys for dev/staging/prod

2. **Input Sanitization**
   - ✅ Validate and sanitize all prompts
   - ✅ Limit prompt length (e.g., max 10,000 chars)
   - ✅ Filter sensitive information from logs
   - ✅ Prevent prompt injection attacks

3. **Rate Limiting**
   - ✅ Implement per-user rate limits
   - ✅ Track token usage per user
   - ✅ Set spending limits
   - ✅ Alert on unusual usage patterns

4. **Error Handling**
   - ✅ Never expose API keys in error messages
   - ✅ Log errors securely
   - ✅ Fail gracefully with user-friendly messages
   - ✅ Implement circuit breaker pattern

---

## Cost Optimization

1. **Prompt Engineering**
   - Use concise, efficient prompts
   - Limit context to relevant information only
   - Use system prompts to reduce repetition

2. **Caching**
   - Cache identical or similar queries
   - Use semantic caching for near-duplicates
   - Cache for at least 1 hour for common queries

3. **Model Selection**
   - Use cheaper models for simple tasks
   - Reserve expensive models for complex reasoning
   - Allow per-endpoint model configuration

4. **Token Management**
   - Track token usage per user
   - Implement token budgets
   - Alert when approaching limits
   - Truncate long contexts intelligently

---

## Example Usage

### Basic Configuration
```bash
# .env
LLM_BACKEND=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-3.5-turbo
```

### Custom API Configuration
```bash
# .env
LLM_BACKEND=custom
CUSTOM_LLM_URL=https://api.your-llm.com/v1/chat/completions
CUSTOM_LLM_API_KEY=your-secret-key
CUSTOM_LLM_MODEL=your-model-v1
CUSTOM_LLM_HEADERS={"X-Organization": "your-org"}
```

### Testing with curl
```bash
# Test RAG endpoint
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What did I write about machine learning?"
  }'
```

---

## Dependencies to Add

```toml
# pyproject.toml or requirements.txt

openai>=1.12.0              # OpenAI API
anthropic>=0.18.0           # Anthropic API
tiktoken>=0.5.2             # Token counting for OpenAI
tenacity>=8.2.3             # Retry logic
httpx>=0.26.0               # Already in project
```

---

## Migration Path

For users currently on the dummy adapter:

1. **Backup Data**: Ensure all data is backed up
2. **Choose Provider**: Select LLM backend (OpenAI, Anthropic, Ollama, Custom)
3. **Update Environment**: Add required environment variables
4. **Test Connection**: Use health check endpoint
5. **Gradual Rollout**: Test with sample queries first
6. **Monitor Metrics**: Watch token usage and costs
7. **Optimize**: Tune prompts and caching based on usage

---

## Questions to Answer

Before implementing, clarify:

1. **Budget**: What's the monthly budget for LLM API costs?
2. **Providers**: Which LLM providers should be prioritized?
3. **Streaming**: Is streaming required for the UI?
4. **Fallbacks**: Should the system fall back to dummy if API fails?
5. **Multi-Model**: Should different features use different models?
6. **Privacy**: Are there data residency or privacy requirements?
7. **Caching**: Is aggressive caching acceptable for your use case?

---

## References

- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [Anthropic API Documentation](https://docs.anthropic.com/claude/reference/getting-started-with-the-api)
- [Ollama API Documentation](https://github.com/ollama/ollama/blob/main/docs/api.md)
- [LangChain LLM Integration Patterns](https://python.langchain.com/docs/modules/model_io/llms/)

---

## Current Workaround

Until this feature is implemented, the RAG endpoint will return:
```json
{
  "answer": "Retrieval results are ready, but no LLM adapter is configured to draft an answer.",
  "citations": [...],
  "sources_used": 5
}
```

Users can see the retrieved context but won't get LLM-generated answers.
