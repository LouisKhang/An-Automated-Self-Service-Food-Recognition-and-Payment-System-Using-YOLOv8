# utils/image_utils.py
"""
Các hàm tiện ích xử lý ảnh
"""
import cv2
from PIL import Image, ImageTk

def resize_image_to_canvas(img, canvas_width, canvas_height):
    """
    Resize ảnh để fit vào canvas (tối ưu hóa)
    
    Args:
        img: Ảnh đầu vào (numpy array BGR)
        canvas_width: Chiều rộng canvas
        canvas_height: Chiều cao canvas
        
    Returns:
        img_tk: Ảnh đã resize dạng ImageTk
        new_w, new_h: Kích thước mới
    """
    h, w = img.shape[:2]
    
    # Tính kích thước mới (maintain aspect ratio)
    scale = min(canvas_width/w, canvas_height/h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    # Resize với INTER_LINEAR (nhanh hơn INTER_CUBIC)
    img_resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    
    # Convert BGR -> RGB
    img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)
    
    # Convert to PIL then PhotoImage
    img_pil = Image.fromarray(img_rgb)
    img_tk = ImageTk.PhotoImage(img_pil)
    
    return img_tk, new_w, new_h

def load_image(file_path):
    """
    Load ảnh từ file path
    
    Args:
        file_path: Đường dẫn file
        
    Returns:
        img: Ảnh dạng numpy array hoặc None nếu lỗi
    """
    try:
        img = cv2.imread(file_path)
        return img
    except Exception as e:
        print(f"❌ Lỗi load ảnh {file_path}: {e}")
        return None