# app.py
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
import uuid
import random
import socket

# 引入游戏逻辑和我们最新版的AI逻辑
from game_logic import Game
from ai_logic import BotPlayer

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key_for_lan_party!'
socketio = SocketIO(app)

# --- 全局状态变量 ---
game = Game()
host_sid = None
bot_count = 0


def _assign_host_if_needed(preferred_sid=None):
    """确保房主始终是一个在线的人类玩家。"""
    global host_sid

    # 仅在当前没有有效房主时，才使用本次事件关联的人类玩家作为候选
    if host_sid is None and preferred_sid and preferred_sid in game.players and not game.players[preferred_sid].get('is_bot', False):
        host_sid = preferred_sid
        return

    # 如果当前房主仍是在线人类，则保持不变
    if host_sid in game.players and not game.players[host_sid].get('is_bot', False):
        return

    # 否则按入场顺序寻找第一个人类玩家作为房主
    for sid in game.player_order:
        player = game.players.get(sid)
        if player and not player.get('is_bot', False):
            host_sid = sid
            return

    # 没有人类玩家时，房主置空
    host_sid = None

@app.route('/')
def index():
    """提供主游戏页面"""
    return render_template('index.html', lan_ip=_get_lan_ip())


def _get_lan_ip():
    """尽量获取当前机器可用于局域网访问的IP地址。"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(('8.8.8.8', 80))
            return s.getsockname()[0]
    except OSError:
        return None

def broadcast_game_state(message=""):
    """
    广播最新的游戏状态给所有人类玩家。
    这是游戏循环的核心：在广播后，它会检查是否轮到机器人出牌。
    """
    # 仅向人类玩家发送更新
    for sid, player_data in game.players.items():
        if not player_data.get('is_bot', False):
            state = game.get_game_state(sid)
            state['host_sid'] = host_sid
            state['message'] = message
            emit('game_update', state, room=sid)
    
    # 检查当前回合是否属于机器人
    current_sid = game.current_turn_sid
    if game.game_started and current_sid and game.players.get(current_sid, {}).get('is_bot', False):
        # 仅在即将触发机器人回合时短暂等待，减少不必要的阻塞
        socketio.sleep(0.25)
        handle_bot_turn(current_sid)

def handle_bot_turn(bot_sid):
    """处理并执行一个机器人回合的所有逻辑"""
    # 模拟机器人的“思考”时间，增加随机性使其更逼真
    socketio.sleep(random.uniform(0.8, 1.5))
    
    # 为AI创建一个手牌的副本，防止AI分析时意外修改原始数据
    bot_hand = list(game.players[bot_sid]['hand'])
    # 获取机器人视角的游戏状态
    game_state = game.get_game_state(bot_sid)
    
    # 创建AI实例并让它做出决策
    ai = BotPlayer(bot_hand, game_state, game)
    move = ai.decide_move()
    
    bot_name = game.players[bot_sid]['name']
    
    if move == ["pass"]:
        success, msg = game.pass_turn(bot_sid)
        if success:
            broadcast_game_state(f"{bot_name} 选择 pass")
    else:
        status, msg = game.play_turn(bot_sid, move)
        if status == 'WIN':
            # 机器人获胜
            broadcast_game_state(f"{bot_name} 打出了 {' '.join(move)}")
            socketio.emit('game_over', {'winner_name': bot_name})
        elif status == 'OK':
            # 正常出牌，继续广播状态，触发下一轮
            broadcast_game_state(f"{bot_name} 打出了 {' '.join(move)}")
        else:
            # AI出错了（作为保险措施），让它pass
            print(f"机器人 {bot_name} 出牌错误: {msg}. AI决策: {move}")
            game.pass_turn(bot_sid)
            broadcast_game_state(f"{bot_name} 思考后选择 pass")


# --- SocketIO 事件处理器 ---

@socketio.on('connect')
def handle_connect():
    sid = request.sid
    print(f'客户端已连接: {sid}')
    # 新用户连接时，如果游戏未开始，也广播一下大厅状态
    if not game.game_started:
        broadcast_game_state()

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    player_name = game.players.get(sid, {}).get('name', '一名玩家')
    print(f'客户端已断开: {sid}')
    game.remove_player(sid)
    _assign_host_if_needed()
    broadcast_game_state(f"{player_name} 已离开")

@socketio.on('join_game')
def handle_join_game(data):
    """处理人类玩家加入游戏的请求"""
    global host_sid
    name = data.get('name', '匿名玩家')
    sid = request.sid
    
    if game.add_player(sid, name, is_bot=False):
        _assign_host_if_needed(preferred_sid=sid)
        join_room(sid)
        broadcast_game_state(f"{name} 加入了游戏！")
    else:
        emit('error', {'message': '无法加入游戏，可能游戏已开始或您已在游戏中。'}, room=sid)

@socketio.on('add_bot')
def handle_add_bot():
    """处理添加机器人的请求"""
    global bot_count
    if not game.game_started:
        bot_count += 1
        # 为机器人生成一个唯一的ID和名字
        bot_sid = f"bot_{uuid.uuid4().hex[:8]}"
        bot_name = f"专家AI🤖️ {bot_count}号"
        game.add_player(bot_sid, bot_name, is_bot=True)
        _assign_host_if_needed()
        broadcast_game_state(f"{bot_name} 加入了对局！")



@socketio.on('update_room_settings')
def handle_update_room_settings(data):
    _assign_host_if_needed(preferred_sid=request.sid)
    if request.sid != host_sid:
        emit('error', {'message': '只有房主才能修改房间设置。'}, room=request.sid)
        return
    if game.game_started:
        emit('error', {'message': '游戏进行中，不能修改房间设置。'}, room=request.sid)
        return

    num_decks = int((data or {}).get('num_decks', 1) or 1)
    num_decks = max(1, min(6, num_decks))
    preset = (data or {}).get('preset', 'full')

    preset_map = {
        'classic': {'include_jokers': False, 'allow_rocket': False, 'allow_airplane_wings': True, 'allow_four_with_two': False},
        'full': {'include_jokers': True, 'allow_rocket': True, 'allow_airplane_wings': True, 'allow_four_with_two': True},
        'strict': {'include_jokers': False, 'allow_rocket': False, 'allow_airplane_wings': False, 'allow_four_with_two': True},
    }
    game.update_room_settings({'num_decks': num_decks, **preset_map.get(preset, preset_map['full'])})
    broadcast_game_state(f"房间规则已更新：{num_decks}副牌，模式 {preset}")

@socketio.on('start_game')
def handle_start_game():
    """处理房主开始游戏的请求"""
    _assign_host_if_needed(preferred_sid=request.sid)
    if request.sid != host_sid:
        emit('error', {'message': '只有房主才能开始游戏。'}, room=request.sid)
        return
        
    if game.start_game(num_decks=game.room_settings.get('num_decks', 1)):
        # 游戏开始后，立即广播状态，这会触发第一个玩家（可能是机器人）的回合
        broadcast_game_state("游戏开始！")
    else:
        emit('error', {'message': '玩家不足2人或游戏已开始，无法启动。'}, room=request.sid)

@socketio.on('play_cards')
def handle_play_cards(data):
    """处理人类玩家出牌的动作"""
    cards = data.get('cards', [])
    sid = request.sid
    
    status, message = game.play_turn(sid, cards)
    
    if status is None:
        emit('error', {'message': message}, room=sid)
    elif status == 'WIN':
        broadcast_game_state(f"{game.players[sid]['name']} 打出了 {' '.join(cards)}")
        socketio.emit('game_over', {'winner_name': game.players[sid]['name']})
    else:
        broadcast_game_state(f"{game.players[sid]['name']} 打出了 {' '.join(cards)}")

@socketio.on('pass_turn')
def handle_pass_turn():
    """处理人类玩家选择“要不起”的动作"""
    sid = request.sid
    success, message = game.pass_turn(sid)
    if success:
        broadcast_game_state(f"{game.players[sid]['name']} 选择 pass")
    else:
        emit('error', {'message': message}, room=sid)

if __name__ == '__main__':
    # 监听在 0.0.0.0 上，使得局域网内其他设备可以访问
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
