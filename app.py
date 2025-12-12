import os
import sys
import threading
import time

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import numpy as np
import base64
import cv2

# Import our new modular backend components
from backend_modules.user_manager import UserManager
from backend_modules.communicator import MorseCodeCommunicator

# --- Configuration ---
app = Flask(__name__, template_folder='.', static_folder='.', static_url_path='/')
app.config['SECRET_KEY'] = 'secret_key_change_in_production'

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', max_http_buffer_size=10 * 1024 * 1024)

# Global Instances
user_manager = UserManager()
communicator = MorseCodeCommunicator()
communicator.user_manager = user_manager

# Global processing state
processing_thread = None
thread_lock = threading.Lock()
processing_active = False
current_frame = None

# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/quick_messages')
def quick_messages():
    return render_template('quick_messages.html')

@app.route('/message.html')
def message_page():
    return render_template('message.html')

@app.route('/roomcontrol.html')
def room_control():
    return render_template('roomcontrol.html')

@app.route('/devicecontrol.html')
def device_control():
    return render_template('devicecontrol.html')

@app.route('/flappy_bird')
def flappy_bird():
    return render_template('flappy_bird.html')

# --- User API ---

@app.route('/users')
def list_users_api():
    """API endpoint to list all users."""
    users = user_manager.list_users()
    # Safely get trained status
    user_data = {}
    for u in users:
        info = user_manager.get_user(u)
        user_data[u] = {'trained': info.get('trained', False) if info else False}
    return jsonify(user_data)

@app.route('/create_user/<username>')
def create_user_api(username):
    if user_manager.add_user(username):
        return jsonify({"status": "success", "message": f"User '{username}' created."})
    return jsonify({"status": "error", "message": "User exists."}), 409

# --- Socket Events ---

@socketio.on('connect')
def handle_connect():
    print(f'Client connected: {request.sid}')

@socketio.on('disconnect')
def handle_disconnect():
    print(f'Client disconnected: {request.sid}')
    # Stop processing if the controlling client disconnects
    # In a multi-user scenario, you might want to track which SID started the stream
    global processing_active
    processing_active = False

@socketio.on('select_user')
def handle_select_user(data):
    username = data.get('username')
    user_info = user_manager.get_user(username)
    
    if not user_info:
        return {'status': 'error', 'message': 'User not found'}
    
    # Store current user in communicator
    communicator.current_user = username
    
    # Try to load their trained model
    if communicator.load_user_profile(user_info):
        print(f"Loaded model for {username}")
        return {'status': 'success', 'message': f"User {username} loaded"}
    else:
        print(f"User {username} selected (No trained model found)")
        return {'status': 'success', 'message': f"User {username} selected (Not trained)"}

@socketio.on('set_mode')
def set_mode(data):
    mode = data.get('mode')
    print(f"Mode switched to: {mode}")
    if mode == 'idle':
        communicator.reset_state()

@socketio.on('start_stream')
def start_stream():
    global processing_active, processing_thread
    if not processing_active:
        processing_active = True
        processing_thread = socketio.start_background_task(process_frames, request.sid)
        emit('stream_started', {'message': 'Backend processing started'})

@socketio.on('stop_stream')
def stop_stream():
    global processing_active
    processing_active = False
    emit('stream_stopped', {'message': 'Backend processing stopped'})

@socketio.on('send_quick_message')
def handle_quick_message(data):
    msg = data.get('message')
    print(f"Quick Message: {msg}")
    emit('status', {'message': f"Sent: {msg}"})

@socketio.on('room_command')
def handle_room_command(data):
    device = data.get('device')
    action = data.get('action')
    # Call the communicator's hardware control method
    result = communicator.send_room_control(device, action)
    emit('status', {'message': result['message']})

@socketio.on('frame')
def handle_frame(data):
    global current_frame
    try:
        # Decode base64 image
        if 'image' in data:
            img_str = data['image']
            if ',' in img_str:
                img_str = img_str.split(',')[1]
            img_bytes = base64.b64decode(img_str)
            nparr = np.frombuffer(img_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            current_frame = frame
    except Exception as e:
        # print(f"Frame decode error: {e}") # Optional logging
        pass

def process_frames(sid):
    """Background thread to process the latest frame."""
    global processing_active, current_frame
    
    print(f"Background processing loop started for SID: {sid}")
    
    while processing_active:
        socketio.sleep(0.02) # Yield to event loop (~50 FPS max)
        
        if current_frame is None:
            continue
            
        # Grab local reference to avoid race conditions during processing
        frame = current_frame.copy()
        
        # 1. Detect Blink
        blink_info, current_ear = communicator.blink_detector.detect_blink(frame)
        
        # 2. Logic Flow
        if blink_info:
            # Predict Dot vs Dash using the classifier
            blink_type = communicator.classifier.predict(blink_info) # 'dot' or 'dash'
            
            print(f"Detected: {blink_type} ({blink_info['duration']:.2f}s)")

            # Send Detection Event to Client (for Navigation/Game)
            socketio.emit('blink_detected', {'type': blink_type}, room=sid)
            
            # Process Morse Logic
            # Pass the already determined blink_type to avoid re-calculation or errors
            status, result = communicator.process_blink(blink_info, blink_type)
            
            if status == "blink_added":
                update_ui(sid)
        
        # 3. Check for Time-based Decoding (End of letter/word)
        decode_result = communicator.handle_time_based_decoding()
        if decode_result["status"] in ["decoded", "space_added"]:
            print(f"Decoded: {decode_result.get('char', 'SPACE')}")
            update_ui(sid)

def update_ui(sid):
    """Helper to emit current state to UI"""
    socketio.emit('update_ui', {
        'message': communicator.message_accum,
        'morse_sequence': communicator.current_morse_sequence,
        'status': 'Processing',
        # Optional: Add timing info for UI progress bars
        'letter_timer': max(0, communicator.LETTER_PAUSE - (time.time() - communicator.last_blink_time)) if communicator.current_morse_sequence else 0,
        'space_timer': max(0, communicator.SPACE_PAUSE - (time.time() - communicator.last_letter_time)) if communicator.last_letter_time > 0 else 0
    }, room=sid)

if __name__ == '__main__':
    print("Starting Blink Communicator Server...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)