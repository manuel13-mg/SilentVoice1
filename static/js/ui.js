/**
 * ui.js
 * Handles DOM updates, User Interface logic, and User Management.
 */
import { state, elements } from './config.js';

// --- Timer Logic ---
export function updateTimerDisplay() {
    if (!state.communicationStartTime) return;
    
    const elapsedSeconds = Math.floor((Date.now() - state.communicationStartTime) / 1000);
    const hours = Math.floor(elapsedSeconds / 3600);
    const minutes = Math.floor((elapsedSeconds % 3600) / 60);
    const seconds = elapsedSeconds % 60;
    
    // We safeguard against null elements in case they don't exist on the current page
    const hDisplay = document.getElementById('hoursDisplay');
    const mDisplay = document.getElementById('minutesDisplay');
    const sDisplay = document.getElementById('secondsDisplay');

    if (hDisplay) hDisplay.textContent = hours.toString().padStart(2, '0');
    if (mDisplay) mDisplay.textContent = minutes.toString().padStart(2, '0');
    if (sDisplay) sDisplay.textContent = seconds.toString().padStart(2, '0');
}

// --- Status & Feedback Updates ---
export function updateStatus(message) {
    if (elements.statusText) {
        elements.statusText.textContent = message || 'Status: Idle';
    }
    console.log(`${new Date().toLocaleTimeString()} Status: ${message}`);
}

export function updateMessageDisplay(data) {
    const msgDisplay = document.getElementById('messageDisplay');
    const seqDisplay = document.getElementById('morseSequenceDisplay');
    const progressBar = document.getElementById('cooldownProgressBar');
    const letterTimer = document.getElementById('letterTimerInfo');
    const spaceTimer = document.getElementById('spaceTimerInfo');

    // Update Message Text
    if (msgDisplay) {
        // Different logic for quick messages page vs standard Morse page
        if (document.body.classList.contains('quick-messages-page')) {
            if (!msgDisplay.textContent.startsWith('Selected Message: ')) {
                msgDisplay.textContent = 'Selected Message: ';
            }
        } else if (data.message !== undefined) {
             msgDisplay.textContent = `Message: ${data.message}`;
        }
    }

    // Update Morse Sequence (dots/dashes)
    if (seqDisplay) {
        seqDisplay.textContent = `Current: ${state.currentMode === 'morse_input' ? (data.morse_sequence || '') : ''}`;
    }

    // Update Visual Progress Bar
    if (progressBar) {
        if (data.cooldown_percent !== undefined) {
            progressBar.style.width = `${data.cooldown_percent * 100}%`;
            progressBar.style.backgroundColor = data.cooldown_percent < 1 ? 'orange' : 'var(--success-green)';
        } else {
            progressBar.style.width = '0%';
        }
    }

    // Update Timers for next letter/space
    if (letterTimer) letterTimer.textContent = (data.letter_timer > 0) ? `Letter in: ${data.letter_timer.toFixed(1)}s` : '';
    if (spaceTimer) spaceTimer.textContent = (data.space_timer > 0) ? `Space in: ${data.space_timer.toFixed(1)}s` : '';
}

// --- User Management Logic ---
export async function populateUserDropdown() {
    if (!elements.userSelect) return;

    try {
        const response = await fetch('/users');
        const users = await response.json();
        
        elements.userSelect.innerHTML = '<option value="">-- Select User --</option>';
        let foundStoredUser = false;

        for (const username in users) {
            const option = document.createElement('option');
            option.value = username;
            option.textContent = `${username} (${users[username].trained ? 'Trained' : 'Not Trained'})`;
            elements.userSelect.appendChild(option);
        }

        // Restore user from session storage
        const storedUser = sessionStorage.getItem('currentSelectedUser');
        if (storedUser && elements.userSelect.querySelector(`option[value="${storedUser}"]`)) {
            elements.userSelect.value = storedUser;
            state.currentSelectedUser = storedUser;
            foundStoredUser = true;
        }

        // Default to 'test' if no user found
        if (!foundStoredUser) {
            const testUserOption = elements.userSelect.querySelector('option[value="test"]');
            if (testUserOption) {
                elements.userSelect.value = 'test';
                state.currentSelectedUser = 'test';
            }
        }
    } catch (error) {
        console.error('Error fetching users:', error);
    }
}

export function setupUserListeners() {
    // Dropdown change listener
    if (elements.userSelect) {
        elements.userSelect.addEventListener('change', (e) => {
            state.currentSelectedUser = e.target.value;
            if (state.currentSelectedUser) {
                sessionStorage.setItem('currentSelectedUser', state.currentSelectedUser);
            } else {
                sessionStorage.removeItem('currentSelectedUser');
            }
        });
    }

    // Create User Button
    const createUserBtn = document.getElementById('createUserBtn');
    if (createUserBtn) {
        createUserBtn.addEventListener('click', async () => {
            const input = document.getElementById('newUsernameInput');
            const username = input.value.trim();
            if (!username) return alert("Enter a username.");

            try {
                const res = await fetch(`/create_user/${username}`);
                const data = await res.json();
                alert(data.message);
                if (data.status === 'success') {
                    input.value = '';
                    populateUserDropdown();
                }
            } catch (err) {
                console.error(err);
                alert("Failed to create user.");
            }
        });
    }

    // Train User Button
    const trainUserBtn = document.getElementById('trainUserBtn');
    if (trainUserBtn) {
        trainUserBtn.addEventListener('click', () => {
            if (!state.currentSelectedUser) return alert("Select a user to train.");
            alert(`Please run 'Train.py' in your terminal for user: ${state.currentSelectedUser}`);
        });
    }
}