from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict

from ...utils import LogManager

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
You must output RAW PYTHON CODE ONLY.
NO markdown fences like ``` or ```python. NO explanation text.

Only call methods that appear in [Runtime Contract] in the user prompt.
NEVER invent new methods (e.g. wait_for_deployment) or new classes.

Actor identity:
- Use actor.actor_id as the primary identifier.
- actor.id may exist only for backward compatibility. Always prefer actor.actor_id.

Review rules (when fixing):
- You MUST change the code to address the specific error. DO NOT repeat the same failing line.
- If the error is "attribute ... not found", switch to a safe getter pattern:
    aid = getattr(actor, "actor_id", None) or getattr(actor, "id", None)
- If the step is already satisfied by game state, return success without performing actions.

Hard safety rules:
- DO NOT import anything.
- DO NOT do file I/O, network, subprocess, threads, reflection, eval/exec.
- DO NOT access globals() / locals().
- Keep loops bounded.

You MUST set __result__ exactly once at the end.
__result__ MUST be a dict with keys:
{
  "next_state": "RUN|OBSERVE|PLAN|REVIEW|COMMIT|NEED_USER|STOP",
  "player_message": str,
  "observations": str,
  "next_step_hint": str
}
next_step_hint MUST be a JSON string or "" (not a python dict).
"""


# -----------------------------
# Observe Node Prompts
# -----------------------------
OBSERVE_SYSTEM = f"""
You are the OBSERVE node.
You MAY call gameapi query methods only (no actions like move/produce/deploy/attack).
Your job is to decide whether we have enough info to PLAN.

Output python only. No fences.

If enough info:
- next_state must be "PLAN"

{_python_only_rule()}
"""

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
    "You are the PLAN node in an agent workflow.\n\n"
    "CRITICAL RULES:\n"
    "1. Your ONLY job is to plan how to achieve the [Goal] given by the user.\n"
    "2. DO NOT expand or interpret the goal - follow it EXACTLY as stated.\n"
    "3. DO NOT assume the goal is already completed.\n"
    "4. If the goal is simple and direct (e.g., '展开基地车'), your plan should directly address that specific task.\n"
    "5. DO NOT add extra steps beyond what the user asked for.\n\n"
    "Planning guidelines:\n"
    "- Keep plan short and testable (1~4 steps max).\n"
    "- For simple goals like '展开基地车', the plan should be just that one step.\n"
    "- Only break into multiple steps if the goal explicitly requires multiple actions.\n"
    "- Your assumptions should reflect what needs to be true for YOUR PLAN to work, not assumptions about the goal being done.\n\n"
    + _json_only_rule() +
    "Output schema:\n"
    "{\n"
    '  "plan": [\n'
    "    {\n"
    '      "step": string,  // The actual action to take, matching the user goal\n'
    "    }\n"
    "  ],\n"
    '  "assumptions": [string]  // What must be true for this plan to execute, NOT assumptions about goal completion\n'
    "}\n"
)


def build_plan_user(p: Dict[str, Any]) -> str:
    goal = p.get('goal', '')
    return (
        f"[User Goal]\n"
        f"{goal}\n\n"
        f"IMPORTANT: Your plan must achieve exactly this goal: \"{goal}\"\n"
        f"Do NOT assume this goal is already completed.\n"
        f"Do NOT add steps beyond what the user asked for.\n\n"
        "[Game Basic State]\n"
        f"{p.get('game_basic_state', '')}\n\n"
        "[GameDetailState(optional)] (Observed by earlier nodes)\n"
        f"{p.get('game_detail_state', '')}\n\n"
        "Task:\n"
        f"Generate a plan to achieve the user goal: \"{goal}\"\n"
        "- If the goal is simple (1 action), make a 1-step plan.\n"
        "- Keep plan focused and direct (1~4 steps max).\n"
    )


# -----------------------------
# ActionGen Node Prompts
# -----------------------------
ACTIONGEN_SYSTEM = (
    f"""
You are the ACTION_PROGRAM node.

{_python_only_rule()}

This is a example of the output for Step: "展开基地车，建造一个电厂，再造一个兵营, 造5个步兵":

Notes:
- In this runtime, `api` refers to the **OpenRA midlayer API (MacroActions)**, not the raw GameAPI.
- Use MacroActions methods like: deploy_mcv_and_wait / ensure_can_produce_unit / produce_wait / query_actor / dispatch_explore / dispatch_attack
- Do NOT use old methods like: able_to_produce / produce_units / wait (they do not exist on MacroActions).

try:
    # 展开基地车（会阻塞等待一小会）
    api.deploy_mcv_and_wait(wait_time=1.0)
    logger.info("展开了基地车")

    # 生产前置：确保能生产对应单位/建筑（必要时会自动建造前置并等待）
    if not api.ensure_can_produce_unit("电厂"):
        raise RuntimeError("不能生产电厂：前置不足或失败")
    api.produce_wait("电厂", 1, auto_place_building=True)
    logger.info("建造了电厂")

    if not api.ensure_can_produce_unit("兵营"):
        raise RuntimeError("不能生产兵营：前置不足或失败")
    api.produce_wait("兵营", 1, auto_place_building=True)
    logger.info("建造了兵营")

    if not api.ensure_can_produce_unit("步兵"):
        raise RuntimeError("不能生产步兵：前置不足或失败")
    api.produce_wait("步兵", 5, auto_place_building=True)
    logger.info("建造了步兵")

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
- prefer querying units safely: check list length before indexing, and escalate to NEED_USER when the game state requires manual input
- when referencing unit identifiers, use actor.actor_id (actor.id 仍旧可用，但仅作兼容)

[GameBasicState]
{p.get('game_basic_state','')}

[GameDetailState(optional)](Observed by earlier nodes)
{p.get('game_detail_state','')}

Task:
Generate an Action Program in python that attempts the current step intent robustly.
- Validate preconditions before acting; if无法安全执行，请设置 next_state="NEED_USER" 并简要说明原因。
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
