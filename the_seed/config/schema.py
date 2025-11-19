from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Literal


@dataclass
class LoggingSection:
    level: str = "info"
    debug_mode: bool = False
    log_dir: str = "Logs"


@dataclass
class OpenAISection:
    enabled: bool = True
    api_key: str = ""
    base_url: Optional[str] = None
    organization: Optional[str] = None
    model: str = "gpt-4o-mini"
    use_responses_api: bool = False
    reasoning: bool = False
    reasoning_effort: Literal["low", "medium", "high"] = "medium"
    max_output_tokens: int = 1024
    temperature: float = 0.4
    top_p: float = 0.9
    response_format: Literal["json_schema", "json_object"] = "json_schema"


@dataclass
class PlannerSection:
    json_mode: bool = True
    max_tools_per_tick: int = 3


@dataclass
class AgentSection:
    role_prompt: str = "You is playing a game. Use tools concisely."


@dataclass
class RuntimeSection:
    interval_sec: float = 5.5
    max_ticks: Optional[int] = None


@dataclass
class SeedConfig:
    logging: LoggingSection = field(default_factory=LoggingSection)
    openai: OpenAISection = field(default_factory=OpenAISection)
    planner: PlannerSection = field(default_factory=PlannerSection)
    agent: AgentSection = field(default_factory=AgentSection)
    runtime: RuntimeSection = field(default_factory=RuntimeSection)

