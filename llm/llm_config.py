# llm/llm_config.py
"""
Central configuration for LLM behavior across the entire system.

This file defines:
- Model defaults (model, temperature, max_tokens, json_mode, etc.)
- Per-task overrides (classification, extraction, explanation, follow-up)
- Stylistic/behavioral switches (concise answers, chain-of-thought, markdown formatting, etc.)

All LLM functions should use parameters from this configuration.

Usage Examples:
    # Use default configuration
    from llm.llm_config import config

    # Override model
    config.override_model_config(model="llama3:8b", temperature=0.2)

    # Override specific task
    config.override_task_config("explanation", temperature=0.3, max_tokens=1024)

    # Change behavior
    config.override_behavior(concise_mode=False, use_emojis=True)

    # Save/load configuration
    config.save_to_file("my_config.json")
    new_config = LLMConfig.load_from_file("my_config.json")
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class LLMModelConfig:
    """
    Configuration for the base LLM model.

    These settings define the model itself and its core parameters.
    Task-specific overrides can adjust these values per operation.

    Attributes:
        model: Model name/identifier (e.g., "qwen2:7b", "llama3:8b")
        host: Ollama server URL
        temperature: Randomness in responses (0.0 = deterministic, 1.0 = creative)
        top_p: Nucleus sampling parameter (0.0-1.0)
        repeat_penalty: Penalty for repeating tokens (1.0 = no penalty, >1.0 = discourage)
        max_tokens: Maximum context window size (num_ctx in Ollama)
        timeout: Request timeout in seconds
        stop_sequences: Sequences that stop generation when encountered
    """
    model: str = "qwen2:7b"
    host: str = "http://localhost:11434"
    temperature: float = 0.0  # Deterministic by default for optimization tasks
    top_p: float = 0.9
    repeat_penalty: float = 1.1
    max_tokens: int = 4096  # num_ctx in Ollama
    timeout: int = 60  # seconds
    stop_sequences: list = field(default_factory=lambda: ["\n\n```", "\n\n#", "</json>"])


@dataclass
class TaskConfig:
    """
    Configuration for a specific task type (e.g., classification, extraction).

    Each task can have different requirements:
    - Classification needs high accuracy → temperature=0, json_mode=True
    - Explanation can be slightly creative → temperature=0.1-0.3
    - Analysis suggestions benefit from creativity → temperature=0.2-0.5

    Attributes:
        temperature: Randomness for this task (overrides model default)
        json_mode: Force JSON output format (Ollama's format="json")
        max_tokens: Maximum tokens for this task (can be less than model max)
        system_prompt_style: How to structure system prompts
            - "concise": Short, direct instructions
            - "detailed": Comprehensive instructions with examples
            - "chain_of_thought": Step-by-step reasoning prompts
        user_prompt_style: How to structure user prompts
            - "direct": Straightforward task description
            - "few_shot": Include examples in the prompt
            - "chain_of_thought": Request step-by-step reasoning
        enforce_schema: Validate JSON output against expected schema
        max_retries: How many times to retry on failure
        timeout: Task-specific timeout (overrides model default)
    """
    temperature: float = 0.0
    json_mode: bool = False
    max_tokens: int = 4096
    system_prompt_style: str = "concise"  # "concise", "detailed", "chain_of_thought"
    user_prompt_style: str = "direct"  # "direct", "few_shot", "chain_of_thought"
    enforce_schema: bool = False
    max_retries: int = 1
    timeout: int = 60


@dataclass
class GlobalBehaviorConfig:
    """
    Global behavioral settings that affect all interactions.

    These settings control the overall "personality" and behavior
    of the optimization assistant, affecting how it communicates
    and processes information.

    Response Style:
        use_markdown: Format responses with markdown (bold, lists, etc.)
        use_emojis: Include emojis in responses (⚡, 🎯, etc.)
        concise_mode: Prefer short, direct answers over verbose explanations
        technical_depth: How technical to make explanations
            - "low": Simple language, minimal jargon
            - "medium": Balance of clarity and precision
            - "high": Full technical detail with mathematical notation

    Explanation Behavior:
        explain_deterministically: Prefer deterministic (code-based) explanations
            over LLM-generated ones when possible. Reduces hallucination risk.
        ground_explanations: Only allow facts that reference actual solution data.
            Filters out speculation and unverified claims.
        include_units: Always include units (currency, distance, weight, etc.)
            in numerical results.

    Follow-up Handling:
        enable_deterministic_followups: Answer common questions (objective,
            variables, constraints) without calling the LLM. Faster and
            more accurate.
        enable_conversation_context: Track conversation history to enable
            follow-up questions and modifications.

    Error Handling:
        user_friendly_errors: Convert technical errors to user-friendly
            messages (e.g., "ConnectionError" → "Can't reach Ollama server")
        verbose_logging: Print detailed logs for debugging
    """
    # Response style
    use_markdown: bool = True
    use_emojis: bool = False
    concise_mode: bool = True  # Prefer short, direct answers
    technical_depth: str = "medium"  # "low", "medium", "high"

    # Explanation behavior
    explain_deterministically: bool = True  # Prefer deterministic over LLM when possible
    ground_explanations: bool = True  # Only allow grounded facts in explanations
    include_units: bool = True  # Always include units (currency, distance, etc.)

    # Follow-up handling
    enable_deterministic_followups: bool = True  # Answer common questions without LLM
    enable_conversation_context: bool = True  # Track conversation state

    # Error handling
    user_friendly_errors: bool = True  # Convert technical errors to user-friendly messages
    verbose_logging: bool = False  # Detailed logs for debugging


class LLMConfig:
    """
    Central LLM configuration manager.

    This class manages all LLM-related configuration across the system.
    It provides:
    - Base model configuration (applies to all tasks)
    - Task-specific overrides (per-operation settings)
    - Global behavior settings (affects all interactions)

    The configuration can be:
    - Modified programmatically (override_* methods)
    - Saved/loaded from JSON files
    - Exported as a dictionary

    Example:
        # Create and customize config
        config = LLMConfig()
        config.override_model_config(model="llama3:8b")
        config.override_task_config("classification", temperature=0.0, max_retries=5)

        # Save for later
        config.save_to_file("my_config.json")

        # Load in another session
        config = LLMConfig.load_from_file("my_config.json")
    """

    def __init__(self):
        """Initialize with default configuration"""
        # Base model configuration
        self.model_config = LLMModelConfig()

        # Global behavior settings
        self.behavior = GlobalBehaviorConfig()

        # Task-specific configurations
        # Each task is optimized for its specific use case
        self.task_configs: Dict[str, TaskConfig] = {
            # Intent routing: Fast detection of user intent (smalltalk/help/optimization/follow-up)
            # Needs to be fast and accurate, hence low timeout and strict schema
            "intent_detection": TaskConfig(
                temperature=0.0,  # Deterministic for consistency
                json_mode=True,   # Structured output required
                max_tokens=512,   # Short output expected
                system_prompt_style="concise",
                enforce_schema=True,
                timeout=30  # Fast response needed
            ),

            # Problem classification: Identify problem type (transportation, assignment, etc.)
            # Critical task - wrong classification breaks everything
            # Higher retries and longer timeout for reliability
            "classification": TaskConfig(
                temperature=0.0,     # Must be deterministic
                json_mode=True,      # Structured output required
                max_tokens=1024,     # Moderate output size
                system_prompt_style="detailed",  # Clear instructions needed
                enforce_schema=True,
                max_retries=3,       # Classification is critical, retry if needed
                timeout=45
            ),

            # Parameter extraction: Extract numbers, entities, constraints from text
            # Must be accurate - extraction errors cause solver failures
            # Longer context for complex problem descriptions
            "extraction": TaskConfig(
                temperature=0.0,     # Deterministic for accuracy
                json_mode=True,      # Structured output required
                max_tokens=2048,     # May need longer context for complex problems
                system_prompt_style="detailed",
                user_prompt_style="direct",
                enforce_schema=True,
                max_retries=2,       # Allow one retry
                timeout=60           # Extraction can be slow for complex problems
            ),

            # Solution explanation: Generate natural language explanation of results
            # Can be slightly creative for better readability
            # Shorter context since solution data is compact
            "explanation": TaskConfig(
                temperature=0.1,     # Slightly creative for natural language
                json_mode=False,     # Natural language output
                max_tokens=512,      # Explanations should be concise
                system_prompt_style="concise",
                user_prompt_style="direct",
                timeout=30
            ),

            # Follow-up detection: Detect if message is about previous solution
            # Fast and accurate to enable responsive conversation
            "follow_up_detection": TaskConfig(
                temperature=0.0,     # Deterministic
                json_mode=True,      # Structured output
                max_tokens=512,
                system_prompt_style="concise",
                enforce_schema=True,
                timeout=30           # Fast response for good UX
            ),

            # Modification detection: Identify what parameters user wants to change
            # Needs careful analysis to avoid misinterpretation
            "modification_detection": TaskConfig(
                temperature=0.0,     # Deterministic
                json_mode=True,      # Structured output
                max_tokens=1024,
                system_prompt_style="detailed",  # Clear instructions to avoid confusion
                enforce_schema=True,
                timeout=45
            ),

            # Analysis suggestion: Suggest relevant analyses for the solution
            # Can be creative - suggesting novel insights is valuable
            "analysis_suggestion": TaskConfig(
                temperature=0.2,     # Slightly creative for diverse suggestions
                json_mode=False,     # Natural language output
                max_tokens=1024,
                timeout=30
            )
        }

    def get_task_config(self, task_name: str) -> TaskConfig:
        """
        Get configuration for a specific task.

        Args:
            task_name: Name of the task (e.g., "classification", "extraction")

        Returns:
            TaskConfig object with settings for this task, or default config
            if task name not found
        """
        return self.task_configs.get(task_name, TaskConfig())

    def get_chat_params(self, task_name: str) -> Dict[str, Any]:
        """
        Get chat parameters for a specific task.

        Combines model config with task-specific overrides to create
        a complete set of parameters for an LLM call.

        Args:
            task_name: Name of the task

        Returns:
            Dictionary of parameters ready to pass to LLM client

        Example:
            params = config.get_chat_params("classification")
            response = llm_client._chat(
                system="...",
                user="...",
                **params
            )
        """
        task_config = self.get_task_config(task_name)

        return {
            "model": self.model_config.model,
            "temperature": task_config.temperature,
            "top_p": self.model_config.top_p,
            "repeat_penalty": self.model_config.repeat_penalty,
            "num_ctx": task_config.max_tokens,
            "stop": self.model_config.stop_sequences,
            "json_mode": task_config.json_mode,
            "timeout": task_config.timeout
        }

    def override_task_config(self, task_name: str, **kwargs):
        """
        Override specific parameters for a task.

        Args:
            task_name: Name of the task to modify
            **kwargs: Parameters to override (e.g., temperature=0.5, max_tokens=2048)

        Example:
            # Make explanations more creative
            config.override_task_config("explanation", temperature=0.3)

            # Increase extraction retries
            config.override_task_config("extraction", max_retries=5)
        """
        if task_name in self.task_configs:
            for key, value in kwargs.items():
                if hasattr(self.task_configs[task_name], key):
                    setattr(self.task_configs[task_name], key, value)

    def override_model_config(self, **kwargs):
        """
        Override model configuration parameters.

        Args:
            **kwargs: Model parameters to override (e.g., model="llama3:8b")

        Example:
            # Switch to a different model
            config.override_model_config(
                model="llama3:8b",
                host="http://localhost:11434",
                temperature=0.1
            )
        """
        for key, value in kwargs.items():
            if hasattr(self.model_config, key):
                setattr(self.model_config, key, value)

    def override_behavior(self, **kwargs):
        """
        Override global behavior settings.

        Args:
            **kwargs: Behavior parameters to override

        Example:
            # Make responses more technical and verbose
            config.override_behavior(
                concise_mode=False,
                technical_depth="high",
                use_emojis=True
            )
        """
        for key, value in kwargs.items():
            if hasattr(self.behavior, key):
                setattr(self.behavior, key, value)

    def to_dict(self) -> Dict[str, Any]:
        """
        Export configuration as dictionary.

        Useful for:
        - Saving to JSON
        - Logging current configuration
        - Comparing configurations

        Returns:
            Dictionary representation of entire configuration
        """
        return {
            "model": {
                "model": self.model_config.model,
                "host": self.model_config.host,
                "temperature": self.model_config.temperature,
                "top_p": self.model_config.top_p,
                "repeat_penalty": self.model_config.repeat_penalty,
                "max_tokens": self.model_config.max_tokens,
                "timeout": self.model_config.timeout,
                "stop_sequences": self.model_config.stop_sequences
            },
            "behavior": {
                "use_markdown": self.behavior.use_markdown,
                "use_emojis": self.behavior.use_emojis,
                "concise_mode": self.behavior.concise_mode,
                "technical_depth": self.behavior.technical_depth,
                "explain_deterministically": self.behavior.explain_deterministically,
                "ground_explanations": self.behavior.ground_explanations,
                "include_units": self.behavior.include_units,
                "enable_deterministic_followups": self.behavior.enable_deterministic_followups,
                "enable_conversation_context": self.behavior.enable_conversation_context,
                "user_friendly_errors": self.behavior.user_friendly_errors,
                "verbose_logging": self.behavior.verbose_logging
            },
            "tasks": {
                name: {
                    "temperature": cfg.temperature,
                    "json_mode": cfg.json_mode,
                    "max_tokens": cfg.max_tokens,
                    "system_prompt_style": cfg.system_prompt_style,
                    "user_prompt_style": cfg.user_prompt_style,
                    "enforce_schema": cfg.enforce_schema,
                    "max_retries": cfg.max_retries,
                    "timeout": cfg.timeout
                }
                for name, cfg in self.task_configs.items()
            }
        }

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'LLMConfig':
        """
        Create configuration from dictionary.

        Args:
            config_dict: Dictionary with configuration (from to_dict() or JSON)

        Returns:
            New LLMConfig instance with settings from dictionary

        Example:
            config_dict = {
                "model": {"model": "llama3:8b", "temperature": 0.2},
                "behavior": {"concise_mode": False},
                "tasks": {"classification": {"max_retries": 5}}
            }
            config = LLMConfig.from_dict(config_dict)
        """
        config = cls()

        # Override model config
        if "model" in config_dict:
            config.override_model_config(**config_dict["model"])

        # Override behavior
        if "behavior" in config_dict:
            config.override_behavior(**config_dict["behavior"])

        # Override task configs
        if "tasks" in config_dict:
            for task_name, task_params in config_dict["tasks"].items():
                config.override_task_config(task_name, **task_params)

        return config

    def save_to_file(self, filepath: str):
        """
        Save configuration to JSON file.

        Args:
            filepath: Path to save configuration (e.g., "config.json")

        Example:
            config.save_to_file("production_config.json")
        """
        import json
        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: str) -> 'LLMConfig':
        """
        Load configuration from JSON file.

        Args:
            filepath: Path to configuration file

        Returns:
            LLMConfig instance with settings from file

        Example:
            config = LLMConfig.load_from_file("production_config.json")
        """
        import json
        with open(filepath, 'r') as f:
            config_dict = json.load(f)
        return cls.from_dict(config_dict)


# ============================================================================
# GLOBAL CONFIGURATION INSTANCE
# ============================================================================
# This is the default configuration used throughout the system.
# You can modify it directly or create your own instance.

config = LLMConfig()


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================
# Quick helper functions for common configuration adjustments.
# These modify the global `config` instance.

def set_model(model: str, host: str = None):
    """
    Quick setter for model and host.

    Args:
        model: Model name (e.g., "llama3:8b", "qwen2:7b")
        host: Optional Ollama server URL

    Example:
        set_model("llama3:8b", "http://localhost:11434")
    """
    config.override_model_config(model=model)
    if host:
        config.override_model_config(host=host)


def set_concise_mode(enabled: bool = True):
    """
    Enable/disable concise response mode.

    When enabled, responses are shorter and more direct.
    When disabled, responses include more detail and context.

    Args:
        enabled: True for concise, False for detailed

    Example:
        set_concise_mode(False)  # Get more detailed responses
    """
    config.override_behavior(concise_mode=enabled)


def set_technical_depth(level: str):
    """
    Set technical depth of explanations.

    Args:
        level: "low", "medium", or "high"
            - "low": Simple language, minimal jargon
            - "medium": Balance of clarity and precision
            - "high": Full technical detail with math notation

    Example:
        set_technical_depth("high")  # For expert users
    """
    if level in ["low", "medium", "high"]:
        config.override_behavior(technical_depth=level)


def set_temperature(task: str, temperature: float):
    """
    Set temperature for a specific task.

    Args:
        task: Task name (e.g., "classification", "explanation")
        temperature: Randomness (0.0 = deterministic, 1.0 = creative)

    Example:
        set_temperature("explanation", 0.3)  # More creative explanations
    """
    config.override_task_config(task, temperature=temperature)


def enable_verbose_logging(enabled: bool = True):
    """
    Enable detailed logging for debugging.

    When enabled, prints detailed information about LLM calls,
    prompts, responses, and internal processing.

    Args:
        enabled: True to enable, False to disable

    Example:
        enable_verbose_logging(True)  # Debug mode
    """
    config.override_behavior(verbose_logging=enabled)


def enable_deterministic_mode(enabled: bool = True):
    """
    Enable full deterministic mode.

    When enabled:
    - All tasks use temperature=0 (fully deterministic)
    - Explanations use code-based generation (not LLM)
    - Follow-ups answered deterministically when possible

    This is the most reliable mode but least creative.

    Args:
        enabled: True for deterministic, False for default settings

    Example:
        enable_deterministic_mode(True)  # Maximum reliability
    """
    if enabled:
        # Set all tasks to temperature 0
        for task_name in config.task_configs.keys():
            config.override_task_config(task_name, temperature=0.0)

        config.override_behavior(
            explain_deterministically=True,
            enable_deterministic_followups=True
        )
    else:
        # Reset to defaults (some tasks slightly creative)
        config.override_task_config("explanation", temperature=0.1)
        config.override_task_config("analysis_suggestion", temperature=0.2)
