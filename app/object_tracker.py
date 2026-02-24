"""
Object Tracker - Theo dõi các món ăn qua các khung hình liên tiếp
Sử dụng Simple Online and Realtime Tracking (SORT) logic
"""

import numpy as np
from collections import defaultdict
from datetime import datetime
import uuid

class FoodTracker:
    """
    Theo dõi các món ăn qua các khung hình
    - Gán ID cho mỗi món
    - Tracking theo vị trí (bounding box)
    - Loại bỏ các phát hiện trùng lặp (deduplication)
    - Callback khi phát hiện lần đầu tiên để phát beep
    """
    
    def __init__(self, max_distance=50, confidence_threshold=0.5, min_detections=2, on_first_detection=None):
        """
        Args:
            max_distance: Khoảng cách tối đa (pixels) để coi là cùng 1 vật
            confidence_threshold: Ngưỡng tin cậy để giữ phát hiện
            min_detections: Số lần phải thấy để coi là xác nhận
            on_first_detection: Callback function khi phát hiện lần đầu - args: (food_name, track_id)
        """
        self.max_distance = max_distance
        self.confidence_threshold = confidence_threshold
        self.min_detections = min_detections
        self.on_first_detection = on_first_detection
        
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
        
    def reset(self):
        """Reset tracker (bắt đầu phiên mới)"""
        self.tracks = {}
        self.accumulated_detections = defaultdict(dict)
        self.confirmed_tracks = set()
        self.track_counter = 0
        self.frame_count = 0
    
    def update(self, detections):
        """
        Cập nhật tracker với các phát hiện từ frame hiện tại
        
        Args:
            detections: List các phát hiện từ YOLOv8
                       [
                           {
                               "name": "pho",
                               "confidence": 0.95,
                               "bbox": [x1, y1, x2, y2]  # bounding box
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
        
        # Ghép nối detections với existing tracks
        matched_pairs, unmatched_detections, unmatched_tracks = self._match_detections(
            valid_detections
        )
        
        # Cập nhật các track đã match
        for track_id, det_idx in matched_pairs:
            detection = valid_detections[det_idx]
            track = self.tracks[track_id]
            
            print(f"  ✓ MATCHED: {track['food_name']} (track_id={track_id}) with detection {det_idx}")
            
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
        
        # Tạo track mới cho các detections không match
        # Nhưng trước tiên, kiểm tra xem có track cùng loại không
        for det_idx in unmatched_detections:
            detection = valid_detections[det_idx]
            detection_name = detection["name"]
            detection_bbox = detection.get("bbox")
            
            # Tìm track cùng loại (active) để reuse thay vì tạo mới
            same_type_tracks = [
                track_id for track_id, track in self.tracks.items()
                if track["food_name"] == detection_name and track["status"] == "active"
            ]
            
            if same_type_tracks and detection_bbox is not None:
                # Có track cùng loại → gán detection vào track cùng loại gần nhất
                # Tính khoảng cách đến tất cả track cùng loại
                best_track_id = None
                best_dist = float('inf')
                
                for track_id in same_type_tracks:
                    track = self.tracks[track_id]
                    if track["bbox"] is not None:
                        dist = self._bbox_distance(track["bbox"], detection_bbox)
                        if dist < best_dist:
                            best_dist = dist
                            best_track_id = track_id
                
                # Gán vào track cùng loại gần nhất
                if best_track_id and best_dist < 300:  # Threshold để assign
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
                "status": "active"  # active, confirmed, lost
            }
        
        # Đánh dấu track bị mất (không thấy trong vài frame)
        for track_id in unmatched_tracks:
            track = self.tracks[track_id]
            frames_since_seen = self.frame_count - track["last_seen_frame"]
            
            if frames_since_seen > 10:  # Mất quá 10 frame → xác nhận
                track["status"] = "confirmed"
            elif frames_since_seen > 30:  # Mất quá 30 frame → xóa
                track["status"] = "lost"
        
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
        
        # Tính toán cost matrix (khoảng cách giữa bbox)
        cost_matrix = self._compute_cost_matrix(detections)
        
        # Gán các detection đến track gần nhất
        matched_pairs = []
        unmatched_detections = set(range(len(detections)))
        unmatched_tracks = set(self.tracks.keys())
        
        # Sắp xếp theo cost từ bé đến lớn
        track_ids = list(self.tracks.keys())
        for track_idx, track_id in enumerate(track_ids):
            if track_id not in unmatched_tracks:
                continue
            
            # Tìm detection gần nhất cho track này
            best_det_idx = -1
            best_cost = self.max_distance
            
            for det_idx in unmatched_detections:
                cost = cost_matrix[track_idx][det_idx]
                
                # Thêm điều kiện: cùng loại food
                if (self.tracks[track_id]["food_name"] == 
                    detections[det_idx]["name"] and 
                    cost < best_cost):
                    best_cost = cost
                    best_det_idx = det_idx
            
            # Nếu tìm được, ghép cặp
            if best_det_idx >= 0:
                matched_pairs.append((track_id, best_det_idx))
                unmatched_detections.discard(best_det_idx)
                unmatched_tracks.discard(track_id)
        
        return matched_pairs, list(unmatched_detections), list(unmatched_tracks)
    
    def _compute_cost_matrix(self, detections):
        """Tính toán chi phí (khoảng cách) giữa các bounding boxes"""
        track_ids = list(self.tracks.keys())
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
                    continue
                
                # Tính khoảng cách Euclidean giữa center của 2 bbox
                dist = self._bbox_distance(track_bbox, det_bbox)
                cost_matrix[i][j] = dist
        
        return cost_matrix
    
    def _bbox_distance(self, bbox1, bbox2):
        """Tính khoảng cách giữa tâm của 2 bounding box"""
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2
        
        center1 = ((x1_min + x1_max) / 2, (y1_min + y1_max) / 2)
        center2 = ((x2_min + x2_max) / 2, (y2_min + y2_max) / 2)
        
        dist = np.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)
        return dist
    
    def _accumulate_confirmed_detections(self):
        """Tích lũy các track đã confirmed và phát callback cho phát hiện lần đầu"""
        for track_id, track in self.tracks.items():
            # Chỉ tích lũy nếu đã thấy đủ lần (min_detections)
            if track["detection_count"] >= self.min_detections:
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
                    
                    print(f"✅ ACCUMULATED: {food_name} (track_id={track_id}, detections={track['detection_count']}, confidence={track['avg_confidence']:.2%})")
                    
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
            
            # Vẽ bbox với màu sắc khác nhau
            color = self._get_track_color(int(track_id))
            cv2.rectangle(result, (x1, y1), (x2, y2), color, 2)
            
            # Hiển thị track ID + food name
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
                cv2.circle(result, (x2, y1), 5, (0, 255, 0), -1)  # Green circle
        
        return result
    
    def _get_track_color(self, track_idx):
        """Lấy màu UV dựa trên track ID"""
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
