"""
山峰库 - Mountain Library
=========================
中国可攀山峰查询库，支持按省份、地理分区、难度、海拔、季节气候等多维度筛选。

数据来源：中国可攀山峰库.xlsx

使用示例：
    from mountain_library import MountainLibrary

    lib = MountainLibrary()

    # 全部入门级山峰
    beginner = lib.filter(difficulty='入门')

    # 西南地区海拔 3000m+ 进阶山峰
    high = lib.filter(region='西南', difficulty='进阶', min_elevation=3000)

    # 按名称搜索
    mt = lib.find_by_name('华山')

    # 根据季节筛选
    winter_mts = lib.filter_season('冬季')
"""

import json
import os
import re
from typing import Any, List, Optional


DIFFICULTY_LEVELS = {'入门': 1, '进阶': 2, '高难度': 3}
LEVEL_NAMES = {1: '入门', 2: '进阶', 3: '高难度'}


class MountainLibrary:
    """中国可攀山峰库查询类"""

    def __init__(self, json_path: str = None):
        if json_path is None:
            json_path = os.path.join(os.path.dirname(__file__), 'mountains.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        self.mountains = self.data['mountains']
        self.meta = self.data['_meta']

    # ---------- 基础 ----------
    def all(self) -> List[dict]: return list(self.mountains)
    def count(self) -> int: return len(self.mountains)
    def get_regions(self) -> list:
        return sorted(set(m['region'] for m in self.mountains if m['region']))
    def get_difficulties(self) -> list:
        return sorted(set(m['difficulty'] for m in self.mountains if m['difficulty']))
    def get_provinces(self) -> list:
        return sorted(set(m['province'] for m in self.mountains if m['province']))

    def find_by_name(self, keyword: str) -> List[dict]:
        """按山峰名称模糊搜索"""
        return [m for m in self.mountains if keyword in m['name']]

    def find_by_id(self, mid: str) -> Optional[dict]:
        for m in self.mountains:
            if m['id'] == mid: return m
        return None

    # ---------- 多维筛选 ----------
    def filter(self,
               region: str = None,
               province: str = None,
               difficulty: str = None,
               difficulty_level: int = None,
               min_elevation: int = None,
               max_elevation: int = None,
               min_climb: int = None,
               max_climb: int = None,
               max_distance_km: float = None,
               max_hours: float = None,
               risk_keyword: str = None,
               max_wind: float = None,
               ) -> List[dict]:
        """多维度筛选山峰

        Args:
            region: 地理分区（华东/华中/华南/华北/西北/西南/东北）
            province: 省份
            difficulty: 难度（入门/进阶/高难度）
            difficulty_level: 难度等级（1/2/3）
            min_elevation: 最低最高点海拔 m
            max_elevation: 最高最高点海拔 m
            min_climb: 最低累计爬升 m
            max_climb: 最高累计爬升 m
            max_distance_km: 最大往返路程 km
            max_hours: 最大预估往返时长 h
            risk_keyword: 风险关键词（如 "雪"/"湿滑"）
            max_wind: 最大平均风速 m/s

        Returns:
            匹配的山峰列表
        """
        results = []
        for m in self.mountains:
            if region and m.get('region') != region: continue
            if province and m.get('province') != province: continue
            if difficulty and m.get('difficulty') != difficulty: continue
            if difficulty_level is not None and m.get('difficulty_level') != difficulty_level: continue
            if min_elevation and m.get('peak_elevation') is not None and m['peak_elevation'] < min_elevation: continue
            if max_elevation and m.get('peak_elevation') is not None and m['peak_elevation'] > max_elevation: continue
            if min_climb and m.get('total_climb_m') is not None and m['total_climb_m'] < min_climb: continue
            if max_climb and m.get('total_climb_m') is not None and m['total_climb_m'] > max_climb: continue
            if max_distance_km and m.get('round_trip_km') is not None and m['round_trip_km'] > max_distance_km: continue
            if max_hours and m.get('round_trip_hours') is not None and m['round_trip_hours'] > max_hours: continue
            if max_wind and m.get('avg_wind_mps') is not None and m['avg_wind_mps'] > max_wind: continue
            if risk_keyword:
                text = (m.get('risks', '') or '') + '、'.join(m.get('risk_list', []))
                if risk_keyword not in text: continue
            results.append(m)
        return results

    # ---------- 季节筛选 ----------
    def filter_season(self, season: str, min_peak_temp: float = None,
                      max_peak_temp: float = None) -> List[dict]:
        """按季节筛选适合的山峰（根据山顶平均气温）

        Args:
            season: 季节（"春季"/"夏季"/"春夏"/"秋季"/"冬季"/"秋冬"）
            min_peak_temp: 山顶最低期望温度 ℃
            max_peak_temp: 山顶最高期望温度 ℃

        Returns:
            匹配的山峰列表，附 season_peak_temp 字段
        """
        season_map = {
            '春季': 'ss_peak', '夏季': 'ss_peak', '春夏': 'ss_peak',
            '秋季': 'aw_peak', '冬季': 'aw_peak', '秋冬': 'aw_peak'
        }
        key = season_map.get(season, 'ss_peak')
        results = []
        for m in self.mountains:
            t = m.get(key) or {}
            tmin, tmax = t.get('min'), t.get('max')
            if tmin is None: continue
            if min_peak_temp is not None and tmax < min_peak_temp: continue
            if max_peak_temp is not None and tmin > max_peak_temp: continue
            m2 = dict(m)
            m2['season_peak_temp'] = t.get('raw', '')
            results.append(m2)
        return results

    # ---------- 与人群分类联动 ----------
    def recommend_by_user(self, user_assessment: dict) -> List[dict]:
        """根据 crowd_classification 的评估结果推荐合适的山峰

        Args:
            user_assessment: CrowdClassifier.assess() 返回值

        Returns:
            推荐山峰列表（按爬升高度排序）
        """
        if not user_assessment.get('suitable', True):
            return []

        cats = user_assessment.get('categories', {})
        age_cat = cats.get('age')
        bmi_cat = cats.get('bmi')

        # 年龄 → 最大难度
        max_level = 3
        if age_cat:
            age_range = age_cat.get('range', '')
            if '18岁以下' in age_range or '65岁以上' in age_range:
                max_level = 1
            elif '35' in age_range or '50' in age_range:
                max_level = min(max_level, 2)

        # 偏瘦/体质弱 → 限制爬升
        max_climb = None
        if bmi_cat and bmi_cat.get('type') in ('偏瘦', '肥胖'):
            max_climb = 1200

        results = self.filter(difficulty_level=max_level, max_climb=max_climb)
        results.sort(key=lambda m: m.get('total_climb_m') or 9999)
        return results

    # ---------- 统计 ----------
    def stats(self) -> dict:
        regions, diffs = {}, {}
        elevs = []
        for m in self.mountains:
            r = m.get('region', '未知')
            regions[r] = regions.get(r, 0) + 1
            d = m.get('difficulty', '未知')
            diffs[d] = diffs.get(d, 0) + 1
            if m.get('peak_elevation'):
                elevs.append(m['peak_elevation'])
        return {
            'total': len(self.mountains),
            'by_region': regions,
            'by_difficulty': diffs,
            'elevation_m': {
                'min': min(elevs) if elevs else None,
                'max': max(elevs) if elevs else None,
                'avg': round(sum(elevs)/len(elevs)) if elevs else None,
            }
        }


# ---------- 便捷函数 ----------
_default = None
def _get():
    global _default
    if _default is None:
        _default = MountainLibrary()
    return _default

def filter(**kw): return _get().filter(**kw)
def find_by_name(kw): return _get().find_by_name(kw)
def get_stats(): return _get().stats()


if __name__ == '__main__':
    lib = MountainLibrary()
    print(f'📊 山峰库: {lib.stats()}')
    print(f'🗺️  分区: {lib.get_regions()}')
    print(f'⚡ 难度: {lib.get_difficulties()}')

    print('\n--- 入门 TOP5（低爬升）---')
    b = lib.filter(difficulty='入门')
    b.sort(key=lambda m: m.get('total_climb_m') or 0)
    for m in b[:5]:
        print(f"  {m['id']} {m['name']:12s} {m['region']:4s} 海拔{m['peak_elevation']:5d}m 爬升{m['total_climb_m']:4d}m {m['round_trip_km']:4g}km/{m['round_trip_hours']:g}h")

    print('\n--- 西南 3000m+ ---')
    for m in lib.filter(region='西南', min_elevation=3000):
        print(f"  {m['id']} {m['name']:12s} 海拔{m['peak_elevation']:5d}m {m['difficulty']}")

    print('\n--- 冬季适合（山顶 -10~5℃）---')
    for m in lib.filter_season('冬季', max_peak_temp=5, min_peak_temp=-15)[:8]:
        print(f"  {m['id']} {m['name']:12s} 山顶{m['season_peak_temp']}")

    print('\n--- 高风险"雪崩" ---')
    for m in lib.filter(risk_keyword='雪崩'):
        print(f"  {m['id']} {m['name']}: {m['risks']}")
