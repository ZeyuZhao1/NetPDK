# ai_logic.py (深度优化版)
from collections import Counter, defaultdict
import random
from game_logic import HandType, CARD_VALUES

class BotPlayer:
    """一个基于全局牌张记忆、动态决策权重和高级启发式策略的AI玩家"""

    def __init__(self, hand, game_state, game_logic_instance):
        self.hand_backup = list(hand) # 原始手牌备份
        self.game_state = game_state
        self.game = game_logic_instance
        self.my_sid = game_state['my_sid']
        self.player_states = {p['sid']: p for p in game_state['players']}
        
        # 1. 全局牌张记忆 (Card Counting)
        self.unseen_cards = self._initialize_unseen_cards()
        self.analyzed_hand = self._analyze_hand(list(self.hand_backup))
        
        # 2. 游戏阶段判断
        self.game_phase = self._determine_game_phase()

    def decide_move(self):
        """AI决策主入口"""
        # 每次决策前都更新未见牌信息
        last_played = self.game_state['last_played_cards']
        if last_played:
            for card in last_played:
                self.unseen_cards.remove(card)

        is_my_lead = not last_played or self.game_state['current_turn_sid'] == self.game_state['last_player_sid']

        if is_my_lead:
            return self._decide_lead()
        else:
            return self._decide_follow(last_played)

    def _analyze_hand(self, hand_to_analyze):
        """
        核心函数：使用贪心算法将手牌分解为最优组合。
        新增飞机带翼的智能组合。
        """
        hand = list(hand_to_analyze)
        analysis = defaultdict(list)
        
        # 1. 提取火箭
        if '小王' in hand and '大王' in hand:
            analysis['rocket'].append(['小王', '大王']); hand.remove('小王'); hand.remove('大王')
        
        counts = Counter(self._get_card_value(c) for c in hand)

        # 2. 提取炸弹
        for v, n in list(counts.items()):
            if n == 4: analysis['bombs'].append(self._get_cards_by_values(hand, [v]*4)); counts.pop(v)

        # 3. 提取飞机、连对、顺子 (从长到短)
        for length in range(12, 2, -1): self._find_consecutive(hand, counts, length, 3, analysis, 'airplanes')
        for length in range(12, 2, -1): self._find_consecutive(hand, counts, length, 2, analysis, 'consecutive_pairs')
        for length in range(12, 4, -1): self._find_consecutive(hand, counts, length, 1, analysis, 'straights')

        # 4. 提取剩余的三条、对子、单张
        for v, n in list(counts.items()):
            if n == 3: analysis['threes'].append(self._get_cards_by_values(hand, [v]*3)); counts.pop(v)
            elif n == 2: analysis['pairs'].append(self._get_cards_by_values(hand, [v]*2)); counts.pop(v)
            elif n == 1: analysis['singles'].append(self._get_cards_by_values(hand, [v])); counts.pop(v)
        
        # 5. 智能为飞机寻找翼 (重要优化)
        self._attach_wings_to_airplanes(analysis)
        
        return analysis

    def _decide_lead(self):
        """更智能的主动出牌策略"""
        combos = {k: v for k, v in self.analyzed_hand.items() if v} # 获取所有非空组合

        # 如果只剩一手牌，直接打出
        if len(list(c for v in combos.values() for c in v)) == 1:
            return list(combos.values())[0][0]

        # 游戏末期策略：如果自己牌最少，优先出能一次出完的牌
        if self.game_phase == 'endgame' and self.player_states[self.my_sid]['card_count'] <= min(p['card_count'] for p in self.player_states.values()):
            if 'airplanes' in combos: return combos['airplanes'][0]
            if 'straights' in combos: return combos['straights'][0]

        # 正常出牌策略：
        # 1. 出顺子 (清理手牌效率最高)
        if 'straights' in combos: return combos['straights'][0]
        # 2. 传递废牌 (单张或对子)
        play_order = ['singles', 'pairs', 'threes', 'consecutive_pairs', 'airplanes']
        for hand_type in play_order:
            if hand_type in combos:
                # 评估出哪张牌最安全
                return self._select_safest_play(combos[hand_type])
        
        # 如果只剩炸弹或王炸了
        return list(combos.values())[0][0]

    def _decide_follow(self, last_played):
        """更智能的跟牌策略，包含完整的代价评估"""
        last_type, last_value = self.game._get_play_info(last_played)
        
        # 1. 寻找零代价的牌 (从已分析好的组合里出)
        valid_plays = self._find_plays_from_analysis(last_type, last_value)
        if valid_plays:
            return self._select_best_follow(valid_plays, last_value)

        # 2. 如果没有现成组合，进行模拟拆牌并评估代价
        potential_breaks = self._find_breaking_plays(last_type, last_value)
        if potential_breaks:
            # 选择代价最低的拆法
            best_break = min(potential_breaks, key=lambda x: x['cost'])
            
            # 动态决策：如果代价太高，且不是关键时刻，就放弃
            if best_break['cost'] > 3 and self.game_phase != 'endgame':
                 pass # 继续往下走，看是否用炸弹
            else:
                return best_break['play']

        # 3. 决定是否使用炸弹/火箭
        if self._should_use_bomb(last_played):
            all_bombs = self.analyzed_hand.get('bombs', []) + self.analyzed_hand.get('rocket', [])
            winning_bombs = [b for b in all_bombs if self.game._get_play_info(b)[1] > last_value]
            if winning_bombs:
                return min(winning_bombs, key=lambda b: self.game._get_play_info(b)[1])
        
        return ["pass"]
        
    # --- 策略辅助函数 ---
    
    def _select_safest_play(self, plays):
        """从多个可出牌组中，选择一个最安全的打出"""
        # 安全性评估：值越小，包含未见过的大牌越少，则越安全
        def assess_safety(play):
            value = self.game._get_play_info(play)[1]
            unseen_big_cards = sum(1 for c in play if self._get_card_value(c) > 13 and c in self.unseen_cards)
            return value - unseen_big_cards * 2 # 惩罚出未见过的大牌
        
        return min(plays, key=assess_safety)

    def _select_best_follow(self, plays, last_value):
        """从多个可跟牌组中，选择最优的一个"""
        # 策略：选择刚刚好能大过的最小的牌，避免浪费
        plays.sort(key=lambda p: self.game._get_play_info(p)[1])
        return plays[0]

    def _should_use_bomb(self, last_played):
        """更精细的炸弹使用决策"""
        # 如果上家打的是大牌（K, A, 2），且即将获胜，则必须炸
        last_player_sid = self.game_state['last_player_sid']
        last_player_cards = self.player_states[last_player_sid]['card_count']
        
        if last_player_cards <= 3 and self.game._get_play_info(last_played)[1] > CARD_VALUES['Q']:
            return True
        
        # 如果自己手牌很好，可以用炸弹抢牌权
        if self.game_phase == 'endgame' and len(self.hand_backup) <= 5:
            return True
            
        return False

    def _find_breaking_plays(self, target_type, target_value):
        """模拟所有可能的拆牌方式，并计算代价"""
        potential_plays = []
        original_analysis = self.analyzed_hand

        for combo_type, combos in original_analysis.items():
            if combo_type in ['singles', 'bombs', 'rocket']: continue # 不拆这些
            for combo in combos:
                remaining_hand = list(self.hand_backup)
                for card in combo: remaining_hand.remove(card)
                
                # 在被拆的组合中寻找能打的牌
                temp_counts = Counter(self._get_card_value(c) for c in combo)
                # ... 此处需要复杂的逻辑来从temp_counts中提取符合target_type的牌 ...
                # 这是一个非常复杂的部分，为简化，我们仅实现拆三条和对子
                if target_type == HandType.SINGLE and len(combo) > 1:
                    for card in combo:
                        play = [card]
                        play_value = self._get_card_value(card)
                        if play_value > target_value:
                             cost = self._calculate_break_cost(original_analysis, combo, play)
                             potential_plays.append({'play': play, 'cost': cost})
                
        return potential_plays
    
    def _calculate_break_cost(self, analysis, original_combo, broken_play):
        """计算拆牌的代价"""
        # 代价 = 损失的组合强度 + 新产生的废牌数量
        cost = len(original_combo) # 基础代价
        remaining_cards = list(original_combo)
        for card in broken_play: remaining_cards.remove(card)
        
        # 重新分析剩余牌，看产生了多少废牌
        new_analysis = self._analyze_hand(remaining_cards)
        cost += len(new_analysis.get('singles', [])) + len(new_analysis.get('pairs', [])) * 0.5
        return cost

    # --- 初始化与数据管理 ---

    def _initialize_unseen_cards(self):
        full_deck = [f"{s}{r}" for s in ['♠','♥','♣','♦'] for r in ['3','4','5','6','7','8','9','10','J','Q','K','A','2']]
        full_deck.extend(['小王', '大王'])
        unseen = set(full_deck)
        for card in self.hand_backup: unseen.remove(card)
        # 假设游戏状态中包含所有历史出牌
        for p in self.game_state['players']:
            # 此处需要app.py将所有历史出牌信息传过来，暂时简化
            pass
        return unseen
        
    def _determine_game_phase(self):
        total_cards = len(self.player_states) * (54 // len(self.player_states))
        cards_left = sum(p['card_count'] for p in self.player_states.values())
        if cards_left / total_cards < 0.3: return 'endgame'
        if cards_left / total_cards < 0.7: return 'midgame'
        return 'opening'

    # --- 组合查找辅助函数 ---
    
    def _get_card_value(self, card):
        return CARD_VALUES.get(card, CARD_VALUES.get(card[1:]))

    def _get_cards_by_values(self, hand, values):
        """从一个手牌列表(hand)中，根据值(values)精确提取牌"""
        cards, temp_hand = [], list(hand)
        for v in values:
            for c in temp_hand:
                if self._get_card_value(c) == v:
                    cards.append(c); temp_hand.remove(c); break
        for card in cards: hand.remove(card)
        return cards

    def _find_consecutive(self, hand, counts, length, num_of_kind, analysis, analysis_key):
        valid_values = sorted([v for v, c in counts.items() if c >= num_of_kind and v < CARD_VALUES['2']])
        if len(valid_values) < length: return
        for i in range(len(valid_values) - length, -1, -1):
            subset = valid_values[i : i+length]
            if subset[-1] - subset[0] == length - 1:
                values_to_remove = [v for v in subset for _ in range(num_of_kind)]
                analysis[analysis_key].append(self._get_cards_by_values(hand, values_to_remove))
                for v in subset: counts[v] -= num_of_kind
                # 递归查找更短的
                self._find_consecutive(hand, counts, length, num_of_kind, analysis, analysis_key)
                return

    def _attach_wings_to_airplanes(self, analysis):
        """为分析好的飞机寻找最优的翼"""
        singles = sorted(analysis.get('singles', []), key=lambda c: self._get_card_value(c[0]))
        pairs = sorted(analysis.get('pairs', []), key=lambda p: self._get_card_value(p[0]))
        
        winged_airplanes = []
        for plane in analysis.get('airplanes', []):
            num_trips = len(plane) // 3
            # 优先带对子
            if len(pairs) >= num_trips:
                wings = pairs[:num_trips]
                winged_airplanes.append(plane + [card for p in wings for card in p])
                pairs = pairs[num_trips:]
            # 其次带单张
            elif len(singles) >= num_trips:
                wings = singles[:num_trips]
                winged_airplanes.append(plane + [card for s in wings for card in s])
                singles = singles[num_trips:]
        
        if winged_airplanes:
            analysis['airplanes'] = winged_airplanes
            analysis['singles'] = singles
            analysis['pairs'] = pairs