import time
import os
from collections import deque
from .morse_decoder import MorseCodeDecoder
from .blink_detector import BlinkDetector
from .classifier import BlinkClassifier

class MorseCodeCommunicator:
    def __init__(self):
        self.blink_detector = BlinkDetector()
        self.morse_decoder = MorseCodeDecoder()
        self.classifier = BlinkClassifier()
        self.current_user = None
        
        # State variables
        self.current_morse_sequence = ""
        self.message_accum = ""
        self.last_blink_time = 0
        self.last_letter_time = 0
        
        # Timing Constants (will be adaptive after training)
        self.LETTER_PAUSE = 2.0
        self.SPACE_PAUSE = 4.0
        self.BLINK_COOLDOWN = 1.0

    def load_user_profile(self, user_info):
        """Loads the classifier for the selected user."""
        if user_info and user_info.get('trained'):
            # Normalize path for cross-platform compatibility
            model_path = os.path.normpath(user_info['model_path'])
            success = self.classifier.load_model(model_path)
            if success:
                print(f"User profile loaded from: {model_path}")
            return success
        return False

    def reset_state(self):
        self.current_morse_sequence = ""
        self.message_accum = ""
        self.last_blink_time = 0
        self.last_letter_time = 0

    def process_blink(self, blink_data, blink_type=None):
        """
        Processes a detected blink.
        
        Args:
            blink_data (dict): Contains 'duration', 'timestamp', etc.
            blink_type (str, optional): 'dot' or 'dash'. If None, it will be predicted.
        """
        self.last_blink_time = time.time()
        
        # Determine type if not provided (fallback logic)
        if blink_type is None:
            if self.classifier and 'intensity' in blink_data:
                 blink_type = self.classifier.predict(blink_data)
            else:
                 # Simple duration threshold fallback
                 blink_type = 'dash' if blink_data.get('duration', 0) > 0.4 else 'dot'

        if blink_type == 'dot':
            self.current_morse_sequence += "."
        elif blink_type == 'dash':
            self.current_morse_sequence += "-"
            
        return "blink_added", self.current_morse_sequence

    def handle_time_based_decoding(self):
        """Checks if enough time has passed to decode a letter or add a space."""
        current_time = time.time()
        time_since_blink = current_time - self.last_blink_time
        
        # 1. Check for Letter Pause (End of sequence -> Decode character)
        if self.current_morse_sequence and time_since_blink > self.LETTER_PAUSE:
            decoded_char = self.morse_decoder.decode(self.current_morse_sequence)
            self.message_accum += decoded_char
            sequence_processed = self.current_morse_sequence
            self.current_morse_sequence = "" # Reset sequence
            self.last_letter_time = current_time # Mark when the letter was finished
            
            return {
                "status": "decoded", 
                "char": decoded_char, 
                "sequence": sequence_processed,
                "message": self.message_accum
            }
            
        # 2. Check for Space Pause (End of word -> Add space)
        # Condition: We have a message, it doesn't already end in space, 
        # enough time passed since the last letter was decoded.
        if self.message_accum and not self.message_accum.endswith(' ') and \
           (current_time - self.last_letter_time > self.SPACE_PAUSE) and \
           (self.last_letter_time > 0):
            self.message_accum += " "
            return {"status": "space_added", "message": self.message_accum}
            
        return {"status": "waiting"}

    def send_room_control(self, device, action):
        """
        Executes hardware commands.
        """
        # Placeholder for actual hardware integration (e.g., MQTT, GPIO, Smart Home API)
        msg = f"Device '{device}' turned {action.upper()}"
        print(f"[Hardware Control] {msg}")
        return {"status": "success", "message": msg}