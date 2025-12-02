from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Literal, Dict


@dataclass
class LoggingSection:
    logfile_level: str = "debug"
    console_level: str = "debug"
    debug_mode: bool = True
    log_dir: str = "Logs"

@dataclass
class ModelConfig:
    request_type: str = "openai"
    api_key: str = "sk-xxx"
    base_url: Optional[str] = "https://xxx.com"
    model: str = "gpt-4o-mini"
    max_output_tokens: int = 1024
    temperature: Optional[float] = None
    top_p: Optional[float] = None

@dataclass
class GPT5MiniModel(ModelConfig):
    model: str = "gpt-5-nano"

@dataclass
class MemoryNodeSection:
    short_term_window: int = 6
    long_term_enabled: bool = True
    long_term_interval: int = 3
    long_term_model_template: Optional[str] = None
    long_term_model: OpenAISection = field(default_factory=lambda: OpenAISection(enabled=False))


@dataclass
class RuntimeSection:
    interval_sec: float = 15.5
    max_ticks: Optional[int] = None


@dataclass
class ConsoleSection:
    enabled: bool = True
    width: int = 80
    show_planning: bool = True
    show_actions: bool = True
    show_memory: bool = False


def _model_templates() -> Dict[str, ModelConfig]:
    return {"default": ModelConfig(),
            "GPT-5 mini": GPT5MiniModel()}


@dataclass
class NodeModel:
     plan: str = "default"
     action: str = "default"
     observe: str = "default"
     review: str = "default"
     commit: str = "default"

@dataclass
class SeedConfig:
    logging: LoggingSection = field(default_factory=LoggingSection)
    runtime: RuntimeSection = field(default_factory=RuntimeSection)
    console: ConsoleSection = field(default_factory=ConsoleSection)
    model_templates: Dict[str, ModelConfig] = field(default_factory=_model_templates)
    node_models: NodeModel = field(default_factory=NodeModel)


