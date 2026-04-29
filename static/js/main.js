// static/js/main.js
document.addEventListener('DOMContentLoaded', () => {
    if (typeof io === "undefined") {
        console.error("CRITICAL ERROR: Socket.IO client (io) is not defined.");
        alert("严重错误：无法加载通讯库，请检查网络连接或刷新页面。");
        return;
    }
    const socket = io();

    const lobbyView = document.getElementById('lobby-view');
    const gameView = document.getElementById('game-view');
    const nameInput = document.getElementById('name-input');
    const joinBtn = document.getElementById('join-btn');
    const addBotBtn = document.getElementById('add-bot-btn');
    const lobbyPlayersList = document.getElementById('lobby-players');
    const startBtn = document.getElementById('start-btn');
    const gameMessage = document.getElementById('game-message');
    const turnHint = document.getElementById('turn-hint');
    const opponentsArea = document.getElementById('opponents-area');
    const lastPlayInfo = document.getElementById('last-play-info');
    const lastPlayedCardsDiv = document.getElementById('last-played-cards');
    const myName = document.getElementById('my-name');
    const myHandDiv = document.getElementById('my-hand');
    const playBtn = document.getElementById('play-btn');
    const passBtn = document.getElementById('pass-btn');
    const clearBtn = document.getElementById('clear-btn');
    const sortBtn = document.getElementById('sort-btn');

    let mySid = null;
    let selectedCards = [];
    let currentHand = [];
    const CARD_ORDER = { '3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13,'A':14,'2':15,'小王':16,'大王':17 };
    const SUIT_ORDER = { '♣':1, '♦':2, '♥':3, '♠':4 };

    joinBtn.addEventListener('click', () => { const n = nameInput.value.trim(); if(n){ socket.emit('join_game',{name:n}); joinBtn.disabled=true; nameInput.disabled=true; } else { alert('请输入昵称！'); } });
    startBtn.addEventListener('click', () => socket.emit('start_game'));
    addBotBtn.addEventListener('click', () => socket.emit('add_bot'));
    playBtn.addEventListener('click', () => { if (selectedCards.length > 0) socket.emit('play_cards', { cards: selectedCards }); else alert('请先选择要出的牌！'); });
    passBtn.addEventListener('click', () => socket.emit('pass_turn'));
    clearBtn.addEventListener('click', () => { myHandDiv.querySelectorAll('.card.selected').forEach(d => d.classList.remove('selected')); selectedCards = []; });
    sortBtn.addEventListener('click', () => {
        currentHand = sortCards(currentHand);
        renderCards(myHandDiv, currentHand);
    });
    myHandDiv.addEventListener('click', (e) => { const c=e.target.closest('.card'); if(c){ const d=c.dataset.card; c.classList.toggle('selected'); if(selectedCards.includes(d)){selectedCards=selectedCards.filter(i => i !== d);} else {selectedCards.push(d);}}});

    socket.on('connect', () => console.log('Socket.IO: Connected'));
    socket.on('error', (data) => alert('错误: ' + data.message));
    socket.on('game_update', (state) => {
        mySid = state.my_sid;
        if (state.game_started) {
            lobbyView.style.display='none';
            gameView.style.display='flex';
            renderGame(state);
        } else {
            lobbyView.style.display='block';
            gameView.style.display='none';
            renderLobby(state.players);
            joinBtn.disabled = false;
            nameInput.disabled = false;
        }
    });
    socket.on('game_over', (data) => {
        alert(`游戏结束！获胜者是: ${data.winner_name}`);
        lobbyView.style.display='block';
        gameView.style.display='none';
    });

    function renderLobby(players) {
        lobbyPlayersList.innerHTML = '';
        players.forEach(player => {
            const li = document.createElement('li');
            const bot_tag = player.is_bot ? " (Bot)" : "";
            li.textContent = `${player.name}${bot_tag}`;
            lobbyPlayersList.appendChild(li);
        });
    }
    
    function renderGame(state) {
        selectedCards = [];
        
        const myData = state.players.find(p => p.sid === mySid);
        myName.textContent = myData ? `${myData.name} (你)` : '我的手牌';
        currentHand = sortCards(state.my_hand.slice());
        renderCards(myHandDiv, currentHand);

        if (state.last_played_cards.length > 0) {
            const lastPlayerName = state.players.find(p => p.sid === state.last_player_sid)?.name || '';
            const bot_tag = state.players.find(p => p.sid === state.last_player_sid)?.is_bot ? " (Bot)" : "";
            lastPlayInfo.textContent = `${lastPlayerName}${bot_tag} 打出:`;
        } else {
            lastPlayInfo.textContent = '等待出牌...';
        }
        renderCards(lastPlayedCardsDiv, state.last_played_cards);

        opponentsArea.innerHTML = '';
        state.player_order.forEach(sid => {
            if (sid === mySid) return;
            const p = state.players.find(player => player.sid === sid);
            if (!p) return;
            const o = document.createElement('div');
            o.className = 'opponent';
            if (p.sid === state.current_turn_sid) o.classList.add('active-turn');
            const bot_tag = p.is_bot ? " (Bot)" : "";
            o.innerHTML = `<h4>${p.name}${bot_tag}</h4><p>剩余: ${p.card_count} 张</p>`;
            opponentsArea.appendChild(o);
        });
        
        const isMyTurn = state.current_turn_sid === mySid;
        const isNewRound = !state.last_played_cards.length;
        playBtn.disabled = !isMyTurn;
        clearBtn.disabled = !isMyTurn;
        passBtn.disabled = !isMyTurn || isNewRound;
        document.querySelector('#my-area').classList.toggle('active-turn', isMyTurn);
        
        const currentPlayer = state.players.find(p => p.sid === state.current_turn_sid);
        const currentPlayerName = currentPlayer ? `${currentPlayer.name}${currentPlayer.is_bot ? " (Bot)" : ""}` : '';
        gameMessage.textContent = state.message || (isMyTurn ? "轮到你出牌了！" : `等待 ${currentPlayerName} 出牌...`);
        turnHint.textContent = isMyTurn
            ? "提示：点击牌可选择；可先点“整理手牌”再出牌。"
            : "观察场上牌型，保留关键牌（2、王、炸弹）等待时机。";
    }

    function sortCards(cards) {
        return cards.sort((a, b) => cardValue(a) - cardValue(b) || suitValue(a) - suitValue(b));
    }

    function cardValue(card) {
        if (card === '小王' || card === '大王') return CARD_ORDER[card];
        return CARD_ORDER[card.slice(1)];
    }

    function suitValue(card) {
        if (card === '小王' || card === '大王') return 99;
        return SUIT_ORDER[card[0]] || 0;
    }

    function renderCards(container, cards) {
        container.innerHTML = '';
        cards.forEach(cardStr => {
            const cardDiv = document.createElement('div');
            cardDiv.className = 'card';
            cardDiv.dataset.card = cardStr;
            if (cardStr === '小王' || cardStr === '大王') {
                cardDiv.classList.add('joker');
                const color = cardStr === '大王' ? 'red' : 'black';
                cardDiv.innerHTML = `<div class="joker-text" style="color:${color}">${cardStr.split('').join('<br>')}</div>`;
            } else {
                const suit = cardStr[0];
                const rank = cardStr.slice(1);
                const color = (suit === '♥' || suit === '♦') ? 'red' : 'black';
                cardDiv.innerHTML = `<div class="rank" style="color:${color}">${rank}</div><div class="suit" style="color:${color}">${suit}</div><div class="rank bottom" style="color:${color}">${rank}</div><div class="suit bottom" style="color:${color}">${suit}</div>`;
            }
            container.appendChild(cardDiv);
        });
    }
});
