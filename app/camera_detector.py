"""
Camera Detector - Hệ thống phát hiện liên tục với tracking
Chạy camera realtime, track các món, tích lũy kết quả
"""

import cv2
import threading
from queue import Queue
from datetime import datetime
import time

class CameraDetector:
    """
    Hệ thống phát hiện camera realtime với tracking
    - Camera chạy liên tục trong một thread riêng
    - YOLOv8 detection trên mỗi frame
    - Tracking các vật qua các frame
    - Tích lũy các phát hiện
    - Phát tín hiệu beep khi phát hiện lần đầu
    """
    
    def __init__(self, model_manager, tracker, camera_id=0, frame_queue_size=2, on_first_detection=None):
        """
        Args:
            model_manager: YOLOModelManager instance
            tracker: FoodTracker instance
            camera_id: ID của camera (0 = default)
            frame_queue_size: Kích thước queue để giữ frames
            on_first_detection: Callback function khi phát hiện lần đầu - args: (food_name, track_id)
        """
        self.model_manager = model_manager
        self.tracker = tracker
        self.camera_id = camera_id
        self.on_first_detection = on_first_detection
        
        # Camera
        self.cap = None
        self.is_running = False
        self.detection_enabled = True
        
        # Threading
        self.detection_thread = None
        self.frame_queue = Queue(maxsize=frame_queue_size)
        
        # Frames
        self.latest_frame = None
        self.latest_annotated_frame = None
        self.latest_results = None
        
        # Detected items hiện tại (realtime list)
        self.current_detected_items = {}  # {food_name: {track_id: {...}, ...}, ...}
        self.detected_items_lock = threading.Lock()
        
        # Thống kê
        self.fps = 0
        self.frame_count = 0
        self.detection_count = 0
        self.last_fps_update = time.time()
        self.frame_times = []  # Lưu thời gian xử lý từng frame
        
        # Confidence threshold
        self.confidence = 0.5
    
    def start(self, confidence=0.5):
        """Khởi động camera detection"""
        if self.is_running:
            return False
        
        self.confidence = confidence
        self.tracker.reset()  # Reset tracker cho phiên mới
        self.current_detected_items = {}
        
        # Mở camera
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            print(f"❌ Không thể mở camera ID {self.camera_id}")
            return False
        
        # Cấu hình camera
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        
        # Kiểm tra kích thước thực tế
        actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"📷 Camera resolution: {actual_width}x{actual_height}")
        
        self.is_running = True
        self.frame_count = 0
        self.detection_count = 0
        
        # Khởi động detection thread
        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()
        
        print("✅ Camera detector started")
        return True
    
    def stop(self):
        """Dừng camera detection"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Chờ thread hoàn thành
        if self.detection_thread:
            self.detection_thread.join(timeout=5)
        
        # Release camera
        if self.cap:
            self.cap.release()
            self.cap = None
        
        print(f"✅ Camera detector stopped. Total frames: {self.frame_count}, Detections: {self.detection_count}")
    
    def _detection_loop(self):
        """
        Vòng lặp chính - đọc frame, detect, track, tích lũy
        Chạy trong thread riêm
        """
        skip_frames = 0  # Skip some frames để optimize FPS
        
        try:
            while self.is_running:
                try:
                    frame_start = time.time()
                    
                    # Đọc frame
                    ret, frame = self.cap.read()
                    if not ret:
                        print("⚠️  Không thể đọc frame từ camera")
                        time.sleep(0.1)
                        continue
                    
                    self.latest_frame = frame.copy()  # Lưu trữ copy để thread safety
                    self.frame_count += 1
                    
                    # Skip frames để optimize - chỉ process 1 trong N frames (giảm từ 2 xuống 1.5)
                    skip_frames += 1
                    should_detect = (skip_frames >= 1)  # Process every frame (detect mỗi frame)
                    if should_detect:
                        skip_frames = 0
                    
                    # Detection (nếu enabled và frame được chọn)
                    if self.detection_enabled and self.model_manager.is_loaded() and should_detect:
                        try:
                            # YOLOv8 inference
                            result = self.model_manager.detect(frame, self.confidence)
                            
                            if result:
                                # Parse detections từ YOLO result
                                detections = self._parse_yolo_result(result)
                                self.detection_count += len(detections)
                                
                                # Update tracker
                                tracker_result = self.tracker.update(detections)
                                self.latest_results = tracker_result
                                
                                # Cập nhật current_detected_items từ accumulated_detections
                                self._update_current_detected_items()
                                
                                # Annotate frame with tracking info
                                annotated = self._annotate_frame_with_detections(
                                    frame, result, tracker_result
                                )
                                self.latest_annotated_frame = annotated.copy()  # Copy để thread safety
                        except Exception as e:
                            print(f"❌ Detection error: {e}")
                            import traceback
                            traceback.print_exc()
                            self.latest_annotated_frame = frame.copy()
                    else:
                        # Khi detection disabled hoặc skip frame, vẫn hiển thị raw frame
                        self.latest_annotated_frame = frame.copy()
                    
                    # Tính FPS
                    frame_time = time.time() - frame_start
                    self.frame_times.append(frame_time)
                    if len(self.frame_times) > 30:
                        self.frame_times.pop(0)
                    
                    if time.time() - self.last_fps_update > 1.0:
                        avg_time = sum(self.frame_times) / len(self.frame_times)
                        self.fps = 1.0 / avg_time if avg_time > 0 else 0
                        self.last_fps_update = time.time()
                
                except Exception as e:
                    print(f"❌ Frame processing error: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(0.1)
                    continue
        
        except Exception as e:
            print(f"❌ CRITICAL: Detection loop crashed: {e}")
            import traceback
            traceback.print_exc()
            self.is_running = False
    
    def _parse_yolo_result(self, result):
        """
        Chuyển đổi YOLO result sang dạng detections cho tracker
        
        Returns:
            List các phát hiện
        """
        detections = []
        
        for box in result.boxes:
            try:
                cls_id = int(box.cls[0])
                conf = float(box.conf[0])
                
                # Bounding box (x1, y1, x2, y2)
                bbox = box.xyxy[0].cpu().numpy()  # [x1, y1, x2, y2]
                
                class_name = result.names[cls_id]
                
                detections.append({
                    "name": class_name.lower(),
                    "confidence": conf,
                    "bbox": list(bbox),
                    "class_id": cls_id
                })
            except Exception as e:
                print(f"⚠️  Lỗi parse detection: {e}")
                continue
        
        return detections
    
    def get_latest_frame(self):
        """Lấy frame hiện tại (gốc hoặc annotated) - với thread safety"""
        # Trả về annotated frame nếu có, nếu không thì dùng raw frame
        if self.latest_annotated_frame is not None:
            # Tạo copy để tránh threading issue
            return self.latest_annotated_frame.copy()
        elif self.latest_frame is not None:
            return self.latest_frame.copy()
        else:
            return None
    
    def get_accumulated_items(self):
        """Lấy danh sách các món đã tích lũy"""
        return self.tracker.get_accumulated_items()
    
    def get_active_tracks(self):
        """Lấy danh sách các track đang active"""
        return self.tracker.get_active_tracks()
    
    def toggle_detection(self, enabled=None):
        """Bật/tắt detection"""
        if enabled is not None:
            self.detection_enabled = enabled
        else:
            self.detection_enabled = not self.detection_enabled
        
        status = "✅ ON" if self.detection_enabled else "⏸️ OFF"
        print(f"Detection {status}")
    
    def set_confidence(self, confidence):
        """Cập nhật confidence threshold"""
        self.confidence = max(0.1, min(0.99, confidence))
        self.model_manager.model.conf = self.confidence
    
    def _update_current_detected_items(self):
        """Cập nhật current_detected_items từ tracker accumulated_detections"""
        try:
            with self.detected_items_lock:
                self.current_detected_items = {}
                
                # Chuyển đổi từ tracker's accumulated_detections format
                for food_name, tracks_dict in self.tracker.accumulated_detections.items():
                    if food_name not in self.current_detected_items:
                        self.current_detected_items[food_name] = {}
                    
                    for track_id, track_info in tracks_dict.items():
                        self.current_detected_items[food_name][track_id] = track_info
        except Exception as e:
            print(f"⚠️  Lỗi cập nhật detected items: {e}")
    
    def get_current_detected_items(self):
        """Lấy danh sách các món hiện đang được phát hiện"""
        try:
            with self.detected_items_lock:
                return dict(self.current_detected_items)
        except:
            return {}
    
    def _annotate_frame_with_detections(self, frame, yolo_result, tracker_result):
        """
        Annotate frame với bounding box, tracking ID, confidence
        
        Args:
            frame: Frame gốc
            yolo_result: YOLO detection result
            tracker_result: Tracker result dict
        
        Returns:
            Annotated frame
        """
        import cv2
        
        result = frame.copy()
        
        # Vẽ YOLO bounding boxes
        if yolo_result:
            for box in yolo_result.boxes:
                try:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    bbox = box.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = [int(v) for v in bbox]
                    
                    class_name = yolo_result.names[cls_id]
                    
                    # Vẽ bounding box
                    color = (0, 255, 0)  # Green color
                    cv2.rectangle(result, (x1, y1), (x2, y2), color, 2)
                    
                    # Vẽ label
                    label = f"{class_name}: {conf:.2f}"
                    label_size, _ = cv2.getTextSize(
                        label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
                    )
                    cv2.rectangle(
                        result,
                        (x1, y1 - label_size[1] - 4),
                        (x1 + label_size[0], y1),
                        color,
                        -1
                    )
                    cv2.putText(
                        result,
                        label,
                        (x1, y1 - 2),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 0, 0),
                        2
                    )
                except Exception as e:
                    continue
        
        # Thêm FPS vào góc trên cùng
        fps_text = f"FPS: {self.fps:.1f}"
        cv2.putText(
            result,
            fps_text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )
        
        # Thêm detected count
        total_detected = len(self.current_detected_items)
        count_text = f"Items: {total_detected}"
        cv2.putText(
            result,
            count_text,
            (10, 70),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )
        
        return result
    
    def get_summary(self):
        """Lấy tóm tắt hoạt động"""
        try:
            summary = self.tracker.get_summary()
        except:
            summary = {}
            
        summary.update({
            "fps": self.fps,
            "frames_processed": self.frame_count,
            "detections_found": self.detection_count,
            "is_running": self.is_running,
            "detection_enabled": self.detection_enabled,
            "current_detected_count": len(self.current_detected_items)
        })
        return summary
    
    def finalize_session(self):
        """
        Hoàn thúc phiên detection - trả về toàn bộ kết quả tích lũy
        Gọi khi user bấm "Checkout"
        """
        try:
            accumulated = self.tracker.get_accumulated_items()
            summary = self.get_summary()
            
            print(f"\n=== FINALIZE SESSION ===")
            print(f"Accumulated items: {accumulated}")
            print(f"Summary: {summary}")
            print(f"======================\n")
            
            return {
                "items": accumulated,
                "summary": summary,
                "session_end_time": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"❌ Error finalizing session: {e}")
            import traceback
            traceback.print_exc()
            return {
                "items": {},
                "summary": {},
                "session_end_time": datetime.now().isoformat(),
                "error": str(e)
            }
