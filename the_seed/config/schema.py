from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Dict


@dataclass
class LoggingSection:
    # 默认值: "debug"
    logfile_level: str = "debug"
    # 默认值: "debug"
    console_level: str = "debug"
    # 默认值: True
    debug_mode: bool = True
    # 默认值: "Logs"
    log_dir: str = "Logs"


@dataclass
class ModelConfig:
    # 默认值: "openai"
    request_type: str = "openai"
    # 默认值: "sk-xxx"
    api_key: str = "sk-xxx"
    # 默认值: "https://openai.com/api/v1"
    base_url: Optional[str] = "https://openai.com/api/v1"
    # 默认值: "gpt-4o-mini"
    model: str = "gpt-4o-mini"
    # 默认值: 1024
    max_output_tokens: int = 1024
    # 默认值: None
    temperature: Optional[float] = None
    # 默认值: None
    top_p: Optional[float] = None


@dataclass
class GPT5MiniModel(ModelConfig):
    # 默认值: "gpt-5-nano"
    model: str = "gpt-5-nano"


@dataclass
class MemoryNodeSection:
    # 默认值: 6
    short_term_window: int = 6
    # 默认值: True
    long_term_enabled: bool = True
    # 默认值: 3
    long_term_interval: int = 3
    # 默认值: None
    long_term_model_template: Optional[str] = None
    # 默认值: OpenAISection(enabled=False)
    long_term_model: OpenAISection = field(default_factory=lambda: OpenAISection(enabled=False))


@dataclass
class RuntimeSection:
    # 默认值: 15.5
    interval_sec: float = 15.5
    # 默认值: None
    max_ticks: Optional[int] = None


@dataclass
class ConsoleSection:
    # 默认值: True
    enabled: bool = True
    # 默认值: 80
    width: int = 80
    # 默认值: True
    show_planning: bool = True
    # 默认值: True
    show_actions: bool = True
    # 默认值: False
    show_memory: bool = False


def _model_templates() -> Dict[str, ModelConfig]:
    return {"default": ModelConfig(), "GPT-5 mini": GPT5MiniModel()}


@dataclass
class NodeModel:
    # 默认值: "default"
    plan: str = "default"
    # 默认值: "default"
    action: str = "default"
    # 默认值: "default"
    observe: str = "default"
    # 默认值: "default"
    review: str = "default"
    # 默认值: "default"
    commit: str = "default"


@dataclass
class SeedConfig:
    # 默认值: LoggingSection()
    logging: LoggingSection = field(default_factory=LoggingSection)
    # 默认值: RuntimeSection()
    runtime: RuntimeSection = field(default_factory=RuntimeSection)
    # 默认值: ConsoleSection()
    console: ConsoleSection = field(default_factory=ConsoleSection)
    # 默认值: {"default": ModelConfig(), "GPT-5 mini": GPT5MiniModel()}
    model_templates: Dict[str, ModelConfig] = field(default_factory=_model_templates)
    # 默认值: NodeModel()
    node_models: NodeModel = field(default_factory=NodeModel)