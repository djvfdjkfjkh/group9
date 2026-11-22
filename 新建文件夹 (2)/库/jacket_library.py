"""
登山外套库 - Jacket Library
============================
登山外套产品查询库，支持按品牌、类别、价格、防水/防风、保暖等级、适宜温度等多维度筛选。

数据来源：登山外套库.xlsx（120 件外套，25 字段/件）

使用示例：
    from jacket_library import JacketLibrary

    lib = JacketLibrary()

    # 入门级外套（防水中+防风中+价格≤1000）
    budget = lib.filter(max_waterproof=2, max_windproof=2, max_price=1000)

    # 适合冬季、高海拔的强防水硬壳
    alpine = lib.filter(category='硬壳', min_waterproof=3, high_altitude=True,
                       max_temp=0)

    # 与人群/山峰库联动：给定人群+山峰 → 推荐外套
    recs = lib.recommend_by_context(user_assessment, mountain_info)
"""

import json
import os
import re
from typing import Any, List, Optional


class JacketLibrary:
    """登山外套库查询类"""

    def __init__(self, json_path: str = None):
        if json_path is None:
            json_path = os.path.join(os.path.dirname(__file__), 'jackets.json')
        with open(json_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
        self.jackets = self.data['jackets']
        self.meta = self.data['_meta']

    # ---------- 基础 ----------
    def all(self) -> List[dict]: return list(self.jackets)
    def count(self) -> int: return len(self.jackets)
    def get_brands(self) -> list: return self.meta['brands']
    def get_countries(self) -> list: return self.meta['brand_countries']
    def get_categories(self) -> list: return self.meta['categories']

    def find_by_name(self, keyword: str) -> List[dict]:
        """按品牌或产品名模糊搜索"""
        results = []
        for j in self.jackets:
            if keyword in (j.get('brand') or '') or keyword in (j.get('product_name') or ''):
                results.append(j)
        return results

    def find_by_id(self, jid: str) -> Optional[dict]:
        for j in self.jackets:
            if j['id'] == jid: return j
        return None

    # ---------- 多维筛选 ----------
    def filter(self,
               brand: str = None,
               category: str = None,       # '硬壳'/'软壳'/'三合一/可拆'/'羽绒服'/'棉服/保暖'/'蜡棉/防风'
               country: str = None,
               season: str = None,         # '春'/'夏'/'秋'/'冬'
               min_waterproof: int = None, # 1=弱 2=中 3=强
               max_waterproof: int = None,
               min_windproof: int = None,
               max_windproof: int = None,
               min_price: float = None,
               max_price: float = None,
               max_weight: float = None,   # g
               min_temp: float = None,     # 适宜最高温度 ≥ 此值
               max_temp: float = None,     # 适宜最低温度 ≤ 此值
               high_altitude: bool = None, # 是否适合高海拔
               is_single_layer: bool = None,
               has_inner: bool = None,
               detachable: bool = None,
               warmth_keyword: str = None, # '强保暖'/'轻量'/'中等'/'极寒'
               ) -> List[dict]:
        """多维度筛选外套

        Returns:
            匹配的外套列表
        """
        results = []
        for j in self.jackets:
            if brand and j.get('brand') != brand: continue
            if category and j.get('category_norm') != category: continue
            if country and j.get('brand_country') != country: continue
            if season and season not in (j.get('season_list') or []): continue

            wp = j.get('waterproof_level_num', 0)
            if min_waterproof is not None and wp < min_waterproof: continue
            if max_waterproof is not None and wp > max_waterproof: continue

            wd = j.get('windproof_level_num', 0)
            if min_windproof is not None and wd < min_windproof: continue
            if max_windproof is not None and wd > max_windproof: continue

            pr = j.get('price_range') or {}
            pmax = pr.get('max')
            pmin = pr.get('min')
            if max_price is not None and (pmax is None or pmax > max_price): continue
            if min_price is not None and (pmin is None or pmin < min_price): continue

            wg = j.get('weight_g_num')
            if max_weight is not None and wg is not None and wg > max_weight: continue

            tr = j.get('temp_range') or {}
            tmin, tmax = tr.get('min'), tr.get('max')
            if min_temp is not None and (tmax is None or tmax < min_temp): continue
            if max_temp is not None and (tmin is None or tmin > max_temp): continue

            if high_altitude is not None and j.get('high_altitude_bool') != high_altitude: continue
            if is_single_layer is not None and j.get('is_single_layer') != is_single_layer: continue
            if has_inner is not None and (j.get('has_inner') == '有') != has_inner: continue
            if detachable is not None and (j.get('detachable_inner') == '是') != detachable: continue
            if warmth_keyword and warmth_keyword not in (j.get('warmth_simple') or '')                     and warmth_keyword not in (j.get('warmth_level') or ''): continue

            results.append(j)
        return results

    # ---------- 场景推荐 ----------
    def recommend_by_context(self, user_assessment: dict = None,
                              mountain: dict = None,
                              season: str = None) -> List[dict]:
        """根据人群 + 山峰 + 季节上下文推荐外套

        Args:
            user_assessment: crowd_classification.assess() 返回值（可选）
            mountain: mountain_library 的山峰 dict（可选）
            season: 季节关键词（可选）

        Returns:
            推荐外套列表，按匹配度排序
        """
        # 从用户评估推导温度/防水需求
        target_min_temp, target_max_temp = None, None
        min_wp, min_wd = None, None

        if season:
            season_temp = {
                '春': (5, 20), '夏': (15, 30),
                '秋': (0, 15), '冬': (-15, 5),
                '秋冬': (-15, 10), '春夏': (5, 25),
            }
            t = season_temp.get(season, (None, None))
            target_min_temp, target_max_temp = t

        if mountain:
            # 从山峰数据获取山顶气温
            peak_temp_key = 'ss_peak' if season in ('春', '夏', '春夏') else 'aw_peak'
            pt = mountain.get(peak_temp_key) or {}
            if pt.get('min') is not None:
                target_min_temp = pt['min']
            if pt.get('max') is not None:
                target_max_temp = pt['max']

            # 降水/风 → 防水防风等级
            risk_text = (mountain.get('risks') or '') + '、'.join(mountain.get('risk_list', []))
            if any(k in risk_text for k in ['雨', '湿滑', '雾']):
                min_wp = 2
            if any(k in risk_text for k in ['风', '大风']):
                min_wd = 3

        # 人群特殊需求
        need_extra_warmth = False
        if user_assessment:
            bmi_cat = (user_assessment.get('categories') or {}).get('bmi')
            health_cats = (user_assessment.get('categories') or {}).get('health', [])
            if bmi_cat and bmi_cat.get('type') == '偏瘦':
                need_extra_warmth = True
            for hc in health_cats:
                if '冷' in (hc.get('condition') or '') or '体寒' in (hc.get('condition') or ''):
                    need_extra_warmth = True
                    break

        jackets = self.filter(
            min_waterproof=min_wp, min_windproof=min_wd,
            min_temp=target_min_temp, max_temp=target_max_temp,
        )

        # 匹配度打分
        def score(j):
            s = 0
            tr = j.get('temp_range') or {}
            if target_min_temp is not None and tr.get('min') is not None:
                # 温度下限接近目标 → 加分
                s -= abs(tr['min'] - target_min_temp)
            if need_extra_warmth and ('强保暖' in (j.get('warmth_simple') or '')
                                      or '强保暖' in (j.get('warmth_level') or '')):
                s += 10
            if j.get('high_altitude_bool'):
                s += 3
            return s

        jackets.sort(key=score, reverse=True)
        return jackets

    # ---------- 统计 ----------
    def stats(self) -> dict:
        brands = {}
        cats = {}
        prices = []
        for j in self.jackets:
            b = j.get('brand', '未知')
            brands[b] = brands.get(b, 0) + 1
            c = j.get('category_norm', '未知')
            cats[c] = cats.get(c, 0) + 1
            p = (j.get('price_range') or {}).get('max')
            if p: prices.append(p)
        return {
            'total': len(self.jackets),
            'by_brand': brands,
            'by_category': cats,
            'price_yuan': {
                'min': min(prices) if prices else None,
                'max': max(prices) if prices else None,
                'avg': round(sum(prices)/len(prices)) if prices else None,
            }
        }


# ---------- 便捷函数 ----------
_default = None
def _get():
    global _default
    if _default is None:
        _default = JacketLibrary()
    return _default

def filter(**kw): return _get().filter(**kw)
def find_by_name(kw): return _get().find_by_name(kw)
def get_stats(): return _get().stats()


if __name__ == '__main__':
    lib = JacketLibrary()
    print(f'📊 外套库: {lib.stats()}')
    print(f'🏷️  类别: {lib.get_categories()}')
    print(f'🎨 品牌数: {len(lib.get_brands())}')

    print('\n--- 强防水高海拔硬壳 ---')
    for j in lib.filter(category='硬壳', min_waterproof=3, high_altitude=True):
        print(f"  {j['id']} {j['brand']:16s} {j['product_name'][:20]:20s} {j['waterproof_level']}/{j['windproof_level']}  {j['temp_range_c']}")

    print('\n--- 入门性价比（防水≤中 价格≤1000）---')
    budget = lib.filter(max_waterproof=2, max_windproof=2, max_price=1000)
    budget.sort(key=lambda j: (j.get('price_range') or {}).get('min') or 0)
    for j in budget[:8]:
        pr = j.get('price_range') or {}
        print(f"  {j['id']} {j['brand']:16s} {j['product_name'][:18]:18s} ¥{pr.get('min','?')}-{pr.get('max','?')}")

    print('\n--- 冬季强保暖（防水≥中 温度上限≤0）---')
    for j in lib.filter(min_waterproof=2, max_temp=0, warmth_keyword='保暖')[:8]:
        print(f"  {j['id']} {j['brand']:16s} {j['product_name'][:20]:20s} {j['temp_range_c']} {j['warmth_simple']}")

    print('\n--- 夏季风壳（温度下限≥10 单层 防水≤中）---')
    for j in lib.filter(min_temp=10, max_waterproof=2, is_single_layer=True)[:5]:
        print(f"  {j['id']} {j['brand']:16s} {j['product_name'][:20]:20s} {j['temp_range_c']} {j['weight_g']}g")
