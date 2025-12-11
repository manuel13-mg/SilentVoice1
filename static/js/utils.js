/**
 * utils.js
 * General utility functions.
 */

export function speakMessage(text) {
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel(); // Stop any current speech
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = 'en-US';
        window.speechSynthesis.speak(utterance);
    } else {
        console.warn('TTS not supported in this browser.');
    }
}