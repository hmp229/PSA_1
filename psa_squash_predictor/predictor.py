import numpy as np
import pandas as pd
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class PSAPredictor:
    def __init__(self):
        # 基于Joeri Hapers的历史数据进行权重调整
        self.ranking_weight = 0.4
        self.recent_form_weight = 0.3
        self.head_to_head_weight = 0.2
        self.experience_weight = 0.1

    def predict_match(self, player1_data: Dict, player2_data: Dict) -> Dict:
        """预测比赛结果"""
        try:
            # 计算各项得分
            p1_ranking_score = self._calculate_ranking_score(player1_data, player2_data)
            p1_form_score = self._calculate_form_score(player1_data, player2_data)
            p1_h2h_score = self._calculate_head_to_head_score(player1_data, player2_data)
            p1_experience_score = self._calculate_experience_score(player1_data, player2_data)

            # 综合得分
            p1_total_score = (
                    p1_ranking_score * self.ranking_weight +
                    p1_form_score * self.recent_form_weight +
                    p1_h2h_score * self.head_to_head_weight +
                    p1_experience_score * self.experience_weight
            )

            p2_total_score = 1.0 - p1_total_score

            # 转换为胜率
            p1_win_probability = p1_total_score
            p2_win_probability = p2_total_score

            # 预测获胜者
            if p1_win_probability > p2_win_probability:
                predicted_winner = player1_data['name']
                confidence = p1_win_probability
            else:
                predicted_winner = player2_data['name']
                confidence = p2_win_probability

            return {
                'player1': player1_data['name'],
                'player2': player2_data['name'],
                'predicted_winner': predicted_winner,
                'confidence': round(confidence * 100, 1),
                'player1_win_probability': round(p1_win_probability * 100, 1),
                'player2_win_probability': round(p2_win_probability * 100, 1),
                'analysis': self._generate_analysis(
                    player1_data, player2_data,
                    p1_win_probability, p2_win_probability
                )
            }

        except Exception as e:
            logger.error(f"预测错误: {str(e)}")
            return {
                'player1': player1_data['name'],
                'player2': player2_data['name'],
                'predicted_winner': '无法预测',
                'confidence': 0,
                'player1_win_probability': 50,
                'player2_win_probability': 50,
                'analysis': '预测过程中出现错误'
            }

    def _calculate_ranking_score(self, p1: Dict, p2: Dict) -> float:
        """基于排名的得分计算"""
        rank1 = p1.get('current_ranking', 100)
        rank2 = p2.get('current_ranking', 100)

        # 排名越低越好
        if rank1 < rank2:
            return 0.7 + (rank2 - rank1) * 0.01
        elif rank1 > rank2:
            return 0.3 - (rank1 - rank2) * 0.01
        else:
            return 0.5

    def _calculate_form_score(self, p1: Dict, p2: Dict) -> float:
        """基于近期状态的得分计算"""
        matches1 = p1.get('recent_matches', [])
        matches2 = p2.get('recent_matches', [])

        # 计算胜率
        p1_wins = sum(1 for m in matches1 if m.get('result') == 'win')
        p2_wins = sum(1 for m in matches2 if m.get('result') == 'win')

        p1_win_rate = p1_wins / len(matches1) if matches1 else 0.5
        p2_win_rate = p2_wins / len(matches2) if matches2 else 0.5

        if p1_win_rate > p2_win_rate:
            return 0.6 + (p1_win_rate - p2_win_rate) * 0.4
        elif p1_win_rate < p2_win_rate:
            return 0.4 - (p2_win_rate - p1_win_rate) * 0.4
        else:
            return 0.5

    def _calculate_head_to_head_score(self, p1: Dict, p2: Dict) -> float:
        """基于历史交锋记录的得分计算"""
        # 这里需要实际的交锋数据，暂时返回中性值
        return 0.5

    def _calculate_experience_score(self, p1: Dict, p2: Dict) -> float:
        """基于经验的得分计算"""
        stats1 = p1.get('career_stats', {})
        stats2 = p2.get('career_stats', {})

        matches1 = stats1.get('total_matches', 0)
        matches2 = stats2.get('total_matches', 0)

        if matches1 > matches2:
            return 0.6
        elif matches1 < matches2:
            return 0.4
        else:
            return 0.5

    def _generate_analysis(self, p1: Dict, p2: Dict, p1_prob: float, p2_prob: float) -> str:
        """生成分析报告"""
        analysis_points = []

        # 排名分析
        rank1 = p1.get('current_ranking', 100)
        rank2 = p2.get('current_ranking', 100)

        if rank1 < rank2:
            analysis_points.append(f"{p1['name']} 当前排名第{rank1}位，优于{p2['name']}的第{rank2}位")
        elif rank1 > rank2:
            analysis_points.append(f"{p2['name']} 当前排名第{rank2}位，优于{p1['name']}的第{rank1}位")
        else:
            analysis_points.append("两位选手排名相近")

        # 近期状态分析
        matches1 = p1.get('recent_matches', [])
        matches2 = p2.get('recent_matches', [])

        p1_recent_wins = sum(1 for m in matches1 if m.get('result') == 'win')
        p2_recent_wins = sum(1 for m in matches2 if m.get('result') == 'win')

        if p1_recent_wins > p2_recent_wins:
            analysis_points.append(f"{p1['name']} 近期状态更好")
        elif p1_recent_wins < p2_recent_wins:
            analysis_points.append(f"{p2['name']} 近期状态更好")

        # 综合预测
        if p1_prob > 0.7:
            analysis_points.append(f"{p1['name']} 被强烈看好获胜")
        elif p1_prob > 0.6:
            analysis_points.append(f"{p1['name']} 被看好获胜")
        elif p1_prob > 0.4:
            analysis_points.append("比赛预计会非常接近")

        return " | ".join(analysis_points)