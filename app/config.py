# config.py
"""
File cấu hình chung cho ứng dụng Food Detection
"""

# Đường dẫn model
MODEL_PATH = r"C:\Users\PC\Downloads\food_selected_pho_bun\food_detection_1100_image_in_36class\food_detection_36class_1100_resume\yolov8s_vietfood_36class_1100\weights\best.pt"

# Cấu hình camera
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
CAMERA_FPS = 30

# Cấu hình UI
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900
CANVAS_WIDTH = 800
CANVAS_HEIGHT = 550

# Màu sắc theme
COLORS = {
    'bg_dark': '#0f0f23',
    'bg_medium': '#16213e',
    'bg_header': '#1a1a2e',
    'accent_green': '#00ff88',
    'accent_purple': '#6c5ce7',
    'accent_blue': '#00b894',
    'accent_red': '#ff6348',
    'accent_orange': '#ff4757',
    'text_white': 'white',
    'text_gray': '#535c68'
}

# Cấu hình detection
DEFAULT_CONFIDENCE = 0.5
MIN_CONFIDENCE = 0.1
MAX_CONFIDENCE = 1.0

# File paths
FOOD_DATA_FILE = r"C:\Users\PC\Downloads\food_selected_pho_bun\food_36.json"
HISTORY_FILE = "detection_history.json"
MAX_HISTORY_RECORDS = 100