import cv2
import numpy as np
import dlib
import mediapipe as mp
from scipy.spatial import distance
from collections import deque
import time
import os

class BlinkDetector:
    def __init__(self):
        self.detector = dlib.get_frontal_face_detector()
        predictor_path = "shape_predictor_68_face_landmarks.dat"
        if not os.path.exists(predictor_path):
            print("Downloading dlib shape predictor model...")
            self._download_shape_predictor()
        self.predictor = dlib.shape_predictor(predictor_path)

        self.mp_face_mesh = mp.solutions.face_mesh
        self.LEFT_EYE_POINTS = list(range(36, 42))
        self.RIGHT_EYE_POINTS = list(range(42, 48))
        self.LEFT_EYE_EAR_INDICES = [33, 160, 158, 133, 153, 144]
        self.RIGHT_EYE_EAR_INDICES = [362, 385, 387, 263, 373, 380]
        
        self.base_ear_thresh = 0.21
        self.current_ear_thresh = self.base_ear_thresh
        self.ear_history = deque(maxlen=30)
        self.EYE_AR_CONSEC_FRAMES = 1
        self.counter = 0
        self.blink_detected = False
        self.blink_start_time = 0
        self.brightness_history = deque(maxlen=10)
        self.use_enhancement = False

    def _download_shape_predictor(self):
        import urllib.request
        import bz2
        url = "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2"
        try:
            urllib.request.urlretrieve(url, "shape_predictor_68_face_landmarks.dat.bz2")
            with bz2.BZ2File("shape_predictor_68_face_landmarks.dat.bz2", 'rb') as f_in:
                with open("shape_predictor_68_face_landmarks.dat", 'wb') as f_out:
                    f_out.write(f_in.read())
            os.remove("shape_predictor_68_face_landmarks.dat.bz2")
            print("Shape predictor model downloaded successfully!")
        except Exception as e:
            print(f"Failed to download shape predictor: {e}. Please ensure internet connection or provide the file manually.")
            raise

    def enhance_frame(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        self.brightness_history.append(brightness)
        avg_brightness = np.mean(self.brightness_history)
        self.use_enhancement = avg_brightness < 80
        if self.use_enhancement:
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
            lab[:,:,0] = clahe.apply(lab[:,:,0])
            enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            if avg_brightness < 50:
                enhanced = cv2.convertScaleAbs(enhanced, alpha=1.3, beta=25)
            return enhanced
        return frame

    def eye_aspect_ratio_dlib(self, eye_landmarks):
        try:
            A = distance.euclidean(eye_landmarks[1], eye_landmarks[5])
            B = distance.euclidean(eye_landmarks[2], eye_landmarks[4])
            C = distance.euclidean(eye_landmarks[0], eye_landmarks[3])
            if C == 0: return 0
            return (A + B) / (2.0 * C)
        except IndexError:
            return 0

    def eye_aspect_ratio_mediapipe(self, eye_landmarks):
        try:
            A = distance.euclidean(eye_landmarks[1], eye_landmarks[5])
            B = distance.euclidean(eye_landmarks[2], eye_landmarks[4])
            C = distance.euclidean(eye_landmarks[0], eye_landmarks[3])
            if C == 0: return 0
            return (A + B) / (2.0 * C)
        except IndexError:
            return 0

    def get_eye_landmarks_mediapipe(self, landmarks, eye_indices, image_width, image_height):
        eye_points = []
        for idx in eye_indices:
            landmark = landmarks.landmark[idx]
            x = int(landmark.x * image_width)
            y = int(landmark.y * image_height)
            eye_points.append([x, y])
        return np.array(eye_points)

    def adapt_threshold(self, current_ear):
        if current_ear is not None:
            self.ear_history.append(current_ear)
            if len(self.ear_history) >= 10:
                recent_ears = list(self.ear_history)[-10:]
                mean_ear = np.mean(recent_ears)
                std_ear = np.std(recent_ears)
                adaptive_thresh = max(0.15, min(0.25, mean_ear - 2*std_ear))
                self.current_ear_thresh = 0.7 * self.current_ear_thresh + 0.3 * adaptive_thresh

    def detect_blink_dlib(self, frame):
        try:
            enhanced_frame = self.enhance_frame(frame)
            gray = cv2.cvtColor(enhanced_frame, cv2.COLOR_BGR2GRAY)
            faces = self.detector(gray)
            if len(faces) > 0:
                face = faces[0]
                landmarks = self.predictor(gray, face)
                left_eye = np.array([(landmarks.part(i).x, landmarks.part(i).y) for i in self.LEFT_EYE_POINTS])
                right_eye = np.array([(landmarks.part(i).x, landmarks.part(i).y) for i in self.RIGHT_EYE_POINTS])
                left_ear = self.eye_aspect_ratio_dlib(left_eye)
                right_ear = self.eye_aspect_ratio_dlib(right_eye)
                ear = (left_ear + right_ear) / 2.0
                return ear, True
            return None, False
        except Exception:
            return None, False

    def detect_blink_mediapipe(self, frame):
        try:
            with self.mp_face_mesh.FaceMesh(
                max_num_faces=1,
                min_detection_confidence=0.3,
                min_tracking_confidence=0.3) as face_mesh:

                enhanced_frame = self.enhance_frame(frame)
                rgb_frame = cv2.cvtColor(enhanced_frame, cv2.COLOR_BGR2RGB)
                rgb_frame.flags.writeable = False
                results = face_mesh.process(rgb_frame)
                rgb_frame.flags.writeable = True

                if results.multi_face_landmarks:
                    for face_landmarks in results.multi_face_landmarks:
                        h, w = enhanced_frame.shape[:2]
                        left_eye = self.get_eye_landmarks_mediapipe(face_landmarks, self.LEFT_EYE_EAR_INDICES, w, h)
                        right_eye = self.get_eye_landmarks_mediapipe(face_landmarks, self.RIGHT_EYE_EAR_INDICES, w, h)
                        left_ear = self.eye_aspect_ratio_mediapipe(left_eye)
                        right_ear = self.eye_aspect_ratio_mediapipe(right_eye)
                        ear = (left_ear + right_ear) / 2.0
                        return ear, True
            return None, False
        except Exception:
            return None, False

    def detect_blink(self, frame):
        blink_info = None
        current_ear = None
        ear, dlib_success = self.detect_blink_dlib(frame)
        if not dlib_success:
            ear, mp_success = self.detect_blink_mediapipe(frame)
            if not mp_success:
                return None, None
        
        current_ear = ear
        self.adapt_threshold(current_ear)
        
        if ear is not None and ear < self.current_ear_thresh:
            self.counter += 1
            if not self.blink_detected:
                self.blink_start_time = time.time()
                self.blink_detected = True
        else:
            if self.counter >= self.EYE_AR_CONSEC_FRAMES and self.blink_detected:
                blink_duration = time.time() - self.blink_start_time
                if 0.05 < blink_duration < 3.0: 
                    blink_info = {
                        'duration': blink_duration,
                        'intensity': max(0.01, self.current_ear_thresh - min(ear if ear else 0, self.current_ear_thresh)),
                        'timestamp': time.time(),
                        'min_ear': ear if ear else 0,
                        'enhanced': self.use_enhancement
                    }
            self.counter = 0
            self.blink_detected = False
        return blink_info, current_ear