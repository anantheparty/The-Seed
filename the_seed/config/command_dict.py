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
            "部署基地",
            "展开建造车",
            "展开建造厂",
            "建造厂展开",
            "mcv部署",
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
            "产",
            "做",
            "来",
            "来个",
            "来一个",
            "来一辆",
            "搞",
            "造一个",
            "造一辆",
            "做一个",
            "做一辆",
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
    "attack": {
        "synonyms": [
            "攻击",
            "进攻",
            "打",
            "集火",
            "冲",
            "突袭",
            "火力压制",
            "干掉",
            "消灭",
        ],
        "template": """
try:
    attackers = api.query_actor($attackers)
    targets = api.query_actor($targets)
    if not attackers or not targets:
        raise RuntimeError("未找到攻击者或目标")
    api.dispatch_attack(attackers, targets[0])
    logger.info("已下达攻击指令")
    __result__ = {
        "success": True,
        "message": "已下达攻击指令",
        "observations": ""
    }
except Exception as e:
    __result__ = {
        "success": False,
        "message": f"执行失败: {e}",
        "observations": ""
    }
""",
    },
    "explore": {
        "synonyms": [
            "侦察",
            "探索",
            "探路",
            "巡查",
            "查看周围",
            "去看看",
            "搜索",
        ],
        "template": """
try:
    units = api.query_actor($units)
    if not units:
        raise RuntimeError("未找到可侦察单位")
    api.dispatch_explore(units)
    logger.info("已派出侦察单位")
    __result__ = {
        "success": True,
        "message": "已派出侦察单位",
        "observations": ""
    }
except Exception as e:
    __result__ = {
        "success": False,
        "message": f"执行失败: {e}",
        "observations": ""
    }
""",
    },
    "mine": {
        "synonyms": [
            "采矿",
            "挖矿",
            "采集",
            "采资源",
            "去矿区",
            "去采矿",
        ],
        "template": """
try:
    harvesters = api.query_actor($harvesters)
    if not harvesters:
        raise RuntimeError("未找到矿车")
    api.harvester_mine(harvesters[0])
    logger.info("已下达采矿指令")
    __result__ = {
        "success": True,
        "message": "已下达采矿指令",
        "observations": ""
    }
except Exception as e:
    __result__ = {
        "success": False,
        "message": f"执行失败: {e}",
        "observations": ""
    }
""",
    },
    "query_actor": {
        "synonyms": [
            "查询单位",
            "查看单位",
            "列出单位",
            "查询兵力",
            "查看兵力",
            "列出兵力",
            "查兵",
            "查单位",
        ],
        "template": """
try:
    actors = api.query_actor($targets)
    __result__ = {
        "success": True,
        "message": "查询完成",
        "observations": f"actor_count={len(actors)}"
    }
except Exception as e:
    __result__ = {
        "success": False,
        "message": f"执行失败: {e}",
        "observations": ""
    }
""",
    },
}

# Simple entity lexicon with aliases -> canonical name.
ENTITY_ALIASES = {
    "基地车": ["基地车", "mcv"],
    "电厂": ["电厂", "发电厂", "电站"],
    "兵营": ["兵营", "营房"],
    "矿场": ["矿场", "采矿场", "精炼厂", "矿石精炼厂"],
    "战车工厂": ["战车工厂", "车间", "坦克厂", "坦克工厂", "载具工厂"],
    "雷达站": ["雷达站", "雷达", "侦察站", "雷达圆顶"],
    "维修厂": ["维修厂", "修理厂", "维修站", "修理站"],
    "核电站": ["核电站", "核电厂", "大电", "大电厂", "高级电厂"],
    "空军基地": ["空军基地", "机场", "飞机场", "航空站"],
    "科技中心": ["科技中心", "高科技", "高科技中心", "研究中心", "实验室"],
    "火焰塔": ["火焰塔", "喷火塔", "喷火碉堡", "防御塔"],
    "特斯拉塔": ["特斯拉塔", "电塔", "特斯拉线圈", "高级防御塔"],
    "防空导弹": ["防空导弹", "防空塔", "防空炮", "防空炮塔", "防空"],
    "步兵": ["步兵", "大兵", "步枪兵", "兵"],
    "火箭兵": ["火箭兵", "火箭筒兵", "炮兵", "导弹兵"],
    "矿车": ["矿车", "采矿车", "harvester"],
    "装甲运输车": ["装甲运输车", "装甲车", "运兵车"],
    "防空车": ["防空车", "防空炮车", "移动防空车"],
    "坦克": ["坦克", "战车"],
    "重型坦克": ["重型坦克", "重坦", "犀牛坦克", "犀牛"],
    "超重型坦克": ["超重型坦克", "猛犸坦克", "猛犸", "天启坦克", "天启"],
    "雅克战机": ["雅克战机", "雅克", "雅克攻击机", "苏联战机"],
    "米格战机": ["米格战机", "米格", "米格战斗机"],
    "建造厂": ["建造厂", "基地", "主基地", "主要建筑"],
}

DIRECTION_ALIASES = {
    "北": ["北", "上"],
    "东北": ["东北", "右上"],
    "东": ["东", "右"],
    "东南": ["东南", "右下"],
    "南": ["南", "下"],
    "西南": ["西南", "左下"],
    "西": ["西", "左"],
    "西北": ["西北", "左上"],
}

FACTION_ALIASES = {
    "己方": ["己方", "自己", "我方"],
    "敌方": ["敌方", "敌人", "对方"],
    "中立": ["中立"],
}

RANGE_ALIASES = {
    "all": ["全部", "所有", "全图"],
    "screen": ["屏幕", "视野"],
    "selected": ["选中", "当前选择"],
}
