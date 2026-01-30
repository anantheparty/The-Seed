from __future__ import annotations

# Default command dictionary for OpenRA agent demo.
# Keep this small and extensible; add more intents as needed.

COMMAND_DICT = {
    "deploy_mcv": {
        "synonyms": [
            "展开基地车",
            "部署基地车",
            "展开基地",
            "展开mcv",
            "部署mcv",
            "deploy mcv",
        ],
        "template": """
try:
    api.deploy_mcv_and_wait(wait_time=1.0)
    logger.info(\"基地车已展开\")
    __result__ = {
        \"success\": True,
        \"message\": \"已展开基地车\",
        \"observations\": \"\"
    }
except Exception as e:
    __result__ = {
        \"success\": False,
        \"message\": f\"执行失败: {e}\",
        \"observations\": \"\"
    }
""",
    },
    "produce": {
        "synonyms": [
            "建造",
            "生产",
            "训练",
            "制造",
            "造",
            "出",
        ],
        "template": """
try:
    if not api.ensure_can_produce_unit(\"$unit\"):
        raise RuntimeError(\"不能生产$unit：前置不足或失败\")
    api.produce_wait(\"$unit\", $count, auto_place_building=True)
    logger.info(\"生产了$count个$unit\")
    __result__ = {
        \"success\": True,
        \"message\": \"已生产$count个$unit\",
        \"observations\": \"\"
    }
except Exception as e:
    __result__ = {
        \"success\": False,
        \"message\": f\"执行失败: {e}\",
        \"observations\": \"\"
    }
""",
    },
}

# Simple entity lexicon with aliases -> canonical name.
ENTITY_ALIASES = {
    "基地车": ["基地车", "mcv"],
    "电厂": ["电厂", "发电厂", "电站"],
    "兵营": ["兵营", "营房"],
    "步兵": ["步兵", "大兵", "步枪兵", "兵"],
    "矿车": ["矿车", "采矿车", "harvester"],
    "坦克": ["坦克", "战车"],
}
