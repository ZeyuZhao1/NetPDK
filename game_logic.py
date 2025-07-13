# game_logic.py
import random
from collections import Counter

# --- 常量定义 (加入大小王) ---
CARD_VALUES = {
    '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 11, 'Q': 12, 'K': 13, 'A': 14, '2': 15,
    '小王': 16, '大王': 17
}
SUITS = ['♠', '♥', '♣', '♦']
RANKS = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']

# 牌型定义 (新增ROCKET)
class HandType:
    UNKNOWN = 0
    SINGLE = 1
    PAIR = 2
    THREE_OF_A_KIND = 3
    THREE_WITH_ONE = 4
    THREE_WITH_TWO = 5
    STRAIGHT = 6
    CONSECUTIVE_PAIRS = 7
    AIRPLANE = 8
    AIRPLANE_WITH_SINGLES = 9
    AIRPLANE_WITH_PAIRS = 10
    BOMB = 11
    FOUR_WITH_TWO = 12
    ROCKET = 13 # 王炸

class Game:
    def __init__(self):
        self.players = {}
        self.player_order = []
        self.game_started = False
        self.current_turn_sid = None
        self.last_played_cards = []
        self.last_player_sid = None

    def add_player(self, sid, name):
        if not self.game_started and sid not in self.players:
            self.players[sid] = {'name': name, 'hand': []}
            self.player_order.append(sid)
            return True
        return False

    def remove_player(self, sid):
        if sid in self.players: del self.players[sid]
        if sid in self.player_order: self.player_order.remove(sid)

    def start_game(self, num_decks=1):
        if self.game_started or len(self.players) < 2: return False
        
        # 生成牌库 (加入大小王)
        self.deck = [f"{suit}{rank}" for suit in SUITS for rank in RANKS] * num_decks
        self.deck.extend(['小王', '大王'] * num_decks)
        random.shuffle(self.deck)
        
        # 发牌
        player_sids = self.player_order
        num_players = len(player_sids)
        cards_per_player = len(self.deck) // num_players
        for i, sid in enumerate(player_sids):
            hand = self.deck[i * cards_per_player : (i + 1) * cards_per_player]
            self.players[sid]['hand'] = self._sort_hand(hand)

        self.game_started = True
        self.current_turn_sid = self.player_order[0]
        self.last_player_sid = self.current_turn_sid
        return True

    def _get_card_value(self, card):
        """更健壮地获取牌值，支持大小王"""
        if card in CARD_VALUES: return CARD_VALUES[card]
        return CARD_VALUES.get(card[1:], 0)

    def _sort_hand(self, hand):
        return sorted(hand, key=lambda card: self._get_card_value(card))

    def _get_play_info(self, cards):
        if not cards: return HandType.UNKNOWN, 0

        n = len(cards)
        counts = Counter(self._get_card_value(c) for c in cards)
        values = sorted(counts.keys())
        
        # 优先判断王炸
        if n == 2 and set(cards) == {'小王', '大王'}:
            return HandType.ROCKET, 99 # 王炸的值最大

        # --- 单牌、对子、三张、炸弹 ---
        if len(counts) == 1:
            if n == 1: return HandType.SINGLE, values[0]
            if n == 2: return HandType.PAIR, values[0]
            if n == 3: return HandType.THREE_OF_A_KIND, values[0]
            if n == 4: return HandType.BOMB, values[0]

        # --- 三带X / 四带X ---
        if len(counts) == 2:
            if n == 4 and 3 in counts.values(): # 三带一
                return HandType.THREE_WITH_ONE, [v for v,c in counts.items() if c==3][0]
            if n == 5 and 3 in counts.values(): # 三带二
                return HandType.THREE_WITH_TWO, [v for v,c in counts.items() if c==3][0]
            if n == 6 and 4 in counts.values(): # 四带二 (单或对)
                return HandType.FOUR_WITH_TWO, [v for v,c in counts.items() if c==4][0]

        # --- 顺子 / 连对 / 飞机 ---
        # 2和大小王不能参与顺子类
        if CARD_VALUES['2'] in values or CARD_VALUES['小王'] in values or CARD_VALUES['大王'] in values:
            return HandType.UNKNOWN, 0

        is_consecutive = values[-1] - values[0] == len(values) - 1
        if is_consecutive:
            # 顺子
            if n >= 5 and len(counts) == n:
                return HandType.STRAIGHT, values[-1]
            # 连对
            if n >= 6 and n % 2 == 0 and all(c == 2 for c in counts.values()):
                return HandType.CONSECUTIVE_PAIRS, values[-1]
            # 飞机不带翼
            if n >= 6 and n % 3 == 0 and all(c == 3 for c in counts.values()):
                return HandType.AIRPLANE, values[-1]
        
        # 飞机带翼
        threes = sorted([v for v, c in counts.items() if c == 3])
        if len(threes) >= 2 and threes[-1] - threes[0] == len(threes) - 1:
            if len(cards) == len(threes) * 4: # 飞机带单
                return HandType.AIRPLANE_WITH_SINGLES, threes[-1]
            if len(cards) == len(threes) * 5: # 飞机带对
                return HandType.AIRPLANE_WITH_PAIRS, threes[-1]

        return HandType.UNKNOWN, 0

    def _validate_play(self, cards_to_play):
        current_type, current_value = self._get_play_info(cards_to_play)
        if current_type == HandType.UNKNOWN: return False, "不合法的牌型。"

        if not self.last_played_cards or self.current_turn_sid == self.last_player_sid:
            return True, "OK"

        last_type, last_value = self._get_play_info(self.last_played_cards)
        
        # 规则1: 王炸最大
        if current_type == HandType.ROCKET: return True, "OK"
        if last_type == HandType.ROCKET: return False, "王炸是最大的！"
        
        # 规则2: 炸弹可以压任何非炸弹
        if current_type == HandType.BOMB and last_type != HandType.BOMB:
            return True, "OK"

        # 规则3: 牌型、长度必须一致，且牌值要更大
        if current_type == last_type and len(cards_to_play) == len(self.last_played_cards):
            if current_value > last_value:
                return True, "OK"
            else:
                return False, "出的牌要比上家小。"
        
        return False, "必须出与上家相同类型的牌，或使用炸弹。"

    def play_turn(self, sid, cards):
        if not self.game_started or sid != self.current_turn_sid: return None, "还没轮到你。"
        player_hand = self.players[sid]['hand']
        if not all(card in player_hand for card in cards): return None, "试图打出不存在的牌。"
        
        is_valid, reason = self._validate_play(cards)
        if not is_valid: return None, reason

        for card in cards: player_hand.remove(card)
        self.last_played_cards = self._sort_hand(cards)
        self.last_player_sid = sid
        
        if not player_hand:
            self.game_started = False
            return 'WIN', None

        self._next_turn()
        return 'OK', None

    def pass_turn(self, sid):
        if not self.game_started or sid != self.current_turn_sid: return False, "还没轮到你。"
        if self.current_turn_sid == self.last_player_sid or not self.last_played_cards: return False, "你是新一轮，必须出牌。"
        
        self._next_turn()
        if self.current_turn_sid == self.last_player_sid: self.last_played_cards = []
        return True, None

    def _next_turn(self):
        while True:
            current_index = self.player_order.index(self.current_turn_sid)
            next_index = (current_index + 1) % len(self.player_order)
            self.current_turn_sid = self.player_order[next_index]
            if len(self.players.get(self.current_turn_sid, {}).get('hand', [])) > 0: break

    def get_game_state(self, for_sid):
        # (此函数无变化)
        return {'game_started':self.game_started,'my_hand':self.players.get(for_sid,{}).get('hand',[]),'my_sid':for_sid,'players':[{'name':p['name'],'sid':s,'card_count':len(p['hand'])}for s,p in self.players.items()],'player_order':self.player_order,'current_turn_sid':self.current_turn_sid,'last_played_cards':self.last_played_cards,'last_player_sid':self.last_player_sid}