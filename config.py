# config.py
import os


class Config:
    """Configuration management for LLM backends and API server."""

    # ----- LLM backend selection -----
    # LLM_BACKEND ∈ {"ollama", "groq"}. Default ollama for local dev;
    # deployed instances set LLM_BACKEND=groq explicitly.
    LLM_BACKEND: str = os.getenv("LLM_BACKEND", "ollama").lower()

    # ----- Ollama -----
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    # One model across stages so Ollama keeps it warm across calls;
    # override per-stage via env vars if needed.
    CLASSIFICATION_MODEL: str = os.getenv("CLASSIFICATION_MODEL", "qwen3:14b")
    EXTRACTION_MODEL: str = os.getenv("EXTRACTION_MODEL", "qwen3:14b")
    REASONING_MODEL: str = os.getenv("REASONING_MODEL", "qwen3:14b")

    # Legacy: backward compatibility
    OLLAMA_MODEL: str = CLASSIFICATION_MODEL

    # ----- Groq -----
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_CLASSIFICATION_MODEL: str = os.getenv("GROQ_CLASSIFICATION_MODEL", "llama-3.3-70b-versatile")
    GROQ_EXTRACTION_MODEL: str = os.getenv("GROQ_EXTRACTION_MODEL", "llama-3.3-70b-versatile")
    GROQ_REASONING_MODEL: str = os.getenv("GROQ_REASONING_MODEL", "llama-3.3-70b-versatile")

    # ----- API server -----
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    @classmethod
    def get_llm_client(cls):
        """Factory: returns an EnhancedLLMClient bound to the selected backend."""
        from llm.enhanced_client import EnhancedLLMClient
        return EnhancedLLMClient()


config = Config()
