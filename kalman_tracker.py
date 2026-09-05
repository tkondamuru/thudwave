import cv2
import numpy as np
import config

class BallKalmanTracker:
    """
    2D Kalman Filter tracking position (x, y) and velocity (vx, vy).
    State vector X = [x, y, vx, vy]^T
    Measurement vector Z = [x, y]^T
    """
    
    def __init__(self):
        self.kf = cv2.KalmanFilter(4, 2)
        
        # State transition matrix F (x_k = x_{k-1} + vx * dt)
        self.kf.transitionMatrix = np.array([
            [1, 0, 1, 0],
            [0, 1, 0, 1],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ], dtype=np.float32)
        
        # Measurement matrix H
        self.kf.measurementMatrix = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ], dtype=np.float32)
        
        # Noise covariance matrices
        self.kf.processNoiseCov = np.eye(4, dtype=np.float32) * config.PROCESS_NOISE_COV
        self.kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * config.MEASUREMENT_NOISE_COV
        self.kf.errorCovPost = np.eye(4, dtype=np.float32) * config.POST_ERROR_COV
        
        self.is_initialized = False
        self.missed_frames = 0
        self.history = []
        
    def reset(self):
        """Resets the tracker state."""
        self.is_initialized = False
        self.missed_frames = 0
        self.history = []
        self.kf.errorCovPost = np.eye(4, dtype=np.float32) * config.POST_ERROR_COV
        
    def predict(self):
        """Predicts the next state of the ball."""
        if not self.is_initialized:
            return None
        prediction = self.kf.predict()
        x, y, vx, vy = prediction.ravel()
        return (float(x), float(y), float(vx), float(vy))
        
    def update(self, measurement):
        """
        Updates the Kalman filter with a new measurement (x, y).
        If measurement is None, it uses prediction for up to MAX_MISSED_FRAMES before resetting.
        """
        if measurement is not None:
            mx, my = measurement
            z = np.array([[np.float32(mx)], [np.float32(my)]])
            self.missed_frames = 0
            
            if not self.is_initialized:
                # Initialize state vector X with first measurement and zero velocity
                self.kf.statePost = np.array([[np.float32(mx)], [np.float32(my)], [0], [0]], dtype=np.float32)
                self.is_initialized = True
                state = (float(mx), float(my), 0.0, 0.0)
            else:
                self.kf.predict()
                corrected = self.kf.correct(z)
                x, y, vx, vy = corrected.ravel()
                state = (float(x), float(y), float(vx), float(vy))
        else:
            if not self.is_initialized:
                return None
                
            self.missed_frames += 1
            if self.missed_frames > getattr(config, 'MAX_MISSED_FRAMES', 12):
                # Ball has been missing for too long (e.g. held in hands or caught) -> Reset tracker
                self.reset()
                return None
                
            prediction = self.kf.predict()
            x, y, vx, vy = prediction.ravel()
            state = (float(x), float(y), float(vx), float(vy))
            
        self.history.append((state[0], state[1]))
        if len(self.history) > config.TRAIL_LENGTH:
            self.history.pop(0)
            
        return state
