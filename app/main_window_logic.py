"""
Logic của ứng dụng Food Detection - Tất cả business logic, không có UI
"""
import cv2
from tkinter import filedialog, messagebox, END
from pathlib import Path
from datetime import datetime
import json
import os
import threading
import time
import requests

import config
from yolo_model import YOLOModelManager
from image_utils import resize_image_to_canvas, load_image
from history_utils import HistoryManager
from cart_manager import CartManager
from payment_handler import PaymentHandler
from camera_detector import CameraDetector
from object_tracker import FoodTracker
from audio_utils import play_success_beep

try:
    import qrcode
    from PIL import Image, ImageTk
    HAS_QR = True
except ImportError:
    HAS_QR = False


class MainWindowLogic:
    """
    Chứa toàn bộ business logic của ứng dụng Food Detection.
    Không tạo bất kỳ widget nào — chỉ thao tác dữ liệu và gọi lại UI thông qua self.root / self.*_frame.
    """

    def _init_logic(self):
        self.model_manager = YOLOModelManager()
        self.food_data = self.load_food_data()
        self.history_manager = HistoryManager()
        self.cart_manager = CartManager()

        self.payment_handler = PaymentHandler(
            root=self.root,
            cart_manager=self.cart_manager,
            get_cart_totals_func=self._get_cart_totals,
            normalize_food_key_func=self.normalize_food_key,
            food_data=self.food_data
        )

        self.food_tracker = FoodTracker(
            max_distance=100,
            confidence_threshold=config.DEFAULT_CONFIDENCE,
            min_detections=1,
            on_first_detection=self._on_first_detection,
            same_item_cooldown_seconds=5.0
        )

        self.camera_detector = CameraDetector(
            model_manager=self.model_manager,
            tracker=self.food_tracker,
            camera_id=0,
            frame_queue_size=2,
            on_first_detection=None  # FIX: bỏ duplicate — tracker đã gọi callback rồi
        )

        self.cap = None
        self.is_camera_running = False
        self.is_realtime_mode = False
        self.current_image = None
        self.confidence_threshold = config.DEFAULT_CONFIDENCE

        self.uploaded_images = []
        self.current_index = 0
        self.current_detections = []
        self.realtime_detected_items = {}
        self.cart = {}
        self.current_session = None

        self._last_payment_method = None
        self._last_invoice_path = None

        self.current_screen = "main"

        self.history_current_page = 0
        self.history_items_per_page = 20

        self.loading_angle = 0
        self.is_loading_active = False

        self.detected_items_label = None
        self.current_photo_image = None
        self._result_image_refs = []

        self.payment_handler.start_payment_server(self)

    # ===================== DATA =====================

    def load_food_data(self):
        """Load dữ liệu món ăn từ JSON"""
        try:
            if os.path.exists(config.FOOD_DATA_FILE):
                with open(config.FOOD_DATA_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"⚠️ Không tìm thấy file {config.FOOD_DATA_FILE}")
                return {}
        except Exception as e:
            print(f"❌ Lỗi load food data: {e}")
            return {}

    # ===================== SEPAY INTEGRATION =====================
    # 1.8
    def create_sepay_order(self, amount, description="Food Order"):
        """Tạo đơn hàng trên SePay backend"""
        try:
            backend_url = config.SEPAY_BACKEND_URL
            resp = requests.post(
                f"{backend_url}/api/create-order",
                json={"amount": amount, "description": description},
                timeout=10
            )
            result = resp.json()
            if result.get('success'):
                return result.get('order_id'), result.get('qr_code'), result.get('qr_url')
            else:
                messagebox.showerror("Lỗi", f"Không tạo được đơn hàng: {result.get('error')}")
                return None, None, None
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Lỗi kết nối",
                "Không thể kết nối đến SePay Backend.\n\n"
                "Hãy chạy: python app/sepay_backend.py")
            return None, None, None
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi tạo đơn hàng: {str(e)}")
            return None, None, None

    def check_payment_status(self, order_id):
        """Kiểm tra trạng thái thanh toán từ backend"""
        try:
            backend_url = config.SEPAY_BACKEND_URL
            resp = requests.get(
                f"{backend_url}/api/check-order/{order_id}",
                timeout=5
            )
            result = resp.json()
            if result.get('success'):
                order = result.get('order', {})
                return order.get('status')
            return None
            
        except Exception:
            return None
    # 1.9
    def poll_payment_status(self, order_id, on_success_callback=None, max_wait=120):
        """Polling kiểm tra trạng thái thanh toán — chạy trong thread riêng."""
        start_time = time.time()
        poll_interval = 2

        print(f"🔄 Bắt đầu polling thanh toán cho order: {order_id}")

        while time.time() - start_time < max_wait and getattr(self, '_payment_polling_active', True):
            try:
                status = self.check_payment_status(order_id)
                print(f"⏳ Order {order_id}: {status}")

                if status == 'paid':
                    print(f"✅ Order {order_id} đã thanh toán!")
                    self.root.after(0, lambda: messagebox.showinfo(
                        "✅ Thanh toán thành công",
                        "Giao dịch đã được xác nhận bởi ngân hàng!"
                    ))
                    if on_success_callback:
                        self.root.after(0, on_success_callback)
                    return True

                elif status == 'failed':
                    print(f"❌ Order {order_id} thất bại!")
                    self.root.after(0, lambda: messagebox.showerror(
                        "❌ Thanh toán thất bại",
                        "Giao dịch bị từ chối hoặc hết hạn"
                    ))
                    return False

                time.sleep(poll_interval)

            except Exception as e:
                print(f"⚠️ Lỗi polling: {e}")
                time.sleep(poll_interval)

        print(f"⏱️ Hết thời gian chờ ({max_wait}s)")
        self.root.after(0, lambda: messagebox.showwarning(
            "⏱️ Hết thời gian",
            f"Chưa nhận được giao dịch trong {max_wait} giây.\n"
            "Bạn có thể quay lại kiểm tra sau."
        ))
        return None

    # ===================== CONFIDENCE =====================

    def update_confidence(self, value):
        """Update confidence threshold"""
        self.confidence_threshold = float(value)
        self.conf_label.config(text=f"Confidence: {self.confidence_threshold:.2f}")
        self.food_tracker.confidence_threshold = self.confidence_threshold
        self.camera_detector.set_confidence(self.confidence_threshold)

    # ===================== IMAGE UPLOAD & NAVIGATION =====================
    # 1.1
    def upload_images(self):
        """Upload NHIỀU ảnh cùng lúc"""
        file_paths = filedialog.askopenfilenames(
            title="Chọn nhiều ảnh",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")]
        )
        if not file_paths:
            return

        self.uploaded_images = []
        self.current_index = 0

        for path in file_paths:
            img = load_image(path)
            if img is not None:
                self.uploaded_images.append({
                    'path': path,
                    'image': img,
                    'detected_image': None,
                    'results': None
                })

        if len(self.uploaded_images) > 0:
            self.current_index = 0
            self.display_current_image()
            self.update_navigation()
            self.status_label.config(text=f"📁 Đã load {len(self.uploaded_images)} ảnh")
        else:
            messagebox.showerror("Lỗi", "Không thể load ảnh nào!")

    def prev_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.display_current_image()
            self.update_navigation()

    def next_image(self):
        if self.current_index < len(self.uploaded_images) - 1:
            self.current_index += 1
            self.display_current_image()
            self.update_navigation()

    def display_current_image(self):
        if len(self.uploaded_images) == 0:
            return

        current = self.uploaded_images[self.current_index]

        if current['detected_image'] is not None:
            self.display_image(current['detected_image'])
            if current['results'] is not None:
                self.show_results(current['results'])
        else:
            self.display_image(current['image'])
            self.results_text.delete(1.0, END)
            self.results_text.insert(END, "⚠️ Chưa detect ảnh này\n\n")
            self.results_text.insert(END, "Nhấn nút DETECT để nhận diện")

        self.image_counter_label.config(
            text=f"📸 Ảnh {self.current_index + 1}/{len(self.uploaded_images)}: {Path(current['path']).name}"
        )

    def update_navigation(self):
        from tkinter import NORMAL, DISABLED
        if len(self.uploaded_images) <= 1:
            self.btn_prev.config(state=DISABLED)
            self.btn_next.config(state=DISABLED)
        else:
            self.btn_prev.config(state=NORMAL if self.current_index > 0 else DISABLED)
            self.btn_next.config(state=NORMAL if self.current_index < len(self.uploaded_images) - 1 else DISABLED)

    # ===================== CAMERA =====================
    # 2.1
    def toggle_camera(self):
        """Bật/tắt camera — preview mode mặc định"""
        if not self.is_camera_running:
            self.uploaded_images = []
            self.current_index = 0
            self.update_navigation()
            self.image_counter_label.config(text="📷 Camera Mode — Chọn chế độ nhận diện")

            if self.camera_detector.start(confidence=self.confidence_threshold):
                self.camera_detector.detection_enabled = False
                self.is_camera_running = True
                self.is_realtime_mode = False
                self.btn_camera.config(text="⏸️ TẮT CAMERA", bg=config.COLORS['accent_orange'])
                self.btn_detect_camera.config(state="normal", bg=config.COLORS['accent_red'])
                self.btn_realtime.config(state="normal", bg=config.COLORS['accent_purple'])
                self.status_label.config(text="📷 Camera đang chạy... Chọn: 'Chụp & Detect' hoặc 'Realtime'")
                self.update_camera()
            else:
                self.status_label.config(text="❌ Không thể bật camera!")
        else:
            self.stop_camera()

    def stop_camera(self):
        """Dừng camera"""
        self.is_camera_running = False
        self.is_realtime_mode = False
        self.camera_detector.stop()
        self.btn_camera.config(text="📷 BẬT CAMERA", bg=config.COLORS['accent_blue'])
        self.btn_detect_camera.config(state="disabled", bg=config.COLORS['text_gray'])
        self.btn_realtime.config(
            state="disabled",
            bg=config.COLORS['text_gray'],
            text="🔴 REALTIME DETECT"
        )
        self.status_label.config(text="⏸️ Camera đã tắt")
        self.image_counter_label.config(text="📸 Chưa có ảnh")
        self.realtime_detected_items = {}
        self.canvas.delete("all")
        # Giải phóng reference ảnh sau khi xóa canvas
        self.current_photo_image = None
    #3.1   mode realtime detect
    def toggle_realtime_detection(self):
        """
        Bật/tắt chế độ realtime detection.
        ON  → detector chạy YOLO mỗi frame, tracker dedup,
               beep + add cart khi confirmed món mới.
        OFF → quay về preview (detection_enabled = False).
        """
        if not self.is_camera_running:
            return

        self.is_realtime_mode = not self.is_realtime_mode

        if self.is_realtime_mode:
            self.food_tracker.reset()
            self.camera_detector.clear_snapshots()
            self.camera_detector.detection_enabled = True
            self.btn_realtime.config(
                text="⏹️ DỪNG REALTIME",
                bg=config.COLORS['accent_red']
            )
            self.btn_detect_camera.config(state="disabled", bg=config.COLORS['text_gray'])
            self.status_label.config(text="🔴 Realtime ON — Đưa món vào khung hình...")
        else:
            self.camera_detector.detection_enabled = False
            self.btn_realtime.config(
                text="🔴 REALTIME DETECT",
                bg=config.COLORS['accent_purple']
            )
            self.btn_detect_camera.config(state="normal", bg=config.COLORS['accent_red'])
            self.status_label.config(text="⏸️ Realtime OFF — Camera đang preview")

    def _on_first_detection(self, food_name, track_id):
        """
       add món ăn vào hệ thống khi tracker xác nhận phát hiện món mới 
        """
        play_success_beep()

        # ─── Lấy confidence từ tracker ───
        conf = 0.0
        try:
            tracks = self.food_tracker.accumulated_detections.get(food_name, {})
            if track_id in tracks:
                conf = tracks[track_id].get("avg_confidence", 0.0)
        except Exception:
            pass

        # ─── Lấy snapshot frame + bbox từ camera_detector ───
        # food_name ở tracker dùng lower(), snapshot key cũng lower() → khớp nhau
        snapshot = self.camera_detector.get_detection_snapshot(food_name)

        crop_image = None
        bbox = []

        if snapshot is not None:
            try:
                annotated_frame = snapshot["annotated_frame"]
                raw_bbox = snapshot["bbox"]  # [x1, y1, x2, y2] dạng float

                if raw_bbox and len(raw_bbox) == 4:
                    bbox = [int(v) for v in raw_bbox]
                    crop_image = self._create_detection_crop(annotated_frame, raw_bbox)
                    print(f"📸 Realtime crop OK: {food_name} bbox={bbox}")
                else:
                    # Không có bbox — fallback: dùng toàn bộ annotated frame
                    crop_image = annotated_frame.copy()
                    print(f"⚠️ Realtime: không có bbox cho {food_name}, dùng full frame")
            except Exception as e:
                print(f"⚠️ Không thể crop realtime detection: {e}")
                # Fallback an toàn: lấy frame hiện tại không cần bbox
                try:
                    fallback_frame = self.camera_detector.get_latest_frame()
                    if fallback_frame is not None:
                        crop_image = fallback_frame
                except Exception:
                    pass
        else:
            # Snapshot chưa kịp lưu (edge case) — fallback lấy frame hiện tại
            print(f"⚠️ Không có snapshot cho {food_name}, dùng latest frame làm fallback")
            try:
                fallback_frame = self.camera_detector.get_latest_frame()
                if fallback_frame is not None:
                    crop_image = fallback_frame
            except Exception:
                pass

        # ─── Tạo detection record đầy đủ (giống upload mode) ───
        new_detection = {
            "name":         food_name,
            "confidence":   conf,
            "bbox":         bbox,           # list[int] hoặc [] nếu không có
            "crop_image":   crop_image,     # np.ndarray hoặc None
            "source_image": "camera_realtime",
        }
        # 2.6
        def update_ui():
            self.current_detections.append(new_detection)

            if self.current_session is None:
                self.current_session = {
                    "id":         datetime.now().strftime("%Y%m%d_%H%M%S"),
                    "status":     "unpaid",
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "type":       "camera_realtime"
                }

            self.cart = self.cart_manager.build_cart_from_detections(
                self.current_detections,
                self.food_data,
                self.normalize_food_key
            )
            self._recalc_cart_totals()
            self._update_detected_items_display()
            self.update_result_button_visibility()
            self.status_label.config(
                text=f"✅ Phát hiện: {food_name} | Giỏ hàng: {len(self.current_detections)} món"
            )

        self.root.after(0, update_ui)

    def _update_detected_items_display(self):
        """Cập nhật hiển thị danh sách các món đã phát hiện"""
        if not self.detected_items_label:
            return

        if not self.current_detections:
            self.detected_items_label.config(text="🛒 Chưa phát hiện món nào")
            return

        counts = {}
        for d in self.current_detections:
            name = d.get('name', 'Unknown')
            counts[name] = counts.get(name, 0) + 1

        lines = ["🛒 Đã phát hiện:"]
        total = 0
        for name, cnt in counts.items():
            lines.append(f"  • {name}: {cnt}")
            total += cnt
        lines.append(f"\n📊 Tổng: {total} món")
        self.detected_items_label.config(text="\n".join(lines))
    # 2.2 
    def update_camera(self):
        """
        Update camera frame trên main thread mỗi 50ms.
        get_latest_frame() để chạy realtime liên tục 
        """
        if not self.is_camera_running:
            return
        try:
            frame = self.camera_detector.get_latest_frame()
            if frame is not None:
                self.current_image = frame   # frame đã là .copy() từ CameraDetector
                self.display_image(frame)
        except Exception as e:
            print(f"❌ Lỗi update camera: {e}")

        # Lên lịch lần tiếp theo — 50ms (≈20fps) giảm tải CPU so với 33ms
        if self.is_camera_running:
            self.root.after(50, self.update_camera)

    # ===================== DETECT ONCE FROM CAMERA - MODE DETECT chụp =====================
    # 2.3
    def detect_once_from_camera(self):
        """
        Chụp 1 frame từ camera và chạy YOLO detect 1 lần.
        Kết quả được add tích lũy vào giỏ hàng.
        """
        if not self.is_camera_running:
            messagebox.showwarning("Thông báo", "Camera chưa được bật!")
            return

        if not self.model_manager.is_loaded():
            messagebox.showwarning("Thông báo", "Model chưa load!")
            return

        if self.is_realtime_mode:
            messagebox.showwarning("Thông báo", "Đang chạy Realtime mode!\nDừng Realtime trước khi chụp thủ công.")
            return

        # lấy frame hiện tại
        frame = self.camera_detector.get_raw_frame()
        if frame is None:
            messagebox.showwarning("Thông báo", "Không lấy được frame từ camera!")
            return

        self.status_label.config(text="⚡ Đang nhận diện...")
        self.btn_detect_camera.config(state="disabled")
        # 2.4
        def run():
            #  hàm xử lí detect bằng chụp ảnh
            try:
                # Detect trên bản copy riêng
                detect_frame = frame.copy()
                result = self.model_manager.detect(detect_frame, self.confidence_threshold)

                if result is None or len(result.boxes) == 0:
                    self.root.after(0, lambda: self.status_label.config(
                        text="⚠️ Không phát hiện món ăn nào trong frame này!"))
                    self.root.after(0, lambda: self.btn_detect_camera.config(state="normal"))
                    return

                annotated_frame = result.plot()

                new_detections = []
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    conf = float(box.conf[0])
                    class_name = result.names[cls_id]
                    bbox = box.xyxy[0].cpu().numpy().tolist()
                    crop = self._create_detection_crop(annotated_frame, bbox)
                    new_detections.append({
                        "name": class_name,
                        "confidence": conf,
                        "bbox": [int(v) for v in bbox],
                        "crop_image": crop,
                        "source_image": "camera"
                    })

                self.current_detections.extend(new_detections)

                self.cart = self.cart_manager.build_cart_from_detections(
                    self.current_detections,
                    self.food_data,
                    self.normalize_food_key
                )
                self._recalc_cart_totals()

                if self.current_session is None:
                    self.current_session = {
                        "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
                        "status": "unpaid",
                        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "type": "camera_manual"
                    }

                names = [d["name"] for d in new_detections]
                count = len(new_detections)

                # Giữ reference annotated_frame để dùng trong lambda
                _annotated = annotated_frame.copy()

                def update_ui():
                    # cập nhật ui ở trang detect 
                    self.display_image(_annotated) # vẽ bbox lên frame 
                    self.show_results(result) # hiển thị kq detect 
                    self._update_detected_items_display() # cập nhật lên giỏ hàng ở trang detect 
                    self.update_result_button_visibility()# update các nút điều khiển
                    self.btn_detect_camera.config(state="normal")
                    self.status_label.config(
                        text=f"✅ Phát hiện {count} món: {', '.join(names[:3])}{'...' if len(names) > 3 else ''}"
                              f" | Tổng giỏ: {len(self.current_detections)} món"
                    )
                    play_success_beep()

                self.root.after(0, update_ui)

            except Exception as e:
                print(f"❌ Lỗi detect_once_from_camera: {e}")
                import traceback
                traceback.print_exc()
                self.root.after(0, lambda: self.status_label.config(text=f"❌ Lỗi nhận diện: {e}"))
                self.root.after(0, lambda: self.btn_detect_camera.config(state="normal"))

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

    def checkout_camera(self):
        if not self.current_detections:
            messagebox.showwarning("Thông báo", "Chưa có món nào trong giỏ hàng!\nHãy nhận diện trước.")
            return

        if self.is_realtime_mode:
            self.toggle_realtime_detection()

        self.stop_camera()
        self.history_manager.add_record(self.current_detections, source="camera")

        self.loading_message_label.config(text="Đang xử lý kết quả...")
        self.loading_progress_label.config(text="⚡ Sắp xếp dữ liệu...")
        self.show_screen("loading")

        def show_results_safe():
            self.build_cart_from_detections()
            self.show_screen("result")

        self.root.after(1000, show_results_safe)

    # ===================== DETECT (upload mode) =====================

    def _transition_to_result(self):
        """Transition từ loading sang result screen"""
        self.show_screen("result")
        self.update_result_button_visibility()
        self.status_label.config(text="✅ Quét hoàn tất! Kiểm tra kết quả")
    # 1.2 
    def detect_food(self):
        """Chạy detection cho ảnh upload"""
        if not self.model_manager.is_loaded():
            self.status_label.config(text="❌ Model chưa được load!")
            return

        if len(self.uploaded_images) == 0:
            self.status_label.config(text="⚠️ Chưa có ảnh để detect!")
            return
        # lọc các ảnh detect rồi tránh detect lại 
        images_to_detect = [img for img in self.uploaded_images if img['detected_image'] is None]

        if len(images_to_detect) == 0:
            messagebox.showinfo("Thông báo", "Tất cả ảnh đã được detect!")
            return

        self.detect_with_loading(images_to_detect, is_camera=False)
    # 1.3 
    def detect_with_loading(self, items, is_camera=False):
        """Chạy detection với màn hình loading"""
        self.show_screen("loading")
        self.loading_message_label.config(text="Đang xử lý...")
        self.loading_progress_label.config(text="⚡ Đang phân tích hình ảnh...")

        self.current_session = {
            "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "status": "unpaid",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.cart = {}
        self.current_detections = []
    # 1.4
        def run_detection():
            # chỉ có nhiệm vụ detect object trên từng frame camera, 
            try:
                total = len(items)
                all_detections = []

                for i, img_data in enumerate(items):
                    self.root.after(0, lambda idx=i, t=total:
                        self.loading_message_label.config(text=f"Đang xử lý ảnh {idx+1}/{t}..."))
                    self.root.after(0, lambda i=i:
                        self.loading_progress_label.config(text=f"⚡ {Path(items[i]['path']).name}"))

                    result = self.model_manager.detect(img_data['image'], self.confidence_threshold)
                    if result:
                        annotated_frame = result.plot()
                        img_data['detected_image'] = annotated_frame
                        img_data['results'] = result

                        detections = []
                        for box in result.boxes:
                            cls_id = int(box.cls[0])
                            conf = float(box.conf[0])
                            class_name = result.names[cls_id]
                            bbox = box.xyxy[0].cpu().numpy().tolist()
                            crop_image = self._create_detection_crop(annotated_frame, bbox)
                            detections.append({
                                "name": class_name,
                                "confidence": conf,
                                "bbox": [int(v) for v in bbox],
                                "crop_image": crop_image,
                                "source_image": Path(img_data['path']).name
                            })

                        all_detections.extend(detections)

                if all_detections:
                    self.root.after(0, lambda d=all_detections:
                        self.history_manager.add_record(d, "upload"))

                self.root.after(0, self.update_history_display)
                self.root.after(0, lambda: self.status_label.config(
                    text=f"✅ Đã detect {len(items)} ảnh!"))

                self.current_detections = all_detections

                if len(all_detections) > 0:
                    def show_results_safe():
                        self.build_cart_from_detections()
                        self.show_result_screen()
                    self.root.after(500, show_results_safe)
                else:
                    self.root.after(500, lambda: self.show_screen("main"))

            except Exception as e:
                print(f"❌ Lỗi detection: {e}")
                self.root.after(0, lambda: self.show_screen("main"))
                self.root.after(0, lambda: messagebox.showerror("Lỗi", f"Lỗi khi detect:\n{e}"))

        thread = threading.Thread(target=run_detection, daemon=True)
        thread.start()
    # 1.5 , 2.5 
    def _create_detection_crop(self, annotated_image, bbox, padding=10):
        """Crop vùng bbox từ ảnh đã annotate"""
        if annotated_image is None or bbox is None:
            return None
        try:
            h, w = annotated_image.shape[:2]
            x1, y1, x2, y2 = [int(round(v)) for v in bbox]
            x1 = max(0, x1 - padding)
            y1 = max(0, y1 - 50)
            x2 = min(w, x2 + padding)
            y2 = min(h, y2 + padding)
            if x2 <= x1 or y2 <= y1:
                return None
            return annotated_image[y1:y2, x1:x2].copy()
        except Exception as e:
            print(f"❌ Lỗi crop ảnh detection: {e}")
            return None

    # ===================== CART / SESSION =====================

    def normalize_food_key(self, class_name):
        return CartManager.normalize_food_key(class_name, self.food_data)
    # 1.6
    def build_cart_from_detections(self):
        self.cart = CartManager.build_cart_from_detections(
            self.current_detections,
            self.food_data,
            self.normalize_food_key
        )
        self._recalc_cart_totals()

    def _get_cart_totals(self):
        return CartManager.get_cart_totals(self.cart)

    def _recalc_cart_totals(self):
        _, total_price, total_calories = self._get_cart_totals()
        self._result_total_price = total_price
        self._result_total_calories = total_calories

    def _validate_cart_before_payment(self):
        return CartManager.validate_cart_before_payment(self.cart)

    def _can_edit_cart(self):
        return CartManager.can_edit_cart(self.current_session)

    # ===================== RESULT / PAYMENT ACTIONS =====================

    def cancel_result(self):
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn hủy kết quả nhận diện này?"):
            self.current_detections = []
            self.cart = {}
            self.current_session = None
            if hasattr(self, 'detected_items_label') and self.detected_items_label:
                self.detected_items_label.config(text="🛒 Chưa phát hiện món nào")
            self.show_screen("main")
            self.status_label.config(text="✅ Đã hủy kết quả. Bạn có thể detect lại.")
    #1.7
    def show_payment_dialog(self):
        if not self._validate_cart_before_payment():
            return
        self.show_screen("payment")
        self.display_payment_screen()

    def _generate_invoice_text(self):
        total_items, total_price, total_cal = self._get_cart_totals()
        payment_method = getattr(self, '_last_payment_method', 'Tiền mặt')
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")

        lines = []
        lines.append(" " * 20 + "🍕 FOOD DETECTION AI")
        lines.append(" " * 18 + "=" * 30)
        lines.append(" " * 20 + "HÓA ĐƠN BÁN HÀNG")
        lines.append(" " * 18 + "=" * 30)
        lines.append("")
        lines.append(f"Ngày: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        lines.append(f"Mã HĐ: INV_{ts}")
        lines.append(f"Phương thức: {payment_method}")
        lines.append("-" * 50)
        lines.append(f"{'Tên món':<25} {'SL':>3} {'Giá':>12} {'TT':>12}")
        lines.append("-" * 50)

        for item in self.cart.values():
            qty = int(item.get("quantity", 0))
            if item.get("excluded") or qty <= 0:
                continue
            name = (item.get("name_vi") or item.get("key"))[:23]
            price = item.get("price", 0)
            total_line = price * qty
            lines.append(f"{name:<25} {qty:>3} {price:>11,}đ {total_line:>11,}đ")

        lines.append("-" * 50)
        lines.append(f"{'Tổng số phần:':<25} {total_items:>3}")
        lines.append(f"{'Tổng calo:':<25} {total_cal:,} kcal")
        lines.append("")
        lines.append(f"{'TỔNG TIỀN:':<25} {total_price:>11,}đ")
        lines.append("")
        lines.append(" " * 15 + "Cảm ơn quý khách!")
        lines.append(" " * 12 + "Hẹn gặp lại 🎉")
        lines.append("=" * 50)

        return "\n".join(lines)

    # ===================== HISTORY ACTIONS =====================

    def history_prev_page(self):
        if self.history_current_page > 0:
            self.history_current_page -= 1
            self.display_history_screen()

    def history_next_page(self):
        history_data = self.history_manager.get_history()
        total_pages = (len(history_data) + self.history_items_per_page - 1) // self.history_items_per_page
        if self.history_current_page < total_pages - 1:
            self.history_current_page += 1
            self.display_history_screen()

    def clear_history(self):
        if messagebox.askyesno("Xác nhận", "Bạn có chắc muốn xóa toàn bộ lịch sử?"):
            self.history_manager.clear_history()
            self.update_history_display()
            self.status_label.config(text="🗑️ Đã xóa lịch sử")

    def export_history(self):
        if self.history_manager.get_total_records() == 0:
            messagebox.showwarning("Cảnh báo", "Chưa có lịch sử để xuất!")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"food_detection_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )

        if file_path:
            if self.history_manager.export_history(file_path):
                messagebox.showinfo(
                    "Thành công",
                    f"Đã xuất {self.history_manager.get_total_records()} bản ghi!\n\n{file_path}"
                )
                self.status_label.config(text=f"💾 Đã xuất lịch sử: {Path(file_path).name}")
            else:
                messagebox.showerror("Lỗi", "Không thể xuất file!")
                self.status_label.config(text="❌ Lỗi xuất file!")

    # ===================== RESET / SESSION =====================

    def reset(self):
        if self.is_camera_running:
            self.stop_camera()

        self.food_tracker.reset()
        self.camera_detector.stop()
        self.camera_detector.clear_snapshots()

        self.current_image = None
        self.uploaded_images = []
        self.current_index = 0
        self.realtime_detected_items = {}
        self.canvas.delete("all")
        self.current_photo_image = None
        self.results_text.delete(1.0, END)
        self.image_counter_label.config(text="📸 Chưa có ảnh")
        if hasattr(self, 'detected_items_label') and self.detected_items_label:
            self.detected_items_label.config(text="🛒 Chưa phát hiện món nào")
        self.update_navigation()
        self.status_label.config(text="✅ Ready! Upload ảnh hoặc dùng camera để detect")
        self.current_detections = []
        self.cart = {}
        self.current_session = None
        self.is_realtime_mode = False
        self.update_result_button_visibility()
    # 1 final
    def _end_session(self):
        self.stop_camera()
        self.camera_detector.clear_snapshots()

        self.current_image = None
        self.uploaded_images = []
        self.current_index = 0
        self.cart = {}
        self.current_detections = []
        self.current_session = None
        self._last_payment_method = None
        self._last_invoice_path = None
        self.is_realtime_mode = False

        if hasattr(self, 'canvas'):
            self.canvas.delete("all")
        if hasattr(self, 'results_text'):
            self.results_text.delete(1.0, END)
        if hasattr(self, 'image_counter_label'):
            self.image_counter_label.config(text="📸 Chưa có ảnh")
        if hasattr(self, 'detected_items_label') and self.detected_items_label:
            self.detected_items_label.config(text="🛒 Chưa phát hiện món nào")
        if hasattr(self, 'update_navigation'):
            self.update_navigation()

        self.update_result_button_visibility()
        self.show_screen("main")
        self.status_label.config(text="✅ Đã kết thúc phiên. Sẵn sàng cho lần detect mới.")

    # ===================== IMAGE DISPLAY =====================

    def display_image(self, img):
        """
        Hiển thị numpy image lên canvas.
        QUAN TRỌNG: giữ strong reference vào self.current_photo_image
        để Tkinter không garbage-collect ảnh trong khi đang hiển thị.
        """
        if img is None:
            return
        try:
            img_tk, new_w, new_h = resize_image_to_canvas(
                img, config.CANVAS_WIDTH, config.CANVAS_HEIGHT
            )
            self.canvas.delete("all")
            self.canvas.create_image(
                config.CANVAS_WIDTH // 2,
                config.CANVAS_HEIGHT // 2,
                image=img_tk,
                anchor="center"
            )
            # Giữ reference — PHẢI gán SAU khi create_image để tránh GC
            self.current_photo_image = img_tk
        except Exception as e:
            print(f"❌ Lỗi hiển thị ảnh: {e}")

    def show_results(self, result):
        self.results_text.delete(1.0, END)

        if len(result.boxes) == 0:
            self.results_text.insert(END, "❌ Không phát hiện món ăn nào!\n\n")
            self.results_text.insert(END, "💡 Thử:\n")
            self.results_text.insert(END, "  • Giảm confidence threshold\n")
            self.results_text.insert(END, "  • Chọn ảnh rõ hơn\n")
            return

        self.results_text.insert(END, f"🎯 Phát hiện: {len(result.boxes)} món\n")
        self.results_text.insert(END, "=" * 35 + "\n\n")

        for i, box in enumerate(result.boxes):
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            class_name = result.names[cls_id]
            self.results_text.insert(END, f"#{i+1} {class_name}\n")
            self.results_text.insert(END, f"   Confidence: {conf:.2%}\n")
            bar_length = int(conf * 20)
            bar = "█" * bar_length + "░" * (20 - bar_length)
            self.results_text.insert(END, f"   [{bar}]\n\n")

    # ===================== UI VISIBILITY =====================

    def update_result_button_visibility(self):
        if hasattr(self, 'btn_see_result') and self.btn_see_result.winfo_exists():
            if self.current_detections:
                self.btn_see_result.place(relx=1.0, rely=0.5, anchor="e", x=-10)
            else:
                self.btn_see_result.place_forget()

        if hasattr(self, 'btn_history') and self.btn_history.winfo_exists():
            self.btn_history.place(relx=1.0, rely=0.5, anchor="e", x=-140)

        if hasattr(self, 'btn_checkout_camera') and self.btn_checkout_camera.winfo_exists():
            if self.is_camera_running and self.current_detections:
                self.btn_checkout_camera.grid()
            else:
                self.btn_checkout_camera.grid_remove()

    def show_result_screen(self):
        if self.current_detections:
            self.show_screen("result")
        self.update_result_button_visibility()

    def update_history_display(self):
        if hasattr(self, 'stats_label') and self.stats_label.winfo_exists():
            self.stats_label.config(
                text=f"📊 Tổng: {self.history_manager.get_total_records()} lần detect"
            )
        if hasattr(self, 'history_text') and self.history_text.winfo_exists():
            self.history_text.delete(1.0, END)
            history = self.history_manager.get_history()
            if not history:
                self.history_text.insert(END, "📭 Chưa có lịch sử\n\nBắt đầu detect để\nlưu lịch sử!")
                return
            for record in history:
                source_icon = "📷" if "camera" in record["source"] else "📁"
                self.history_text.insert(END, f"{source_icon} {record['timestamp']}\n")
                self.history_text.insert(END, f"   Nguồn: {record['source']}\n")
                self.history_text.insert(END, f"   Phát hiện: {record['total_detected']} món\n")
                for item in record["items"][:3]:
                    self.history_text.insert(END, f"   • {item['name']} ({item['confidence']:.0%})\n")
                if record["total_detected"] > 3:
                    self.history_text.insert(END,
                        f"   ... và {record['total_detected'] - 3} món khác\n")
                self.history_text.insert(END, "-" * 40 + "\n\n")

        self.update_result_button_visibility()

    def __del__(self):
        if self.cap:
            self.cap.release()