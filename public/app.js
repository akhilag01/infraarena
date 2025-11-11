let sessionId = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let currentUser = null;
let authToken = null;

const chatScreen = document.getElementById('chat-screen');
const leaderboardScreen = document.getElementById('leaderboard-screen');
const backBtn = document.getElementById('back-btn');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const voiceBtn = document.getElementById('voice-btn');
const chatMessages = document.getElementById('chat-messages');
const votePrompt = document.getElementById('vote-prompt');

const loginBtn = document.getElementById('login-btn');
const headerLoginBtn = document.getElementById('header-login-btn');
const loginModal = document.getElementById('login-modal');
const modalClose = document.getElementById('modal-close');
const userProfile = document.getElementById('user-profile');
const headerUserProfile = document.getElementById('header-user-profile');
const userEmail = document.getElementById('user-email');
const headerUserEmail = document.getElementById('header-user-email');
const logoutBtn = document.getElementById('logout-btn');
const emailLoginBtn = document.getElementById('email-login-btn');
const emailSignupBtn = document.getElementById('email-signup-btn');
const googleLoginBtn = document.getElementById('google-login-btn');
const emailInput = document.getElementById('email-input');
const passwordInput = document.getElementById('password-input');

function showScreen(screen) {
    [chatScreen, leaderboardScreen].forEach(s => s.classList.remove('active'));
    screen.classList.add('active');
}

let currentVoiceCards = { voiceA: null, voiceB: null };

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
            
            currentVoiceCards.voiceA = voiceA;
            currentVoiceCards.voiceB = voiceB;
            
            voicesContainer.appendChild(voiceA);
            voicesContainer.appendChild(voiceB);
            messageDiv.appendChild(voicesContainer);
        }
    }
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return messageDiv;
}

function addGeneratingPlaceholder() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message assistant';
    
    const voicesContainer = document.createElement('div');
    voicesContainer.className = 'voices-container';
    
    const voiceA = document.createElement('div');
    voiceA.className = 'voice-card generating';
    voiceA.innerHTML = '<div class="voice-card-header"><span class="voice-label">Voice A</span></div><div class="voice-controls"></div>';
    
    const voiceB = document.createElement('div');
    voiceB.className = 'voice-card generating';
    voiceB.innerHTML = '<div class="voice-card-header"><span class="voice-label">Voice B</span></div><div class="voice-controls"></div>';
    
    voicesContainer.appendChild(voiceA);
    voicesContainer.appendChild(voiceB);
    messageDiv.appendChild(voicesContainer);
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageDiv;
}

function createVoiceCard(label, audioHex) {
    const card = document.createElement('div');
    card.className = 'voice-card';
    card.dataset.label = label;
    
    const header = document.createElement('div');
    header.className = 'voice-card-header';
    header.innerHTML = `<span class="voice-label">Voice ${label}</span>`;
    
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
    } catch (error) {
        console.error('Error starting session:', error);
        alert('Failed to start session. Please try again.');
    }
}

async function sendMessage(message) {
    if (!message.trim() || !sessionId) return;
    
    addMessage(message, true);
    messageInput.value = '';
    
    const placeholder = addGeneratingPlaceholder();
    
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ session_id: sessionId, message })
        });
        
        const data = await response.json();
        
        placeholder.remove();
        
        addMessage(data.text, false, data.audio_a, data.audio_b);
        
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        if (data.should_vote) {
            showVotePrompt();
        }
    } catch (error) {
        console.error('Error sending message:', error);
        placeholder.remove();
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
        
        if (winner === 'A') {
            currentVoiceCards.voiceA.classList.add('winner');
            currentVoiceCards.voiceB.classList.add('loser');
        } else if (winner === 'B') {
            currentVoiceCards.voiceB.classList.add('winner');
            currentVoiceCards.voiceA.classList.add('loser');
        } else if (winner === 'tie') {
            currentVoiceCards.voiceA.classList.add('winner');
            currentVoiceCards.voiceB.classList.add('winner');
        } else if (winner === 'both_bad') {
            currentVoiceCards.voiceA.classList.add('loser');
            currentVoiceCards.voiceB.classList.add('loser');
        }
        
        showModelReveal(data.model_a_name, data.model_a_provider, data.model_b_name, data.model_b_provider);
    } catch (error) {
        console.error('Error submitting vote:', error);
        alert('Failed to submit vote. Please try again.');
    }
}

function getProviderLogo(provider) {
    const logos = {
        'ElevenLabs': '<img src="/logos/ElevenLabs_logo.png" alt="ElevenLabs">',
        'OpenAI': '<img src="/logos/openai-icon.webp" alt="OpenAI">',
        'Deepgram': '<img src="/logos/Deepgram-wordmark-black.png" alt="Deepgram">',
        'Cartesia': '<img src="/logos/cartesia-logo.svg" alt="Cartesia">'
    };
    return logos[provider] || '';
}

function showModelReveal(modelAName, modelAProvider, modelBName, modelBProvider) {
    if (currentVoiceCards.voiceA && currentVoiceCards.voiceB) {
        const headerA = currentVoiceCards.voiceA.querySelector('.voice-card-header');
        const headerB = currentVoiceCards.voiceB.querySelector('.voice-card-header');
        
        const logoA = getProviderLogo(modelAProvider);
        const logoB = getProviderLogo(modelBProvider);
        
        headerA.innerHTML = `
            <div class="model-reveal-inline">
                <div class="model-logo-small">${logoA}</div>
                <div class="model-info-inline">
                    <div class="model-name-small">${modelAName}</div>
                    <div class="provider-name-small">${modelAProvider}</div>
                </div>
            </div>
        `;
        
        headerB.innerHTML = `
            <div class="model-reveal-inline">
                <div class="model-logo-small">${logoB}</div>
                <div class="model-info-inline">
                    <div class="model-name-small">${modelBName}</div>
                    <div class="provider-name-small">${modelBProvider}</div>
                </div>
            </div>
        `;
        
        currentVoiceCards.voiceA.classList.add('revealed');
        currentVoiceCards.voiceB.classList.add('revealed');
    }
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

backBtn.addEventListener('click', () => showScreen(chatScreen));

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
    
    btn.addEventListener('mouseenter', () => {
        const vote = btn.dataset.vote;
        if (currentVoiceCards.voiceA && currentVoiceCards.voiceB) {
            if (vote === 'A') {
                currentVoiceCards.voiceA.classList.add('preview-winner');
                currentVoiceCards.voiceB.classList.add('preview-loser');
            } else if (vote === 'B') {
                currentVoiceCards.voiceB.classList.add('preview-winner');
                currentVoiceCards.voiceA.classList.add('preview-loser');
            } else if (vote === 'tie') {
                currentVoiceCards.voiceA.classList.add('preview-winner');
                currentVoiceCards.voiceB.classList.add('preview-winner');
            } else if (vote === 'both_bad') {
                currentVoiceCards.voiceA.classList.add('preview-loser');
                currentVoiceCards.voiceB.classList.add('preview-loser');
            }
        }
    });
    
    btn.addEventListener('mouseleave', () => {
        if (currentVoiceCards.voiceA && currentVoiceCards.voiceB) {
            currentVoiceCards.voiceA.classList.remove('preview-winner', 'preview-loser');
            currentVoiceCards.voiceB.classList.remove('preview-winner', 'preview-loser');
        }
    });
});

const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebar-toggle');
const navChat = document.getElementById('nav-chat');
const navLeaderboard = document.getElementById('nav-leaderboard');

sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
});

navChat.addEventListener('click', () => {
    showScreen(chatScreen);
    updateActiveNav(navChat);
});

navLeaderboard.addEventListener('click', () => {
    loadLeaderboard();
    updateActiveNav(navLeaderboard);
});

function updateActiveNav(activeItem) {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    activeItem.classList.add('active');
}

// Authentication functions
function updateUIForUser(user) {
    currentUser = user;
    if (user) {
        loginBtn.classList.add('hidden');
        headerLoginBtn.classList.add('hidden');
        userProfile.classList.remove('hidden');
        headerUserProfile.classList.remove('hidden');
        userEmail.textContent = user.email;
        headerUserEmail.textContent = user.email;
    } else {
        loginBtn.classList.remove('hidden');
        headerLoginBtn.classList.remove('hidden');
        userProfile.classList.add('hidden');
        headerUserProfile.classList.add('hidden');
        currentUser = null;
        authToken = null;
    }
}

loginBtn.addEventListener('click', () => {
    loginModal.classList.remove('hidden');
});

headerLoginBtn.addEventListener('click', () => {
    loginModal.classList.remove('hidden');
});

modalClose.addEventListener('click', () => {
    loginModal.classList.add('hidden');
});

loginModal.addEventListener('click', (e) => {
    if (e.target === loginModal) {
        loginModal.classList.add('hidden');
    }
});


emailLoginBtn.addEventListener('click', async () => {
    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: emailInput.value,
                password: passwordInput.value
            })
        });
        
        const data = await response.json();
        if (response.ok) {
            authToken = data.access_token;
            localStorage.setItem('authToken', authToken);
            updateUIForUser(data.user);
            loginModal.classList.add('hidden');
        } else {
            alert(data.detail || 'Login failed');
        }
    } catch (error) {
        console.error('Login error:', error);
        alert('Login failed. Please try again.');
    }
});

emailSignupBtn.addEventListener('click', async () => {
    try {
        const response = await fetch('/api/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: emailInput.value,
                password: passwordInput.value
            })
        });
        
        const data = await response.json();
        if (response.ok) {
            alert('Signup successful! Please login.');
        } else {
            alert(data.detail || 'Signup failed');
        }
    } catch (error) {
        console.error('Signup error:', error);
        alert('Signup failed. Please try again.');
    }
});

googleLoginBtn.addEventListener('click', async () => {
    try {
        const response = await fetch('/api/auth/google', {
            method: 'POST'
        });
        const data = await response.json();
        if (data.url) {
            window.location.href = data.url;
        }
    } catch (error) {
        console.error('Google auth error:', error);
        alert('Google authentication failed');
    }
});

logoutBtn.addEventListener('click', async () => {
    try {
        if (authToken) {
            await fetch('/api/auth/logout', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${authToken}`
                }
            });
        }
        localStorage.removeItem('authToken');
        updateUIForUser(null);
    } catch (error) {
        console.error('Logout error:', error);
    }
});

// Check for existing auth token on load
const storedToken = localStorage.getItem('authToken');
if (storedToken) {
    fetch('/api/auth/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: storedToken })
    })
    .then(res => res.json())
    .then(data => {
        if (data.user) {
            authToken = storedToken;
            updateUIForUser(data.user);
        } else {
            localStorage.removeItem('authToken');
        }
    })
    .catch(() => {
        localStorage.removeItem('authToken');
    });
}

startSession();
updateActiveNav(navChat);
