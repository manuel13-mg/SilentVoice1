import { state } from './config.js';
import { moveHighlight, selectHighlightedElement } from './navigation.js';
import { updateStatus, updateMessageDisplay, updateTimerDisplay } from './ui.js';
import { stopCommunication } from './main.js'; // Circular dependency handled by function reference
import { handleGameBlink } from './game.js';

export function setupSocketEvents() {
    if (state.socket && state.socket.connected) return;

    state.socket = io();

    state.socket.on('connect', () => {
        console.log('Connected to server.');
        if (state.currentMode !== 'idle') {
            state.socket.emit('set_mode', { mode: state.currentMode });
        }
    });

    state.socket.on('disconnect', () => {
        console.log('Disconnected.');
        stopCommunication();
    });

    state.socket.on('blink_detected', (data) => {
        // Route blink events based on page/mode
        if (document.body.classList.contains('flappy-bird-page')) {
            handleGameBlink(data.type);
        } else if (state.currentMode === 'navigation') {
            if (data.type === 'dot') moveHighlight(1);
            else if (data.type === 'dash') selectHighlightedElement();
        }
    });

    state.socket.on('update_ui', (data) => {
        updateMessageDisplay(data);
        updateStatus(data.status);
        updateTimerDisplay();
    });

    state.socket.on('status', (data) => {
        updateStatus(data.message);
        if (data.message.includes('not trained') || data.message.includes('No user')) {
            stopCommunication();
        }
    });
}