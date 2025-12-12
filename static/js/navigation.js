import { state } from './config.js';
import { stopCommunication, startCommunication } from './main.js';
import { speakMessage } from './utils.js';

let navigableElements = [];
let currentNavIndex = -1;

export function initializeNavigation() {
    navigableElements = [];
    currentNavIndex = -1;
    
    // Selectors based on page
    if (document.body.classList.contains('main-page')) {
        navigableElements = Array.from(document.querySelectorAll('.nav-button, .control-button'));
    } else if (document.body.classList.contains('room-control-page')) {
        navigableElements = Array.from(document.querySelectorAll('.device-button'));
    } else if (document.body.classList.contains('quick-messages-page')) {
        navigableElements = Array.from(document.querySelectorAll('.quick-message-button, #backButton, #startQuickMsgButton'));
    } else if (document.body.classList.contains('device-control-page')) {
        navigableElements = Array.from(document.querySelectorAll('.control-button'));
    }

    if (navigableElements.length > 0) setHighlight(0);
}

export function setHighlight(index) {
    navigableElements.forEach(el => el.classList.remove('highlighted'));
    currentNavIndex = index;
    if (navigableElements[currentNavIndex]) {
        navigableElements[currentNavIndex].classList.add('highlighted');
        navigableElements[currentNavIndex].scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

export function moveHighlight(direction) {
    if (navigableElements.length === 0) return;
    let newIndex = (currentNavIndex + direction + navigableElements.length) % navigableElements.length;
    setHighlight(newIndex);
}

export function selectHighlightedElement() {
    if (currentNavIndex < 0 || !navigableElements[currentNavIndex]) return;
    const el = navigableElements[currentNavIndex];
    el.classList.remove('highlighted');
    
    console.log(`Selected: ${el.id || el.innerText}`);

    // Handle generic links
    if (el.tagName === 'A') {
        // Do NOT stop communication here; let main.js auto-start on the next page
        window.location.assign(el.href);
        return;
    }

    // Handle specific Logic
    if (el.id === 'startButton') startCommunication();
    else if (el.id === 'stopButton') stopCommunication();
    else if (el.id === 'navMessageBtn' && document.body.classList.contains('main-page')) {
        state.currentMode = 'morse_input';
        state.socket.emit('set_mode', { mode: 'morse_input' });
    }
    else if (el.classList.contains('quick-message-button')) {
        const text = el.querySelector('.text').innerText;
        speakMessage(text);
        if (document.getElementById('messageDisplay')) {
             document.getElementById('messageDisplay').innerText = `Selected: ${text}`;
        }
    }
    else if (el.dataset.device) {
        window.location.assign(`/devicecontrol.html?device=${el.dataset.device}`);
    }
    else if (el.id === 'backBtn' || el.id === 'backButton') {
        // Do NOT stop communication here; allow seamless restart on index page
        window.location.assign('/');
    }
    
    // Auto-advance if not mode switching
    if (state.currentMode !== 'morse_input' && el.tagName !== 'A') {
        moveHighlight(1);
    }
}