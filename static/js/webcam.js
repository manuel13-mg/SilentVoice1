import { state } from './config.js';

export function initWebcam(onFrameReady) {
    state.video = document.getElementById('webcam');
    state.canvas = document.getElementById('canvas');
    state.ctx = state.canvas.getContext('2d');

    if (state.stream && state.stream.active) {
        if (!state.frameSendingInterval) startSendingFrames();
        return;
    }

    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ video: true }).then(s => {
            state.stream = s;
            state.video.srcObject = state.stream;
            state.video.addEventListener('loadedmetadata', () => {
                state.canvas.width = state.video.videoWidth;
                state.canvas.height = state.video.videoHeight;
                state.video.play();
                startSendingFrames();
                if(onFrameReady) onFrameReady();
            });
        }).catch(err => {
            console.error("Webcam error:", err);
            alert("Could not access webcam.");
            stopWebcam();
        });
    }
}

export function startSendingFrames() {
    if (state.frameSendingInterval) clearInterval(state.frameSendingInterval);
    
    state.frameSendingInterval = setInterval(() => {
        if (!state.stream || !state.stream.active) {
            clearInterval(state.frameSendingInterval);
            return;
        }
        state.ctx.drawImage(state.video, 0, 0, state.canvas.width, state.canvas.height);
        const frameData = state.canvas.toDataURL('image/jpeg', 0.5);
        if(state.socket) state.socket.emit('frame', { image: frameData });
    }, 100);
}

export function stopWebcam() {
    if (state.frameSendingInterval) {
        clearInterval(state.frameSendingInterval);
        state.frameSendingInterval = null;
    }
    if (state.stream) {
        state.stream.getTracks().forEach(track => track.stop());
        state.stream = null;
    }
    if (state.video) state.video.srcObject = null;
}