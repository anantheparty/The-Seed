"""
CodeGenNode - 单一代码生成节点

接收玩家指令 + 游戏状态，直接生成可执行的 Python 代码。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..model import ModelAdapter, ModelResponse
from ..utils import LogManager

logger = LogManager.get_logger()


@dataclass
class CodeGenResult:
    """代码生成结果"""
    code: str
    raw_response: ModelResponse


CODEGEN_SYSTEM_PROMPT = """你是 OpenRA 红色警戒游戏的 Python 代码生成器。

根据玩家指令和游戏状态，生成可执行的 Python 代码。

## 严格规则

1. 只输出纯 Python 代码，不要 markdown 围栏，不要解释文字
2. **绝对不要 import 任何东西** — 所有对象都已在全局作用域中可用
3. 不要做文件 I/O、网络、subprocess、线程、反射、eval/exec
4. 保持代码简短直接，**一条指令只做一件事**，不要过度展开
5. 代码最后必须设置 `__result__` 字典
6. 对于模糊/抽象的指令（如"继续造部队"），选择一种具体的操作执行即可，不要试图做太多

## 战争迷雾机制（重要）

- `query_actor(faction="敌人")` **只能看到当前视野内的敌人**，视野外的返回空
- 要查看**残影**（之前见过但现在被迷雾覆盖的建筑/单位），必须用 `query_actor_with_frozen`
- 游戏状态的 [EnemyFrozen] 段会列出所有残影及其最后已知位置
- 进攻时优先使用残影位置作为目标，用 `attack_move` 攻击移动过去

## 全局可用对象（不需要 import）

- `api` — MacroActions 实例，所有游戏操作都通过它
- `logger` — 日志记录器
- `TargetsQueryParam` — 查询参数类（已在全局作用域中）
- `Location` — 位置类（已在全局作用域中）
- `Actor` — 单位类（已在全局作用域中，有 .position / .hppercent 属性）
- `FrozenActor` — 残影类（有 .type/.faction/.position 属性）

## PlayerBaseInfo 属性（注意大写字母开头！）

`api.player_base_info()` 返回 PlayerBaseInfo 对象，属性如下：
- `.Cash` (int) — 现金
- `.Resources` (int) — 资源
- `.Power` (int) — 剩余电力 = PowerProvided - PowerDrained
- `.PowerDrained` (int) — 消耗的电力
- `.PowerProvided` (int) — 提供的电力

**判断是否断电**: `info.Power < 0` 或 `info.PowerDrained > info.PowerProvided`
**没有** `.power_ok` / `.cash` / `.get()` 这些属性！PlayerBaseInfo 不是字典！

## API 方法（完整签名）

### 生产相关
- `api.deploy_mcv_and_wait(wait_time=1.0)` — 展开基地车
- `api.ensure_can_produce_unit(unit_name: str) -> bool` — 确保能生产某单位/建筑（自动建前置）
- `api.produce_wait(unit_type: str, quantity: int, auto_place_building=True)` — 生产并等待完成（阻塞）

### 查询相关
- `api.query_actor(query_params: TargetsQueryParam) -> List[Actor]` — 查询当前可见的单位
- `api.query_combat_units() -> List[Actor]` — **查询己方所有战斗单位**（自动排除矿车/工程师/基地车）
- `api.query_actor_with_frozen(query_params: TargetsQueryParam) -> Tuple[List[Actor], List[FrozenActor]]` — 查询可见单位+残影
- `api.unit_attribute_query(actors: Sequence[Actor]) -> Dict` — 查询单位属性
- `api.query_production_queue(queue_type: str) -> Dict` — 查询生产队列（Building/Infantry/Vehicle/Aircraft）
- `api.player_base_info() -> PlayerBaseInfo` — 查询经济和电力信息

### 进攻相关（推荐用 dispatch_attack）
- `api.dispatch_attack(actors: Sequence[Actor])` — **推荐进攻方式**：将单位交给攻击系统，自动寻敌、分配目标、攻击建筑，持续作战直到手动停止
- `api.dispatch_explore(actors: Sequence[Actor])` — 派遣单位自动探索地图
- `api.attack_move(actors: Sequence[Actor], location: Location)` — 攻击移动到位置（路上遇敌才交战，到达后停下）
- `api.attack_target(attacker: Actor, target: Actor) -> bool` — 指定单个单位攻击单个目标

### 直接单位控制
- `api.move_units(actors: Sequence[Actor], location: Location, attack_move=False)` — 移动到指定位置
- `api.stop_units(actors: Sequence[Actor])` — 停止单位行动
- `api.repair(actors: Sequence[Actor])` — 修理建筑或载具
- `api.harvester_mine(harvesters: Sequence[Actor])` — 采矿车采矿
- `api.form_group(actors: Sequence[Actor], group_id: int)` — 编组
- `api.set_rally_point(buildings: Sequence[Actor], location: Location)` — 设置集结点

## 进攻策略说明（重要）

- **进攻/出击/全军出击 → 用 `dispatch_attack`**，它会自动寻找敌人（包括建筑）并持续攻击
- **移动到某位置 → 用 `attack_move`**，只在路上遇敌时交战
- **进攻时必须用 `query_combat_units()` 获取战斗单位**，不要用 `query_actor(faction="自己")` 因为会包含矿车！
- 矿车、工程师、基地车是非战斗单位，永远不要派去进攻

### 建筑相关
- `api.place_building(queue_type: str, location: Optional[Location] = None)` — 放置建筑
- `api.manage_production(queue_type: str, action: str)` — 管理队列（pause/cancel/resume）

## TargetsQueryParam 构造参数

```
TargetsQueryParam(
    type: Optional[List[str]] = None,       # 单位类型名称列表，如 ["步兵", "重坦"]
    faction: Optional[str] = None,          # 阵营: "自己" | "敌人" | "中立"
    group_id: Optional[List[int]] = None,   # 编组 ID 列表
    restrain: Optional[List[dict]] = None,  # 约束: [{"distance": int}, {"visible": bool}, {"maxnum": int}]
    location: Optional[Location] = None,    # 配合 distance 使用
    direction: Optional[str] = None,        # 配合 maxnum 使用
    range: Optional[str] = None             # "screen" | "selected" | "all"(默认)
)
```

**注意**：没有 owner/include/exclude/categories 这些参数！

## 可用的单位/建筑名称

建筑: 电厂、兵营、矿场、战车工厂/车间、雷达、维修中心、核电站、科技中心、机场、狗窝、火焰塔、特斯拉塔、防空炮、建造厂
步兵: 步兵、火箭兵、工程师、掷弹兵、军犬/狗、喷火兵、磁暴步兵
载具: 矿车、装甲车/APC、防空车、重坦/重型坦克、V2火箭发射车/v2、猛犸坦克/天启坦克、特斯拉坦克、吉普车
飞机: 雅克战机、米格战机、雌鹿直升机、运输直升机

**电力不足时**：建造"电厂"（基础）或"核电站"（高级，提供更多电力）

## __result__ 格式

```python
__result__ = {"success": True/False, "message": "描述结果", "observations": ""}
```

## 正确示例

### 示例1：查询并派遣步兵探索
```python
try:
    infantry = api.query_actor(TargetsQueryParam(type=["步兵"], faction="自己"))
    if not infantry:
        __result__ = {"success": False, "message": "没有步兵可用", "observations": ""}
    else:
        api.dispatch_explore(infantry)
        __result__ = {"success": True, "message": f"已派遣{len(infantry)}个步兵探索", "observations": ""}
except Exception as e:
    __result__ = {"success": False, "message": f"失败: {e}", "observations": ""}
```

### 示例2：全军出击 / 进攻（用 dispatch_attack + query_combat_units）
```python
try:
    fighters = api.query_combat_units()
    if not fighters:
        __result__ = {"success": False, "message": "没有战斗单位", "observations": ""}
    else:
        api.dispatch_attack(fighters)
        __result__ = {"success": True, "message": f"已派遣{len(fighters)}个战斗单位出击", "observations": ""}
except Exception as e:
    __result__ = {"success": False, "message": f"失败: {e}", "observations": ""}
```

### 示例3：修理受损建筑
```python
try:
    buildings = api.query_actor(TargetsQueryParam(faction="自己"))
    damaged = [b for b in buildings if b.hppercent is not None and b.hppercent < 100]
    if damaged:
        api.repair(damaged)
        __result__ = {"success": True, "message": f"正在修理{len(damaged)}个受损建筑/单位", "observations": ""}
    else:
        __result__ = {"success": True, "message": "没有受损建筑", "observations": ""}
except Exception as e:
    __result__ = {"success": False, "message": f"失败: {e}", "observations": ""}
```

### 示例4：检查电力并建发电厂
```python
try:
    info = api.player_base_info()
    if info.Power < 0:
        api.produce_wait("核电站", 1, auto_place_building=True)
        __result__ = {"success": True, "message": f"断电中(电力={info.Power})，正在建造核电站", "observations": ""}
    else:
        __result__ = {"success": True, "message": f"电力正常: {info.Power} (供应{info.PowerProvided}/消耗{info.PowerDrained})", "observations": ""}
except Exception as e:
    __result__ = {"success": False, "message": f"失败: {e}", "observations": ""}
```

### 示例5：继续造部队（抽象指令的处理方式）
```python
try:
    api.produce_wait("重坦", 3, auto_place_building=True)
    __result__ = {"success": True, "message": "正在生产3辆重坦", "observations": ""}
except Exception as e:
    __result__ = {"success": False, "message": f"失败: {e}", "observations": ""}
```
"""


def build_codegen_user_prompt(
    command: str,
    game_state: str,
    api_rules: str,
    history: Optional[str] = None
) -> str:
    """构建用户 prompt"""
    parts = [
        "[Player Command]",
        command,
        "",
        "[Current Game State]",
        game_state,
        "",
        "[Available API]",
        api_rules,
    ]
    
    if history:
        parts.extend([
            "",
            "[Recent History]",
            history
        ])
    
    parts.extend([
        "",
        "Now generate Python code to execute the player's command.",
        "Output code only, no explanation."
    ])
    
    return "\n".join(parts)


class CodeGenNode:
    """
    单一代码生成节点
    
    职责：
    1. 接收玩家指令
    2. 结合游戏状态
    3. 生成可执行的 Python 代码
    """
    
    def __init__(self, model: ModelAdapter):
        self.model = model
    
    def generate(
        self,
        command: str,
        game_state: str,
        api_rules: str,
        history: Optional[str] = None
    ) -> CodeGenResult:
        """
        生成代码
        
        Args:
            command: 玩家指令
            game_state: 当前游戏状态
            api_rules: 可用的 API 文档
            history: 最近的执行历史（可选）
        
        Returns:
            CodeGenResult: 生成的代码和原始响应
        """
        user_prompt = build_codegen_user_prompt(
            command=command,
            game_state=game_state,
            api_rules=api_rules,
            history=history
        )
        
        logger.debug("CodeGenNode: generating code for command: %s", command)
        
        response = self.model.complete(
            system=CODEGEN_SYSTEM_PROMPT,
            user=user_prompt,
            metadata={"node": "codegen"}
        )
        
        # 清理代码（移除可能的 markdown 围栏）
        code = self._clean_code(response.text)
        
        logger.info("CodeGenNode: generated code length=%d", len(code))
        logger.debug("CodeGenNode: code=\n%s", code)
        
        return CodeGenResult(code=code, raw_response=response)
    
    def _clean_code(self, text: str) -> str:
        """清理代码，移除 markdown 围栏、import 语句等"""
        if not text:
            return ""

        # 移除 ```python ... ``` 或 ``` ... ```
        cleaned = re.sub(
            r"^```(?:python)?\s*|\s*```$",
            "",
            text.strip(),
            flags=re.IGNORECASE | re.MULTILINE
        )

        # 移除 import / from ... import 语句（LLM 有时会忽略 no-import 规则）
        lines = cleaned.strip().splitlines()
        filtered = []
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                logger.warning("CodeGenNode: stripped import line: %s", stripped)
                continue
            filtered.append(line)

        return "\n".join(filtered).strip()
