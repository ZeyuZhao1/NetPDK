# app.py
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room
from game_logic import Game

app = Flask(__name__)
app.config['SECRET_KEY'] = 'a_very_secret_key_for_lan_party!'
socketio = SocketIO(app)

# 全局游戏实例
game = Game()
host_sid = None

@app.route('/')
def index():
    """提供主游戏页面"""
    return render_template('index.html')

def broadcast_game_state(message=""):
    """向所有连接的玩家广播最新的游戏状态"""
    for sid in game.players:
        state = game.get_game_state(sid)
        state['message'] = message
        emit('game_update', state, room=sid)

@socketio.on('connect')
def handle_connect():
    sid = request.sid
    print(f'客户端已连接: {sid}')
    # 如果游戏还没开始，新用户连上后也广播一下大厅状态，使其能看到已加入的玩家
    if not game.game_started:
        broadcast_game_state()

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    player_name = game.players.get(sid, {}).get('name', '一名玩家')
    print(f'客户端已断开: {sid}')
    game.remove_player(sid)
    broadcast_game_state(f"{player_name} 已离开")

@socketio.on('join_game')
def handle_join_game(data):
    """处理玩家加入游戏的请求"""
    global host_sid
    name = data.get('name', '匿名玩家')
    sid = request.sid
    
    # 第一个加入的玩家成为房主
    if not host_sid and not game.players:
        host_sid = sid
    
    if game.add_player(sid, name):
        join_room(sid) # 为该玩家创建一个独立的房间，方便单独通讯
        broadcast_game_state(f"{name} 加入了游戏！")
    else:
        emit('error', {'message': '无法加入游戏，可能游戏已开始或您已在游戏中。'}, room=sid)

@socketio.on('start_game')
def handle_start_game():
    """处理房主开始游戏的请求"""
    if request.sid != host_sid:
        emit('error', {'message': '只有房主才能开始游戏。'}, room=request.sid)
        return
        
    if game.start_game():
        broadcast_game_state("游戏开始！")
    else:
        emit('error', {'message': '玩家不足2人或游戏已开始，无法启动。'}, room=request.sid)

@socketio.on('play_cards')
def handle_play_cards(data):
    """处理玩家出牌的动作"""
    cards = data.get('cards', [])
    sid = request.sid
    
    status, message = game.play_turn(sid, cards)
    
    if status is None:
        emit('error', {'message': message}, room=sid)
    elif status == 'WIN':
        winner_name = game.players[sid]['name']
        broadcast_game_state() # 先广播最后一次出牌的状态
        socketio.emit('game_over', {'winner_name': winner_name})
    else:
        player_name = game.players[sid]['name']
        broadcast_game_state(f"{player_name} 打出了 {' '.join(cards)}")

@socketio.on('pass_turn')
def handle_pass_turn():
    """处理玩家选择“要不起”的动作"""
    sid = request.sid
    success, message = game.pass_turn(sid)
    if success:
        player_name = game.players[sid]['name']
        broadcast_game_state(f"{player_name} 选择 pass")
    else:
        emit('error', {'message': message}, room=sid)

if __name__ == '__main__':
    # 监听在 0.0.0.0 上，使得局域网内其他设备可以访问
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)