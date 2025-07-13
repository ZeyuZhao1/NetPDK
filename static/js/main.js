document.addEventListener('DOMContentLoaded', () => {
    if (typeof io === "undefined") { console.error("CRITICAL ERROR: Socket.IO client (io) is not defined."); return; }
    const socket = io();

    const lobbyView = document.getElementById('lobby-view');
    const gameView = document.getElementById('game-view');
    const nameInput = document.getElementById('name-input');
    const joinBtn = document.getElementById('join-btn');
    const lobbyPlayersList = document.getElementById('lobby-players');
    const startBtn = document.getElementById('start-btn');
    const gameMessage = document.getElementById('game-message');
    const opponentsArea = document.getElementById('opponents-area');
    const lastPlayInfo = document.getElementById('last-play-info');
    const lastPlayedCardsDiv = document.getElementById('last-played-cards');
    const myName = document.getElementById('my-name');
    const myHandDiv = document.getElementById('my-hand');
    const playBtn = document.getElementById('play-btn');
    const passBtn = document.getElementById('pass-btn');
    const clearBtn = document.getElementById('clear-btn');

    let mySid = null;
    let selectedCards = [];

    joinBtn.addEventListener('click', () => { const n = nameInput.value.trim(); if(n){ socket.emit('join_game',{name:n}); joinBtn.disabled=true; nameInput.disabled=true; } else { alert('请输入昵称！'); } });
    startBtn.addEventListener('click', () => socket.emit('start_game'));
    playBtn.addEventListener('click', () => { if (selectedCards.length > 0) socket.emit('play_cards', { cards: selectedCards }); else alert('请先选择要出的牌！'); });
    passBtn.addEventListener('click', () => socket.emit('pass_turn'));
    clearBtn.addEventListener('click', () => { myHandDiv.querySelectorAll('.card.selected').forEach(d => d.classList.remove('selected')); selectedCards = []; });
    myHandDiv.addEventListener('click', (e) => { const c=e.target.closest('.card'); if(c){ const d=c.dataset.card; c.classList.toggle('selected'); if(selectedCards.includes(d)){selectedCards=selectedCards.filter(i => i !== d);} else {selectedCards.push(d);}}});

    socket.on('connect', () => console.log('Socket.IO: Connected'));
    socket.on('error', (data) => alert('错误: ' + data.message));
    socket.on('game_update', (state) => { mySid = state.my_sid; if (state.game_started) { lobbyView.style.display='none'; gameView.style.display='flex'; renderGame(state); } else { lobbyView.style.display='block'; gameView.style.display='none'; renderLobby(state.players); joinBtn.disabled=false; nameInput.disabled=false; } });
    socket.on('game_over', (data) => { alert(`游戏结束！获胜者是: ${data.winner_name}`); lobbyView.style.display='block'; gameView.style.display='none'; });
    
    function renderLobby(players) { /* ...与之前相同... */ }
    
    function renderGame(state) {
        selectedCards = [];
        const myData = state.players.find(p => p.sid === mySid);
        myName.textContent = myData ? `${myData.name} (你)` : '我的手牌';
        renderCards(myHandDiv, state.my_hand);

        if (state.last_played_cards.length > 0) {
            const lastPlayerName = state.players.find(p => p.sid === state.last_player_sid)?.name || '';
            lastPlayInfo.textContent = `${lastPlayerName} 打出:`;
        } else {
            lastPlayInfo.textContent = '等待出牌...';
        }
        renderCards(lastPlayedCardsDiv, state.last_played_cards);

        opponentsArea.innerHTML = '';
        state.player_order.forEach(sid => { if (sid===mySid) return; const p=state.players.find(player => player.sid === sid); if (!p) return; const o=document.createElement('div'); o.className='opponent'; if(p.sid===state.current_turn_sid) o.classList.add('active-turn'); o.innerHTML=`<h4>${p.name}</h4><p>剩余: ${p.card_count} 张</p>`; opponentsArea.appendChild(o); });
        const isMyTurn = state.current_turn_sid === mySid;
        const isNewRound = !state.last_played_cards.length;
        playBtn.disabled = !isMyTurn;
        clearBtn.disabled = !isMyTurn;
        passBtn.disabled = !isMyTurn || isNewRound;
        document.querySelector('#my-area').classList.toggle('active-turn', isMyTurn);
        gameMessage.textContent = state.message || (isMyTurn ? "轮到你出牌了！" : `等待 ${state.players.find(p=>p.sid===state.current_turn_sid)?.name || ''} 出牌...`);
    }

    // 更新：renderCards函数现在可以处理大小王
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