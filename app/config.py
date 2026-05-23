# config.py
"""
File cấu hình chung cho ứng dụng Food Detection
"""

# Đường dẫn model
MODEL_PATH = r"C:\Users\PC\Downloads\food_selected_pho_bun\yolov8s_vietfood_36class-20260124T101124Z-3-001\yolo_8m_augumented_v2_them_1k_image\best.pt"

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
MAX_HISTORY_RECORDS = 200

# ===== SePay Configuration =====
# Lấy từ: https://sepay.vn (Đăng ký merchant)
SEPAY_API_KEY = "K085OZZ8N9WFLLMQYBJRFCT5BCJEDTAJMUC6WDUO1SPVSHJPPGFQHLSMXA21I3YZ"  # TODO: Điền API Key của bạn từ SePay
SEPAY_ACCOUNT_NO = "0949810032"  # Số tài khoản Techcombank
SEPAY_ACCOUNT_NAME = "Hoang Ninh Khang"  # Tên chủ tài khoản

# SePay Backend server
SEPAY_BACKEND_URL = "http://127.0.0.1:5000"  # URL backend (local hoặc cloud)

