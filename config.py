# config.py
import os

class Config:
    """Configuration management"""

    # Ollama Configuration
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    # Multi-LLM Pipeline Models
    # Stage A: Intent Detection & Problem Classification (fast, accurate)
    # Qwen2.5 3B Instruct - extremely fast, high accuracy, cheap to run, minimal hallucination
    CLASSIFICATION_MODEL: str = os.getenv("CLASSIFICATION_MODEL", "qwen2.5:3b-instruct")

    # Stage B: Parameter Extraction (structured JSON, mathematical understanding)
    # Qwen2.5-Coder 7B - best small model for accurate JSON/schema outputs, strong at extracting variables
    EXTRACTION_MODEL: str = os.getenv("EXTRACTION_MODEL", "qwen2.5-coder:7b")

    # Stage E: Reasoning, Explanations, What-If Analysis (deep reasoning)
    REASONING_MODEL: str = os.getenv("REASONING_MODEL", "deepseek-r1:latest")

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