# ui/loading_screen.py
"""
Màn hình loading chuyên nghiệp
"""
from tkinter import *
import config
import math

class LoadingScreen:
    def __init__(self, parent):
        self.parent = parent
        self.window = None
        self.canvas = None
        self.angle = 0
        self.is_active = False
        
    def show(self, message="Đang xử lý..."):
        """Hiển thị màn hình loading"""
        # Tạo toplevel window
        self.window = Toplevel(self.parent)
        self.window.title("Loading")
        self.window.geometry("500x400")
        self.window.configure(bg=config.COLORS['bg_dark'])
        self.window.resizable(False, False)
        
        # Center window
        self.window.transient(self.parent)
        self.window.grab_set()
        
        # Center on parent
        self.window.update_idletasks()
        x = (self.parent.winfo_x() + self.parent.winfo_width()//2 - 250)
        y = (self.parent.winfo_y() + self.parent.winfo_height()//2 - 200)
        self.window.geometry(f"+{x}+{y}")
        
        # Main frame
        main_frame = Frame(self.window, bg=config.COLORS['bg_dark'])
        main_frame.pack(expand=True, fill=BOTH)
        
        # Title
        title_label = Label(
            main_frame,
            text="🍕 FOOD DETECTION AI",
            font=("Arial", 20, "bold"),
            bg=config.COLORS['bg_dark'],
            fg=config.COLORS['accent_green']
        )
        title_label.pack(pady=30)
        
        # Loading canvas với spinner
        self.canvas = Canvas(
            main_frame,
            width=200,
            height=200,
            bg=config.COLORS['bg_dark'],
            highlightthickness=0
        )
        self.canvas.pack(pady=20)
        
        # Message
        self.message_label = Label(
            main_frame,
            text=message,
            font=("Arial", 14),
            bg=config.COLORS['bg_dark'],
            fg=config.COLORS['text_white']
        )
        self.message_label.pack(pady=10)
        
        # Progress text
        self.progress_label = Label(
            main_frame,
            text="⚡ Đang phân tích hình ảnh...",
            font=("Arial", 11),
            bg=config.COLORS['bg_dark'],
            fg=config.COLORS['accent_purple']
        )
        self.progress_label.pack(pady=5)
        
        self.is_active = True
        self.animate_spinner()
        
        self.window.update()
    
    def animate_spinner(self):
        """Animate loading spinner"""
        if not self.is_active or not self.window or not self.window.winfo_exists():
            return
        
        self.canvas.delete("all")
        
        # Vẽ spinner với 8 dots
        center_x, center_y = 100, 100
        radius = 50
        num_dots = 8
        
        for i in range(num_dots):
            angle = (self.angle + i * 45) % 360
            rad = math.radians(angle)
            
            x = center_x + radius * math.cos(rad)
            y = center_y + radius * math.sin(rad)
            
            # Độ mờ dần
            alpha = 1 - (i / num_dots)
            size = 8 - (i * 0.5)
            
            # Màu gradient
            if alpha > 0.7:
                color = config.COLORS['accent_green']
            elif alpha > 0.4:
                color = config.COLORS['accent_purple']
            else:
                color = config.COLORS['text_gray']
            
            self.canvas.create_oval(
                x - size, y - size,
                x + size, y + size,
                fill=color,
                outline=""
            )
        
        # Vẽ icon giữa
        self.canvas.create_text(
            center_x, center_y,
            text="🍜",
            font=("Arial", 40),
        )
        
        self.angle = (self.angle + 10) % 360
        
        if self.is_active:
            self.window.after(50, self.animate_spinner)
    
    def update_message(self, message):
        """Cập nhật message"""
        if self.message_label and self.message_label.winfo_exists():
            self.message_label.config(text=message)
            self.window.update()
    
    def update_progress(self, text):
        """Cập nhật progress text"""
        if self.progress_label and self.progress_label.winfo_exists():
            self.progress_label.config(text=text)
            self.window.update()
    
    def close(self):
        """Đóng màn hình loading"""
        self.is_active = False
        if self.window and self.window.winfo_exists():
            self.window.grab_release()
            self.window.destroy()
            self.window = None