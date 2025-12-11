import time
from collections import deque
from .morse_decoder import MorseCodeDecoder
from .blink_detector import BlinkDetector
from .classifier import BlinkClassifier

class MorseCodeCommunicator:
    def __init__(self):
        self.blink_detector = BlinkDetector()
        self.morse_decoder = MorseCodeDecoder()
        # UserManager is instantiated in app.py and passed or used separately
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
        if user_info and user_info['trained']:
            success = self.classifier.load_model(user_info['model_path'])
            if success:
                # Optionally adapt timings based on training data if stored
                pass
            return success
        return False

    def reset_state(self):
        self.current_morse_sequence = ""
        self.message_accum = ""
        self.last_blink_time = 0
        self.last_letter_time = 0