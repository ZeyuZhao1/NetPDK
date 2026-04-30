document.addEventListener('DOMContentLoaded', () => {
    const socket = io();

    const lobbyView = document.getElementById('lobby-view');
    const gameView = document.getElementById('game-view');
    const nameInput = document.getElementById('name-input');
    const joinBtn = document.getElementById('join-btn');
    const addBotBtn = document.getElementById('add-bot-btn');
    const lobbyPlayersList = document.getElementById('lobby-players');
    const startBtn = document.getElementById('start-btn');
    const applySettingsBtn = document.getElementById('apply-settings-btn');
    const deckCountSelect = document.getElementById('deck-count');
    const rulePresetSelect = document.getElementById('rule-preset');
    const roomUrl = document.getElementById('room-url');
    const roomQr = document.getElementById('room-qr');
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

    let mySid = null, selectedCards = [], currentHand = [];
    const CARD_ORDER = { '3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13,'A':14,'2':15,'小王':16,'大王':17 };
    const SUIT_ORDER = { '♣':1, '♦':2, '♥':3, '♠':4 };

    const lanIp = document.body.dataset.lanIp;
    const currentUrl = new URL(window.location.href);
    const isLocalLoopback = ['127.0.0.1', 'localhost', '::1'].includes(currentUrl.hostname);
    const shareUrl = (isLocalLoopback && lanIp)
        ? `${currentUrl.protocol}//${lanIp}${currentUrl.port ? `:${currentUrl.port}` : ''}${currentUrl.pathname}`
        : currentUrl.href;
    roomUrl.textContent = `分享地址：${shareUrl}`;
    roomQr.src = `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(shareUrl)}`;

    joinBtn.onclick = () => { const n=nameInput.value.trim(); if(n){socket.emit('join_game',{name:n}); joinBtn.disabled=true; nameInput.disabled=true;} };
    startBtn.onclick = () => socket.emit('start_game');
    addBotBtn.onclick = () => socket.emit('add_bot');
    applySettingsBtn.onclick = () => socket.emit('update_room_settings', {num_decks:Number(deckCountSelect.value), preset:rulePresetSelect.value});
    playBtn.onclick = () => selectedCards.length>0 ? socket.emit('play_cards',{cards:selectedCards}) : alert('请先选择要出的牌！');
    passBtn.onclick = () => socket.emit('pass_turn');
    clearBtn.onclick = () => { myHandDiv.querySelectorAll('.card.selected').forEach(d=>d.classList.remove('selected')); selectedCards=[]; };
    sortBtn.onclick = () => { currentHand = sortCards(currentHand); renderCards(myHandDiv, currentHand); };
    myHandDiv.onclick = (e) => { const c=e.target.closest('.card'); if(!c) return; const d=c.dataset.card; c.classList.toggle('selected'); selectedCards = selectedCards.includes(d) ? selectedCards.filter(i => i !== d) : [...selectedCards, d]; };

    socket.on('error', (data) => alert('错误: ' + data.message));
    socket.on('game_update', (state) => {
        mySid = state.my_sid;
        const isHost = state.host_sid === mySid;
        startBtn.disabled = !isHost;
        applySettingsBtn.disabled = !isHost;
        startBtn.textContent = isHost ? '开始游戏 (你是房主)' : '开始游戏 (仅房主)';
        if (state.room_settings) {
            deckCountSelect.value = String(state.room_settings.num_decks || 1);
        }
        if (state.game_started) { lobbyView.style.display='none'; gameView.style.display='flex'; renderGame(state); }
        else { lobbyView.style.display='block'; gameView.style.display='none'; renderLobby(state.players); }
    });
    socket.on('game_over', (data) => { alert(`游戏结束！获胜者是: ${data.winner_name}`); lobbyView.style.display='block'; gameView.style.display='none'; });

    function renderLobby(players){ lobbyPlayersList.innerHTML=''; players.forEach(p=>{const li=document.createElement('li');li.textContent=`${p.name}${p.is_bot?' (Bot)':''}`; lobbyPlayersList.appendChild(li);}); }
    function renderGame(state){ selectedCards=[]; const myData=state.players.find(p=>p.sid===mySid); myName.textContent=myData?`${myData.name} (你)`:'我的手牌'; currentHand=sortCards(state.my_hand.slice()); updateHandLayout(currentHand.length); renderCards(myHandDiv,currentHand);
        lastPlayInfo.textContent=state.last_played_cards.length?`${state.players.find(p=>p.sid===state.last_player_sid)?.name||''} 打出:`:'等待出牌...'; renderCards(lastPlayedCardsDiv,state.last_played_cards);
        opponentsArea.innerHTML=''; state.player_order.forEach(sid=>{if(sid===mySid)return; const p=state.players.find(a=>a.sid===sid); if(!p)return; const o=document.createElement('div'); o.className='opponent'; if(p.sid===state.current_turn_sid)o.classList.add('active-turn'); o.innerHTML=`<h4>${p.name}${p.is_bot?' (Bot)':''}</h4><p>剩余: ${p.card_count} 张</p>`; opponentsArea.appendChild(o);});
        const isMyTurn=state.current_turn_sid===mySid; playBtn.disabled=!isMyTurn; clearBtn.disabled=!isMyTurn; passBtn.disabled=!isMyTurn||!state.last_played_cards.length; document.querySelector('#my-area').classList.toggle('active-turn',isMyTurn);
        gameMessage.textContent=state.message || (isMyTurn?'轮到你出牌了！':'等待其他玩家出牌...'); turnHint.textContent = isMyTurn ? '提示：先整理再出牌。' : '观察牌势，控制大牌节奏。';
    }
    function sortCards(cards){ return cards.sort((a,b)=>cardValue(a)-cardValue(b)||suitValue(a)-suitValue(b)); }
    function cardValue(card){ return (card==='小王'||card==='大王') ? CARD_ORDER[card] : CARD_ORDER[card.slice(1)]; }
    function suitValue(card){ return (card==='小王'||card==='大王') ? 99 : (SUIT_ORDER[card[0]]||0); }
    function updateHandLayout(cardCount){
        const isNarrow = window.matchMedia('(max-width: 900px)').matches;
        myHandDiv.classList.toggle('is-scroll-layout', isNarrow && cardCount > 8);
    }
    window.addEventListener('resize', () => updateHandLayout(currentHand.length));
    function renderCards(container, cards){ container.innerHTML=''; cards.forEach(cardStr=>{ const d=document.createElement('div'); d.className='card'; d.dataset.card=cardStr; if(cardStr==='小王'||cardStr==='大王'){d.classList.add('joker'); const color=cardStr==='大王'?'red':'black'; d.innerHTML=`<div class="joker-text" style="color:${color}">${cardStr.split('').join('<br>')}</div>`;} else {const suit=cardStr[0], rank=cardStr.slice(1), color=(suit==='♥'||suit==='♦')?'red':'black'; d.innerHTML=`<div class="rank" style="color:${color}">${rank}</div><div class="suit" style="color:${color}">${suit}</div><div class="rank bottom" style="color:${color}">${rank}</div><div class="suit bottom" style="color:${color}">${suit}</div>`;} container.appendChild(d); }); }
});
