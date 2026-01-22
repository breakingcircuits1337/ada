
// DOM Elements
const connectBtn = document.getElementById('connect-btn');
const micBtn = document.getElementById('mic-btn');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const chatMessages = document.getElementById('chat-messages');
const connectionStatus = document.getElementById('connection-status');
const gestureResult = document.getElementById('gesture-result');
const inputVideo = document.getElementById('input-video');
const outputCanvas = document.getElementById('output-canvas');
const canvasCtx = outputCanvas.getContext('2d');
const agentStatusText = document.getElementById('agent-status-text');

// State
let room = null;
let isConnected = false;
let isMicOn = false;
let lastGesture = "NONE";
let lastGestureTime = 0;

// Configuration
const API_URL = 'http://localhost:8000';
const LIVEKIT_URL = 'ws://localhost:7880'; 

// --- Helper Functions ---

function addLog(text, type = 'system') {
    const div = document.createElement('div');
    div.className = `message ${type}`;
    div.innerText = `> ${text}`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// --- LiveKit Integration ---

async function connectToLiveKit() {
    if (isConnected) return;

    try {
        addLog("Requesting access token...", "system");
        
        // 1. Get Token
        const response = await fetch(`${API_URL}/token`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                room_name: 'command-center',
                participant_name: 'Commander'
            })
        });

        if (!response.ok) throw new Error("Failed to get token");
        const data = await response.json();
        const token = data.token;

        addLog("Token acquired. Connecting to LiveKit...", "system");

        // 2. Connect to Room
        room = new LiveKitClient.Room({
            adaptiveStream: true,
            dynacast: true,
        });

        await room.connect(LIVEKIT_URL, token);
        
        isConnected = true;
        connectionStatus.classList.add('connected');
        connectBtn.innerText = "DISCONNECT";
        micBtn.classList.remove('disabled');
        agentStatusText.innerText = "ONLINE";
        addLog("L.I.S.A System Online. Voice Channel Active.", "system");

        // 3. Set up Event Listeners
        room.on(LiveKitClient.RoomEvent.DataReceived, (payload, participant, kind, topic) => {
            const strData = new TextDecoder().decode(payload);
            
            if (topic === "chat_message") {
                addLog(`L.I.S.A: ${strData}`, "agent");
            }
        });

        room.on(LiveKitClient.RoomEvent.ActiveSpeakersChanged, (speakers) => {
           if (speakers.length > 0) {
               agentStatusText.innerText = "SPEAKING...";
               document.querySelector('.core').style.animationDuration = "0.5s";
           } else {
               agentStatusText.innerText = "ONLINE";
               document.querySelector('.core').style.animationDuration = "2s";
           }
        });

        // 4. Publish Microphone (optional, starts muted)
        await room.localParticipant.setMicrophoneEnabled(true);
        isMicOn = true;
        micBtn.innerText = "MUTE MIC";

    } catch (error) {
        console.error(error);
        addLog(`Connection Failed: ${error.message}`, "error");
        connectionStatus.classList.add('error');
    }
}

async function sendChatMessage() {
    const text = chatInput.value.trim();
    if (!text || !room) return;

    addLog(`You: ${text}`, "user");
    
    // Send to Agent via Data Packet
    const data = new TextEncoder().encode(text);
    await room.localParticipant.publishData(data, {
        reliable: true,
        topic: "chat_message"
    });

    chatInput.value = "";
}

// --- Hand Tracking (MediaPipe) ---

function onResults(results) {
    // Draw Video
    canvasCtx.save();
    canvasCtx.clearRect(0, 0, outputCanvas.width, outputCanvas.height);
    canvasCtx.drawImage(results.image, 0, 0, outputCanvas.width, outputCanvas.height);

    if (results.multiHandLandmarks) {
        for (const landmarks of results.multiHandLandmarks) {
            // Draw Connectors and Landmarks
            drawConnectors(canvasCtx, landmarks, HAND_CONNECTIONS, {color: '#00f3ff', lineWidth: 2});
            drawLandmarks(canvasCtx, landmarks, {color: '#0ff', lineWidth: 1, radius: 3});

            // Detect Gesture
            const gesture = detectGesture(landmarks);
            if (gesture !== "NONE") {
                updateGestureUI(gesture);
            }
        }
    }
    canvasCtx.restore();
}

function detectGesture(landmarks) {
    // Simple heuristic based on finger states (extended vs curled)
    
    // Thumb tip vs IP joint (simplified)
    const thumbIsOpen = landmarks[4].x < landmarks[3].x; // Assuming right hand logic for simplicity or mirroring
    
    // Fingers: Compare tip y with pip y (up is lower y in canvas usually, but let's check distance)
    const indexIsOpen = landmarks[8].y < landmarks[6].y;
    const middleIsOpen = landmarks[12].y < landmarks[10].y;
    const ringIsOpen = landmarks[16].y < landmarks[14].y;
    const pinkyIsOpen = landmarks[20].y < landmarks[18].y;

    // Logic
    if (indexIsOpen && middleIsOpen && ringIsOpen && pinkyIsOpen) {
        return "Open_Palm";
    } else if (!indexIsOpen && !middleIsOpen && !ringIsOpen && !pinkyIsOpen) {
        // Check thumb for Thumb Up
        // Thumb Up: Thumb is up (y) and extended
        if (landmarks[4].y < landmarks[3].y && landmarks[4].y < landmarks[8].y) {
             return "Thumb_Up";
        }
        return "Closed_Fist";
    }
    
    return "NONE";
}

function updateGestureUI(gesture) {
    gestureResult.innerText = gesture;
    gestureResult.style.color = "#00f3ff";

    // Rate limit sending gestures to 1 per second
    const now = Date.now();
    if (now - lastGestureTime > 2000 && gesture !== lastGesture) {
        lastGesture = gesture;
        lastGestureTime = now;
        
        if (room && isConnected) {
             const data = new TextEncoder().encode(gesture);
             room.localParticipant.publishData(data, {
                 reliable: true,
                 topic: "gesture"
             });
             addLog(`Gesture Sent: ${gesture}`, "system");
        }
    }
}

// Initialize MediaPipe
const hands = new Hands({locateFile: (file) => {
    return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
}});

hands.setOptions({
    maxNumHands: 1,
    modelComplexity: 1,
    minDetectionConfidence: 0.5,
    minTrackingConfidence: 0.5
});

hands.onResults(onResults);

// Setup Camera
const camera = new Camera(inputVideo, {
    onFrame: async () => {
        await hands.send({image: inputVideo});
    },
    width: 640,
    height: 480
});

// --- Event Listeners ---

connectBtn.addEventListener('click', async () => {
    if (!isConnected) {
        await connectToLiveKit();
        camera.start();
        // Resize canvas to match video
        outputCanvas.width = 640;
        outputCanvas.height = 480;
    } else {
        // Disconnect logic
        if (room) room.disconnect();
        isConnected = false;
        connectBtn.innerText = "INITIALIZE CONNECTION";
        connectionStatus.classList.remove('connected');
        addLog("Disconnected.", "system");
    }
});

micBtn.addEventListener('click', async () => {
    if (!room) return;
    
    isMicOn = !isMicOn;
    await room.localParticipant.setMicrophoneEnabled(isMicOn);
    micBtn.innerText = isMicOn ? "MUTE MIC" : "UNMUTE MIC";
    micBtn.classList.toggle('active', isMicOn);
});

sendBtn.addEventListener('click', sendChatMessage);
chatInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendChatMessage();
});

// Initial Log
addLog("System initialized. Waiting for user authorization...", "system");
