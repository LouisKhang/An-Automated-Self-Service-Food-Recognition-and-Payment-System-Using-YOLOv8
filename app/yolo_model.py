# models/yolo_model.py
"""
Quản lý YOLOv8 model
"""
from ultralytics import YOLO
from tkinter import messagebox
import config

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
            results = self.model(image, conf=confidence)
            return results[0]
        except Exception as e:
            print(f"❌ Lỗi detection: {e}")
            return None
    
    def is_loaded(self):
        """Kiểm tra model đã được load chưa"""
        return self.model is not None