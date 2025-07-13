# ai_logic.py
from collections import Counter
import random
from game_logic import HandType, CARD_VALUES

class BotPlayer:
    """一个基于手牌结构分析和启发式策略的AI玩家"""

    def __init__(self, hand, game_state, game_logic_instance):
        self.hand = hand
        self.game_state = game_state
        self.game = game_logic_instance
        self.my_sid = game_state['my_sid']
        self.analyzed_hand = self._analyze_hand()

    def decide_move(self):
        """AI决策主入口"""
        last_played = self.game_state['last_played_cards']
        is_my_lead = not last_played or self.game_state['current_turn_sid'] == self.game_state['last_player_sid']

        if is_my_lead:
            return self._decide_lead()
        else:
            return self._decide_follow(last_played)

    def _analyze_hand(self):
        """
        核心函数：使用贪心算法将手牌分解为最优组合。
        优先级: 火箭 > 炸弹 > 飞机 > 连对 > 顺子 > 三条 > 对子 > 单张
        """
        analysis = {
            "rocket": [], "bombs": [], "airplanes": [], "consecutive_pairs": [],
            "straights": [], "threes": [], "pairs": [], "singles": []
        }
        
        # 1. 提取火箭
        if '小王' in self.hand and '大王' in self.hand:
            analysis['rocket'].append(['小王', '大王'])
            self.hand.remove('小王')
            self.hand.remove('大王')

        counts = Counter(self._get_card_value(c) for c in self.hand)

        # 2. 提取炸弹
        for value, num in list(counts.items()):
            if num == 4:
                analysis['bombs'].append(self._get_cards_from_values([value]*4))
                del counts[value]

        # 3. 提取飞机、连对、顺子 (从长到短)
        for length in range(12, 2, -1): # 从最长的连对/飞机开始
            self._find_consecutive_in_counts(counts, length, 3, analysis['airplanes'])
            self._find_consecutive_in_counts(counts, length, 2, analysis['consecutive_pairs'])
        for length in range(12, 4, -1): # 从最长的顺子开始
            self._find_consecutive_in_counts(counts, length, 1, analysis['straights'])

        # 4. 提取三条、对子、单张
        for value, num in list(counts.items()):
            if num == 3: analysis['threes'].append(self._get_cards_from_values([value]*3)); del counts[value]
            elif num == 2: analysis['pairs'].append(self._get_cards_from_values([value]*2)); del counts[value]
            elif num == 1: analysis['singles'].append(self._get_cards_from_values([value])); del counts[value]
        
        return analysis

    def _decide_lead(self):
        """决定主动出什么牌"""
        # 如果只剩一手牌，直接打出获胜
        all_combos = [c for cat in self.analyzed_hand.values() for c in cat]
        if len(all_combos) == 1:
            return all_combos[0]
            
        # 策略：优先出顺子/飞机清理手牌，然后是递送废牌（单张/对子）
        if self.analyzed_hand['straights']:
            return self.analyzed_hand['straights'][0]
        if self.analyzed_hand['airplanes']: # 简化：暂时不支持飞机带翼
            return self.analyzed_hand['airplanes'][0]
        if self.analyzed_hand['singles']:
            # 不出最小的单张，避免对方轻易接牌
            self.analyzed_hand['singles'].sort(key=lambda c: self._get_card_value(c[0]))
            return self.analyzed_hand['singles'][len(self.analyzed_hand['singles']) // 2] # 出中间的单张
        if self.analyzed_hand['pairs']:
            return self.analyzed_hand['pairs'][0]
        if self.analyzed_hand['threes']:
            return self.analyzed_hand['threes'][0]
        
        # 如果什么都没有，只能从炸弹里出了
        return all_combos[0]
    
    def _decide_follow(self, last_played):
        """决定跟什么牌，包含拆牌代价评估"""
        last_type, last_value = self.game._get_play_info(last_played)
        
        # 寻找零代价的牌 (从已分析好的组合里出)
        valid_follows = self._find_valid_plays(last_type, last_value, cost=0)
        
        if valid_follows:
            # 选最小的打
            valid_follows.sort(key=lambda p: self.game._get_play_info(p)[1])
            return valid_follows[0]

        # 如果没有零代价的牌，考虑是否要拆牌或用炸弹
        # 局势判断：如果下家牌很少，提高动用炸弹的意愿
        next_player_sid = self.game.player_order[(self.game.player_order.index(self.my_sid) + 1) % len(self.game.player_order)]
        next_player_state = next(p for p in self.game_state['players'] if p['sid'] == next_player_sid)
        
        use_bomb = False
        if next_player_state['card_count'] <= 3: # 如果下家是地主
            use_bomb = True
        
        if use_bomb and self.analyzed_hand['bombs']:
            bombs_can_win = [b for b in self.analyzed_hand['bombs'] if self.game._get_play_info(b)[1] > last_value]
            if bombs_can_win:
                return bombs_can_win[0]
        
        if use_bomb and self.analyzed_hand['rocket']:
            return self.analyzed_hand['rocket'][0]

        # 最终决定放弃
        return ["pass"]

    def _find_valid_plays(self, target_type, target_value, cost=0):
        """根据目标牌型和代价，查找可出的牌"""
        # 简化版：这里只实现了查找零代价的牌
        valid_plays = []
        if cost == 0:
            potential_plays = []
            if target_type == HandType.SINGLE: potential_plays = self.analyzed_hand['singles']
            elif target_type == HandType.PAIR: potential_plays = self.analyzed_hand['pairs']
            # ...可以扩展到所有牌型
            
            for play in potential_plays:
                play_type, play_value = self.game._get_play_info(play)
                if play_value > target_value:
                    valid_plays.append(play)
        
        # 总是检查炸弹和火箭
        for bomb in self.analyzed_hand['bombs']:
            if target_type != HandType.BOMB or self.game._get_play_info(bomb)[1] > target_value:
                valid_plays.append(bomb)
        if self.analyzed_hand['rocket'] and target_type != HandType.ROCKET:
            valid_plays.extend(self.analyzed_hand['rocket'])
            
        return valid_plays

    # --- Helper Methods ---
    def _get_card_value(self, card):
        if card in CARD_VALUES: return CARD_VALUES[card]
        return CARD_VALUES.get(card[1:], 0)

    def _get_cards_from_values(self, values):
        """根据牌值列表，从手牌中找出对应的牌"""
        cards = []
        temp_hand = list(self.hand)
        for v in values:
            for c in temp_hand:
                if self._get_card_value(c) == v:
                    cards.append(c)
                    temp_hand.remove(c)
                    break
        return cards

    def _find_consecutive_in_counts(self, counts, length, num_of_kind, result_list):
        """在counts字典中寻找连续的序列 (顺子/连对/飞机)"""
        if len(counts) < length: return
        
        valid_values = sorted([v for v, c in counts.items() if c >= num_of_kind and v < CARD_VALUES['2']])
        if len(valid_values) < length: return

        for i in range(len(valid_values) - length + 1):
            subset = valid_values[i : i+length]
            if subset[-1] - subset[0] == length - 1:
                # 找到了，提取并从counts中删除
                values_to_remove = []
                for v in subset:
                    values_to_remove.extend([v] * num_of_kind)
                    counts[v] -= num_of_kind
                    if counts[v] == 0: del counts[v]

                result_list.append(self._get_cards_from_values(values_to_remove))
                self._find_consecutive_in_counts(counts, length, num_of_kind, result_list) # 递归查找
                return