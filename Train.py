import os
import cv2
import numpy as np
import time
import sys
import warnings
import logging
import pickle

# --- Suppress TensorFlow and related logs ---
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'

warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

import tensorflow as tf
tf.get_logger().setLevel('ERROR')
logging.getLogger('tensorflow').setLevel(logging.ERROR)
logging.getLogger('absl').setLevel(logging.ERROR)
logging.getLogger('mediapipe').setLevel(logging.ERROR)

from tf_keras.models import Sequential
from tf_keras.layers import Dense, Dropout
from tf_keras.optimizers import Adam
from sklearn.preprocessing import StandardScaler

# --- IMPORT MODULES FROM BACKEND (No Duplication) ---
from backend_modules.blink_detector import BlinkDetector
from backend_modules.user_manager import UserManager
from backend_modules.classifier import BlinkClassifier

class TrainableClassifier(BlinkClassifier):
    """
    Extends the runtime BlinkClassifier with training capabilities.
    """
    def create_model(self):
        model = Sequential([
            Dense(32, activation='relu', input_shape=(4,)),
            Dropout(0.2),
            Dense(16, activation='relu'),
            Dropout(0.2),
            Dense(8, activation='relu'),
            Dense(1, activation='sigmoid')
        ])
        model.compile(optimizer=Adam(learning_rate=0.001), loss='binary_crossentropy', metrics=['accuracy'])
        return model

    def train(self, dot_blinks, dash_blinks):
        # Extract durations for statistics
        dot_durations = [b['duration'] for b in dot_blinks]
        dash_durations = [b['duration'] for b in dash_blinks]
        
        if not dot_durations or not dash_durations:
            print("Insufficient data for training.")
            return None, None

        dot_mean = np.mean(dot_durations)
        dash_mean = np.mean(dash_durations)
        print(f"Dot mean duration: {dot_mean:.3f}s, Dash mean duration: {dash_mean:.3f}s")
        
        # Determine threshold fallback
        if dash_mean > dot_mean:
            self.dot_threshold = (max(dot_durations) + min(dash_durations)) / 2
        else:
            self.dot_threshold = 0.4
        print(f"Backup threshold set to: {self.dot_threshold:.3f}s")

        # Prepare data using the parent class method
        X_dot = self.prepare_features(dot_blinks)
        X_dash = self.prepare_features(dash_blinks)
        
        X = np.vstack([X_dot, X_dash])
        y = np.hstack([np.zeros(len(X_dot)), np.ones(len(X_dash))])
        
        # Handle NaNs
        X = np.nan_to_num(X)
        
        # Scale features
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # Create and fit model
        self.model = self.create_model()
        try:
            self.model.fit(
                X_scaled, y, 
                epochs=50, 
                batch_size=min(8, len(X)) if len(X) > 0 else 1, 
                verbose=0, 
                validation_split=0.2 if len(X) > 5 else 0
            )
            loss, accuracy = self.model.evaluate(X_scaled, y, verbose=0)
            print(f"Training completed - Loss: {loss:.4f}, Accuracy: {accuracy:.4f}")
            return loss, accuracy
        except Exception as e:
            print(f"Model training failed: {e}")
            self.model = None
            return 0, 0.5

    def save_model(self, filepath):
        try:
            if self.model: 
                self.model.save(f"{filepath}_model.h5")
            
            model_data = {
                'scaler': self.scaler, 
                'dot_threshold': self.dot_threshold, 
                'has_model': self.model is not None
            }
            with open(f"{filepath}_data.pkl", 'wb') as f: 
                pickle.dump(model_data, f)
            print(f"Model and scaler saved to {filepath}")
        except Exception as e: 
            print(f"Error saving model: {e}")


class UserTrainer:
    def __init__(self):
        self.blink_detector = BlinkDetector()
        self.user_manager = UserManager()
        self.classifier = TrainableClassifier()
        
    def train_user(self, username):
        print(f"\n=== Training Model for {username} ===")
        print("Position yourself in front of the camera with good lighting.")
        cap = None
        try:
            # Open Camera
            for cam_index in [0, 1]:
                cap = cv2.VideoCapture(cam_index)
                if cap.isOpened():
                    print(f"Camera {cam_index} opened successfully.")
                    break
            if not cap or not cap.isOpened():
                raise Exception("Could not open any camera.")

            # --- 1. Collect Dots ---
            print("\n--- Collecting DOT blinks (SHORT) ---")
            dot_blinks = []
            if not self.collect_training_data(cap, dot_blinks, "dot", 15):
                raise Exception("Dot blink collection cancelled or failed.")

            if not dot_blinks:
                print("No short blinks collected.")
                return False
                
            max_dot_duration = max([b['duration'] for b in dot_blinks])
            print(f"\nYour longest SHORT blink was {max_dot_duration:.3f}s. Your long blinks should be longer than this.")

            # --- 2. Collect Dashes ---
            print("\n--- Collecting DASH blinks (LONG) ---")
            dash_blinks = []
            if not self.collect_training_data(cap, dash_blinks, "dash", 15, max_dot_duration=max_dot_duration):
                raise Exception("Dash blink collection cancelled or failed.")

            if len(dot_blinks) >= 8 and len(dash_blinks) >= 8:
                print("\nTraining model with collected data...")
                user_info = self.user_manager.get_user(username)
                
                loss, accuracy = self.classifier.train(dot_blinks, dash_blinks)
                
                if loss is not None and accuracy is not None and accuracy > 0.5:
                    # Save the trained model to the user's directory
                    self.classifier.save_model(user_info['model_path'])
                    self.user_manager.mark_user_trained(username)

                    print(f"Training completed successfully! Accuracy: {accuracy:.2%}")
                    return True
                else:
                    print(f"Model training insufficient or low accuracy ({accuracy:.2%}). Please try again.")
                    return False
            else:
                print(f"Insufficient data. Need at least 8 of each blink type.")
                return False
        except Exception as e:
            print(f"Training error: {e}")
            return False
        finally:
            if cap: cap.release()
            try: cv2.destroyAllWindows()
            except: pass

    def collect_training_data(self, cap, data_list, blink_type, target_count, max_dot_duration=None):
        collecting = False
        collected_count = 0
        cooldown_time = 0
        last_duration = None
        
        if blink_type == 'dot':
            instruction_text = "Perform SHORT, QUICK blinks (0.1-0.4s)"
        else:
            instruction_text = "Perform LONG, DELIBERATE blinks"

        while collected_count < target_count:
            ret, frame = cap.read()
            if not ret: return False
            
            current_time = time.time()
            display_frame = frame.copy()
            h, w = display_frame.shape[:2]

            # UI Text
            cv2.putText(display_frame, f"Collecting {blink_type.upper()} blinks: {collected_count}/{target_count}", 
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(display_frame, instruction_text, (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)

            if not collecting and current_time > cooldown_time:
                cv2.putText(display_frame, "Press SPACE to start collecting", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            elif collecting:
                cv2.putText(display_frame, "PERFORM BLINK NOW!", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            elif current_time <= cooldown_time:
                cv2.putText(display_frame, "Wait for cooldown...", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 1)
            
            if last_duration is not None:
                cv2.putText(display_frame, f"Last: {last_duration:.3f}s", (w - 200, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Blink Detection
            if collecting:
                blink_info, current_ear = self.blink_detector.detect_blink(frame)
                if blink_info:
                    duration = blink_info['duration']
                    last_duration = duration
                    valid = False
                    
                    # Validation Logic
                    if blink_type == "dot" and 0.05 <= duration <= 0.4:
                        valid = True
                    elif blink_type == "dash" and max_dot_duration is not None:
                        if duration > max_dot_duration * 1.25:
                            valid = True
                        else:
                            print(f"Invalid DASH ({duration:.3f}s). Must be > {max_dot_duration * 1.25:.3f}s.")
                    elif blink_type == "dash" and max_dot_duration is None:
                         # Fallback if no dot duration provided (shouldn't happen in flow)
                         if duration >= 0.5: valid = True

                    if valid:
                        data_list.append(blink_info)
                        collected_count += 1
                        cooldown_time = current_time + 1.5
                        print(f"Collected {blink_type.upper()} #{collected_count}: {duration:.3f}s")
                    else:
                        if blink_type == "dot":
                            print(f"Invalid DOT ({duration:.3f}s). Try shorter.")
                        cooldown_time = max(cooldown_time, current_time + 1.0)
                    
                    collecting = False
            
            # Show EAR for feedback
            if collecting:
                _, ear_val = self.blink_detector.detect_blink(frame) # Just to get EAR without processing event
                if ear_val:
                    cv2.putText(display_frame, f"EAR: {ear_val:.2f}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 1)

            cv2.imshow('Training Data Collection', display_frame)
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord(' ') and current_time > cooldown_time:
                collecting = not collecting
                if collecting: print(f"Ready for {blink_type} blink #{collected_count + 1}...")
            elif key == 27: # ESC
                return False
        return True


def main_train():
    trainer = UserTrainer()
    user_manager = trainer.user_manager

    while True:
        print("\n=== Blink Communicator Training Menu ===")
        print("1. List existing users")
        print("2. Create new user and train")
        print("3. Retrain existing user")
        print("4. Exit")
        
        choice = input("\nEnter your choice (1-4): ").strip()

        if choice == '1':
            users = user_manager.list_users()
            if users:
                print("\nExisting users:")
                for i, user in enumerate(users, 1):
                    info = user_manager.get_user(user)
                    status = "Trained" if info['trained'] else "Not trained"
                    print(f"{i}. {user} ({status})")
            else:
                print("No users found.")
        
        elif choice == '2':
            username = input("Enter new username: ").strip()
            if username:
                if user_manager.add_user(username):
                    print(f"User '{username}' created. Proceeding to training.")
                    trainer.train_user(username)
                else:
                    print(f"User '{username}' already exists.")
            else:
                print("Username cannot be empty.")
        
        elif choice == '3':
            users = user_manager.list_users()
            if not users:
                print("No users to retrain.")
                continue
            
            print("\nSelect user to retrain:")
            for i, user in enumerate(users, 1):
                print(f"{i}. {user}")
            
            try:
                idx = int(input("\nEnter user number: ")) - 1
                if 0 <= idx < len(users):
                    username = users[idx]
                    trainer.train_user(username)
                else:
                    print("Invalid number.")
            except ValueError:
                print("Invalid input.")
        
        elif choice == '4':
            print("Exiting.")
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main_train()