from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from ..utils import LogManager

logger = LogManager.get_logger()


@dataclass(frozen=True)
class PromptDef:
    system: str
    build_user: Callable[[Dict[str, Any]], str]


def _json_only_rule() -> str:
    return (
        "IMPORTANT: Output MUST be valid JSON only. No prose, no markdown, no code fences.\n"
        "If you output anything else, the program will crash.\n"
        "DONT output Empty Response. If you have no response, output an empty JSON object."
    )

def _python_only_rule() -> str:
    
    return """

You must output RAW PYTHON CODE ONLY. No explanation text.
If you output anything other than Python code, the program will crash.

Your job:
- Implement the given step intent robustly using the provided runtime objects.
- You MAY perform multiple gameapi calls and conditional branches.
- You MAY choose to do no execution and only return a decision by assigning __result__.

Runtime objects available (predefined globals):
- gameapi: game control/query API (see contract in user prompt)
- logger: logger object for logging(use logger.debug|info|warning|error(message) to log information)

Hard safety rules:
- DO NOT import anything.
- DO NOT do file I/O, network, subprocess, threads, reflection, eval/exec.
- DO NOT access globals() / locals() to escape the sandbox.
- Keep loops BOUNDED (no unbounded while True). Respect budgets.

You MUST set __result__ exactly once at the end of the script.
__result__ MUST be a dict with EXACT keys:
{
  "next_state": "RUN|OBSERVE|PLAN|REVIEW|COMMIT|STOP",
  "player_message": str,
  "observations": str,p
  "next_step_hint": str     # {intent, skill, args} or {}
}

Semantics:
- next_state: the next state of the node
- player_message: the message to the player
- observations: the information gotten from action execution, which may be used by next node
- next_step_hint: some extra information may be used by next node

You should prefer:
- short messages to player
- bounded self-repair only when safe and low-risk
- otherwise escalate via observe/replan/need_user

"""


# -----------------------------
# Observe Node Prompts
# -----------------------------
OBSERVE_SYSTEM = (
    f"""
You are the OBSERVE node in an agent workflow.
Your goal is to decide what minimal additional information is required before planning.
You do NOT execute actions.
You do NOT propose long plans.
{_python_only_rule()}
"""
)


def build_observe_user(p: Dict[str, Any]) -> str:
    # p keys expected: goal, last_outcome, intel
    return (
        "[Goal]\n"
        f"{p.get('goal','')}\n\n"
        "[Last Outcome]\n"
        f"{p.get('last_outcome',{})}\n\n"
        "[Current Intel Snapshot]\n"
        f"{p.get('intel',{})}\n\n"
        "[GameBasicState]\n"
        f"{p.get('game_basic_state','')}\n\n"
        "[GameDetailState(optional)](Observed by earlier nodes)\n"
        f"{p.get('game_detail_state','')}\n\n"
        "Task: Decide what *minimal* additional info is required before planning.\n"
    )


# -----------------------------
# Plan Node Prompts
# -----------------------------
PLAN_SYSTEM = (
    "You are the PLAN node in an agent workflow.\n"
    "You must choose the next macro step(s) based on the current situation and goal.\n"
    "Your plan must be short and testable (2~4 steps max).\n"
    + _json_only_rule() +
    "Output schema:\n"
    "{\n"
    '  "plan": [\n'
    "    {\n"
    '      "step": string,\n'
    "    }\n"
    "  ],\n"
    '  "assumptions": [string]\n'
    "}\n"
)


def build_plan_user(p: Dict[str, Any]) -> str:
    return (
        "[Goal]\n"
        f"{p.get('goal', '')}\n\n"
        "[Game Basic State]\n"
        f"{p.get('game_basic_state', '')}\n\n"
        "[GameDetailState(optional)] (Observed by earlier nodes)\n"
        f"{p.get('game_detail_state', '')}\n\n"
        "Constraints:\n"
        "- Keep plan short (2~4 steps).\n"
    )


# -----------------------------
# ActionGen Node Prompts
# -----------------------------
ACTIONGEN_SYSTEM = (
    f"""
You are the ACTION_PROGRAM node.

{_python_only_rule()}

This is a example of the output for Step: "建造一个电厂，再造一个兵营, 造5个步兵":

try:
    if api.able_to_produce("电厂"):
        p1 = api.produce_units("电厂", 1)
        api.wait(p1)
        logger.info("建造了电厂")
    else:
        raise RuntimeError("不能建造电厂")
    if api.able_to_produce("兵营"):
        p2 = api.produce_units("兵营", 1)
        api.wait(p2)
        logger.info("建造了兵营")
    else:
        raise RuntimeError("不能建造兵营")
    if api.able_to_produce("步兵"):
        p3 = api.produce_units("步兵", 5)
        api.wait(p3)
        logger.info("建造了步兵")
    else:
        raise RuntimeError("不能建造步兵")
    infantry = api.query_actor(TargetsQueryParam(type=["步兵"], faction="自己"))
    logger.info(f"now infantry count: {{len(infantry)}}")
    
    __result__ = {{
        "next_state": "RUN",
        "player_message": "建造了电厂和兵营，并建造了5个步兵",
        "observations": f"now infantry count: {{len(infantry)}}",
        "next_step_hint": ""
    }}
except Exception as e:
    __result__ = {{
        "next_state": "REVIEW",
        "player_message": f"执行时发生异常。异常信息: {{e}}",
        "observations": "",
        "next_step_hint": f"exception: {{e}}, try to fix it",
    }}
"""
)


def build_actiongen_user(p: Dict[str, Any]) -> str:
    intel_block = ""
    if p.get("intel") is not None:
        intel_block = f"[Intel Snapshot]\n{p.get('intel', {})}\n\n"

    events_block = ""
    if p.get("events"):
        events_block = f"[Recent Events]\n{p.get('events', [])}\n\n"

    return f"""
[Big Goal]
{p.get('goal','')}

[Your Current Step]
{p.get('step',{})}
# step includes: id, intent, skill, args, preflight(optional)

{intel_block}{events_block}

[Runtime Contract (gameapi allowed methods + return conventions)]
{p.get('rt_contract','')}

[Budgets / Policy]
- if missing info blocks safe execution: return status="observe" with 0~3 hints

[GameBasicState]
{p.get('game_basic_state','')}

[GameDetailState(optional)](Observed by earlier nodes)
{p.get('game_detail_state','')}

Task:
Generate an Action Program in python that attempts the current step intent robustly.
If you choose to not execute any action, return a "decision-only" program by directly assigning __result__.
Remember: output python code only, and end by setting __result__ exactly once.
"""


# -----------------------------
# Review Node Prompts
# -----------------------------
REVIEW_SYSTEM = (
    f"""
    You are the REVIEW node.
    The Action Node Before this node didn't finished successfully, and you need to review the excution error or excution result, try generate a new python code to fix it.
    {_python_only_rule()}
    
"""   
)


def build_review_user(p: Dict[str, Any]) -> str:
    return f"""
[Goal]
{p.get('goal','')}

[Last Action Step]
{p.get('step',{})}
# step includes: id, intent, skill, args, preflight(optional)

[Last Action Python]
{p.get('action_code','')}

[Last Action Result]
{p.get('action_result','')}

[GameBasicState]
{p.get('game_basic_state','')}

[GameDetailState(optional)](Observed by earlier nodes)
{p.get('game_detail_state','')}

[Scratchpad]
{p.get('scratchpad','')}
"""


# -----------------------------
# Commit Node Prompts
# -----------------------------
COMMIT_SYSTEM = (
    "You are the COMMIT node.\n"
    "You must produce a concise commit record for persistence and a player-facing message.\n"
    "You do NOT execute code. The runtime will submit tasks separately.\n\n"
    + _json_only_rule() +
    "Output schema:\n"
    "{\n"
    '  "db_records": [{"type": string, "data": object}],\n'
    '  "player_message": string,\n'
    '  "next_hint": {"observe_force": boolean}\n'
    "}\n"
)


def build_commit_user(p: Dict[str, Any]) -> str:
    return (
        "[Goal]\n"
        f"{p.get('goal','')}\n\n"
        "[Last Step]\n"
        f"{p.get('step',{})}\n\n"
        "[GameBasicState]\n"
        f"{p.get('game_basic_state','')}\n\n"
        "[GameDetailState(optional)](Observed by earlier nodes)\n"
        f"{p.get('game_detail_state','')}\n\n"
        "[Scratchpad]\n"
        f"{p.get('scratchpad','')}\n\n"
        
        "Task:\n"
        "- Create a minimal DB record set for later debugging.\n"
        "- Player message must be short and concise.\n"
    )


PROMPTS: Dict[str, PromptDef] = {
    "observe": PromptDef(system=OBSERVE_SYSTEM, build_user=build_observe_user),
    "plan": PromptDef(system=PLAN_SYSTEM, build_user=build_plan_user),
    "action_gen": PromptDef(system=ACTIONGEN_SYSTEM, build_user=build_actiongen_user),
    "review": PromptDef(system=REVIEW_SYSTEM, build_user=build_review_user),
    "commit": PromptDef(system=COMMIT_SYSTEM, build_user=build_commit_user),
}


def get_prompt(node_key: str) -> PromptDef:
    if node_key not in PROMPTS:
        logger.error("Prompt key not found: %s", node_key)
        raise KeyError(f"prompt not found: {node_key}")
    return PROMPTS[node_key]
