import { state, elements } from './config.js';
import { setupSocketEvents } from './socketClient.js';
import { initWebcam, stopWebcam } from './webcam.js';
import { initializeNavigation } from './navigation.js';
import { populateUserDropdown, setupUserListeners, updateTimerDisplay } from './ui.js';
import { initGame } from './game.js';

// --- Global Controls ---
export function startCommunication() {
    if (!state.currentSelectedUser) {
        alert("Select a user first.");
        return;
    }

    // Prevent multiple start calls
    if (state.isStreaming) return;

    // 1. Tell backend to load user
    state.socket.emit('select_user', { username: state.currentSelectedUser }, (response) => {
        if (response.status === 'success') {
            // 2. Start Webcam
            initWebcam();
            // 3. Start Backend Stream
            state.currentMode = 'navigation';
            state.socket.emit('start_stream');
            state.socket.emit('set_mode', { mode: 'navigation' });
            
            state.communicationStartTime = Date.now();
            state.timerInterval = setInterval(updateTimerDisplay, 1000);
            
            // Set streaming flag for persistence
            state.isStreaming = true;
            sessionStorage.setItem('isStreaming', 'true');
            
            initializeNavigation();
            
            // Update buttons state if they exist
            const startBtn = document.getElementById('startButton');
            const stopBtn = document.getElementById('stopButton');
            const clearBtn = document.getElementById('clearButton');
            if (startBtn) startBtn.disabled = true;
            if (stopBtn) stopBtn.disabled = false;
            if (clearBtn) clearBtn.disabled = false;

        } else {
            alert(response.message);
        }
    });
}

export function stopCommunication() {
    stopWebcam();
    clearInterval(state.timerInterval);
    state.currentMode = 'idle';
    state.isStreaming = false;
    sessionStorage.setItem('isStreaming', 'false');

    if(state.socket) {
        state.socket.emit('stop_stream');
        state.socket.emit('set_mode', { mode: 'idle' });
    }

    // Update buttons state if they exist
    const startBtn = document.getElementById('startButton');
    const stopBtn = document.getElementById('stopButton');
    const clearBtn = document.getElementById('clearButton');
    if (startBtn) startBtn.disabled = false;
    if (stopBtn) stopBtn.disabled = true;
    if (clearBtn) clearBtn.disabled = true;
}

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    // Cache common elements
    elements.userSelect = document.getElementById('userSelect');
    elements.statusText = document.getElementById('overallStatusText');
    
    setupSocketEvents();
    populateUserDropdown();
    setupUserListeners();

    // Page Specific Init
    if (document.body.classList.contains('main-page')) {
        document.getElementById('startButton')?.addEventListener('click', startCommunication);
        document.getElementById('stopButton')?.addEventListener('click', stopCommunication);
        setTimeout(initializeNavigation, 500);
    } 
    else if (document.body.classList.contains('flappy-bird-page')) {
        initGame();
    }
    else {
        // Other pages
        setTimeout(initializeNavigation, 500);
    }

    // --- Auto-Start Logic for Persistence ---
    // If the user was streaming on the previous page, restart immediately.
    if (sessionStorage.getItem('isStreaming') === 'true' && state.currentSelectedUser) {
        // Slight delay to ensure socket is ready
        setTimeout(() => {
            console.log("Restoring webcam stream...");
            startCommunication();
        }, 500);
    }
});