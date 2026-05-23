# models/yolo_model.py
"""
Quản lý YOLOv8 model
"""
from ultralytics import YOLO
from tkinter import messagebox
import config
import cv2
import numpy as np

class YOLOModelManager:
    def __init__(self, model_path=None):
        self.model_path = model_path or config.MODEL_PATH
        self.model = None
        self.load_model()
    
    def load_model(self):
        """Load YOLOv8 model"""
        try:
            self.model = YOLO(self.model_path)
            print(f"✅ Model loaded: {self.model_path}")
            return True
        except Exception as e:
            print(f" Lỗi load model: {e}")
            messagebox.showerror(
                "Lỗi Model", 
                f"Không thể load model:\n{e}\n\nĐảm bảo file model tồn tại tại:\n{self.model_path}"
            )
            return False
    
    def detect(self, image, confidence=0.5):
        """
        Chạy detection trên ảnh
        
        Args:
            image: Ảnh đầu vào (numpy array)
            confidence: Ngưỡng confidence
            
        Returns:
            results: Kết quả detection từ YOLO
        """
        if self.model is None:
            return None
        
        try:
            preprocessed = self.preprocess_image(image)
            results = self.model(preprocessed, conf=confidence)
            return results[0]
        except Exception as e:
            print(f"❌ Lỗi detection: {e}")
            return None

    def preprocess_image(self, image):
        """
        Tiền xử lý ảnh - bản gốc: không áp dụng enhancement
        """
        if image is None:
            return image

        img = image.copy()
        if img.ndim == 2:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        elif img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

        # Không áp dụng bất kỳ enhancement nào - giữ nguyên ảnh gốc
        return img
    
    def is_loaded(self):
        """Kiểm tra model đã được load chưa"""
        return self.model is not None