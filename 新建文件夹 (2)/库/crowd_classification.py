"""
人群分类库 - Crowd Classification Library
==========================================
用于判断用户是否适合登山，并根据人群类别推荐登山外套选择要点。

数据来源：人群分类库.docx

使用示例：
    from crowd_classification import CrowdClassifier
    
    classifier = CrowdClassifier()
    
    user = {
        "gender": "男",
        "age": 30,
        "height": 175,  # cm
        "weight": 70,   # kg
        "health_status": "健康",
        "season": "夏季"
    }
    
    result = classifier.assess(user)
    print(result)
"""

import json
import os
from typing import Any


def calculate_bmi(height_cm: float, weight_kg: float) -> float:
    """计算 BMI 指数

    Args:
        height_cm: 身高，单位 cm
        weight_kg: 体重，单位 kg

    Returns:
        BMI 值，保留 1 位小数
    """
    height_m = height_cm / 100.0
    if height_m <= 0:
        return 0.0
    bmi = weight_kg / (height_m ** 2)
    return round(bmi, 1)


class CrowdClassifier:
    """登山人群分类器

    根据用户信息判断是否适合登山，并匹配登山服选择要点。
    """

    def __init__(self, data_path: str = None):
        """初始化分类器

        Args:
            data_path: JSON 数据文件路径，默认为同目录下 crowd_classification.json
        """
        if data_path is None:
            data_path = os.path.join(os.path.dirname(__file__), "crowd_classification.json")
        self.data_path = data_path
        self.data = self._load_data()

    def _load_data(self) -> dict:
        """加载 JSON 数据文件"""
        with open(self.data_path, "r", encoding="utf-8") as f:
            return json.load(f)

    # ------------------------------------------------------------------
    # 不适合登山人群判断
    # ------------------------------------------------------------------

    def is_unsuitable(self, health_status: str, age: int,
                      bmi: float = None, weight: float = None) -> list:
        """判断用户是否属于不适合登山的高风险人群

        Args:
            health_status: 健康状况描述（自由文本）
            age: 年龄
            bmi: BMI 值（可选，不传则根据 weight/height 计算）
            weight: 体重 kg（可选，用于判断极度肥胖）

        Returns:
            匹配到的不适合登山人群列表（含风险和建议），空列表表示适合
        """
        matched = []
        unsuitable_list = self.data.get("unsuitable_people", [])

        health_status = health_status or ""

        # 关键词匹配健康状况
        for item in unsuitable_list:
            keywords = item.get("keywords", [])
            exclude_keywords = item.get("exclude_keywords", [])
            for kw in keywords:
                if kw in health_status:
                    # 检查排除关键词（如"控制良好"的高血压不应判为不适合）
                    if exclude_keywords and any(ek in health_status for ek in exclude_keywords):
                        break
                    matched.append(item)
                    break

        # 高龄且不运动
        if age >= 70 and ("不运动" in health_status or "缺乏锻炼" in health_status):
            # U10 已通过关键词匹配
            pass

        # 极度肥胖判断
        if bmi is not None:
            if bmi >= 32 and ("不运动" in health_status or "缺乏锻炼" in health_status or "无锻炼" in health_status):
                # 避免重复添加
                if not any(m["id"] == "U05" for m in matched):
                    u05 = next((u for u in unsuitable_list if u["id"] == "U05"), None)
                    if u05:
                        matched.append(u05)

        return matched

    # ------------------------------------------------------------------
    # 分类匹配函数
    # ------------------------------------------------------------------

    def match_age(self, age: int) -> dict:
        """根据年龄匹配年龄段分类

        Args:
            age: 年龄

        Returns:
            匹配到的年龄段分类信息
        """
        for cat in self.data.get("age_categories", []):
            if cat["age_min"] <= age <= cat["age_max"]:
                return cat
        return None

    def match_bmi(self, bmi: float) -> dict:
        """根据 BMI 匹配体型分类

        Args:
            bmi: BMI 值

        Returns:
            匹配到的体型分类信息
        """
        for cat in self.data.get("bmi_categories", []):
            if cat["bmi_min"] <= bmi <= cat["bmi_max"]:
                return cat
        return None

    def match_health(self, health_status: str) -> list:
        """根据健康状况匹配健康分类

        Args:
            health_status: 健康状况描述（自由文本）

        Returns:
            匹配到的健康分类列表
        """
        matched = []
        health_status = health_status or ""
        for cat in self.data.get("health_categories", []):
            for kw in cat.get("keywords", []):
                if kw in health_status:
                    matched.append(cat)
                    break
        return matched

    def match_season(self, season: str) -> list:
        """根据季节/天气匹配季节分类

        Args:
            season: 季节或天气描述（如 "夏季"、"多雨"、"冬季"）

        Returns:
            匹配到的季节分类列表
        """
        matched = []
        season = season or ""
        for cat in self.data.get("season_categories", []):
            for kw in cat.get("keywords", []):
                if kw in season:
                    matched.append(cat)
                    break
        return matched

    # ------------------------------------------------------------------
    # 综合评估（主入口）
    # ------------------------------------------------------------------

    def assess(self, user: dict) -> dict:
        """综合评估用户是否适合登山，并给出分类与推荐

        Args:
            user: 用户信息字典，支持以下字段：
                - gender: 性别
                - age: 年龄（必填）
                - height: 身高 cm（可选，用于计算 BMI）
                - weight: 体重 kg（可选，用于计算 BMI）
                - bmi: BMI 值（可选，优先使用）
                - health_status: 健康状况描述（必填）
                - season: 目标季节/天气（必填）

        Returns:
            评估结果字典：
                - suitable: bool，是否适合登山
                - warnings: list，不适合登山的风险警告列表
                - categories: dict，各维度匹配到的分类
                - jacket_tips: list，综合登山服选择要点
        """
        age = user.get("age", 0)
        height = user.get("height")
        weight = user.get("weight")
        bmi = user.get("bmi")
        health_status = user.get("health_status", "")
        season = user.get("season", "")

        # --- 1. 计算 BMI ---
        if bmi is None and height and weight:
            bmi = calculate_bmi(height, weight)

        # --- 2. 判断不适合登山 ---
        unsuitable = self.is_unsuitable(health_status, age, bmi, weight)

        # --- 3. 各维度分类匹配 ---
        age_cat = self.match_age(age)
        bmi_cat = self.match_bmi(bmi) if bmi else None
        health_cats = self.match_health(health_status)
        season_cats = self.match_season(season)

        # --- 4. 汇总登山服选择要点 ---
        all_tips = []
        if age_cat:
            all_tips.append(f"[年龄] {age_cat['tips']}")
        if bmi_cat:
            all_tips.append(f"[体型] {bmi_cat['tips']}")
        for hc in health_cats:
            all_tips.append(f"[健康] {hc['tips']}")
        for sc in season_cats:
            all_tips.append(f"[季节] {sc['tips']}")

        return {
            "suitable": len(unsuitable) == 0,
            "warnings": [
                {
                    "type": u["type"],
                    "risk": u["risk"],
                    "suggestion": u["suggestion"]
                }
                for u in unsuitable
            ],
            "categories": {
                "age": age_cat,
                "bmi": bmi_cat,
                "health": health_cats,
                "season": season_cats
            },
            "bmi": bmi,
            "jacket_tips": all_tips,
            "summary": self._generate_summary(unsuitable, age_cat, bmi_cat, health_cats, season_cats)
        }

    def _generate_summary(self, unsuitable, age_cat, bmi_cat, health_cats, season_cats) -> str:
        """生成可读的评估摘要"""
        if unsuitable:
            names = [u["type"] for u in unsuitable]
            summary = f"⚠️ 不建议登山：属于{'+'.join(names)}人群。"
            for u in unsuitable:
                summary += f"\n  - {u['type']}：{u['risk']} → {u['suggestion']}"
            return summary

        summary = "✅ 适合登山。"
        parts = []
        if age_cat:
            parts.append(f"年龄{age_cat['range']}")
        if bmi_cat:
            parts.append(f"体型{bmi_cat['type']}")
        if parts:
            summary += " 人群：" + "、".join(parts) + "。"
        if health_cats:
            for hc in health_cats:
                summary += f"\n  · {hc['condition']}：{hc['tips']}"
        if season_cats:
            for sc in season_cats:
                summary += f"\n  · {sc['season']}：{sc['tips']}"
        return summary

    # ------------------------------------------------------------------
    # 便捷查询
    # ------------------------------------------------------------------

    def query(self, category: str, value: str = None) -> Any:
        """查询分类数据

        Args:
            category: 分类名称，可选：
                'unsuitable', 'age', 'bmi', 'health', 'season', 'all'
            value: 关键词或数值，用于过滤（可选）

        Returns:
            匹配的数据
        """
        mapping = {
            "unsuitable": "unsuitable_people",
            "age": "age_categories",
            "bmi": "bmi_categories",
            "health": "health_categories",
            "season": "season_categories"
        }

        if category == "all":
            return self.data

        key = mapping.get(category)
        if not key:
            return None

        items = self.data.get(key, [])

        if value is None:
            return items

        # 关键词搜索
        results = []
        for item in items:
            text = json.dumps(item, ensure_ascii=False).lower()
            if str(value).lower() in text:
                results.append(item)
        return results if results else items


# ----------------------------------------------------------------------
# 模块级便捷函数
# ----------------------------------------------------------------------

_default_classifier = None


def _get_classifier() -> CrowdClassifier:
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = CrowdClassifier()
    return _default_classifier


def assess(user: dict) -> dict:
    """便捷函数：综合评估用户登山适配性"""
    return _get_classifier().assess(user)


def judge_suitable(health_status: str, age: int,
                   bmi: float = None, weight: float = None) -> list:
    """便捷函数：判断是否属于不适合登山人群"""
    return _get_classifier().is_unsuitable(health_status, age, bmi, weight)


def calculate_bmi_value(height_cm: float, weight_kg: float) -> float:
    """便捷函数：计算 BMI"""
    return calculate_bmi(height_cm, weight_kg)


if __name__ == "__main__":
    # 简单自测
    classifier = CrowdClassifier()

    test_users = [
        {
            "gender": "男", "age": 28, "height": 175, "weight": 70,
            "health_status": "健康", "season": "夏季晴朗"
        },
        {
            "gender": "女", "age": 55, "height": 160, "weight": 55,
            "health_status": "高血压控制良好，体质较弱", "season": "秋季多雨"
        },
        {
            "gender": "男", "age": 45, "height": 170, "weight": 95,
            "health_status": "极度肥胖，几乎不运动", "season": "冬季"
        },
        {
            "gender": "女", "age": 35, "height": 165, "weight": 50,
            "health_status": "对冷过敏，膝关节旧伤", "season": "昼夜温差大"
        }
    ]

    for i, user in enumerate(test_users, 1):
        print(f"\n{'='*50}")
        print(f"测试用户 {i}：{user['gender']}，{user['age']}岁，"
              f"{user['height']}cm/{user['weight']}kg，"
              f"BMI={calculate_bmi_value(user['height'], user['weight'])}")
        print(f"健康：{user['health_status']} | 季节：{user['season']}")
        print('-' * 50)

        result = classifier.assess(user)
        print(result["summary"])
        if result["jacket_tips"]:
            print("\n登山服推荐要点：")
            for tip in result["jacket_tips"]:
                print(f"  ✔ {tip}")
