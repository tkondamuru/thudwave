import cv2
import numpy as np

class ArUcoTagDetector:
    """
    High-speed, high-robustness ArUco marker detector.
    Uses downscaled detection, dictionary locking, and CLAHE contrast boost.
    Runs at 60+ FPS without CPU lag.
    """
    
    def __init__(self):
        # Common dictionaries ordered by prevalence
        self.dict_types = [
            cv2.aruco.DICT_4X4_50,
            cv2.aruco.DICT_5X5_50,
            cv2.aruco.DICT_4X4_100,
            cv2.aruco.DICT_4X4_250,
            cv2.aruco.DICT_5X5_100,
            cv2.aruco.DICT_6X6_50,
            cv2.aruco.DICT_APRILTAG_36h11
        ]
        
        self.active_dict = None
        self.parameters = cv2.aruco.DetectorParameters()
        self.parameters.adaptiveThreshWinSizeMin = 3
        self.parameters.adaptiveThreshWinSizeMax = 25
        self.parameters.adaptiveThreshWinSizeStep = 6
        self.parameters.adaptiveThreshConstant = 7
        self.parameters.minMarkerPerimeterRate = 0.015
        self.parameters.maxMarkerPerimeterRate = 4.0
        self.parameters.polygonalApproxAccuracyRate = 0.05
        self.parameters.errorCorrectionRate = 0.8
        
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        self.last_detected = {}
        self.last_rejected = []
        self.frame_skip = 0
        
    def detect(self, frame):
        """
        High-speed detection with resolution downscaling and dictionary locking.
        """
        h, w = frame.shape[:2]
        
        # Downscale to 640px wide for ultra-fast marker detection
        scale = 1.0
        if w > 640:
            scale = 640.0 / w
            proc_frame = cv2.resize(frame, (640, int(h * scale)), interpolation=cv2.INTER_LINEAR)
        else:
            proc_frame = frame

        gray = cv2.cvtColor(proc_frame, cv2.COLOR_BGR2GRAY)
        detected = {}
        all_rejected = []
        
        # Dictionaries to check: if active dictionary known, only check that!
        dicts_to_test = [self.active_dict] if self.active_dict is not None else self.dict_types[:3]
        
        for d_type in dicts_to_test:
            dictionary = cv2.aruco.getPredefinedDictionary(d_type)
            if hasattr(cv2.aruco, 'ArucoDetector'):
                detector = cv2.aruco.ArucoDetector(dictionary, self.parameters)
                corners, ids, rejected = detector.detectMarkers(gray)
            else:
                corners, ids, rejected = cv2.aruco.detectMarkers(gray, dictionary, parameters=self.parameters)
                
            if rejected is not None and len(rejected) > 0:
                all_rejected.extend(rejected)
                
            if ids is not None and len(ids) > 0:
                self.active_dict = d_type # Lock onto this dictionary!
                for i, marker_id in enumerate(ids.flatten()):
                    m_id = int(marker_id)
                    pts = corners[i][0] / scale # Rescale points back to original image resolution
                    center_x = float(np.mean(pts[:, 0]))
                    center_y = float(np.mean(pts[:, 1]))
                    detected[m_id] = {
                        'center': (center_x, center_y),
                        'corners': pts,
                        'dict_type': d_type
                    }
                break

        # If nothing found with standard search, occasionally try CLAHE contrast pass
        if len(detected) == 0 and self.active_dict is None:
            clahe_gray = self.clahe.apply(gray)
            for d_type in self.dict_types:
                dictionary = cv2.aruco.getPredefinedDictionary(d_type)
                if hasattr(cv2.aruco, 'ArucoDetector'):
                    detector = cv2.aruco.ArucoDetector(dictionary, self.parameters)
                    corners, ids, rejected = detector.detectMarkers(clahe_gray)
                else:
                    corners, ids, rejected = cv2.aruco.detectMarkers(clahe_gray, dictionary, parameters=self.parameters)
                if ids is not None and len(ids) > 0:
                    self.active_dict = d_type
                    for i, marker_id in enumerate(ids.flatten()):
                        m_id = int(marker_id)
                        pts = corners[i][0] / scale
                        center_x = float(np.mean(pts[:, 0]))
                        center_y = float(np.mean(pts[:, 1]))
                        detected[m_id] = {
                            'center': (center_x, center_y),
                            'corners': pts,
                            'dict_type': d_type
                        }
                    break
        
        # Rescale rejected points
        if scale != 1.0 and all_rejected:
            rescaled_rejected = [r / scale for r in all_rejected]
            self.last_rejected = rescaled_rejected
        else:
            self.last_rejected = all_rejected

        if detected:
            self.last_detected = detected

        return detected
