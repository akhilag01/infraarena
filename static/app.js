let sessionId = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

const startScreen = document.getElementById('start-screen');
const chatScreen = document.getElementById('chat-screen');
const leaderboardScreen = document.getElementById('leaderboard-screen');
const startBtn = document.getElementById('start-btn');
const leaderboardBtn = document.getElementById('leaderboard-btn');
const backBtn = document.getElementById('back-btn');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const voiceBtn = document.getElementById('voice-btn');
const chatMessages = document.getElementById('chat-messages');
const votePrompt = document.getElementById('vote-prompt');

function showScreen(screen) {
    [startScreen, chatScreen, leaderboardScreen].forEach(s => s.classList.remove('active'));
    screen.classList.add('active');
}

function addMessage(text, isUser, audioDataA = null, audioDataB = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
    
    if (isUser) {
        const textDiv = document.createElement('div');
        textDiv.textContent = text;
        messageDiv.appendChild(textDiv);
    } else {
        const textDiv = document.createElement('div');
        textDiv.className = 'message-text';
        textDiv.textContent = text;
        messageDiv.appendChild(textDiv);
        
        if (audioDataA && audioDataB) {
            const voicesContainer = document.createElement('div');
            voicesContainer.className = 'voices-container';
            
            const voiceA = createVoiceCard('A', audioDataA);
            const voiceB = createVoiceCard('B', audioDataB);
            
            voicesContainer.appendChild(voiceA);
            voicesContainer.appendChild(voiceB);
            messageDiv.appendChild(voicesContainer);
        }
    }
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function createVoiceCard(label, audioHex) {
    const card = document.createElement('div');
    card.className = 'voice-card';
    
    const header = document.createElement('div');
    header.className = 'voice-card-header';
    header.textContent = `Voice ${label}`;
    
    const audioBytes = new Uint8Array(audioHex.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
    const audioBlob = new Blob([audioBytes], { type: 'audio/mpeg' });
    const audioUrl = URL.createObjectURL(audioBlob);
    
    const audio = new Audio(audioUrl);
    
    const controls = document.createElement('div');
    controls.className = 'voice-controls';
    
    const playBtn = document.createElement('button');
    playBtn.className = 'play-btn';
    playBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M3 2l10 6-10 6V2z"/></svg>`;
    
    const progressContainer = document.createElement('div');
    progressContainer.className = 'progress-container';
    
    const progressBar = document.createElement('div');
    progressBar.className = 'progress-bar';
    
    const progress = document.createElement('div');
    progress.className = 'progress';
    
    progressBar.appendChild(progress);
    progressContainer.appendChild(progressBar);
    
    const timeLabel = document.createElement('span');
    timeLabel.className = 'time-label';
    timeLabel.textContent = '0:00';
    
    let isPlaying = false;
    
    playBtn.addEventListener('click', () => {
        document.querySelectorAll('audio').forEach(a => {
            if (a !== audio) {
                a.pause();
                a.currentTime = 0;
            }
        });
        
        document.querySelectorAll('.play-btn').forEach(btn => {
            if (btn !== playBtn) {
                btn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M3 2l10 6-10 6V2z"/></svg>`;
            }
        });
        
        if (isPlaying) {
            audio.pause();
            playBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M3 2l10 6-10 6V2z"/></svg>`;
        } else {
            audio.play();
            playBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="3" y="2" width="4" height="12"/><rect x="9" y="2" width="4" height="12"/></svg>`;
        }
        isPlaying = !isPlaying;
    });
    
    audio.addEventListener('timeupdate', () => {
        const percentage = (audio.currentTime / audio.duration) * 100;
        progress.style.width = `${percentage}%`;
        timeLabel.textContent = formatTime(audio.currentTime);
    });
    
    audio.addEventListener('ended', () => {
        isPlaying = false;
        playBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M3 2l10 6-10 6V2z"/></svg>`;
        progress.style.width = '0%';
        timeLabel.textContent = formatTime(audio.duration);
    });
    
    audio.addEventListener('loadedmetadata', () => {
        timeLabel.textContent = formatTime(audio.duration);
    });
    
    progressContainer.addEventListener('click', (e) => {
        const rect = progressBar.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const percentage = x / rect.width;
        audio.currentTime = percentage * audio.duration;
    });
    
    controls.appendChild(playBtn);
    controls.appendChild(progressContainer);
    controls.appendChild(timeLabel);
    
    card.appendChild(header);
    card.appendChild(controls);
    
    return card;
}

function formatTime(seconds) {
    if (isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function showVotePrompt() {
    votePrompt.classList.remove('hidden');
}

function hideVotePrompt() {
    votePrompt.classList.add('hidden');
}

async function startSession() {
    try {
        const response = await fetch('/api/start-session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        sessionId = data.session_id;
        
        chatMessages.innerHTML = '';
        showScreen(chatScreen);
        addMessage(data.message, false, 'System');
    } catch (error) {
        console.error('Error starting session:', error);
        alert('Failed to start session. Please try again.');
    }
}

async function sendMessage(message) {
    if (!message.trim() || !sessionId) return;
    
    addMessage(message, true);
    messageInput.value = '';
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, message })
        });
        
        const data = await response.json();
        
        addMessage(data.text, false, data.audio_a, data.audio_b);
        
        if (data.should_vote) {
            showVotePrompt();
        }
    } catch (error) {
        console.error('Error sending message:', error);
        addMessage('Sorry, there was an error. Please try again.', false);
    }
}

async function submitVote(winner) {
    if (!sessionId) return;
    
    try {
        const response = await fetch('/api/vote', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, winner })
        });
        
        const data = await response.json();
        
        hideVotePrompt();
        
        showModelReveal(data.model_a_name, data.model_a_provider, data.model_b_name, data.model_b_provider);
    } catch (error) {
        console.error('Error submitting vote:', error);
        alert('Failed to submit vote. Please try again.');
    }
}

function getProviderLogo(provider) {
    const logos = {
        'ElevenLabs': '<img src="/static/logos/ElevenLabs_logo.png" alt="ElevenLabs">',
        'OpenAI': '<img src="/static/logos/openai-icon.webp" alt="OpenAI">',
        'Deepgram': '<img src="/static/logos/Deepgram-wordmark-black.png" alt="Deepgram">',
        'Cartesia': '<img src="/static/logos/cartesia-logo.svg" alt="Cartesia">'
    };
    return logos[provider] || '';
}

function showModelReveal(modelAName, modelAProvider, modelBName, modelBProvider) {
    const revealDiv = document.createElement('div');
    revealDiv.className = 'model-reveal';
    
    revealDiv.innerHTML = `
        <div class="reveal-header">Model Reveal</div>
        <div class="reveal-models">
            <div class="reveal-model">
                <div class="reveal-voice-label">Voice A</div>
                <div class="reveal-logo">${getProviderLogo(modelAProvider)}</div>
                <div class="reveal-model-name">${modelAName}</div>
                <div class="reveal-provider">${modelAProvider}</div>
            </div>
            <div class="reveal-divider"></div>
            <div class="reveal-model">
                <div class="reveal-voice-label">Voice B</div>
                <div class="reveal-logo">${getProviderLogo(modelBProvider)}</div>
                <div class="reveal-model-name">${modelBName}</div>
                <div class="reveal-provider">${modelBProvider}</div>
            </div>
        </div>
        <div class="reveal-footer">Thank you for voting! Continue the conversation.</div>
    `;
    
    chatMessages.appendChild(revealDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function loadLeaderboard() {
    try {
        const response = await fetch('/api/leaderboard');
        const data = await response.json();
        
        const leaderboardContent = document.getElementById('leaderboard-content');
        leaderboardContent.innerHTML = '';
        
        data.forEach((model, index) => {
            const item = document.createElement('div');
            item.className = 'leaderboard-item';
            
            const winRate = model.total_votes > 0 
                ? ((model.wins / model.total_votes) * 100).toFixed(1) 
                : 0;
            
            item.innerHTML = `
                <div class="rank ${index < 3 ? 'top' : ''}">#${index + 1}</div>
                <div class="model-info">
                    <div class="model-name">${model.name}</div>
                    <div class="model-provider">${model.provider}</div>
                </div>
                <div class="model-stats">
                    <div class="elo">${model.elo}</div>
                    <div class="win-rate">${winRate}% win rate</div>
                </div>
            `;
            
            leaderboardContent.appendChild(item);
        });
        
        showScreen(leaderboardScreen);
    } catch (error) {
        console.error('Error loading leaderboard:', error);
        alert('Failed to load leaderboard. Please try again.');
    }
}

async function startVoiceRecording() {
    if (!sessionId) {
        alert('Please start a conversation first!');
        return;
    }
    
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];
        
        mediaRecorder.ondataavailable = (event) => {
            audioChunks.push(event.data);
        };
        
        mediaRecorder.onstop = async () => {
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            
            voiceBtn.classList.remove('recording');
            voiceBtn.disabled = true;
            isRecording = false;
            
            const formData = new FormData();
            formData.append('file', audioBlob, 'audio.webm');
            
            try {
                addMessage('🎤 Transcribing...', false, 'System');
                
                const response = await fetch('/api/transcribe', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                
                if (data.text && data.text.trim()) {
                    const lastMessage = chatMessages.lastChild;
                    if (lastMessage && lastMessage.textContent.includes('Transcribing')) {
                        chatMessages.removeChild(lastMessage);
                    }
                    
                    sendMessage(data.text);
                } else {
                    addMessage('Could not transcribe audio. Please try again.', false, 'System');
                }
            } catch (error) {
                console.error('Error transcribing audio:', error);
                addMessage('Failed to transcribe audio. Please try again.', false, 'System');
            } finally {
                voiceBtn.disabled = false;
            }
        };
        
        mediaRecorder.start();
        voiceBtn.classList.add('recording');
        isRecording = true;
    } catch (error) {
        console.error('Error accessing microphone:', error);
        alert('Failed to access microphone. Please check permissions.');
    }
}

function stopVoiceRecording() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
    }
}

startBtn.addEventListener('click', startSession);
leaderboardBtn.addEventListener('click', loadLeaderboard);
backBtn.addEventListener('click', () => showScreen(startScreen));

sendBtn.addEventListener('click', () => {
    const message = messageInput.value;
    sendMessage(message);
});

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        const message = messageInput.value;
        sendMessage(message);
    }
});

voiceBtn.addEventListener('click', () => {
    if (isRecording) {
        stopVoiceRecording();
    } else {
        startVoiceRecording();
    }
});

document.querySelectorAll('.vote-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const winner = btn.dataset.vote;
        submitVote(winner);
    });
});
