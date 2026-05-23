# ui/result_screen.py
"""
Màn hình hiển thị kết quả detection với biểu đồ dinh dưỡng
"""
from tkinter import *
from tkinter import ttk, filedialog, messagebox
import json
import config
import math
from datetime import datetime
import os

class ResultScreen:
    def __init__(self, parent, detections, food_data, on_close_callback=None):
        """
        Args:
            parent: Parent window
            detections: List các detection {name, confidence, ...}
            food_data: Dictionary chứa thông tin món ăn
            on_close_callback: Callback function khi click nút Trở về
        """
        self.parent = parent
        self.detections = detections
        self.food_data = food_data
        self.on_close_callback = on_close_callback
        self.window = None
        self.canvas = None
        self.canvas_window = None
        self.scrollable_frame = None
        self.total_price = 0
        self.total_calories = 0

    def normalize_food_key(self, class_name):
        """Chuẩn hóa tên class từ model để khớp với key trong food_data (vd: Banh-canh -> Banh_canh)."""
        variations = [
            class_name,
            class_name.replace('-', '_'),
            class_name.replace('_', '-'),
            class_name.replace(' ', '_'),
            class_name.replace('-', ''),
            class_name.replace('_', ''),
        ]
        if class_name.startswith('Bun-'):
            variations.append('Bun_' + class_name[4:].replace('-', '_'))
        elif class_name.startswith('Banh-'):
            variations.append('Banh_' + class_name[5:].replace('-', '_'))
        for key in variations:
            if key in self.food_data:
                return key
        return class_name

    def get_food_info(self, detection):
        """Lấy food_info từ food_data (có chuẩn hóa key). Trả về dict có đủ name_vi, price, calories, ..."""
        key = self.normalize_food_key(detection['name'])
        info = self.food_data.get(key, {})
        if info:
            return info
        return {
            'name_vi': detection['name'],
            'price': 0,
            'calories': 0,
            'protein': 0,
            'carbs': 0,
            'fat': 0,
            'description': f'Món: {detection["name"]}'
        }

    def show(self):
        """Hiển thị màn hình kết quả"""
        self.window = Toplevel(self.parent)
        self.window.title("🍕 Kết Quả Nhận Diện")
        self.window.geometry("1200x800")
        self.window.minsize(900, 600)
        self.window.configure(bg=config.COLORS['bg_dark'])
        self.window.transient(self.parent)
        self.window.update_idletasks()
        x = (self.parent.winfo_x() + self.parent.winfo_width() // 2 - 600)
        y = (self.parent.winfo_y() + self.parent.winfo_height() // 2 - 400)
        self.window.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.setup_ui()

    def setup_ui(self):
        """Thiết kế giao diện kết quả - layout cân bằng, dễ đọc"""
        # ----- HEADER: title + nút trở về cùng hàng -----
        header = Frame(self.window, bg=config.COLORS['bg_header'], height=72)
        header.pack(fill=X, padx=0, pady=0)
        header.pack_propagate(False)

        btn_back = Button(
            header,
            text="← Trở về",
            bg=config.COLORS['bg_medium'],
            fg=config.COLORS['text_white'],
            font=('Arial', 11, 'bold'),
            bd=0,
            padx=16,
            pady=8,
            cursor='hand2',
            command=self.go_back
        )
        btn_back.pack(side=LEFT, padx=20, pady=16)

        Label(
            header,
            text="📊 Kết quả nhận diện",
            font=("Arial", 20, "bold"),
            bg=config.COLORS['bg_header'],
            fg=config.COLORS['accent_green']
        ).pack(side=LEFT, expand=True)

        # ----- MAIN: scrollable content -----
        main_container = Frame(self.window, bg=config.COLORS['bg_dark'])
        main_container.pack(fill=BOTH, expand=True, padx=24, pady=16)

        self.canvas = Canvas(main_container, bg=config.COLORS['bg_dark'], highlightthickness=0)
        scrollbar = Scrollbar(main_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = Frame(self.canvas, bg=config.COLORS['bg_dark'])

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", self.on_mousewheel)
        self.canvas.bind("<Button-5>", self.on_mousewheel)

        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.total_price = 0
        self.total_calories = 0

        max_cols = 3
        card_pad = 12
        card_w = 320
        card_h = 260

        if not self.detections:
            Label(
                self.scrollable_frame,
                text="Không phát hiện món nào.",
                font=("Arial", 14),
                bg=config.COLORS['bg_dark'],
                fg=config.COLORS['text_gray']
            ).pack(pady=40)
        else:
            grid_wrapper = Frame(self.scrollable_frame, bg=config.COLORS['bg_dark'])
            grid_wrapper.pack(fill=X, pady=(0, 20))

            grid_inner = Frame(grid_wrapper, bg=config.COLORS['bg_dark'])
            grid_inner.pack(anchor=CENTER)

            for idx, detection in enumerate(self.detections):
                food_info = self.get_food_info(detection)
                confidence = detection['confidence']

                self.total_price += food_info.get('price', 0)
                self.total_calories += food_info.get('calories', 0)

                row_index = idx // max_cols
                col_index = idx % max_cols

                card = Frame(
                    grid_inner,
                    bg=config.COLORS['bg_medium'],
                    bd=0,
                    highlightbackground=config.COLORS['accent_green'],
                    highlightthickness=1,
                    width=card_w,
                    height=card_h
                )
                card.grid(row=row_index, column=col_index, padx=card_pad, pady=card_pad, sticky="nsew")
                card.grid_propagate(False)

                inner = Frame(card, bg=config.COLORS['bg_medium'])
                inner.pack(fill=BOTH, expand=True, padx=16, pady=14)

                Label(
                    inner,
                    text=f"#{idx + 1}  {food_info.get('name_vi', detection['name'])}",
                    font=("Arial", 13, "bold"),
                    bg=config.COLORS['bg_medium'],
                    fg=config.COLORS['accent_green'],
                    anchor=W,
                    wraplength=card_w - 40
                ).pack(fill=X, pady=(0, 4))

                Label(
                    inner,
                    text=f"Độ chính xác: {confidence:.0%}",
                    font=("Arial", 9),
                    bg=config.COLORS['bg_medium'],
                    fg=config.COLORS['text_gray'],
                    anchor=W
                ).pack(fill=X, pady=(0, 8))

                desc = food_info.get('description', '') or ''
                desc_short = (desc[:65] + '...') if len(desc) > 65 else desc
                Label(
                    inner,
                    text=desc_short,
                    font=("Arial", 9),
                    bg=config.COLORS['bg_medium'],
                    fg='#aaaaaa',
                    anchor=W,
                    justify=LEFT,
                    wraplength=card_w - 40
                ).pack(fill=X, pady=(0, 10))

                info_row = Frame(inner, bg=config.COLORS['bg_medium'])
                info_row.pack(fill=X, pady=(0, 10))

                Label(info_row, text=f"💰 {food_info.get('price', 0):,}đ", font=("Arial", 11, "bold"),
                      bg=config.COLORS['bg_medium'], fg=config.COLORS['accent_orange']).pack(side=LEFT)
                Label(info_row, text=f"🔥 {food_info.get('calories', 0)} kcal", font=("Arial", 10),
                      bg=config.COLORS['bg_medium'], fg=config.COLORS['accent_red']).pack(side=RIGHT)

                chart_frame = Frame(inner, bg=config.COLORS['bg_medium'])
                chart_frame.pack(fill=X)
                self.draw_nutrition_chart(
                    chart_frame,
                    food_info.get('protein', 0),
                    food_info.get('carbs', 0),
                    food_info.get('fat', 0),
                    size=90
                )

            for c in range(max_cols):
                grid_inner.grid_columnconfigure(c, weight=0)

        # ----- Tổng kết: 1 dòng rõ ràng -----
        summary = Frame(self.scrollable_frame, bg=config.COLORS['bg_header'], padx=24, pady=16)
        summary.pack(fill=X, pady=(0, 16))

        summary_inner = Frame(summary, bg=config.COLORS['bg_header'])
        summary_inner.pack(anchor=CENTER)

        Label(
            summary_inner,
            text=f"🍽️ {len(self.detections)} món",
            font=("Arial", 13, "bold"),
            bg=config.COLORS['bg_header'],
            fg=config.COLORS['text_white']
        ).pack(side=LEFT, padx=20, pady=8)

        Label(
            summary_inner,
            text=f"💰 Tổng: {self.total_price:,}đ",
            font=("Arial", 13, "bold"),
            bg=config.COLORS['bg_header'],
            fg=config.COLORS['accent_orange']
        ).pack(side=LEFT, padx=20, pady=8)

        Label(
            summary_inner,
            text=f"🔥 {self.total_calories:,} kcal",
            font=("Arial", 13, "bold"),
            bg=config.COLORS['bg_header'],
            fg=config.COLORS['accent_red']
        ).pack(side=LEFT, padx=20, pady=8)

        # ----- Nút hành động: căn giữa -----
        actions = Frame(self.scrollable_frame, bg=config.COLORS['bg_dark'])
        actions.pack(fill=X, pady=(0, 24))

        btn_frame = Frame(actions, bg=config.COLORS['bg_dark'])
        btn_frame.pack(anchor=CENTER)

        for text, cmd, bg in [
            ("💳 Thanh toán", self.process_payment, config.COLORS['accent_green']),
            ("🔙 Trở về", self.go_back, config.COLORS['text_gray']),
        ]:
            Button(
                btn_frame,
                text=text,
                bg=bg,
                fg='white',
                font=('Arial', 11, 'bold'),
                width=18,
                height=2,
                bd=0,
                cursor='hand2',
                command=cmd
            ).pack(side=LEFT, padx=10, pady=5)
    
    def on_mousewheel(self, event):
        """Xử lý cuộn chuột trên canvas"""
        scroll_amount = 5
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(scroll_amount, "units")
        elif event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-scroll_amount, "units")
    
    def on_canvas_configure(self, event):
        """Cập nhật width của window trong canvas"""
        # Cập nhật width của scrollable_frame để khớp với canvas width
        self.canvas.itemconfig(self.canvas_window, width=event.width)
    
    def draw_nutrition_chart(self, parent, protein, carbs, fat, size=200):
        """
        Vẽ biểu đồ tròn dinh dưỡng
        
        Args:
            parent: Frame chứa biểu đồ
            protein: Lượng protein (g)
            carbs: Lượng carbs (g)
            fat: Lượng chất béo (g)
            size: Kích thước biểu đồ (default 200px)
        """
        canvas = Canvas(parent, width=size, height=size, bg=config.COLORS['bg_medium'], highlightthickness=0)
        canvas.pack()
        
        # Tổng
        total = protein + carbs + fat
        if total == 0:
            total = 1  # Tránh chia 0
        
        # Màu sắc
        colors = ['#ff6b6b', '#4ecdc4', '#ffe66d']
        labels = ['Protein', 'Carbs', 'Fat']
        values = [protein, carbs, fat]
        
        center_x, center_y = size // 2, size // 2
        radius = (size - 20) // 2
        
        start_angle = 0
        
        # Vẽ từng phần
        for i, (value, color, label) in enumerate(zip(values, colors, labels)):
            if value > 0:
                extent = (value / total) * 360
                
                # Vẽ arc
                canvas.create_arc(
                    center_x - radius, center_y - radius,
                    center_x + radius, center_y + radius,
                    start=start_angle,
                    extent=extent,
                    fill=color,
                    outline='white',
                    width=1
                )
                
                start_angle += extent
        
        # Vẽ vòng tròn trắng ở giữa (donut chart)
        inner_radius = radius // 2
        canvas.create_oval(
            center_x - inner_radius, center_y - inner_radius,
            center_x + inner_radius, center_y + inner_radius,
            fill=config.COLORS['bg_medium'],
            outline=''
        )
        
        # Legend chỉ khi canvas đủ rộng (tránh chồng lên donut khi size nhỏ)
        if size >= 120:
            legend_y = 5
            for i, (value, color, label) in enumerate(zip(values, colors, labels)):
                canvas.create_rectangle(
                    5, legend_y + i*15, 15, legend_y + i*15 + 10,
                    fill=color, outline=''
                )
                canvas.create_text(
                    20, legend_y + i*15 + 5,
                    text=f"{label}: {value}g",
                    anchor=W, fill='white', font=('Arial', 7, 'bold')
                )
    
    def process_payment(self):
        """Xử lý thanh toán - hiển thị dialog và lưu hóa đơn"""
        # Tạo payment window
        payment_window = Toplevel(self.window)
        payment_window.title("💳 Thanh Toán")
        payment_window.geometry("400x350")
        payment_window.configure(bg=config.COLORS['bg_dark'])
        payment_window.transient(self.window)
        payment_window.grab_set()
        
        # Center payment window
        payment_window.update_idletasks()
        x = self.window.winfo_x() + (self.window.winfo_width() // 2) - 200
        y = self.window.winfo_y() + (self.window.winfo_height() // 2) - 175
        payment_window.geometry(f"400x350+{x}+{y}")
        
        # Header
        header_frame = Frame(payment_window, bg=config.COLORS['bg_header'])
        header_frame.pack(fill=X, padx=10, pady=10)
        
        Label(
            header_frame,
            text="💳 THANH TOÁN HÓA ĐƠN",
            font=("Arial", 14, "bold"),
            bg=config.COLORS['bg_header'],
            fg=config.COLORS['accent_green']
        ).pack(pady=10)
        
        # Summary frame
        summary_frame = Frame(payment_window, bg=config.COLORS['bg_medium'])
        summary_frame.pack(fill=X, padx=15, pady=10)
        
        # Tổng số món
        Label(
            summary_frame,
            text=f"🍽️ Số lượng: {len(self.detections)} món",
            font=("Arial", 11),
            bg=config.COLORS['bg_medium'],
            fg=config.COLORS['text_white']
        ).pack(pady=5, anchor=W)
        
        # Tổng giá
        Label(
            summary_frame,
            text=f"💰 Tổng tiền: {self.total_price:,} VND",
            font=("Arial", 12, "bold"),
            bg=config.COLORS['bg_medium'],
            fg=config.COLORS['accent_orange']
        ).pack(pady=5, anchor=W)
        
        # Tổng calories
        Label(
            summary_frame,
            text=f"🔥 Tổng calories: {self.total_calories:,} kcal",
            font=("Arial", 11),
            bg=config.COLORS['bg_medium'],
            fg=config.COLORS['accent_red']
        ).pack(pady=5, anchor=W)
        
        # Payment method frame
        method_frame = LabelFrame(
            payment_window,
            text="Phương Thức Thanh Toán",
            bg=config.COLORS['bg_medium'],
            fg=config.COLORS['accent_green'],
            font=("Arial", 10, "bold"),
            padx=10,
            pady=10
        )
        method_frame.pack(fill=X, padx=15, pady=10)
        
        payment_method = StringVar(value="cash")
        
        Radiobutton(
            method_frame,
            text="💵 Tiền Mặt",
            variable=payment_method,
            value="cash",
            bg=config.COLORS['bg_medium'],
            fg=config.COLORS['text_white'],
            selectcolor=config.COLORS['bg_medium'],
            activebackground=config.COLORS['bg_medium'],
            font=("Arial", 10)
        ).pack(anchor=W, pady=5)
        
        Radiobutton(
            method_frame,
            text="💳 Thẻ Tín Dụng/Ghi Nợ",
            variable=payment_method,
            value="card",
            bg=config.COLORS['bg_medium'],
            fg=config.COLORS['text_white'],
            selectcolor=config.COLORS['bg_medium'],
            activebackground=config.COLORS['bg_medium'],
            font=("Arial", 10)
        ).pack(anchor=W, pady=5)
        
        Radiobutton(
            method_frame,
            text="📱 Mobile Payment",
            variable=payment_method,
            value="mobile",
            bg=config.COLORS['bg_medium'],
            fg=config.COLORS['text_white'],
            selectcolor=config.COLORS['bg_medium'],
            activebackground=config.COLORS['bg_medium'],
            font=("Arial", 10)
        ).pack(anchor=W, pady=5)
        
        # Buttons frame
        button_frame = Frame(payment_window, bg=config.COLORS['bg_dark'])
        button_frame.pack(pady=20)
        
        def confirm_payment():
            """Xác nhận thanh toán và xuất hóa đơn"""
            method = payment_method.get()
            self.generate_invoice(method)
            payment_window.destroy()
            messagebox.showinfo(
                "Thành Công",
                f"✅ Thanh toán thành công!\n\n"
                f"Phương thức: {self.get_method_name(method)}\n"
                f"Số tiền: {self.total_price:,} VND\n\n"
                f"Hóa đơn đã được lưu ✓"
            )
        
        Button(
            button_frame,
            text="✅ XÁC NHẬN",
            bg=config.COLORS['accent_green'],
            fg='white',
            font=('Arial', 11, 'bold'),
            width=15,
            height=2,
            bd=0,
            cursor='hand2',
            command=confirm_payment
        ).pack(side=LEFT, padx=10)
        
        Button(
            button_frame,
            text="❌ HỦY",
            bg=config.COLORS['text_gray'],
            fg='white',
            font=('Arial', 11, 'bold'),
            width=15,
            height=2,
            bd=0,
            cursor='hand2',
            command=payment_window.destroy
        ).pack(side=LEFT, padx=10)
    
    def get_method_name(self, method):
        """Lấy tên phương thức thanh toán"""
        methods = {
            'cash': '💵 Tiền Mặt',
            'card': '💳 Thẻ Tín Dụng/Ghi Nợ',
            'mobile': '📱 Mobile Payment'
        }
        return methods.get(method, 'Không xác định')
    
    def generate_invoice(self, payment_method):
        """Xuất hóa đơn và lưu vào file"""
        # Tạo nội dung hóa đơn
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        invoice_content = self.create_invoice_content(payment_method, timestamp)
        
        # Tạo thư mục invoices nếu chưa có
        invoice_dir = "invoices"
        os.makedirs(invoice_dir, exist_ok=True)
        
        # Lưu hóa đơn dưới dạng text
        invoice_file = os.path.join(invoice_dir, f"invoice_{timestamp}.txt")
        with open(invoice_file, 'w', encoding='utf-8') as f:
            f.write(invoice_content)
        
        # Cũng lưu thông tin vào JSON để lưu lịch sử
        self.save_invoice_history(timestamp, payment_method)
    
    def create_invoice_content(self, payment_method, timestamp):
        """Tạo nội dung hóa đơn"""
        invoice_lines = []
        
        # Header
        invoice_lines.append("=" * 50)
        invoice_lines.append("        🍕 HÓA ĐƠN THANH TOÁN 🍕")
        invoice_lines.append("=" * 50)
        invoice_lines.append("")
        
        # Thông tin hóa đơn
        date_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        invoice_lines.append(f"Ngày: {date_time}")
        invoice_lines.append(f"Mã HĐ: INV_{timestamp}")
        invoice_lines.append("")
        
        # Chi tiết các món ăn
        invoice_lines.append("-" * 50)
        invoice_lines.append(f"{'Tên Món':<30} {'Giá':>10} {'kcal':>8}")
        invoice_lines.append("-" * 50)
        
        for detection in self.detections:
            food_info = self.get_food_info(detection)
            name = (food_info.get('name_vi') or detection['name'])[:28]
            price = food_info.get('price', 0)
            calories = food_info.get('calories', 0)
            invoice_lines.append(f"{name:<30} {price:>9,}đ {calories:>7} kcal")
        
        invoice_lines.append("-" * 50)
        
        # Tổng kết
        invoice_lines.append("")
        invoice_lines.append("📋 TỔNG KẾT:")
        invoice_lines.append(f"  • Số lượng: {len(self.detections)} món")
        invoice_lines.append(f"  • Tổng calories: {self.total_calories:,} kcal")
        invoice_lines.append("")
        invoice_lines.append(f"💰 TỔNG TIỀN: {self.total_price:,} VND")
        invoice_lines.append("")
        
        # Phương thức thanh toán
        invoice_lines.append(f"Phương thức: {self.get_method_name(payment_method)}")
        invoice_lines.append("")
        
        # Footer
        invoice_lines.append("=" * 50)
        invoice_lines.append("      Cảm ơn quý khách! Hẹn gặp lại 🎉")
        invoice_lines.append("=" * 50)
        
        return "\n".join(invoice_lines)
    
    def save_invoice_history(self, timestamp, payment_method):
        """Lưu thông tin hóa đơn vào file JSON"""
        history_file = "invoice_history.json"
        
        invoice_record = {
            "invoice_id": f"INV_{timestamp}",
            "timestamp": timestamp,
            "datetime": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "items": [
                {
                    "name": self.get_food_info(d).get('name_vi', d['name']),
                    "price": self.get_food_info(d).get('price', 0),
                    "calories": self.get_food_info(d).get('calories', 0),
                    "confidence": d['confidence'],
                }
                for d in self.detections
            ],
            "total_items": len(self.detections),
            "total_price": self.total_price,
            "total_calories": self.total_calories,
            "payment_method": self.get_method_name(payment_method)
        }
        
        # Đọc lịch sử cũ
        history = []
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except:
                history = []
        
        # Thêm hóa đơn mới
        history.append(invoice_record)
        
        # Lưu lại
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    
    def close(self):
        """Đóng màn hình kết quả"""
        if self.window and self.window.winfo_exists():
            self.window.destroy()
            self.window = None
    
    def go_back(self):
        """Trở về trang chính (gọi callback nếu có)"""
        if self.on_close_callback:
            self.on_close_callback()
        self.close()