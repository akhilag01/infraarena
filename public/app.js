let sessionId = null;
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let currentUser = null;
let authToken = null;
let currentMode = 'battle';
let selectedModelA = null;
let selectedModelB = null;
let selectedModelSingle = null;
let availableModels = [];
let websocket = null;
let audioPlayers = {};

function showToast(message, duration = 3000) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

const chatScreen = document.getElementById('chat-screen');
const leaderboardScreen = document.getElementById('leaderboard-screen');
const backBtn = document.getElementById('back-btn');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const voiceBtn = document.getElementById('voice-btn');
const chatMessages = document.getElementById('chat-messages');
const votePrompt = document.getElementById('vote-prompt');

const headerModelSelectors = document.getElementById('header-model-selectors');
const headerModelSelectA = document.getElementById('header-model-select-a');
const headerModelSelectB = document.getElementById('header-model-select-b');
const headerSingleModelSelector = document.getElementById('header-single-model-selector');
const headerModelSelectSingle = document.getElementById('header-model-select-single');

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

// MediaSource audio player for streaming MP3
class StreamingAudioPlayer {
    constructor() {
        this.audioElement = new Audio();
        this.mediaSource = new MediaSource();
        this.sourceBuffer = null;
        this.queue = [];
        this.isAppending = false;
        this.isEnded = false;
        
        this.audioElement.src = URL.createObjectURL(this.mediaSource);
        
        this.mediaSource.addEventListener('sourceopen', () => {
            try {
                this.sourceBuffer = this.mediaSource.addSourceBuffer('audio/mpeg');
                this.sourceBuffer.mode = 'sequence';
                
                this.sourceBuffer.addEventListener('updateend', () => {
                    this.isAppending = false;
                    this.processQueue();
                });
                
                this.sourceBuffer.addEventListener('error', (e) => {
                    console.error('SourceBuffer error:', e);
                });
            } catch (e) {
                console.error('Error creating SourceBuffer:', e);
            }
        });
        
        this.mediaSource.addEventListener('sourceended', () => {
            console.log('MediaSource ended');
        });
        
        this.audioElement.addEventListener('error', (e) => {
            console.error('Audio element error:', e, this.audioElement.error);
        });
    }
    
    appendChunk(chunk) {
        if (this.isEnded) {
            console.warn('Attempted to append chunk after end');
            return;
        }
        
        this.queue.push(chunk);
        this.processQueue();
        
        // Auto-play when we have enough buffered
        if (this.audioElement.paused && this.audioElement.readyState >= 2) {
            this.audioElement.play().catch(e => console.error('Play error:', e));
        }
    }
    
    processQueue() {
        if (this.isAppending || this.queue.length === 0 || !this.sourceBuffer || this.sourceBuffer.updating) {
            return;
        }
        
        try {
            this.isAppending = true;
            const chunk = this.queue.shift();
            this.sourceBuffer.appendBuffer(chunk);
        } catch (e) {
            console.error('Error appending buffer:', e);
            this.isAppending = false;
        }
    }
    
    end() {
        this.isEnded = true;
        // Process remaining queue first
        if (this.queue.length > 0) {
            setTimeout(() => this.end(), 100);
            return;
        }
        
        if (this.mediaSource.readyState === 'open' && !this.sourceBuffer.updating) {
            try {
                this.mediaSource.endOfStream();
            } catch (e) {
                console.error('Error ending stream:', e);
            }
        }
    }
    
    play() {
        return this.audioElement.play();
    }
    
    pause() {
        this.audioElement.pause();
    }
    
    getCurrentTime() {
        return this.audioElement.currentTime;
    }
    
    getDuration() {
        return this.audioElement.duration;
    }
    
    seek(time) {
        this.audioElement.currentTime = time;
    }
    
    addEventListener(event, handler) {
        this.audioElement.addEventListener(event, handler);
    }
    
    destroy() {
        this.audioElement.pause();
        this.audioElement.src = '';
        if (this.mediaSource.readyState === 'open') {
            try {
                this.mediaSource.endOfStream();
            } catch (e) {}
        }
        URL.revokeObjectURL(this.audioElement.src);
    }
}

// Progressive audio streaming player - like YouTube/SoundCloud
// Combines sentence chunks into a single audio element with MediaSource
class ProgressiveAudioPlayer {
    constructor(label, voiceCard) {
        this.label = label;
        this.voiceCard = voiceCard;
        this.audioElement = new Audio();
        this.mediaSource = new MediaSource();
        this.sourceBuffer = null;
        this.chunks = {};
        this.queue = [];
        this.isAppending = false;
        this.isStreamComplete = false;
        this.nextChunkId = 0;
        this.totalChunks = 0;
        this.isUserPaused = false;
        this.startTime = Date.now();
        
        this.audioElement.preload = 'auto';
        this.audioElement.src = URL.createObjectURL(this.mediaSource);
        
        this.mediaSource.addEventListener('sourceopen', () => {
            try {
                console.log(`[Player ${this.label}] MediaSource opened, creating SourceBuffer`);
                this.sourceBuffer = this.mediaSource.addSourceBuffer('audio/mpeg');
                this.sourceBuffer.mode = 'sequence';
                
                this.sourceBuffer.addEventListener('updateend', () => {
                    this.isAppending = false;
                    this.processQueue();
                    this.updateProgressUI();
                });
                
                this.sourceBuffer.addEventListener('error', (e) => {
                    console.error(`[Player ${this.label}] SourceBuffer error:`, e);
                });
                
                // Try to append any chunks that arrived early
                if (this.chunks[this.nextChunkId]) {
                    console.log(`[Player ${this.label}] Processing early chunks`);
                    this.appendNextChunks();
                }
            } catch (e) {
                console.error(`[Player ${this.label}] Error creating SourceBuffer:`, e);
            }
        });
        
        // UI updates
        this.audioElement.addEventListener('timeupdate', () => this.updateProgressUI());
        this.audioElement.addEventListener('loadedmetadata', () => this.updateProgressUI());
        this.audioElement.addEventListener('ended', () => this.updatePlayButtonUI(false));
        this.audioElement.addEventListener('play', () => this.updatePlayButtonUI(true));
        this.audioElement.addEventListener('pause', () => this.updatePlayButtonUI(false));
        
        this.setupUI();
    }
    
    setupUI() {
        if (!this.voiceCard) return;
        
        this.voiceCard.classList.add('loading');
        
        const playBtn = document.createElement('button');
        playBtn.className = 'play-btn';
        playBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M3 2l10 6-10 6V2z"/></svg>';
        playBtn.onclick = () => this.togglePlay();
        playBtn.title = 'Play audio';
        
        const progressContainer = document.createElement('div');
        progressContainer.className = 'progress-container';
        progressContainer.style.cssText = 'flex: 1; margin: 0 10px; cursor: pointer; position: relative;';
        
        const progressBar = document.createElement('div');
        progressBar.className = 'progress-bar';
        
        const bufferedBar = document.createElement('div');
        bufferedBar.className = 'buffered';
        bufferedBar.style.width = '0%';
        
        const playedBar = document.createElement('div');
        playedBar.className = 'played';
        playedBar.style.width = '0%';
        
        const timeLabel = document.createElement('span');
        timeLabel.className = 'time-label';
        timeLabel.textContent = '0:00';
        
        
        progressBar.appendChild(bufferedBar);
        progressBar.appendChild(playedBar);
        progressContainer.appendChild(progressBar);
        
        progressContainer.onclick = (e) => {
            if (!this.audioElement.duration) return;
            const rect = progressBar.getBoundingClientRect();
            const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            this.audioElement.currentTime = percent * this.audioElement.duration;
        };
        
        const controls = document.createElement('div');
        controls.className = 'voice-controls';
        
        controls.appendChild(playBtn);
        controls.appendChild(progressContainer);
        controls.appendChild(timeLabel);
        
        this.playBtn = playBtn;
        this.bufferedBar = bufferedBar;
        this.playedBar = playedBar;
        this.timeLabel = timeLabel;
        
        const existingControls = this.voiceCard.querySelector('.voice-controls');
        if (existingControls) {
            existingControls.replaceWith(controls);
        } else {
            this.voiceCard.appendChild(controls);
        }
    }
    
    addChunk(chunkId, hexData) {
        try {
            const bytes = new Uint8Array(hexData.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
            this.chunks[chunkId] = bytes;
            this.totalChunks = Math.max(this.totalChunks, chunkId + 1);
            
            const latency = Date.now() - this.startTime;
            console.log(`[Player ${this.label}] Chunk ${chunkId} received (${latency}ms), ${bytes.length} bytes`);
            
            // Detect WAV format (RIFF header) and use blob URL fallback
            if (chunkId === 0 && bytes.length >= 4) {
                const header = String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3]);
                if (header === 'RIFF') {
                    console.log(`[Player ${this.label}] Detected WAV format, using blob URL fallback`);
                    this.useWavFallback(bytes);
                    return;
                }
            }
            
            if (this.voiceCard) {
                this.voiceCard.classList.remove('loading');
            }
            
            if (chunkId === this.nextChunkId && this.sourceBuffer) {
                this.appendNextChunks();
            }
            
            this.updateProgressUI();
        } catch (e) {
            console.error(`[Player ${this.label}] Error adding chunk ${chunkId}:`, e);
        }
    }
    
    appendNextChunks() {
        // Append all consecutive chunks starting from nextChunkId
        while (this.chunks[this.nextChunkId]) {
            this.queue.push(this.chunks[this.nextChunkId]);
            delete this.chunks[this.nextChunkId];
            this.nextChunkId++;
        }
        this.processQueue();
    }
    
    processQueue() {
        if (this.isAppending || this.queue.length === 0 || !this.sourceBuffer || this.sourceBuffer.updating) {
            return;
        }
        
        try {
            this.isAppending = true;
            const chunk = this.queue.shift();
            this.sourceBuffer.appendBuffer(chunk);
            
            // Don't auto-play - let user click play button
            // (Browser security requires user interaction for auto-play)
        } catch (e) {
            console.error('Error appending buffer:', e);
            this.isAppending = false;
        }
    }
    
    updateProgressUI() {
        if (!this.playedBar || !this.bufferedBar || !this.timeLabel) return;
        
        const duration = this.audioElement.duration;
        const currentTime = this.audioElement.currentTime;
        
        // Update played progress (current position)
        if (duration && !isNaN(duration)) {
            const playedPercent = (currentTime / duration) * 100;
            this.playedBar.style.width = `${playedPercent}%`;
            this.timeLabel.textContent = this.formatTime(currentTime);
        }
        
        // Update buffered progress (downloaded chunks)
        const bufferedPercent = (this.nextChunkId / Math.max(this.totalChunks, this.nextChunkId + 1)) * 100;
        this.bufferedBar.style.width = `${bufferedPercent}%`;
    }
    
    updatePlayButtonUI(isPlaying) {
        if (!this.playBtn) return;
        if (isPlaying) {
            this.playBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M4 2h3v12H4V2zm5 0h3v12H9V2z"/></svg>';
        } else {
            this.playBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor"><path d="M3 2l10 6-10 6V2z"/></svg>';
        }
    }
    
    togglePlay() {
        if (this.audioElement.paused) {
            this.isUserPaused = false;
            this.audioElement.play().catch(e => console.error('Play error:', e));
        } else {
            this.isUserPaused = true;
            this.audioElement.pause();
        }
    }
    
    useWavFallback(bytes) {
        const blob = new Blob([bytes], { type: 'audio/wav' });
        const url = URL.createObjectURL(blob);
        
        this.audioElement.pause();
        URL.revokeObjectURL(this.audioElement.src);
        
        this.audioElement.src = url;
        this.audioElement.load();
        
        if (this.voiceCard) {
            this.voiceCard.classList.remove('loading');
        }
        
        this.isStreamComplete = true;
        console.log(`[Player ${this.label}] WAV fallback ready, ${bytes.length} bytes`);
    }
    
    complete() {
        this.isStreamComplete = true;
        
        const totalTime = Date.now() - this.startTime;
        console.log(`[Player ${this.label}] Stream complete in ${totalTime}ms, ${this.totalChunks} chunks`);
        
        if (this.queue.length === 0 && !this.isAppending && this.mediaSource.readyState === 'open') {
            setTimeout(() => {
                if (this.mediaSource.readyState === 'open') {
                    try {
                        this.mediaSource.endOfStream();
                    } catch (e) {
                        console.error('Error ending stream:', e);
                    }
                }
            }, 100);
        }
    }
    
    formatTime(seconds) {
        if (isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }
    
    destroy() {
        this.audioElement.pause();
        if (this.mediaSource.readyState === 'open') {
            try {
                this.mediaSource.endOfStream();
            } catch (e) {}
        }
        URL.revokeObjectURL(this.audioElement.src);
    }
}

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

function createStreamingVoiceCard(label, audioPlayer, modelName) {
    console.log('createStreamingVoiceCard called:', { label, hasPlayer: !!audioPlayer, modelName });
    
    const card = document.createElement('div');
    card.className = 'voice-card';
    card.dataset.label = label;
    
    const header = document.createElement('div');
    header.className = 'voice-card-header';
    const labelText = modelName && currentMode === 'side-by-side' ? modelName : `Voice ${label}`;
    header.innerHTML = `<span class="voice-label">${labelText}</span>`;
    if (modelName) {
        header.innerHTML += `<span class="model-name">${modelName}</span>`;
    }
    
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
    
    if (audioPlayer) {
        playBtn.addEventListener('click', () => {
            if (isPlaying) {
                audioPlayer.pause();
                playBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M3 2l10 6-10 6V2z"/></svg>`;
            } else {
                audioPlayer.play().catch(e => console.error('Play error:', e));
                playBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><rect x="3" y="2" width="4" height="12"/><rect x="9" y="2" width="4" height="12"/></svg>`;
            }
            isPlaying = !isPlaying;
        });
        
        audioPlayer.addEventListener('timeupdate', () => {
            const currentTime = audioPlayer.getCurrentTime();
            const duration = audioPlayer.getDuration();
            if (duration && !isNaN(duration)) {
                const percentage = (currentTime / duration) * 100;
                progress.style.width = `${percentage}%`;
                timeLabel.textContent = formatTime(currentTime);
            }
        });
        
        audioPlayer.addEventListener('ended', () => {
            isPlaying = false;
            playBtn.innerHTML = `<svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M3 2l10 6-10 6V2z"/></svg>`;
            progress.style.width = '0%';
        });
        
        audioPlayer.addEventListener('loadedmetadata', () => {
            const duration = audioPlayer.getDuration();
            if (duration && !isNaN(duration)) {
                timeLabel.textContent = formatTime(duration);
            }
        });
        
        progressContainer.addEventListener('click', (e) => {
            const rect = progressBar.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const percentage = x / rect.width;
            const duration = audioPlayer.getDuration();
            if (duration && !isNaN(duration)) {
                audioPlayer.seek(percentage * duration);
            }
        });
    }
    
    controls.appendChild(playBtn);
    controls.appendChild(progressContainer);
    controls.appendChild(timeLabel);
    
    card.appendChild(header);
    card.appendChild(controls);
    
    console.log('Streaming voice card created successfully');
    return card;
}

function createVoiceCard(label, audioHex, modelName) {
    console.log('createVoiceCard called:', { label, audioHex: audioHex ? audioHex.substring(0, 50) + '...' : null, modelName });
    
    if (!audioHex) {
        console.error('createVoiceCard: audioHex is null or undefined!');
        return document.createElement('div'); // Return empty div to prevent crashes
    }
    
    const card = document.createElement('div');
    card.className = 'voice-card';
    card.dataset.label = label;
    
    const header = document.createElement('div');
    header.className = 'voice-card-header';
    const labelText = modelName && currentMode === 'side-by-side' ? modelName : `Voice ${label}`;
    header.innerHTML = `<span class="voice-label">${labelText}</span>`;
    if (modelName) {
        header.innerHTML += `<span class="model-name">${modelName}</span>`;
    }
    
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
    
    console.log('Voice card created successfully');
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

async function startSession(force = false) {
    if (sessionId && !force) {
        return;
    }
    
    try {
        const headers = { 'Content-Type': 'application/json' };
        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }
        
        const response = await fetch('/api/start-session', {
            method: 'POST',
            headers: headers,
            body: JSON.stringify({})
        });
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error('Start session failed:', response.status, errorData);
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        console.log('Session started:', data);
        sessionId = data.session_id;
        
        chatMessages.innerHTML = '';
        showScreen(chatScreen);
        
        if (authToken) {
            setTimeout(() => loadChatHistory(), 300);
        }
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
        const requestBody = { 
            session_id: sessionId, 
            message,
            mode: currentMode
        };
        
        if (currentMode === 'direct' && selectedModelSingle) {
            requestBody.model_id = selectedModelSingle;
        } else if (currentMode === 'side-by-side' && selectedModelA && selectedModelB) {
            requestBody.model_a_id = selectedModelA;
            requestBody.model_b_id = selectedModelB;
        }
        
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let textContent = '';
        let audioA = null;
        let audioB = null;
        let shouldVote = false;
        let messageDiv = null;
        let modelA = null;
        let modelB = null;
        let buffer = '';
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;
            
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                if (!line.trim()) continue;
                
                try {
                    const data = JSON.parse(line);
                    
                    if (data.type === 'text_delta') {
                        textContent += data.content;
                        if (!messageDiv) {
                            placeholder.remove();
                            messageDiv = addMessage(textContent, false);
                        } else {
                            const textDiv = messageDiv.querySelector('.message-text');
                            if (textDiv) {
                                textDiv.textContent = textContent;
                            }
                        }
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                        
                    } else if (data.type === 'text') {
                        textContent = data.content;
                        if (!messageDiv) {
                            placeholder.remove();
                            messageDiv = addMessage(textContent, false);
                        }
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                        
                    } else if (data.type === 'model_info') {
                        modelA = data.model_a;
                        modelB = data.model_b;
                        console.log('Received model_info:', modelA, modelB);
                        
                    } else if (data.type === 'audio_a') {
                        audioA = data.content;
                        console.log('=== AUDIO_A RECEIVED ===');
                        if (currentMode === 'direct' && messageDiv) {
                            updateMessageWithAudio(messageDiv, textContent, audioA, null, modelA, modelB);
                        } else if (messageDiv && audioB) {
                            updateMessageWithAudio(messageDiv, textContent, audioA, audioB, modelA, modelB);
                        }
                        
                    } else if (data.type === 'audio_b') {
                        audioB = data.content;
                        console.log('=== AUDIO_B RECEIVED ===');
                        if (messageDiv && audioA) {
                            updateMessageWithAudio(messageDiv, textContent, audioA, audioB, modelA, modelB);
                        }
                        
                    } else if (data.type === 'metadata') {
                        shouldVote = data.should_vote;
                    }
                    
                } catch (e) {
                    console.error('Error parsing stream chunk:', e);
                }
            }
        }
        
        if (buffer.trim()) {
            try {
                const data = JSON.parse(buffer);
                if (data.type === 'metadata') {
                    shouldVote = data.should_vote;
                }
            } catch (e) {
                console.error('Error parsing final buffer:', e);
            }
        }
        
        if (shouldVote) {
            showVotePrompt();
        }
        
        if (authToken) {
            loadChatHistory();
        }
    } catch (error) {
        console.error('Error sending message:', error);
        placeholder.remove();
        addMessage('Sorry, there was an error. Please try again.', false);
    }
}

// Real-time streaming version with sentence-buffered TTS
async function sendMessageRealtime(message) {
    if (!message.trim() || !sessionId) return;
    
    addMessage(message, true);
    messageInput.value = '';
    
    const placeholder = addGeneratingPlaceholder();
    
    // Initialize realtime audio players
    const realtimePlayers = {};
    
    try {
        const requestBody = { 
            session_id: sessionId, 
            message,
            mode: currentMode
        };
        
        if (currentMode === 'direct' && selectedModelSingle) {
            requestBody.model_id = selectedModelSingle;
        } else if (currentMode === 'side-by-side' && selectedModelA && selectedModelB) {
            requestBody.model_a_id = selectedModelA;
            requestBody.model_b_id = selectedModelB;
        }
        
        const response = await fetch('/api/chat/stream-realtime', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let textContent = '';
        let shouldVote = false;
        let messageDiv = null;
        let modelA = null;
        let modelB = null;
        let buffer = '';
        let streamStartTime = Date.now();
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value, { stream: true });
            buffer += chunk;
            
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';
            
            for (const line of lines) {
                if (!line.trim()) continue;
                
                try {
                    const data = JSON.parse(line);
                    
                    if (data.type === 'text_delta') {
                        textContent += data.content;
                        if (!messageDiv) {
                            placeholder.remove();
                            messageDiv = addMessage(textContent, false);
                            const indicator = document.createElement('span');
                            indicator.className = 'streaming-indicator';
                            indicator.innerHTML = '<span></span><span></span><span></span>';
                            const textDiv = messageDiv.querySelector('.message-text');
                            if (textDiv) textDiv.appendChild(indicator);
                        } else {
                            const textDiv = messageDiv.querySelector('.message-text');
                            if (textDiv) {
                                const indicator = textDiv.querySelector('.streaming-indicator');
                                textDiv.textContent = textContent;
                                if (indicator) textDiv.appendChild(indicator);
                            }
                        }
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                        
                    } else if (data.type === 'text') {
                        textContent = data.content;
                        if (messageDiv) {
                            const textDiv = messageDiv.querySelector('.message-text');
                            if (textDiv) textDiv.textContent = textContent;
                        } else {
                            placeholder.remove();
                            messageDiv = addMessage(textContent, false);
                        }
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                        console.log(`Text complete in ${Date.now() - streamStartTime}ms`);
                        
                    } else if (data.type === 'model_info') {
                        modelA = data.model_a;
                        modelB = data.model_b;
                        console.log('Received model_info:', modelA, modelB);
                        
                        if (!messageDiv) {
                            placeholder.remove();
                            messageDiv = addMessage('', false);
                        }
                        
                        // Create voice cards immediately when we know the models
                        if (messageDiv && currentMode !== 'direct') {
                            let voicesContainer = messageDiv.querySelector('.voices-container');
                            if (!voicesContainer) {
                                voicesContainer = document.createElement('div');
                                voicesContainer.className = 'voices-container';
                                messageDiv.appendChild(voicesContainer);
                                
                                // Create both voice cards upfront
                                const voiceCardA = document.createElement('div');
                                voiceCardA.className = 'voice-card';
                                voiceCardA.dataset.label = 'a';
                                
                                const headerA = document.createElement('div');
                                headerA.className = 'voice-card-header';
                                headerA.innerHTML = `<span class="voice-label">${modelA}</span>`;
                                voiceCardA.appendChild(headerA);
                                
                                const voiceCardB = document.createElement('div');
                                voiceCardB.className = 'voice-card';
                                voiceCardB.dataset.label = 'b';
                                
                                const headerB = document.createElement('div');
                                headerB.className = 'voice-card-header';
                                headerB.innerHTML = `<span class="voice-label">${modelB}</span>`;
                                voiceCardB.appendChild(headerB);
                                
                                voicesContainer.appendChild(voiceCardA);
                                voicesContainer.appendChild(voiceCardB);
                                
                                // Update global reference for voting
                                currentVoiceCards.voiceA = voiceCardA;
                                currentVoiceCards.voiceB = voiceCardB;
                                
                                console.log('Voice cards created for both models');
                            }
                        } else if (messageDiv && currentMode === 'direct') {
                            let voicesContainer = messageDiv.querySelector('.voices-container');
                            if (!voicesContainer) {
                                voicesContainer = document.createElement('div');
                                voicesContainer.className = 'voices-container';
                                messageDiv.appendChild(voicesContainer);
                                
                                const voiceCardA = document.createElement('div');
                                voiceCardA.className = 'voice-card';
                                voiceCardA.dataset.label = 'a';
                                
                                const headerA = document.createElement('div');
                                headerA.className = 'voice-card-header';
                                headerA.innerHTML = `<span class="voice-label">${modelA}</span>`;
                                voiceCardA.appendChild(headerA);
                                
                                voicesContainer.appendChild(voiceCardA);
                                
                                // Update global reference
                                currentVoiceCards.voiceA = voiceCardA;
                                currentVoiceCards.voiceB = null;
                                
                                console.log('Voice card created for direct mode');
                            }
                        }
                        
                    } else if (data.type === 'tts_error') {
                        console.error(`TTS ERROR for ${data.label}: ${data.error}`);
                        alert(`TTS Error (${data.label}): ${data.error}`);
                        
                    } else if (data.type === 'audio_chunk') {
                        const label = data.label;
                        const chunkId = data.chunk_id;
                        const hexData = data.data;
                        
                        console.log(`Received audio_chunk: label=${label}, chunkId=${chunkId}, dataLength=${hexData?.length}`);
                        
                        // Create player if doesn't exist
                        if (!realtimePlayers[label]) {
                            // Find the existing voice card
                            let voiceCard = null;
                            if (messageDiv) {
                                const voicesContainer = messageDiv.querySelector('.voices-container');
                                if (voicesContainer) {
                                    voiceCard = voicesContainer.querySelector(`[data-label="${label}"]`);
                                    console.log(`Found voice card for ${label}:`, !!voiceCard);
                                }
                            }
                            
                            // Create progressive audio player with the voice card
                            realtimePlayers[label] = new ProgressiveAudioPlayer(label, voiceCard);
                            console.log(`Created progressive player for ${label} with voiceCard:`, !!voiceCard);
                        }
                        
                        // Add chunk to player (progressive loading like YouTube)
                        realtimePlayers[label].addChunk(chunkId, hexData);
                        console.log(`Added chunk ${chunkId} to player ${label}`);
                        
                    } else if (data.type === 'metadata') {
                        shouldVote = data.should_vote;
                        
                        // Signal completion to all players
                        Object.values(realtimePlayers).forEach(player => {
                            if (player && player.complete) {
                                player.complete();
                            }
                        });
                        
                        // Show vote prompt immediately if needed
                        if (shouldVote) {
                            showVotePrompt();
                        }
                    } else if (data.type === 'error') {
                        console.error('Server error:', data.message);
                    }
                } catch (e) {
                    console.error('Error parsing stream chunk:', e, line);
                }
            }
        }
        
        // Process remaining buffer
        if (buffer.trim()) {
            try {
                const data = JSON.parse(buffer);
                if (data.type === 'metadata') {
                    shouldVote = data.should_vote;
                }
            } catch (e) {
                console.error('Error parsing final buffer:', e);
            }
        }
        
        if (shouldVote) {
            showVotePrompt();
        }
        
        if (authToken) {
            loadChatHistory();
        }
    } catch (error) {
        console.error('Error sending message:', error);
        placeholder.remove();
        addMessage('Sorry, there was an error. Please try again.', false);
        
        // Cleanup players on error
        Object.values(realtimePlayers).forEach(player => player.stop());
    }
}

function updateMessageWithAudio(messageDiv, text, audioA, audioB, modelA, modelB) {
    console.log('updateMessageWithAudio called:', { 
        mode: currentMode, 
        audioA: !!audioA, 
        audioB: !!audioB, 
        modelA, 
        modelB,
        messageDivExists: !!messageDiv,
        messageDivInDOM: messageDiv && document.body.contains(messageDiv)
    });
    
    if (!messageDiv || !document.body.contains(messageDiv)) {
        console.error('messageDiv is null or not in DOM!');
        return;
    }
    
    messageDiv.innerHTML = '';
    
    const textDiv = document.createElement('div');
    textDiv.className = 'message-text';
    textDiv.textContent = text;
    messageDiv.appendChild(textDiv);
    
    if (currentMode !== 'direct' && audioA && audioB) {
        console.log('Creating voice cards for battle/side-by-side');
        try {
            const voicesContainer = document.createElement('div');
            voicesContainer.className = 'voices-container';
            
            const voiceCardA = createVoiceCard('A', audioA, modelA);
            currentVoiceCards.voiceA = voiceCardA;
            voicesContainer.appendChild(voiceCardA);
            
            const voiceCardB = createVoiceCard('B', audioB, modelB);
            currentVoiceCards.voiceB = voiceCardB;
            voicesContainer.appendChild(voiceCardB);
            
            messageDiv.appendChild(voicesContainer);
            console.log('Voice cards added to message, voicesContainer children:', voicesContainer.children.length);
            console.log('Message div HTML after adding voices:', messageDiv.innerHTML.substring(0, 200));
        } catch (error) {
            console.error('Error creating voice cards:', error);
        }
    } else if (currentMode === 'direct' && audioA) {
        console.log('Creating voice card for direct mode');
        try {
            const voicesContainer = document.createElement('div');
            voicesContainer.className = 'voices-container';
            
            const voiceCardA = createVoiceCard('A', audioA, modelA);
            currentVoiceCards.voiceA = voiceCardA;
            voicesContainer.appendChild(voiceCardA);
            
            messageDiv.appendChild(voicesContainer);
            console.log('Voice card added to message');
        } catch (error) {
            console.error('Error creating voice card:', error);
        }
    } else {
        console.log('Conditions not met for voice cards:', { currentMode, audioA: !!audioA, audioB: !!audioB });
    }
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
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
        showToast('Vote recorded');
        
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
        showToast('Failed to submit vote');
    }
}

function getProviderLogo(provider) {
    const logos = {
        'ElevenLabs': '<img src="/logos/ElevenLabs_logo.png" alt="ElevenLabs">',
        'OpenAI': '<img src="/logos/openai-icon.webp" alt="OpenAI">',
        'Deepgram': '<img src="/logos/Deepgram-wordmark-black.png" alt="Deepgram">',
        'Cartesia': '<img src="/logos/cartesia-logo.svg" alt="Cartesia">',
        'Suno': '<img src="/logos/suno-logo.png" alt="Suno">',
        'Sesame': '<img src="/logos/sesame-logo.svg" alt="Sesame">',
        'MiniMax': '<img src="/logos/minimax-logo.png" alt="MiniMax">',
        'Canopy': '<img src="/logos/canopy-logo.png" alt="Canopy">',
        'Kokoro': '<img src="/logos/kokoro-logo.png" alt="Kokoro">'
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
    headerModelSelectors.classList.add('hidden');
    headerSingleModelSelector.classList.add('hidden');
    
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
            
            const logo = getProviderLogo(model.provider);
            
            item.innerHTML = `
                <div class="rank ${index < 3 ? 'top' : ''}">#${index + 1}</div>
                <div class="model-info">
                    <div class="model-name-with-logo">
                        <div class="leaderboard-logo">${logo}</div>
                        <div>
                            <div class="model-name">${model.name}</div>
                            <div class="model-provider">${model.provider}</div>
                        </div>
                    </div>
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

async function loadChatHistory() {
    const chatList = document.getElementById('sidebar-chat-list');
    
    if (!authToken) {
        console.log('loadChatHistory: No auth token, skipping');
        chatList.innerHTML = '<p class="empty-state">Log in to see recent chats</p>';
        return;
    }
    
    console.log('loadChatHistory: Fetching chat history...');
    
    try {
        const response = await fetch('/api/chat-history', {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (!response.ok) {
            console.error('loadChatHistory: HTTP error', response.status);
            return;
        }
        
        const data = await response.json();
        console.log('loadChatHistory: Received data', data);
        
        chatList.innerHTML = '';
        
        if (data.sessions && data.sessions.length > 0) {
            console.log(`loadChatHistory: Loading ${data.sessions.length} sessions`);
            data.sessions.forEach(session => {
                const item = document.createElement('div');
                item.className = 'sidebar-chat-item';
                if (sessionId === session.session_id) {
                    item.classList.add('active');
                }
                
                const date = new Date(session.created_at);
                const formattedDate = formatRelativeTime(date);
                
                item.innerHTML = `
                    <div class="sidebar-chat-item-content">
                        <div class="sidebar-chat-item-title">${session.title || 'New Chat'}</div>
                        <div class="sidebar-chat-item-date">${formattedDate}</div>
                    </div>
                    <button class="sidebar-chat-item-delete" data-session-id="${session.session_id}">
                        <svg width="12" height="12" viewBox="0 0 16 16" fill="currentColor">
                            <path d="M5 3V1h6v2h4v2h-1v9a1 1 0 01-1 1H3a1 1 0 01-1-1V5H1V3h4zm2 3v6h2V6H7zm4 0v6h2V6h-2z"/>
                        </svg>
                    </button>
                `;
                
                item.addEventListener('click', (e) => {
                    if (!e.target.closest('.sidebar-chat-item-delete')) {
                        loadChatSession(session.session_id);
                    }
                });
                
                const deleteBtn = item.querySelector('.sidebar-chat-item-delete');
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    deleteChat(session.session_id);
                });
                
                chatList.appendChild(item);
            });
        } else {
            chatList.innerHTML = '<p class="empty-state">No chats yet</p>';
        }
    } catch (error) {
        console.error('Error loading chat history:', error);
    }
}

function formatRelativeTime(date) {
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
}

async function loadChatSession(sessionIdToLoad) {
    try {
        const response = await fetch(`/api/chat-session/${sessionIdToLoad}`, {
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        const data = await response.json();
        
        sessionId = data.session_id;
        
        chatMessages.innerHTML = '';
        votePrompt.classList.add('hidden');
        
        if (data.messages && data.messages.length > 0) {
            data.messages.forEach(msg => {
                addMessage(msg.content, msg.role === 'user');
            });
        }
        
        showScreen(chatScreen);
        updateActiveNav(navChat);
        loadChatHistory();
    } catch (error) {
        console.error('Error loading chat session:', error);
        alert('Failed to load chat session. Please try again.');
    }
}

async function deleteChat(sessionIdToDelete) {
    if (!confirm('Are you sure you want to delete this chat?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/chat-session/${sessionIdToDelete}`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${authToken}`
            }
        });
        
        if (response.ok) {
            if (sessionId === sessionIdToDelete) {
                startNewChat();
            } else {
                loadChatHistory();
            }
        } else {
            alert('Failed to delete chat.');
        }
    } catch (error) {
        console.error('Error deleting chat:', error);
        alert('Failed to delete chat. Please try again.');
    }
}

async function startNewChat() {
    if (!sessionId) {
        return;
    }
    
    sessionId = null;
    chatMessages.innerHTML = '';
    votePrompt.classList.add('hidden');
    
    showScreen(chatScreen);
    updateActiveNav(navChat);
    
    await startSession(true);
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
                const response = await fetch('/api/transcribe', {
                    method: 'POST',
                    body: formData
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                
                if (data.text && data.text.trim()) {
                    sendMessageRealtime(data.text);
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
    sendMessageRealtime(message);
});

messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
        const message = messageInput.value;
        sendMessageRealtime(message);
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
const newChatBtn = document.getElementById('new-chat-btn');
const navChat = document.getElementById('nav-chat');
const navLeaderboard = document.getElementById('nav-leaderboard');

sidebarToggle.addEventListener('click', () => {
    sidebar.classList.toggle('collapsed');
});

newChatBtn.addEventListener('click', () => {
    startNewChat();
});

navChat.addEventListener('click', () => {
    showScreen(chatScreen);
    updateActiveNav(navChat);
    updateModelSelectorsVisibility();
});

navLeaderboard.addEventListener('click', () => {
    loadLeaderboard();
    updateActiveNav(navLeaderboard);
    headerModelSelectors.classList.add('hidden');
    headerSingleModelSelector.classList.add('hidden');
});

function updateActiveNav(activeItem) {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    activeItem.classList.add('active');
}

// Authentication functions
function updateUIForUser(user) {
    console.log('updateUIForUser called with:', user);
    currentUser = user;
    const userAvatar = document.getElementById('user-avatar');
    
    console.log('DOM elements:', {
        loginBtn: loginBtn,
        headerLoginBtn: headerLoginBtn,
        userProfile: userProfile,
        userEmail: userEmail,
        userAvatar: userAvatar
    });
    
    if (user) {
        console.log('User is logged in, updating UI...');
        console.log('User email:', user.email);
        console.log('User metadata:', user.user_metadata);
        
        loginBtn.classList.add('hidden');
        headerLoginBtn.classList.add('hidden');
        userProfile.classList.remove('hidden');
        headerUserProfile.classList.remove('hidden');
        userEmail.textContent = user.email;
        headerUserEmail.textContent = user.email;
        
        console.log('Updated userEmail text to:', user.email);
        console.log('Login buttons hidden:', loginBtn.classList.contains('hidden'), headerLoginBtn.classList.contains('hidden'));
        console.log('Profile visible:', !userProfile.classList.contains('hidden'));
        
        const avatarUrl = user.user_metadata?.avatar_url || user.user_metadata?.picture;
        console.log('Avatar URL:', avatarUrl);
        if (avatarUrl && userAvatar) {
            userAvatar.src = avatarUrl;
            console.log('Set avatar src to:', avatarUrl);
        }
        
        loadChatHistory();
    } else {
        console.log('User is logged out, resetting UI...');
        loginBtn.classList.remove('hidden');
        headerLoginBtn.classList.remove('hidden');
        userProfile.classList.add('hidden');
        headerUserProfile.classList.add('hidden');
        currentUser = null;
        authToken = null;
        
        loadChatHistory();
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
            alert(data.message || 'Signup successful! You can now login.');
            // Clear the form
            emailInput.value = '';
            passwordInput.value = '';
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
        authToken = null;
        localStorage.removeItem('authToken');
        updateUIForUser(null);
    } catch (error) {
        console.error('Logout error:', error);
        authToken = null;
        localStorage.removeItem('authToken');
        updateUIForUser(null);
    }
});

// Check for OAuth callback (both hash and query params from Supabase)
function handleOAuthCallback() {
    console.log('Checking for OAuth callback...');
    console.log('Current URL:', window.location.href);
    console.log('Hash:', window.location.hash);
    console.log('Search:', window.location.search);
    
    // Check for hash fragment (implicit flow)
    const hashParams = new URLSearchParams(window.location.hash.substring(1));
    let accessToken = hashParams.get('access_token');
    
    // Check for query params (PKCE flow - code exchange)
    const searchParams = new URLSearchParams(window.location.search);
    const code = searchParams.get('code');
    
    console.log('Access token from hash:', accessToken);
    console.log('Code from query:', code);
    
    // If we have a code, exchange it for a token
    if (code && !accessToken) {
        console.log('Found auth code, exchanging for token...');
        fetch('/api/auth/exchange-code', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code })
        })
        .then(res => {
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            return res.json();
        })
        .then(data => {
            console.log('Code exchange response:', data);
            if (data.access_token) {
                accessToken = data.access_token;
                verifyAndUpdateUser(accessToken);
            } else {
                console.error('No access token in response:', data);
                window.history.replaceState({}, document.title, window.location.pathname);
            }
        })
        .catch(err => {
            console.error('Error exchanging code:', err);
            window.history.replaceState({}, document.title, window.location.pathname);
        });
    } else if (accessToken) {
        console.log('Found access token directly, verifying...');
        verifyAndUpdateUser(accessToken);
    } else {
        console.log('No access token or code found in URL');
    }
}

function verifyAndUpdateUser(accessToken) {
    console.log('Verifying token and updating user...');
    authToken = accessToken;
    localStorage.setItem('authToken', accessToken);
    
    fetch('/api/auth/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: accessToken })
    })
    .then(res => res.json())
    .then(data => {
        console.log('Verify response:', data);
        if (data.user) {
            console.log('User verified, updating UI...');
            updateUIForUser(data.user);
            // Close login modal if open
            loginModal.classList.add('hidden');
            // Clean up URL
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    })
    .catch(err => {
        console.error('Error verifying OAuth token:', err);
        localStorage.removeItem('authToken');
    });
}

// Check for existing auth token on load
const storedToken = localStorage.getItem('authToken');

// Always check for OAuth callback first (handles redirect from Google)
const hasOAuthParams = window.location.hash.includes('access_token') || window.location.search.includes('code=');
if (hasOAuthParams) {
    handleOAuthCallback();
} else if (storedToken) {
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
            authToken = null;
        }
    })
    .catch(() => {
        localStorage.removeItem('authToken');
        authToken = null;
        loadChatHistory();
    });
}

loadChatHistory();

// Mode switching
document.querySelectorAll('.mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const mode = btn.dataset.mode;
        switchMode(mode);
    });
});

function switchMode(mode) {
    currentMode = mode;
    
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
    
    showScreen(chatScreen);
    chatScreen.className = 'screen active mode-' + mode;
    
    updateModelSelectorsVisibility();
    updateActiveNav(navChat);
    
    startSession();
}

function updateModelSelectorsVisibility() {
    headerModelSelectors.classList.add('hidden');
    headerSingleModelSelector.classList.add('hidden');
    
    if (currentMode === 'side-by-side') {
        headerModelSelectors.classList.remove('hidden');
        loadModels();
    } else if (currentMode === 'direct') {
        headerSingleModelSelector.classList.remove('hidden');
        loadModels();
    }
}

function getProviderLogoPath(provider) {
    const logoMap = {
        'OpenAI': '/logos/openai-icon.webp',
        'ElevenLabs': '/logos/ElevenLabs_logo.png',
        'Deepgram': '/logos/Deepgram-wordmark-black.png',
        'Cartesia': '/logos/cartesia-logo.svg',
        'Suno': '/logos/suno-logo.png',
        'Sesame': '/logos/sesame-logo.svg',
        'MiniMax': '/logos/minimax-logo.png',
        'Canopy': '/logos/canopy-logo.png',
        'Kokoro': '/logos/kokoro-logo.png'
    };
    return logoMap[provider] || '';
}

function initCustomSelect(selectElement, onChangeCallback) {
    const trigger = selectElement.querySelector('.custom-select-trigger');
    const optionsContainer = selectElement.querySelector('.custom-options');
    
    trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        document.querySelectorAll('.custom-select').forEach(s => {
            if (s !== selectElement) s.classList.remove('active');
        });
        selectElement.classList.toggle('active');
    });
    
    document.addEventListener('click', () => {
        selectElement.classList.remove('active');
    });
    
    selectElement.setOptions = (models, selectedId = null) => {
        optionsContainer.innerHTML = '';
        
        models.forEach(model => {
            const option = document.createElement('div');
            option.className = 'custom-option';
            option.dataset.value = model.id;
            
            const logoPath = getProviderLogoPath(model.provider);
            if (logoPath) {
                const img = document.createElement('img');
                img.src = logoPath;
                img.alt = model.provider;
                img.className = 'model-logo';
                option.appendChild(img);
            }
            
            const text = document.createElement('span');
            text.className = 'custom-option-text';
            text.textContent = model.display_name || model.name;
            option.appendChild(text);
            
            if (model.id === selectedId) {
                option.classList.add('selected');
            }
            
            option.addEventListener('click', () => {
                optionsContainer.querySelectorAll('.custom-option').forEach(o => {
                    o.classList.remove('selected');
                });
                option.classList.add('selected');
                
                const triggerSpan = trigger.querySelector('span');
                triggerSpan.innerHTML = '';
                if (logoPath) {
                    const img = document.createElement('img');
                    img.src = logoPath;
                    img.alt = model.provider;
                    img.className = 'model-logo';
                    triggerSpan.appendChild(img);
                }
                const textNode = document.createTextNode(model.display_name || model.name);
                triggerSpan.appendChild(textNode);
                
                selectElement.classList.remove('active');
                
                if (onChangeCallback) {
                    onChangeCallback(model.id);
                }
            });
            
            optionsContainer.appendChild(option);
        });
        
        if (selectedId && models.length > 0) {
            const selectedModel = models.find(m => m.id === selectedId);
            if (selectedModel) {
                const triggerSpan = trigger.querySelector('span');
                triggerSpan.innerHTML = '';
                const logoPath = getProviderLogoPath(selectedModel.provider);
                if (logoPath) {
                    const img = document.createElement('img');
                    img.src = logoPath;
                    img.alt = selectedModel.provider;
                    img.className = 'model-logo';
                    triggerSpan.appendChild(img);
                }
                const textNode = document.createTextNode(selectedModel.display_name || selectedModel.name);
                triggerSpan.appendChild(textNode);
            }
        }
    };
}

async function loadModels() {
    try {
        const response = await fetch('/api/models');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Loaded models:', data);
        availableModels = data.models || [];
        
        if (!availableModels || availableModels.length === 0) {
            console.error('No models available');
            return;
        }
        
        if (currentMode === 'side-by-side') {
            if (availableModels.length >= 2) {
                selectedModelA = selectedModelA || availableModels[0].id;
                selectedModelB = selectedModelB || availableModels[1].id;
            }
            headerModelSelectA.setOptions(availableModels, selectedModelA);
            headerModelSelectB.setOptions(availableModels, selectedModelB);
        } else if (currentMode === 'direct') {
            if (availableModels.length > 0) {
                selectedModelSingle = selectedModelSingle || availableModels[0].id;
            }
            headerModelSelectSingle.setOptions(availableModels, selectedModelSingle);
        }
    } catch (error) {
        console.error('Error loading models:', error);
    }
}

// Initialize custom select dropdowns
initCustomSelect(headerModelSelectA, (modelId) => {
    selectedModelA = modelId;
    startSession();
});

initCustomSelect(headerModelSelectB, (modelId) => {
    selectedModelB = modelId;
    startSession();
});

initCustomSelect(headerModelSelectSingle, (modelId) => {
    selectedModelSingle = modelId;
    startSession();
});

// Initialize with battle mode
switchMode('battle');
updateActiveNav(navChat);
