import os
import numpy as np
import warnings
import logging
import pickle

# --- Suppress TensorFlow and related logs for a cleaner console ---
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=Warning)

import tensorflow as tf
tf.get_logger().setLevel('ERROR')
logging.getLogger('tensorflow').setLevel(logging.ERROR)
logging.getLogger('absl').setLevel(logging.ERROR)

from tf_keras.models import load_model

class BlinkClassifier:
    def __init__(self):
        self.model = None
        self.scaler = None
        self.dot_threshold = 0.4 # Default backup threshold

    def load_model(self, filepath):
        """Loads the model and scaler from the user's directory."""
        try:
            # 1. Load metadata (scaler and backup threshold)
            data_path = f"{filepath}_data.pkl"
            with open(data_path, 'rb') as f:
                model_data = pickle.load(f)

            if not isinstance(model_data, dict) or 'scaler' not in model_data:
                print(f"Error: {data_path} is corrupted or invalid.")
                return False

            self.scaler = model_data['scaler']
            self.dot_threshold = model_data.get('dot_threshold', 0.4)

            # 2. Load Keras Model if it exists
            if model_data.get('has_model', False):
                model_file = f"{filepath}_model.h5"
                try:
                    self.model = load_model(model_file)
                    print("Neural network model loaded successfully.")
                except Exception as keras_e:
                    print(f"Neural network file missing or corrupted ({model_file}): {keras_e}. Using threshold fallback.")
                    self.model = None
            else:
                self.model = None
                print("No neural network model found, using threshold method.")
            
            return True

        except FileNotFoundError:
            print(f"Model files not found for {filepath}. User needs training.")
            self.model = None
            self.scaler = None
            return False
        except Exception as e:
            print(f"Error loading model for {filepath}: {e}")
            self.model = None
            self.scaler = None
            return False

    def prepare_features(self, blink_data):
        """Extracts feature vector from blink info dictionary."""
        feature = [
            blink_data['duration'],
            blink_data['intensity'],
            blink_data.get('min_ear', 0.2),
            1.0 / (blink_data['duration'] + 0.001)
        ]
        return np.array([feature])

    def predict(self, blink_data):
        """Returns 'dot' or 'dash' based on model or duration threshold."""
        if self.model is not None and self.scaler is not None:
            try:
                features = self.prepare_features(blink_data)
                features_scaled = self.scaler.transform(features)
                prediction = self.model.predict(features_scaled, verbose=0)[0][0]
                return 'dash' if prediction > 0.5 else 'dot'
            except Exception as e:
                print(f"Model prediction failed: {e}, using duration threshold fallback.")
        
        # Fallback method if model fails or isn't loaded
        return 'dash' if blink_data['duration'] > self.dot_threshold else 'dot'