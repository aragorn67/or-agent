# config.py
import os

class Config:
    """Configuration management"""

    # Ollama Configuration
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    # Multi-LLM Pipeline Models
    # Defaults target locally pulled qwen3 weights. One model across stages so
    # Ollama keeps it warm across calls; override per-stage via env vars if needed.
    CLASSIFICATION_MODEL: str = os.getenv("CLASSIFICATION_MODEL", "qwen3:14b")
    EXTRACTION_MODEL:     str = os.getenv("EXTRACTION_MODEL",     "qwen3:14b")
    REASONING_MODEL:      str = os.getenv("REASONING_MODEL",      "qwen3:14b")

    # Legacy: backward compatibility
    OLLAMA_MODEL: str = CLASSIFICATION_MODEL

    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    @classmethod
    def get_llm_client(cls):
        """Factory method to get enhanced LLM client with specialists"""
        from llm.enhanced_client import EnhancedLLMClient
        return EnhancedLLMClient(cls.OLLAMA_HOST)

config = Config()