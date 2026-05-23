"""
Object Tracker - Theo dõi các món ăn qua các khung hình liên tiếp
Sử dụng Simple Online and Realtime Tracking (SORT) logic
"""

import numpy as np
from collections import defaultdict
from datetime import datetime


class FoodTracker:
    """
    Theo dõi các món ăn qua các khung hình
    - Gán ID cho mỗi món
    - Tracking theo vị trí (bounding box)
    - Loại bỏ các phát hiện trùng lặp (deduplication)
    - Callback khi phát hiện lần đầu tiên để phát beep
    - Cooldown theo thời gian thực (seconds) để tránh detect 2 lần cùng 1 ảnh
    """

    def __init__(self, max_distance=50, confidence_threshold=0.5, min_detections=2,
                 on_first_detection=None, same_item_cooldown_seconds=5.0):
        """
        Args:
            max_distance: Khoảng cách tối đa (pixels) để coi là cùng 1 vật
            confidence_threshold: Ngưỡng tin cậy để giữ phát hiện
            min_detections: Số lần phải thấy để coi là xác nhận
            on_first_detection: Callback function khi phát hiện lần đầu - args: (food_name, track_id)
            same_item_cooldown_seconds: Số giây chờ trước khi chấp nhận cùng loại món lần nữa.
                                        Default 5 giây — đủ để người dùng đổi ảnh mà không
                                        bị detect 2 lần cùng 1 ảnh.
                                        Set = 0 để tắt cooldown.
        """
        self.max_distance = max_distance
        self.confidence_threshold = confidence_threshold
        self.min_detections = min_detections
        self.on_first_detection = on_first_detection
        self.same_item_cooldown_seconds = same_item_cooldown_seconds

        # Dict lưu trữ tracked objects: {track_id: {...}}
        self.tracks = {}

        # Tích lũy các phát hiện: {food_name: {track_id: {...}}}
        self.accumulated_detections = defaultdict(dict)

        # Tracking các track ID đã gọi callback (tránh gọi nhiều lần)
        self.confirmed_tracks = set()

        # Counter để tạo unique track ID
        self.track_counter = 0

        # Thống kê
        self.frame_count = 0

        # Lưu THỜI ĐIỂM (timestamp) cuối cùng mỗi loại món được confirmed
        # {food_name: datetime}
        self._last_confirmed_time = {}

    def reset(self):
        """Reset tracker (bắt đầu phiên mới)"""
        self.tracks = {}
        self.accumulated_detections = defaultdict(dict)
        self.confirmed_tracks = set()
        self.track_counter = 0
        self.frame_count = 0
        self._last_confirmed_time = {}

    def _is_in_cooldown(self, food_name):
        """
        Kiểm tra cooldown theo thời gian thực, không phụ thuộc fps.
        Nếu đang cooldown → không tạo track mới, tránh detect 2 lần cùng 1 ảnh.
        Nếu hết cooldown → cho phép detect lại (ảnh mới hợp lệ).
        """
        if self.same_item_cooldown_seconds <= 0:
            return False
        last_time = self._last_confirmed_time.get(food_name)
        if last_time is None:
            return False
        elapsed = (datetime.now() - last_time).total_seconds()
        # return true nếu vẫn đang trong cooldown k kích hoạt, false nếu đã hết cooldown cho phép detect lại    
        return elapsed < self.same_item_cooldown_seconds

    def update(self, detections):
        """
        Cập nhật tracker với các phát hiện từ frame hiện tại

        Args:
            detections: List các phát hiện từ YOLOv8
                       [
                           {
                               "name": "pho",
                               "confidence": 0.95,
                               "bbox": [x1, y1, x2, y2]
                           },
                           ...
                       ]

        Returns:
            Dict các tracked objects với thông tin tích lũy
        """
        self.frame_count += 1

        # Lọc detections theo ngưỡng confidence
        valid_detections = [
            d for d in detections
            if d.get("confidence", 0) >= self.confidence_threshold
        ]

        if len(valid_detections) > 0:
            print(f"\n📊 Frame {self.frame_count}: Detected {len(valid_detections)} items:")
            for d in valid_detections:
                print(f"  - {d['name']}: {d['confidence']:.2%}")

        # cặp trùng , detection mới KHÔNG ghép được với track cũ nào,  track cũ KHÔNG tìm được detection mới nào
        matched_pairs, unmatched_detections, unmatched_tracks = self._match_detections(
            valid_detections
        )

        # Cập nhật các track đã match
        for track_id, det_idx in matched_pairs:
            detection = valid_detections[det_idx]
            track = self.tracks[track_id]

            if track["status"] == "done":
                print(f"  ⏭ SKIP (done): {track['food_name']} track_id={track_id}")
                continue

            print(f"  ✓ MATCHED: {track['food_name']} (track_id={track_id}) với detection {det_idx}")

            # Cập nhật vị trí & thông tin
            track["bbox"] = detection.get("bbox")
            track["latest_confidence"] = detection["confidence"]
            track["detection_count"] += 1
            track["last_seen_frame"] = self.frame_count

            # Nâng cao confidence nếu thấy lại
            track["avg_confidence"] = (
                (track["avg_confidence"] * (track["detection_count"] - 1) +
                 detection["confidence"]) / track["detection_count"]
            )

        # Tạo track mới cho detection lần đầu , khi chưa có track
        for det_idx in unmatched_detections:
            detection = valid_detections[det_idx]
            detection_name = detection["name"]
            detection_bbox = detection.get("bbox")

            # Kiểm tra cooldown theo thời gian thực trước khi tạo track mới
            if self._is_in_cooldown(detection_name):
                last = self._last_confirmed_time.get(detection_name)
                remaining = self.same_item_cooldown_seconds - (datetime.now() - last).total_seconds()
                print(f"  🕐 COOLDOWN: {detection_name} còn {remaining:.1f}s nữa")
                # bỏ detection này, không tạo track mới, tránh detect 2 lần cùng 1 ảnh
                continue

            # Tìm track cùng loại (active) và lấy id track gần nhất ,để tái sử dụng track id cũ 
            # so sánh detect frame món mới so với các track cũ lưu trong tracks
            same_type_tracks = [
                track_id for track_id, track in self.tracks.items()
                if track["food_name"] == detection_name and track["status"] == "active"
            ]

            if same_type_tracks and detection_bbox is not None:
                # Tính khoảng cách đến tất cả track cùng loại
                best_track_id = None
                # best_dist = vô cực để tìm track gần nhất, nếu có track nào gần hơn max_distance thì gán lại best_track_id
                best_dist = float('inf')

                for track_id in same_type_tracks:
                    track = self.tracks[track_id]
                    if track["bbox"] is not None:
                        dist = self._bbox_distance(track["bbox"], detection_bbox)
                        if dist < best_dist:
                            best_dist = dist
                            best_track_id = track_id

                # Gán vào track cùng loại gần nhất , nới lỏng khoảng cách để tái sử dụng track id cũ, 
                # tránh tạo track mới nếu chỉ là detect lại cùng 1 món (ảnh mới) mà thôi
                if best_track_id and best_dist < 300:
                    track = self.tracks[best_track_id]
                    track["bbox"] = detection_bbox
                    track["latest_confidence"] = detection["confidence"]
                    track["detection_count"] += 1
                    track["last_seen_frame"] = self.frame_count
                    track["avg_confidence"] = (
                        (track["avg_confidence"] * (track["detection_count"] - 1) +
                         detection["confidence"]) / track["detection_count"]
                    )
                    print(f"  ↻ RE-ASSIGNED: {detection_name} (detection {det_idx}) → track_id={best_track_id} (dist={best_dist:.1f})")
                    continue

            # Không có track cùng loại hoặc khoảng cách quá xa → tạo track mới
            self.track_counter += 1
            track_id = str(self.track_counter)

            print(f"  🆕 NEW TRACK: {detection_name} (track_id={track_id})")

            self.tracks[track_id] = {
                "id": track_id,
                "food_name": detection_name,
                "bbox": detection_bbox,
                "avg_confidence": detection["confidence"],
                "latest_confidence": detection["confidence"],
                "detection_count": 1,
                "first_seen_frame": self.frame_count,
                "last_seen_frame": self.frame_count,
                "created_at": datetime.now(),
                "status": "active"
            }

        # Đánh dấu track bị mất (những track không thấy detect nào trong khoảng thời gian nhất định)
        for track_id in unmatched_tracks:
            track = self.tracks[track_id]

            # track done không cần xử lý thêm
            if track["status"] == "done":
                continue
            #  số frame kể từ lần cuối thấy object này, nếu quá 30 frame thì đánh dấu lost, 
            # nếu quá 10 frame thì đánh dấu confirmed (đã thấy đủ lần nhưng chưa thấy đủ lâu để lost)
            frames_since_seen = self.frame_count - track["last_seen_frame"]

            if frames_since_seen > 30:
                track["status"] = "lost"
            elif frames_since_seen > 10:
                track["status"] = "confirmed"

        # Tích lũy các confirmed tracks
        self._accumulate_confirmed_detections()

        return {
            "frame": self.frame_count,
            "active_tracks": len([t for t in self.tracks.values() if t["status"] == "active"]),
            "confirmed_detections": dict(self.accumulated_detections),
            "all_tracks": self.tracks
        }

    def _match_detections(self, detections):
        """
        Ghép nối detections với existing tracks dựa trên khoảng cách bounding box

        Returns:
            (matched_pairs, unmatched_detections, unmatched_tracks)
        """
        if len(self.tracks) == 0:
            return [], list(range(len(detections))), []

        if len(detections) == 0:
            return [], [], list(self.tracks.keys())
        # gọi hàm lập bảng tính khoảng cách giữa các track và detection
        cost_matrix = self._compute_cost_matrix(detections)

        matched_pairs = []
        unmatched_detections = set(range(len(detections)))
        unmatched_tracks = set(self.tracks.keys())

        track_ids = list(self.tracks.keys())
        for track_idx, track_id in enumerate(track_ids):
            if track_id not in unmatched_tracks:
                continue

            # FIX: track đã done không tham gia matching
            if self.tracks[track_id]["status"] == "done":
                unmatched_tracks.discard(track_id)
                continue
            # chưa tìm thấy detection nào match 
            best_det_idx = -1
            best_cost = self.max_distance

            for det_idx in unmatched_detections:
                cost = cost_matrix[track_idx][det_idx]

                if (self.tracks[track_id]["food_name"] ==
                        detections[det_idx]["name"] and
                        cost < best_cost):
                    best_cost = cost
                    best_det_idx = det_idx

            if best_det_idx >= 0:
                matched_pairs.append((track_id, best_det_idx))
                unmatched_detections.discard(best_det_idx)
                unmatched_tracks.discard(track_id)

        return matched_pairs, list(unmatched_detections), list(unmatched_tracks)

    def _compute_cost_matrix(self, detections):
        """Tính toán chi phí (khoảng cách) giữa các bounding boxes"""
        track_ids = list(self.tracks.keys())
        # tạo ma trận 0
        cost_matrix = np.zeros((len(track_ids), len(detections)))

        for i, track_id in enumerate(track_ids):
            track = self.tracks[track_id]
            if track["bbox"] is None:
                cost_matrix[i] = self.max_distance + 1
                continue

            track_bbox = track["bbox"]

            for j, detection in enumerate(detections):
                det_bbox = detection.get("bbox")
                if det_bbox is None:
                    cost_matrix[i][j] = self.max_distance + 1
                else:
                    cost_matrix[i][j] = self._bbox_distance(track_bbox, det_bbox)

        return cost_matrix

    def _bbox_distance(self, bbox1, bbox2):
        """Tính khoảng cách giữa tâm của 2 bounding box"""
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2

        center1 = ((x1_min + x1_max) / 2, (y1_min + y1_max) / 2)
        center2 = ((x2_min + x2_max) / 2, (y2_min + y2_max) / 2)

        return np.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)

    def _accumulate_confirmed_detections(self):
        """Tích lũy các track đã confirmed và phát callback cho phát hiện lần đầu"""
        for track_id, track in self.tracks.items():
            # Chỉ tích lũy nếu đã thấy đủ lần (min_detections)
            if track["detection_count"] < self.min_detections:
                continue

            # Chỉ xử lý track đang active (chưa done)
            if track["status"] != "active":
                continue

            food_name = track["food_name"]

            # Chỉ thêm 1 lần (avoid duplicate accumulation)
            if track_id not in self.accumulated_detections[food_name]:
                self.accumulated_detections[food_name][track_id] = {
                    "track_id": track_id,
                    "food_name": food_name,
                    "avg_confidence": track["avg_confidence"],
                    "detection_count": track["detection_count"],
                    "first_seen_frame": track["first_seen_frame"],
                    "confirmed_frame": self.frame_count
                }

                print(f"✅ ACCUMULATED: {food_name} (track_id={track_id}, "
                      f"detections={track['detection_count']}, "
                      f"confidence={track['avg_confidence']:.2%})")
                # sau khi them̉ vÀO cart tạm thì đánh dấu done 
                track["status"] = "done"
                self._last_confirmed_time[food_name] = datetime.now()

                # Gọi callback khi phát hiện lần đầu (confirmed)
                if track_id not in self.confirmed_tracks and self.on_first_detection:
                    try:
                        self.on_first_detection(food_name, track_id)
                        self.confirmed_tracks.add(track_id)
                    except Exception as e:
                        print(f"⚠️  Lỗi gọi on_first_detection callback: {e}")

    def get_accumulated_items(self):
        """
        Lấy danh sách các món đã accumulated

        Returns:
            Dict {food_name: quantity, avg_confidence, ...}
        """
        result = {}

        for food_name, tracks in self.accumulated_detections.items():
            result[food_name] = {
                "quantity": len(tracks),
                "avg_confidence": np.mean([
                    t["avg_confidence"] for t in tracks.values()
                ]),
                "detections": list(tracks.values())
            }

        return result

    def get_active_tracks(self):
        """Lấy danh sách các track đang active"""
        return {
            track_id: track for track_id, track in self.tracks.items()
            if track["status"] == "active"
        }

    def draw_tracks(self, frame, annotated_frame=None):
        """
        Vẽ các track lên frame

        Args:
            frame: Frame gốc
            annotated_frame: Frame đã annotated từ YOLO (optional)

        Returns:
            Frame với các track ID vẽ lên
        """
        import cv2

        if annotated_frame is None:
            result = frame.copy()
        else:
            result = annotated_frame.copy()

        # Vẽ active tracks
        active_tracks = self.get_active_tracks()
        for track_id, track in active_tracks.items():
            if track["bbox"] is None:
                continue

            x1, y1, x2, y2 = track["bbox"]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

            color = self._get_track_color(int(track_id))
            cv2.rectangle(result, (x1, y1), (x2, y2), color, 2)

            label = f"ID: {track_id}\n{track['food_name']}\n{track['detection_count']}x"
            cv2.putText(
                result,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2
            )

            # Tích lũy indicator
            if track["detection_count"] >= self.min_detections:
                cv2.circle(result, (x2, y1), 5, (0, 255, 0), -1)

        return result

    def _get_track_color(self, track_idx):
        """Lấy màu dựa trên track ID"""
        colors = [
            (255, 0, 0),    # Blue
            (0, 255, 0),    # Green
            (0, 0, 255),    # Red
            (255, 255, 0),  # Cyan
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Yellow
        ]
        return colors[track_idx % len(colors)]

    def get_summary(self):
        """Lấy tóm tắt tracking"""
        accumulated = self.get_accumulated_items()

        return {
            "total_frames": self.frame_count,
            "active_tracks": len(self.get_active_tracks()),
            "accumulated_items": accumulated,
            "total_items_detected": len(self.accumulated_detections),
            "total_detections": sum(
                t["detection_count"] for t in self.tracks.values()
            )
        }