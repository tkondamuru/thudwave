import numpy as np

# HSV Color Thresholds for NEON ORANGE Pickleball
# Neon Orange is extremely high-saturation & bright (S >= 160, V >= 160)
# This strictly excludes dull brown cardboard boxes, wooden desks, and gold frames!
LOWER_ORANGE = np.array([8, 165, 165], dtype=np.uint8)
UPPER_ORANGE = np.array([18, 255, 255], dtype=np.uint8)

# Set active color threshold
LOWER_COLOR = LOWER_ORANGE
UPPER_COLOR = UPPER_ORANGE

# Contour Geometry Filtering (Tuned for ball shape, strictly rejects hands & arms)
MIN_BALL_AREA = 100        # Min pixel area for ball blob (rejects noise specks)
MAX_BALL_AREA = 2500       # Max pixel area for ball blob (strictly rejects hands, arms, body)
MIN_CIRCULARITY = 0.58     # Ball is round (0.75-1.0), whereas hands and fingers are < 0.50

# Kalman Filter Parameters
PROCESS_NOISE_COV = 1e-2  # Process noise covariance (Q)
MEASUREMENT_NOISE_COV = 1e-1 # Measurement noise covariance (R)
POST_ERROR_COV = 1.0      # Error covariance post (P)

# Maximum consecutive missed frames before resetting Kalman Filter
MAX_MISSED_FRAMES = 8

# Motion Trail Length (Number of past positions to draw)
TRAIL_LENGTH = 30

# Wall Line Segment Coordinates (x1, y1) -> (x2, y2) in frame space
DEFAULT_WALL = ((50, 150), (700, 150))

# Dual-Camera Timing Parameters
TELEPORT_DELAY_MS = 400   # Milliseconds after crossing side ArUco checkpoint before teleporting target
TELEPORT_HOLD_MS = 150    # Milliseconds to lock target circle on board to prevent tracking rebound

