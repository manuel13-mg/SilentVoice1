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
        // Includes quick message buttons AND the back/start buttons
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

    // Handle generic links (<a> tags)
    if (el.tagName === 'A') {
        window.location.assign(el.href);
        return;
    }

    // --- Specific Logic ---

    // 1. Check for Back Button FIRST to ensure navigation happens
    if (el.id === 'backBtn' || el.id === 'backButton') {
        // Navigate back to index.html without stopping the camera (handled by main.js persistence)
        window.location.assign('/');
        return; 
    }
    
    // 2. Main Page Start/Stop
    else if (el.id === 'startButton') {
        startCommunication();
    }
    else if (el.id === 'stopButton') {
        stopCommunication();
    }
    else if (el.id === 'navMessageBtn' && document.body.classList.contains('main-page')) {
        // Switch to Morse Input Mode if needed
        state.currentMode = 'morse_input';
        state.socket.emit('set_mode', { mode: 'morse_input' });
    }
    
    // 3. Quick Messages (Text to Speech)
    else if (el.classList.contains('quick-message-button')) {
        const textElement = el.querySelector('.text');
        // Only speak if there is text content (prevents errors on buttons without text)
        if (textElement) {
            const text = textElement.innerText;
            speakMessage(text);
            if (document.getElementById('messageDisplay')) {
                 document.getElementById('messageDisplay').innerText = `Selected: ${text}`;
            }
        }
    }
    
    // 4. Device Control
    else if (el.dataset.device) {
        window.location.assign(`/devicecontrol.html?device=${el.dataset.device}`);
    }
    
    // Auto-advance highlight after selection (unless we just navigated away)
    if (state.currentMode !== 'morse_input' && el.tagName !== 'A' && el.id !== 'backButton' && el.id !== 'backBtn') {
        moveHighlight(1);
    }
}