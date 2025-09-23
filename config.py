# config.py
import os

class Config:
    """Configuration management"""

    # Ollama Configuration
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2:7b")

    # API Configuration
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    @classmethod
    def get_llm_client(cls):
        """Factory method to get configured LLM client"""
        from llm.ollama_client import OllamaClient
        return OllamaClient(cls.OLLAMA_HOST, cls.OLLAMA_MODEL)

config = Config()