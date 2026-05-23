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
    Hệ thống camera realtime.
    - detection_enabled = True  → detect mỗi frame (chế độ realtime)
    - detection_enabled = False → chỉ stream preview, không detect
    """

    def __init__(self, model_manager, tracker, camera_id=0, frame_queue_size=2, on_first_detection=None):
        self.model_manager = model_manager
        self.tracker = tracker
        self.camera_id = camera_id
        self.on_first_detection = on_first_detection

        self.cap = None
        self.is_running = False
        self.detection_enabled = True

        self.detection_thread = None
        self.frame_queue = Queue(maxsize=frame_queue_size)

        # ─── LOCK BẢO VỆ MỌI TRUY CẬP FRAME TỪ NHIỀU THREAD ───
        self._frame_lock = threading.Lock()
        self._latest_frame = None           # raw frame từ camera
        self._latest_annotated_frame = None # frame đã vẽ bbox

        # ─── LƯU SNAPSHOT FRAME + BBOX TẠI THỜI ĐIỂM DETECTION ───
        # Key: (food_name, track_id) → {"frame": np.ndarray, "bbox": [x1,y1,x2,y2], "annotated": np.ndarray}
        self._detection_snapshots_lock = threading.Lock()
        self._detection_snapshots = {}

        # Giữ tương thích với code cũ (read-only, không ghi trực tiếp)
        self.latest_results = None
        self.current_detected_items = {}
        self.detected_items_lock = threading.Lock()

        self.fps = 0
        self.frame_count = 0
        self.detection_count = 0
        self.last_fps_update = time.time()
        self.frame_times = []

        self.confidence = 0.5

    # ─────────────────────────────────────────────
    # PROPERTIES — truy cập an toàn từ ngoài
    # ─────────────────────────────────────────────
    @property
    def latest_frame(self):
        with self._frame_lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    @property
    def latest_annotated_frame(self):
        with self._frame_lock:
            return self._latest_annotated_frame.copy() if self._latest_annotated_frame is not None else None

    # ─────────────────────────────────────────────
    # START / STOP
    # ─────────────────────────────────────────────
    def start(self, confidence=0.5):
        """Khởi động camera"""
        if self.is_running:
            return False

        self.confidence = confidence
        self.tracker.reset()
        with self.detected_items_lock:
            self.current_detected_items = {}
        with self._detection_snapshots_lock:
            self._detection_snapshots = {}

        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            print(f" Không thể mở camera ID {self.camera_id}")
            return False

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.cap.set(cv2.CAP_PROP_AUTOFOCUS, 1)

        actual_width  = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"📷 Camera resolution: {actual_width}x{actual_height}")

        self.is_running = True
        self.frame_count = 0
        self.detection_count = 0

        self.detection_thread = threading.Thread(target=self._detection_loop, daemon=True)
        self.detection_thread.start()

        print(" Camera detector started")
        return True

    def stop(self):
        """Dừng camera"""
        if not self.is_running:
            return

        self.is_running = False

        if self.detection_thread:
            self.detection_thread.join(timeout=5)

        if self.cap:
            self.cap.release()
            self.cap = None

        # Xóa frame đang giữ để giải phóng bộ nhớ
        with self._frame_lock:
            self._latest_frame = None
            self._latest_annotated_frame = None

        print(f" Camera detector stopped. "
              f"Total frames: {self.frame_count}, Detections: {self.detection_count}")

    # ─────────────────────────────────────────────
    # DETECTION LOOP (chạy trong thread riêng)
    # ─────────────────────────────────────────────
    def _detection_loop(self):
        try:
            while self.is_running:
                try:
                    frame_start = time.time()

                    ret, frame = self.cap.read()
                    if not ret:
                        print("⚠️  Không thể đọc frame từ camera")
                        time.sleep(0.1)
                        continue

                    self.frame_count += 1

                    with self._frame_lock:
                        self._latest_frame = frame.copy()

                    if self.detection_enabled and self.model_manager.is_loaded():
                        try:
                            detect_frame = frame.copy()
                            result = self.model_manager.detect(detect_frame, self.confidence)

                            if result:
                                detections = self._parse_yolo_result(result)
                                self.detection_count += len(detections)

                                # ─── LƯU SNAPSHOT TRƯỚC KHI GỌI TRACKER ───
                                # annotated_frame dùng để crop ảnh khi _on_first_detection được gọi
                                annotated_frame = self._annotate_frame_with_detections(
                                    frame, result, None
                                )
                                self._save_detection_snapshots(detections, frame, annotated_frame)

                                tracker_result = self.tracker.update(detections)
                                self.latest_results = tracker_result

                                self._update_current_detected_items()

                                with self._frame_lock:
                                    self._latest_annotated_frame = annotated_frame.copy()
                            else:
                                with self._frame_lock:
                                    self._latest_annotated_frame = frame.copy()

                        except Exception as e:
                            print(f" Detection error: {e}")
                            import traceback
                            traceback.print_exc()
                            try:
                                with self._frame_lock:
                                    self._latest_annotated_frame = frame.copy()
                            except Exception:
                                pass
                    else:
                        with self._frame_lock:
                            self._latest_annotated_frame = frame.copy()

                    frame_time = time.time() - frame_start
                    self.frame_times.append(frame_time)
                    if len(self.frame_times) > 30:
                        self.frame_times.pop(0)

                    if time.time() - self.last_fps_update > 1.0:
                        avg_time = sum(self.frame_times) / len(self.frame_times)
                        self.fps = 1.0 / avg_time if avg_time > 0 else 0
                        self.last_fps_update = time.time()

                except Exception as e:
                    print(f" Frame processing error: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(0.1)
                    continue

        except Exception as e:
            print(f" CRITICAL: Detection loop crashed: {e}")
            import traceback
            traceback.print_exc()
            self.is_running = False

    # ─────────────────────────────────────────────
    # SNAPSHOT — lưu frame+bbox khi detect được món
    # ─────────────────────────────────────────────
    def _save_detection_snapshots(self, detections, raw_frame, annotated_frame):
        """
        Lưu snapshot (raw frame, annotated frame, bbox) cho từng detection.
        Dùng food_name làm key (track_id chưa biết ở bước này — tracker chưa assign).
        Logic dùng food_name để tra cứu khi _on_first_detection được gọi.
        Chỉ lưu lần đầu cho mỗi food_name trong 1 batch frame (overwrite OK vì
        _on_first_detection chỉ gọi 1 lần / track_id dù có nhiều frame).
        """
        with self._detection_snapshots_lock:
            for det in detections:
                food_name = det["name"]
                bbox = det.get("bbox", [])
                self._detection_snapshots[food_name] = {
                    "raw_frame":       raw_frame.copy(),
                    "annotated_frame": annotated_frame.copy(),
                    "bbox":            list(bbox),
                    "timestamp":       time.time(),
                }

    def get_detection_snapshot(self, food_name):
        """
        Trả về snapshot mới nhất cho food_name.
        Trả về dict {"raw_frame", "annotated_frame", "bbox"} hoặc None.
        Thread-safe, trả về copy để tránh race condition.
        """
        with self._detection_snapshots_lock:
            snap = self._detection_snapshots.get(food_name)
            if snap is None:
                return None
            return {
                "raw_frame":       snap["raw_frame"].copy(),
                "annotated_frame": snap["annotated_frame"].copy(),
                "bbox":            list(snap["bbox"]),
            }

    def clear_snapshots(self):
        """Xóa toàn bộ snapshot — gọi khi reset session."""
        with self._detection_snapshots_lock:
            self._detection_snapshots.clear()

    # ─────────────────────────────────────────────
    # PUBLIC FRAME ACCESS (thread-safe)
    # ─────────────────────────────────────────────
    def get_latest_frame(self):
        """
        Lấy frame mới nhất (annotated nếu có, raw nếu không).
        Luôn trả về .copy() — an toàn khi dùng từ main thread.
        """
        with self._frame_lock:
            if self._latest_annotated_frame is not None:
                return self._latest_annotated_frame.copy()
            if self._latest_frame is not None:
                return self._latest_frame.copy()
        return None

    def get_raw_frame(self):
        """
        Lấy raw frame (không annotate) — dùng khi chụp thủ công để detect.
        Luôn trả về .copy() — an toàn khi dùng từ main thread.
        """
        with self._frame_lock:
            if self._latest_frame is not None:
                return self._latest_frame.copy()
        return None

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────
    def _parse_yolo_result(self, result):
        """Chuyển đổi YOLO result sang dạng detections cho tracker"""
        detections = []
        for box in result.boxes:
            try:
                cls_id    = int(box.cls[0])
                conf      = float(box.conf[0])
                bbox      = box.xyxy[0].cpu().numpy()
                class_name = result.names[cls_id]
                detections.append({
                    "name":       class_name.lower(),
                    "confidence": conf,
                    "bbox":       list(bbox),
                    "class_id":   cls_id
                })
            except Exception as e:
                print(f"  Lỗi parse detection: {e}")
                continue
        return detections

    def _update_current_detected_items(self):
        """Đồng bộ tracker với UI mỗi khi có update mới"""
        try:
            with self.detected_items_lock:
                self.current_detected_items = {}
                for food_name, tracks_dict in self.tracker.accumulated_detections.items():
                    self.current_detected_items[food_name] = dict(tracks_dict)
        except Exception as e:
            print(f"  Lỗi cập nhật detected items: {e}")

    def _annotate_frame_with_detections(self, frame, yolo_result, tracker_result):
        """Vẽ bounding box và label lên frame (làm việc trên bản sao)"""
        result = frame.copy()

        if yolo_result:
            for box in yolo_result.boxes:
                try:
                    cls_id     = int(box.cls[0])
                    conf       = float(box.conf[0])
                    bbox       = box.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = [int(v) for v in bbox]
                    class_name = yolo_result.names[cls_id]

                    color = (0, 255, 0)
                    cv2.rectangle(result, (x1, y1), (x2, y2), color, 2)

                    label = f"{class_name}: {conf:.2f}"
                    label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                    cv2.rectangle(
                        result,
                        (x1, y1 - label_size[1] - 4),
                        (x1 + label_size[0], y1),
                        color, -1
                    )
                    cv2.putText(result, label, (x1, y1 - 2),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
                except Exception:
                    continue

        cv2.putText(result, f"FPS: {self.fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        with self.detected_items_lock:
            total_detected = len(self.current_detected_items)
        cv2.putText(result, f"Items: {total_detected}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        return result

    # ─────────────────────────────────────────────
    # MISC
    # ─────────────────────────────────────────────
    def get_accumulated_items(self):
        return self.tracker.get_accumulated_items()

    def get_active_tracks(self):
        return self.tracker.get_active_tracks()

    def toggle_detection(self, enabled=None):
        if enabled is not None:
            self.detection_enabled = enabled
        else:
            self.detection_enabled = not self.detection_enabled
        status = " ON" if self.detection_enabled else " OFF"
        print(f"Detection {status}")

    def set_confidence(self, confidence):
        self.confidence = max(0.1, min(0.99, confidence))
        if hasattr(self.model_manager, 'model') and self.model_manager.model:
            self.model_manager.model.conf = self.confidence

    def get_current_detected_items(self):
        try:
            with self.detected_items_lock:
                return dict(self.current_detected_items)
        except Exception:
            return {}

    def get_summary(self):
        try:
            summary = self.tracker.get_summary()
        except Exception:
            summary = {}

        with self.detected_items_lock:
            detected_count = len(self.current_detected_items)

        summary.update({
            "fps":                    self.fps,
            "frames_processed":       self.frame_count,
            "detections_found":       self.detection_count,
            "is_running":             self.is_running,
            "detection_enabled":      self.detection_enabled,
            "current_detected_count": detected_count,
        })
        return summary

    def finalize_session(self):
        """Hoàn thúc phiên detection — trả về kết quả tích lũy"""
        try:
            accumulated = self.tracker.get_accumulated_items()
            summary     = self.get_summary()

            print(f"\n=== FINALIZE SESSION ===")
            print(f"Accumulated items: {accumulated}")
            print(f"Summary: {summary}")
            print(f"======================\n")

            return {
                "items":            accumulated,
                "summary":          summary,
                "session_end_time": datetime.now().isoformat()
            }
        except Exception as e:
            print(f"❌ Error finalizing session: {e}")
            import traceback
            traceback.print_exc()
            return {
                "items":            {},
                "summary":          {},
                "session_end_time": datetime.now().isoformat(),
                "error":            str(e)
            }