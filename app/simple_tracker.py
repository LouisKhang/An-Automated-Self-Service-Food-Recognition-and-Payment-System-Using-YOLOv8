"""
Simple Food Tracker - Phát hiện & tracking đơn giản
Mỗi món chỉ nhận diện 1 lần, sau đó mark as confirmed
"""

import numpy as np
from collections import defaultdict
from datetime import datetime

class SimpleFoodTracker:
    """
    Tracker đơn giản - mỗi món chỉ nhận diện 1 lần
    - Track bằng vị trí bbox + tên món
    - Mỗi vật được confirm 1 lần → ko tích lũy thêm
    - Hiển thị bbox với tracking ID trên camera
    """
    
    def __init__(self, max_distance=60, min_detections=2, confirmation_frames=15):
        """
        Args:
            max_distance: Khoảng cách tối đa (pixels) để coi là cùng 1 vật
            min_detections: Số lần phải thấy mới confirm
            confirmation_frames: Sau confirm, giữ hiển thị bao nhiêu frame
        """
        self.max_distance = max_distance
        self.min_detections = min_detections
        self.confirmation_frames = confirmation_frames
        
        # Lưu trữ tracks: {track_id: {...}}
        self.tracks = {}
        
        # Các mondã được confirmed: {track_id: {...}}
        self.confirmed_items = {}
        
        # Counter
        self.track_counter = 0
        self.frame_count = 0
    
    def reset(self):
        """Reset tracker"""
        self.tracks = {}
        self.confirmed_items = {}
        self.track_counter = 0
        self.frame_count = 0
    
    def update(self, detections):
        """
        Update tracker với detections từ frame hiện tại
        
        Args:
            detections: List các phát hiện
                       [
                           {
                               "name": "pho",
                               "confidence": 0.95,
                               "bbox": [x1, y1, x2, y2]
                           },
                           ...
                       ]
        
        Returns:
            {
                "active_tracks": {...},
                "confirmed_items": {...},
                "frame": frame_number
            }
        """
        self.frame_count += 1
        
        # Lọc detections theo confidence
        valid_detections = [
            d for d in detections 
            if d.get("confidence", 0) >= 0.5
        ]
        
        # Matching: detections ↔ existing tracks
        matched_pairs, unmatched_dets, unmatched_tracks = self._match_detections(
            valid_detections
        )
        
        # Cập nhật tracks đã match
        for track_id, det_idx in matched_pairs:
            detection = valid_detections[det_idx]
            track = self.tracks[track_id]
            
            # Cập nhật thông tin
            track["bbox"] = detection.get("bbox")
            track["latest_confidence"] = detection["confidence"]
            track["detection_count"] += 1
            track["last_seen_frame"] = self.frame_count
            
            # Nâng cao avg confidence
            track["avg_confidence"] = (
                (track["avg_confidence"] * (track["detection_count"] - 1) + 
                 detection["confidence"]) / track["detection_count"]
            )
            
            # Nếu đạt min_detections → confirm
            if (track["detection_count"] >= self.min_detections and 
                track["status"] == "active"):
                track["status"] = "confirmed"
                track["confirmed_frame"] = self.frame_count
                
                # Thêm vào confirmed_items (chỉ 1 lần)
                self.confirmed_items[track_id] = {
                    "id": track_id,
                    "food_name": track["food_name"],
                    "bbox": track["bbox"],
                    "avg_confidence": track["avg_confidence"],
                    "detection_count": track["detection_count"],
                    "confirmed_at": datetime.now().isoformat()
                }
        
        # Tạo track mới cho unmatched detections
        for det_idx in unmatched_dets:
            detection = valid_detections[det_idx]
            self.track_counter += 1
            track_id = str(self.track_counter)
            
            self.tracks[track_id] = {
                "id": track_id,
                "food_name": detection["name"],
                "bbox": detection.get("bbox"),
                "avg_confidence": detection["confidence"],
                "latest_confidence": detection["confidence"],
                "detection_count": 1,
                "first_seen_frame": self.frame_count,
                "last_seen_frame": self.frame_count,
                "confirmed_frame": None,
                "status": "active",  # active, confirmed, expired
                "created_at": datetime.now()
            }
        
        # Xử lý unmatched tracks (cập nhật trạng thái)
        for track_id in unmatched_tracks:
            track = self.tracks[track_id]
            frames_since_seen = self.frame_count - track["last_seen_frame"]
            
            if track["status"] == "confirmed":
                # Confirmed item còn hiển thị thêm `confirmation_frames` khung
                if frames_since_seen > self.confirmation_frames:
                    track["status"] = "expired"
            elif frames_since_seen > 30:
                # Active track mà ko thấy quá 30 frame → xóa
                track["status"] = "expired"
        
        # Xóa expired tracks
        expired_ids = [
            tid for tid, t in self.tracks.items() 
            if t["status"] == "expired"
        ]
        for tid in expired_ids:
            del self.tracks[tid]
        
        return {
            "frame": self.frame_count,
            "active_tracks": self.get_active_tracks(),
            "confirmed_items": self.confirmed_items.copy()
        }
    
    def _match_detections(self, detections):
        """
        Ghép nối detections với tracks
        
        Returns:
            (matched_pairs, unmatched_detections, unmatched_tracks)
        """
        if len(self.tracks) == 0:
            return [], list(range(len(detections))), []
        
        if len(detections) == 0:
            return [], [], list(self.tracks.keys())
        
        # Tính cost matrix
        cost_matrix = self._compute_cost_matrix(detections)
        
        matched_pairs = []
        unmatched_dets = set(range(len(detections)))
        unmatched_tracks = set(self.tracks.keys())
        
        # Gán từng track tới detection gần nhất
        track_ids = list(self.tracks.keys())
        for track_idx, track_id in enumerate(track_ids):
            if track_id not in unmatched_tracks:
                continue
            
            # Tìm detection gần nhất (cùng loại + khoảng cách nhỏ)
            best_det_idx = -1
            best_cost = self.max_distance
            
            for det_idx in unmatched_dets:
                cost = cost_matrix[track_idx][det_idx]
                
                # Điều kiện: cùng loại food + cost < best
                if (self.tracks[track_id]["food_name"] == 
                    detections[det_idx]["name"] and 
                    cost < best_cost):
                    best_cost = cost
                    best_det_idx = det_idx
            
            # Nếu tìm được → ghép cặp
            if best_det_idx >= 0:
                matched_pairs.append((track_id, best_det_idx))
                unmatched_dets.discard(best_det_idx)
                unmatched_tracks.discard(track_id)
        
        return matched_pairs, list(unmatched_dets), list(unmatched_tracks)
    
    def _compute_cost_matrix(self, detections):
        """Tính chi phí (khoảng cách) giữa các bbox"""
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
                
                dist = self._bbox_distance(track_bbox, det_bbox)
                cost_matrix[i][j] = dist
        
        return cost_matrix
    
    def _bbox_distance(self, bbox1, bbox2):
        """Tính khoảng cách giữa tâm 2 bbox"""
        x1_min, y1_min, x1_max, y1_max = bbox1
        x2_min, y2_min, x2_max, y2_max = bbox2
        
        center1 = ((x1_min + x1_max) / 2, (y1_min + y1_max) / 2)
        center2 = ((x2_min + x2_max) / 2, (y2_min + y2_max) / 2)
        
        dist = np.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)
        return dist
    
    def get_active_tracks(self):
        """Lấy tất cả active & confirmed tracks (để vẽ lên khung)"""
        active = {}
        for track_id, track in self.tracks.items():
            if track["status"] in ["active", "confirmed"]:
                active[track_id] = track
        return active
    
    def get_confirmed_items(self):
        """Lấy tất cả items đã confirmed (cho checkout)"""
        return self.confirmed_items.copy()
    
    def draw_tracks(self, frame, annotated_frame=None):
        """
        Vẽ bounding boxes + tracking IDs lên frame
        
        Args:
            frame: Frame gốc
            annotated_frame: Frame từ YOLO result (optional)
        
        Returns:
            Frame với tracking visualization
        """
        import cv2
        
        if annotated_frame is None:
            result = frame.copy()
        else:
            result = annotated_frame.copy()
        
        active_tracks = self.get_active_tracks()
        
        for track_id, track in active_tracks.items():
            if track["bbox"] is None:
                continue
            
            x1, y1, x2, y2 = track["bbox"]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            
            # Chọn màu dựa trên status
            if track["status"] == "confirmed":
                color = (0, 255, 0)  # Xanh lá (confirmed)
                thickness = 3
            else:
                color = (0, 165, 255)  # Cam (tracking)
                thickness = 2
            
            # Vẽ bbox
            cv2.rectangle(result, (x1, y1), (x2, y2), color, thickness)
            
            # Tạo label
            label = f"ID: {track_id} | {track['food_name'].upper()}"
            
            # Display thông tin tracking
            info = f"Det: {track['detection_count']}"
            if track["status"] == "confirmed":
                info += " ✓"
            
            # Vẽ background cho text
            font_scale = 0.6
            font_thickness = 1
            font = cv2.FONT_HERSHEY_SIMPLEX
            
            text_size = cv2.getTextSize(label, font, font_scale, font_thickness)[0]
            cv2.rectangle(
                result,
                (x1, y1 - text_size[1] - 10),
                (x1 + text_size[0] + 10, y1),
                color,
                -1
            )
            
            # Vẽ text
            cv2.putText(
                result,
                label,
                (x1 + 5, y1 - 5),
                font,
                font_scale,
                (255, 255, 255),
                font_thickness
            )
            
            # Vẽ info (detection count)
            cv2.putText(
                result,
                info,
                (x1, y2 + 20),
                font,
                0.5,
                color,
                1
            )
        
        return result
    
    def get_summary(self):
        """Lấy tóm tắt"""
        active = self.get_active_tracks()
        return {
            "total_frames": self.frame_count,
            "active_tracks": len(active),
            "confirmed_items": len(self.confirmed_items),
            "total_unique_items": len(self.confirmed_items)
        }
