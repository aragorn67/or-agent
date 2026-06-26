# config.py
import os


class Config:
    """Configuration management for the Ollama-backed LLM pipeline + API server."""

    # ----- Ollama (the only supported backend) -----
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    # One model across stages so Ollama keeps it warm across calls;
    # override per-stage via env vars if needed.
    # qwen3:8b default: model-sweep (2026-05-17, n=3, both domains) showed
    # it bit-identical to qwen3:14b on every accuracy metric at ~2x speed.
    CLASSIFICATION_MODEL: str = os.getenv("CLASSIFICATION_MODEL", "qwen3:8b")
    EXTRACTION_MODEL: str = os.getenv("EXTRACTION_MODEL", "qwen3:8b")
    REASONING_MODEL: str = os.getenv("REASONING_MODEL", "qwen3:8b")

    # Legacy: backward compatibility
    OLLAMA_MODEL: str = CLASSIFICATION_MODEL

    # ----- API server -----
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    @classmethod
    def get_llm_client(cls):
        """Factory: returns an EnhancedLLMClient (Ollama-backed)."""
        from llm.enhanced_client import EnhancedLLMClient
        return EnhancedLLMClient()


config = Config()
