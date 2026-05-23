"""
Quản lý giỏ hàng và logic điều chỉnh số lượng theo workflow self-service
"""
from tkinter import messagebox


class CartManager:
    """Quản lý giỏ hàng với các ràng buộc theo workflow"""
    
    @staticmethod
    def normalize_food_key(class_name, food_data):
        """
        Chuẩn hóa tên class từ model để khớp với key trong food_data
        Ví dụ: 'banh-canh' -> 'Banh_canh'
                'com chien ga' -> 'Com_chien_ga'
        """
        # Tạo các variations từ class_name
        variations = [
            class_name,  # Original
            class_name.replace('-', '_'),  # Banh-canh -> Banh_canh
            class_name.replace('_', '-'),  # banh_canh -> banh-canh
            class_name.replace(' ', '_'),  # com chien ga -> com_chien_ga
            class_name.replace('-', ''),   # banh-canh -> banhcanh
            class_name.replace('_', ''),   # banh_canh -> banhcanh
        ]
        
        # Tạo thêm biến thể Camelcase
        camel_variations = [
            '_'.join(word.capitalize() for word in class_name.split(' ')),  # com chien ga -> Com_Chien_Ga
            '_'.join(word.capitalize() for word in class_name.replace('-', ' ').split()),  # com-chien-ga -> Com_Chien_Ga
            '_'.join(word.capitalize() for word in class_name.replace('_', ' ').split()),  # com_chien_ga -> Com_Chien_Ga
        ]
        variations.extend(camel_variations)
        
        # Thêm partial CamelCase (chỉ first letter)
        variations.append(class_name[0].upper() + class_name[1:].replace(' ', '_'))  # com chien ga -> Com_chien_ga
        variations.append(' '.join(w.capitalize() for w in class_name.split()).replace(' ', '_'))  # com chien ga -> Com_Chien_Ga
        
        # Special cases
        if class_name.startswith('Bun'):
            variations.append('Bun_' + class_name[4:].replace('-', '_').replace(' ', '_'))
        elif class_name.startswith('Banh'):
            variations.append('Banh_' + class_name[5:].replace('-', '_').replace(' ', '_'))
        
        for key in variations:
            if key in food_data:
                # Debug: print what was matched
                if key != class_name:
                    print(f"✅ Normalized '{class_name}' -> '{key}'")
                return key
        
        print(f"⚠️ Không normalize được '{class_name}' - không tìm thấy trong food_data")
        print(f"   Tried variations: {variations}")
        return class_name
    
    @staticmethod
    def build_cart_from_detections(current_detections, food_data, normalize_func):
        """
        Gom current_detections thành giỏ hàng (cart) theo food_key.
        Đây là bước khởi tạo CartItems từ DetectedItems (read‑only).
        
        Returns:
            dict: Cart dictionary với structure {food_key: {key, name_vi, detected_qty, quantity, ...}}
        """
        cart = {}
        for det in current_detections or []:
            raw_name = det["name"]
            conf = float(det.get("confidence", 0))
            # chuẩn hóa class name
            key = normalize_func(raw_name)
            # Nếu class model trả về không có trong food_data (ví dụ Oc/Canh khi dùng 36-class)
            if key not in food_data:
                print(f"⚠️ Bỏ qua class chưa map: {key} (model trả về: {raw_name})")
                continue

            info = food_data.get(key, {})
            item = cart.setdefault(
                key,
                {
                    "key": key,
                    "name_vi": info.get("name_vi", key),
                    "detected_qty": 0,  # Số lượng mô hình phát hiện (read-only)
                    "quantity": 0,      # Số lượng trong giỏ hàng (cart_qty)
                    "sum_conf": 0.0,
                    "avg_conf": 0.0,
                    "price": info.get("price", 0),
                    "calories": info.get("calories", 0),
                    "excluded": False,  # Bỏ khỏi thanh toán nhưng vẫn giữ trong session
                },
            )
            item["detected_qty"] += 1
            item["quantity"] += 1
            item["sum_conf"] += conf
        
        # Tính avg_conf
        for item in cart.values():
            if item["detected_qty"] > 0:
                item["avg_conf"] = item["sum_conf"] / item["detected_qty"]
            else:
                item["avg_conf"] = 0.0
        
        return cart
    
    @staticmethod
    def get_cart_totals(cart):
        """
        Trả về (total_items, total_price, total_calories) từ cart,
        chỉ tính các món chưa bị excluded_from_payment.
        """
        total_items = 0
        total_price = 0
        total_calories = 0
        for item in cart.values():
            if item.get("excluded"):
                continue
            qty = max(0, int(item.get("quantity", 0)))
            if qty <= 0:
                continue
            total_items += qty
            total_price += item.get("price", 0) * qty
            total_calories += item.get("calories", 0) * qty
        return total_items, total_price, total_calories
    
    @staticmethod
    def can_edit_cart(current_session):
        """Chỉ cho chỉnh giỏ khi session đang ở trạng thái unpaid."""
        if not current_session:
            return True
        return current_session.get("status") == "unpaid"
    
    @staticmethod
    def change_cart_quantity(cart, key, delta, current_session):
        """
        Tăng/giảm quantity trong cart có kiểm soát.
        
        Quy tắc:
        - Luôn đảm bảo quantity (cart_qty) >= detected_qty.
        - Cho phép tăng tự do (người dùng muốn mua nhiều hơn model phát hiện).
        
        Returns:
            bool: True nếu đã thay đổi, False nếu không thể thay đổi
        """
        if not CartManager.can_edit_cart(current_session):
            return False
        
        item = cart.get(key)
        if not item:
            return False
        
        detected_qty = int(item.get("detected_qty", 0))
        current_qty = int(item.get("quantity", 0))
        new_q = current_qty + delta
        
        # Không cho phép giảm xuống thấp hơn detected_qty
        if new_q < detected_qty:
            new_q = detected_qty
        # Đảm bảo không âm trong mọi trường hợp
        if new_q < 0:
            new_q = 0
        
        if new_q == current_qty:
            return False  # Không có thay đổi
        
        item["quantity"] = new_q
        return True
    
    @staticmethod
    def toggle_exclude_item(cart, key, current_session):
        """
        Bật/tắt trạng thái excluded_from_payment cho một món trong cart.
        
        Returns:
            bool: True nếu đã thay đổi, False nếu không thể thay đổi
        """
        if not CartManager.can_edit_cart(current_session):
            return False
        
        item = cart.get(key)
        if not item:
            return False
        
        item["excluded"] = not item.get("excluded", False)
        return True
    
    @staticmethod
    def validate_cart_before_payment(cart):
        """
        Kiểm tra chênh lệch giữa DetectedItems và CartItems trước khi thanh toán.
        
        - Nếu giỏ hàng rỗng → cảnh báo.
        - Nếu có món bị loại khỏi thanh toán hoặc số lượng thanh toán > detected_qty → hỏi xác nhận.
        
        Returns:
            bool: True nếu có thể thanh toán, False nếu không
        """
        if not cart:
            messagebox.showwarning("Giỏ hàng trống", "Chưa có món nào trong giỏ hàng để thanh toán.")
            return False
        
        diffs = []
        excluded_items = []
        for item in cart.values():
            name = item.get("name_vi") or item.get("key")
            detected_qty = int(item.get("detected_qty", 0))
            qty = int(item.get("quantity", 0))
            if item.get("excluded"):
                excluded_items.append(name)
            if qty > detected_qty:
                diffs.append(f"- {name}: model {detected_qty}, thanh toán {qty}")
        
        if not diffs and not excluded_items:
            return True
        
        msg_lines = ["Trước khi thanh toán, hệ thống phát hiện:"]
        if diffs:
            msg_lines.append("\n• Các món có số lượng thanh toán lớn hơn số lượng mô hình phát hiện:")
            msg_lines.extend(diffs)
        if excluded_items:
            msg_lines.append("\n• Các món bị bỏ khỏi thanh toán:")
            for name in excluded_items:
                msg_lines.append(f"- {name}")
        
        msg_lines.append("\nBạn có xác nhận tiếp tục thanh toán với các điều chỉnh này không?")
        return messagebox.askyesno("Xác nhận thanh toán", "\n".join(msg_lines))
