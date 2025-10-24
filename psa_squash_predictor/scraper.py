import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class PSAScraper:
    def __init__(self):
        self.base_url = "https://psaworldtour.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def search_players(self, query: str) -> List[Dict]:
        """搜索选手"""
        try:
            search_url = f"{self.base_url}/players"
            params = {'s': query}

            response = self.session.get(search_url, params=params, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            players = []

            # 解析选手列表
            player_cards = soup.find_all('div', class_=['player-card', 'player-item'])

            for card in player_cards[:10]:  # 限制结果数量
                name_elem = card.find(['h3', 'h4', 'strong'])
                if name_elem:
                    name = name_elem.get_text().strip()
                    if query.lower() in name.lower():
                        players.append({'name': name})

            return players

        except Exception as e:
            logger.error(f"搜索选手错误: {str(e)}")
            return []

    def get_player_data(self, player_name: str) -> Optional[Dict]:
        """获取选手详细数据"""
        try:
            # 首先搜索选手
            players = self.search_players(player_name)
            if not players:
                return None

            # 使用第一个匹配的选手
            exact_player = None
            for player in players:
                if player['name'].lower() == player_name.lower():
                    exact_player = player
                    break

            if not exact_player:
                exact_player = players[0]

            # 获取选手详情页
            player_data = {
                'name': exact_player['name'],
                'current_ranking': self._get_player_ranking(exact_player['name']),
                'recent_matches': self._get_recent_matches(exact_player['name']),
                'head_to_head': {},
                'career_stats': self._get_career_stats(exact_player['name'])
            }

            return player_data

        except Exception as e:
            logger.error(f"获取选手数据错误 {player_name}: {str(e)}")
            return None

    def _get_player_ranking(self, player_name: str) -> int:
        """获取选手当前排名"""
        try:
            rankings_url = f"{self.base_url}/rankings"
            response = self.session.get(rankings_url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 解析排名表格
            ranking_table = soup.find('table', class_=['ranking-table', 'rankings'])
            if ranking_table:
                rows = ranking_table.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        name_cell = cells[1].get_text().strip()
                        if player_name.lower() in name_cell.lower():
                            rank_cell = cells[0].get_text().strip()
                            return int(re.sub(r'\D', '', rank_cell))

            return 100  # 默认排名

        except Exception as e:
            logger.warning(f"获取排名错误 {player_name}: {str(e)}")
            return 100

    def _get_recent_matches(self, player_name: str) -> List[Dict]:
        """获取最近比赛记录"""
        try:
            matches_url = f"{self.base_url}/matches"
            params = {'player': player_name.replace(' ', '+')}

            response = self.session.get(matches_url, params=params, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')
            matches = []

            # 解析比赛记录
            match_rows = soup.find_all('div', class_=['match-row', 'fixture'])

            for row in match_rows[:10]:  # 最近10场比赛
                match_data = self._parse_match_row(row, player_name)
                if match_data:
                    matches.append(match_data)

            return matches

        except Exception as e:
            logger.warning(f"获取比赛记录错误 {player_name}: {str(e)}")
            return []

    def _parse_match_row(self, row, player_name: str) -> Optional[Dict]:
        """解析单行比赛数据"""
        try:
            # 这里需要根据PSA网站的实际HTML结构进行调整
            players = row.find_all('span', class_=['player-name'])
            scores = row.find_all('span', class_=['score'])

            if len(players) >= 2 and len(scores) > 0:
                opponent = None
                for player in players:
                    name = player.get_text().strip()
                    if name.lower() != player_name.lower():
                        opponent = name
                        break

                if opponent:
                    return {
                        'opponent': opponent,
                        'result': 'win' if 'win' in row.get_text().lower() else 'loss',
                        'score': scores[0].get_text().strip() if scores else '3-0'
                    }

            return None

        except Exception as e:
            logger.warning(f"解析比赛行错误: {str(e)}")
            return None

    def _get_career_stats(self, player_name: str) -> Dict:
        """获取选手职业生涯统计"""
        try:
            # 这里可以扩展获取更多统计数据
            return {
                'total_matches': 0,
                'win_percentage': 0.5,
                'tournament_wins': 0
            }
        except Exception as e:
            logger.warning(f"获取统计数据错误 {player_name}: {str(e)}")
            return {'total_matches': 0, 'win_percentage': 0.5, 'tournament_wins': 0}