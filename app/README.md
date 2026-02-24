# Food Detection App - Application Code

This directory contains the main application code for the Vietnamese Food Detection & Recognition System. The application provides a complete GUI-based food detection system with payment integration.

## Directory Structure

```
app/
├── main.py                        # Application entry point
├── main_window.py                 # Main GUI window and detection logic
├── result_screen.py               # Results display with nutrition charts
├── loading_screen.py              # Professional loading animation screen
├── payment_handler.py             # Payment processing and QR code generation
├── cart_manager.py                # Smart cart management and food normalization
├── config.py                      # Application configuration and constants
├── yolo_model.py                  # YOLOv8 model wrapper and inference engine
├── image_utils.py                 # Image processing and utility functions
├── history_utils.py               # Detection history management
├── detection_history.json         # Local detection records storage
├── runs/                          # Local detection result outputs
├── __init__.py                    # Package initialization
└── __pycache__/                   # Python bytecode cache
```

## Core Components

### Main Application (`main.py`)
- **Purpose**: Entry point for the entire application
- **Functionality**:
  - Initializes Tkinter root window
  - Creates MainWindow instance
  - Starts the GUI event loop
- **Usage**: `python main.py`

### Main Window (`main_window.py`)
- **Purpose**: Primary GUI controller and detection interface
- **Key Features**:
  - Real-time camera feed with bounding boxes
  - Multi-image upload functionality
  - Confidence threshold adjustment
  - Detection result processing
  - Screen navigation (main → loading → results → payment)
- **Dependencies**: All other modules

### Result Screen (`result_screen.py`)
- **Purpose**: Display detection results with nutritional information
- **Features**:
  - Grid-based food card layout
  - Nutritional charts (pie charts for macros)
  - Food details (name, confidence, calories, price)
  - Export functionality (JSON)
  - Cart management integration
- **UI Elements**: Scrollable canvas, interactive cards

### Loading Screen (`loading_screen.py`)
- **Purpose**: Professional loading animation during processing
- **Features**:
  - Smooth spinner animation
  - Modal dialog (blocks parent window)
  - Progress indication
  - Automatic dismissal after processing

### Payment Handler (`payment_handler.py`)
- **Purpose**: Complete payment processing system
- **Features**:
  - QR code generation for mobile payments
  - Built-in HTTP server (port 8765) for payment confirmation
  - Multiple payment methods (cash, card, mobile)
  - Invoice generation and storage
  - Payment success web page integration
- **Technical**: Uses `qrcode` library and `http.server`

### Cart Manager (`cart_manager.py`)
- **Purpose**: Intelligent cart management and food normalization
- **Features**:
  - Automatic food grouping from detection results
  - Name normalization (e.g., 'Banh-canh' → 'Banh_canh')
  - Quantity adjustment based on self-service workflow
  - Real-time price and calorie calculations
  - Cart persistence across sessions

### Configuration (`config.py`)
- **Purpose**: Centralized application configuration
- **Settings Include**:
  - Model paths and detection parameters
  - UI dimensions and color themes
  - Camera settings (resolution, FPS)
  - File paths for data and history
  - Confidence thresholds and limits

### YOLO Model (`yolo_model.py`)
- **Purpose**: YOLOv8 model wrapper and inference engine
- **Features**:
  - Model loading and validation
  - Image preprocessing
  - Detection inference
  - Error handling and logging
- **Dependencies**: `ultralytics` library

### Image Utils (`image_utils.py`)
- **Purpose**: Image processing utilities
- **Functions**:
  - Image resizing and canvas fitting
  - Format conversion (BGR ↔ RGB)
  - File loading and validation
- **Dependencies**: `opencv-python`, `Pillow`

### History Utils (`history_utils.py`)
- **Purpose**: Detection history management
- **Features**:
  - JSON-based history storage
  - Record addition and retrieval
  - History cleanup and limits
  - Session tracking

## Application Flow

1. **Initialization** (`main.py`):
   - Load configuration
   - Initialize YOLO model
   - Create main window

2. **Main Interface** (`main_window.py`):
   - Display camera feed or upload options
   - Handle user input (camera start/stop, image upload)
   - Process detections

3. **Processing** (`loading_screen.py`):
   - Show loading animation
   - Run detection in background
   - Prepare results

4. **Results Display** (`result_screen.py`):
   - Show detected foods in grid
   - Display nutritional information
   - Allow cart additions

5. **Payment Processing** (`payment_handler.py`):
   - Generate QR codes
   - Start HTTP server for confirmation
   - Process payment completion

6. **History Management** (`history_utils.py`):
   - Save detection records
   - Maintain session data

## Key Classes and Methods

### MainWindow Class
```python
class MainWindow:
    def __init__(self, root)          # Initialize GUI components
    def start_camera(self)            # Start real-time detection
    def stop_camera(self)             # Stop camera feed
    def upload_images(self)           # Handle multi-image upload
    def process_detection(self)       # Process detection results
    def show_results(self)            # Navigate to results screen
```

### YOLOModelManager Class
```python
class YOLOModelManager:
    def __init__(self)                # Load YOLO model
    def load_model(self)              # Model initialization
    def detect(self, image, conf)     # Run inference
    def is_loaded(self)               # Check model status
```

### CartManager Class
```python
class CartManager:
    @staticmethod
    def normalize_food_key()          # Standardize food names
    @staticmethod
    def build_cart_from_detections()  # Create cart from results
```

## Dependencies

- **ultralytics**: YOLOv8 framework
- **opencv-python**: Computer vision
- **Pillow**: Image processing
- **qrcode[pil]**: QR code generation
- **tkinter**: GUI framework (built-in)

## Configuration

All configuration is centralized in `config.py`. Key settings:

```python
# Model and data paths
MODEL_PATH = r"path/to/best.pt"
FOOD_DATA_FILE = r"path/to/food_36.json"

# UI settings
WINDOW_WIDTH = 1600
WINDOW_HEIGHT = 900

# Detection parameters
DEFAULT_CONFIDENCE = 0.5

# Color theme
COLORS = {
    'bg_dark': '#0f0f23',
    'accent_green': '#00ff88',
    # ... more colors
}
```

## Running the Application

```bash
# From project root
cd app
python main.py
```

## Development Notes

- **Threading**: Uses threading for non-blocking UI during detection
- **Memory Management**: Efficient image processing to prevent memory leaks
- **Error Handling**: Comprehensive try-catch blocks with user-friendly messages
- **Modularity**: Clean separation of concerns across modules
- **Extensibility**: Easy to add new payment methods or UI screens

## File Dependencies

```
main.py
├── main_window.py
│   ├── yolo_model.py
│   ├── image_utils.py
│   ├── loading_screen.py
│   ├── result_screen.py
│   │   ├── cart_manager.py
│   │   └── payment_handler.py
│   │       └── history_utils.py
│   └── config.py
```

This modular architecture ensures maintainable and scalable code.