import cv2
import numpy as np
import config

class GreenBallDetector:
    """Detects color-thresholded ball (Orange / Green) using high-saturation HSV filtering, motion masking, and circularity."""
    
    def __init__(self, lower_color=None, upper_color=None, enable_motion=True):
        self.lower_color = lower_color if lower_color is not None else config.LOWER_COLOR
        self.upper_color = upper_color if upper_color is not None else config.UPPER_COLOR
        self.enable_motion = enable_motion
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        self.prev_gray = None
        
    def detect(self, frame):
        """
        Processes a frame and returns (best_candidate, mask).
        Uses high-speed downscaling, high saturation & value thresholding plus optional motion masking.
        """
        h, w = frame.shape[:2]
        scale = 1.0
        max_dim = max(h, w)
        if max_dim > 640:
            scale = 640.0 / max_dim
            proc_frame = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)
        else:
            proc_frame = frame

        hsv = cv2.cvtColor(proc_frame, cv2.COLOR_BGR2HSV)
        color_mask = cv2.inRange(hsv, self.lower_color, self.upper_color)
        
        gray = cv2.cvtColor(proc_frame, cv2.COLOR_BGR2GRAY)
        gray_blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        if self.enable_motion and self.prev_gray is not None and self.prev_gray.shape == gray_blurred.shape:
            # Motion difference (frame differencing)
            frame_diff = cv2.absdiff(gray_blurred, self.prev_gray)
            _, motion_mask = cv2.threshold(frame_diff, 8, 255, cv2.THRESH_BINARY)
            
            # Dilate motion mask slightly so moving ball is covered
            dilate_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            motion_mask = cv2.dilate(motion_mask, dilate_kernel, iterations=1)
            
            # Combine color mask and motion mask (must be neon orange AND moving)
            mask = cv2.bitwise_and(color_mask, motion_mask)
        else:
            mask = color_mask.copy()
            
        self.prev_gray = gray_blurred
        
        # Morphological OPEN and CLOSE to remove noise and fill small holes
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, self.kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, self.kernel)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        best_candidate = None
        best_score = 0.0
        
        # Scale area thresholds based on downscaling
        min_area = config.MIN_BALL_AREA * (scale * scale)
        max_area = config.MAX_BALL_AREA * (scale * scale)

        for c in contours:
            area = cv2.contourArea(c)
            if min_area <= area <= max_area:
                perimeter = cv2.arcLength(c, True)
                circularity = (4 * np.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0
                
                if circularity >= config.MIN_CIRCULARITY:
                    (x, y), radius = cv2.minEnclosingCircle(c)
                    score = area * circularity
                    if score > best_score:
                        best_score = score
                        # Rescale coordinates back to original frame space
                        best_candidate = {
                            'center': (float(x / scale), float(y / scale)),
                            'radius': float(radius / scale),
                            'area': float(area / (scale * scale)),
                            'circularity': float(circularity),
                            'contour': c
                        }
                        
        return best_candidate, mask
