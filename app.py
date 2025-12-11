import os
import sys
import eventlet

# Patch for SocketIO performance (must be before other imports)
eventlet.monkey_patch()

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

# Initialize SocketIO with async_mode='eventlet' for better video streaming performance
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', max_http_buffer_size=10 * 1024 * 1024)

# Global Instances
user_manager = UserManager()
communicator = MorseCodeCommunicator()
communicator.user_manager = user_manager  # Link manager if needed

# Global processing state
processing_thread = None
thread_lock =  eventlet.semaphore.Semaphore() # Thread safety
processing_active = False

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
    user_data = {u: {'trained': user_manager.get_user(u)['trained']} for u in users}
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
        # Allow selection even if not trained, but warn
        return {'status': 'success', 'message': f"User {username} selected (Not trained)"}

@socketio.on('set_mode')
def set_mode(data):
    mode = data.get('mode')
    print(f"Mode switched to: {mode}")
    # You can pass this mode to the communicator if logic depends on it
    if mode == 'idle':
        communicator.reset_state()

@socketio.on('start_stream')
def start_stream():
    global processing_active, processing_thread
    if not processing_active:
        processing_active = True
        # Start background task using socketio.start_background_task
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
    # Logic to handle message (e.g. logging, TTS on server, etc.)
    emit('status', {'message': f"Sent: {msg}"})

@socketio.on('room_command')
def handle_room_command(data):
    device = data.get('device')
    action = data.get('action')
    print(f"Room Command: {device} -> {action}")
    # Call the communicator's hardware control method
    result = communicator.send_room_control(device, action)
    emit('status', {'message': result['message']})

@socketio.on('frame')
def handle_frame(data):
    """
    Receives base64 image from client.
    Because we are using a background thread loop for processing, 
    we put this frame into a queue or process it directly if efficient.
    
    CURRENT APPROACH: The client sends frames. We process them here directly 
    or store them for the background thread.
    """
    # For simplicity in this architecture, we decode and process immediately
    # inside the event handler or pass to a shared queue.
    # To avoid blocking the event loop, let's use a queue mechanism if strictly needed,
    # but for now, we decode here.
    
    global current_frame
    try:
        img_bytes = base64.b64decode(data['image'].split(',')[1])
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        # Store frame in a global variable for the background thread to pick up
        # This is a simple producer-consumer pattern
        current_frame = frame
    except Exception as e:
        pass

# Global frame buffer for the thread
current_frame = None

def process_frames(sid):
    """Background thread to process the latest frame."""
    global processing_active, current_frame
    
    print("Background processing loop started.")
    
    while processing_active:
        socketio.sleep(0.01) # Yield to event loop
        
        if current_frame is None:
            continue
            
        # Grab local reference and process
        frame = current_frame.copy()
        
        # 1. Detect Blink
        blink_info, current_ear = communicator.blink_detector.detect_blink(frame)
        
        # 2. Logic Flow
        if blink_info:
            # Predict Dot vs Dash
            prediction = communicator.classifier.predict(blink_info)
            blink_type = prediction # 'dot' or 'dash'
            
            # Send Detection Event to Client (for Navigation/Game)
            socketio.emit('blink_detected', {'type': blink_type}, room=sid)
            
            # Process Morse Logic (if applicable)
            status, result = communicator.process_blink({
                'duration': blink_info['duration'], 
                'timestamp': blink_info['timestamp']
            })
            
            if status == "blink_added":
                update_ui(sid)
        
        # 3. Check for Time-based Decoding (End of letter/word)
        decode_status = communicator.handle_time_based_decoding()
        if "decoded" in decode_status:
            update_ui(sid)

def update_ui(sid):
    """Helper to emit current state to UI"""
    socketio.emit('update_ui', {
        'message': communicator.message_accum,
        'morse_sequence': communicator.current_morse_sequence,
        'status': 'Processing',
        # Add timer calcs here if needed, or handle in JS
    }, room=sid)

if __name__ == '__main__':
    print("Starting Blink Communicator Server...")
    # Using socketio.run instead of app.run for WebSocket support
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)