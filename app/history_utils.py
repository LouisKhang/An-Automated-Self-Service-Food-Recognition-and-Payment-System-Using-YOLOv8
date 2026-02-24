# utils/history_utils.py
"""
Quản lý lịch sử detection
"""
import json
import os
from datetime import datetime
import config

class HistoryManager:
    def __init__(self, history_file=None):
        self.history_file = history_file or config.HISTORY_FILE
        self.detection_history = []
        self.load_history()
    
    def load_history(self):
        """Load lịch sử từ file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    self.detection_history = json.load(f)
        except Exception as e:
            print(f"⚠️ Không thể load lịch sử: {e}")
            self.detection_history = []
    
    def save_history(self):
        """Lưu lịch sử vào file"""
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(self.detection_history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Lỗi lưu lịch sử: {e}")
    
    def add_record(self, detections, source="upload"):
        """
        Thêm kết quả vào lịch sử
        
        Args:
            detections: List các detection {name, confidence}
            source: Nguồn (upload, camera, ...)
        """
        record = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": source,
            "total_detected": len(detections),
            "items": []
        }
        
        for det in detections:
            record["items"].append({
                "name": det["name"],
                "confidence": det["confidence"]
            })
        
        self.detection_history.insert(0, record)
        
        if len(self.detection_history) > config.MAX_HISTORY_RECORDS:
            self.detection_history = self.detection_history[:config.MAX_HISTORY_RECORDS]
        
        self.save_history()
    
    def clear_history(self):
        """Xóa toàn bộ lịch sử"""
        self.detection_history = []
        self.save_history()
    
    def export_history(self, file_path):
        """
        Xuất lịch sử ra file
        
        Args:
            file_path: Đường dẫn file xuất
        """
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.detection_history, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"❌ Lỗi xuất file: {e}")
            return False
    
    def get_history(self):
        """Lấy toàn bộ lịch sử"""
        return self.detection_history
    
    def get_total_records(self):
        """Lấy tổng số bản ghi"""
        return len(self.detection_history)