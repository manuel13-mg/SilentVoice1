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
            initializeNavigation();
        } else {
            alert(response.message);
        }
    });
}

export function stopCommunication() {
    stopWebcam();
    clearInterval(state.timerInterval);
    state.currentMode = 'idle';
    if(state.socket) {
        state.socket.emit('stop_stream');
        state.socket.emit('set_mode', { mode: 'idle' });
    }
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
});