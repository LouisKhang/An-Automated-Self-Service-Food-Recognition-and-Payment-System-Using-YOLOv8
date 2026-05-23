"""
Cửa sổ chính của ứng dụng Food Detection - Chỉ UI (kế thừa MainWindowLogic)
"""
import math
from tkinter import *
from tkinter import messagebox
import threading
import requests

import config
from image_utils import resize_image_to_canvas
from main_window_logic import MainWindowLogic

try:
    import qrcode
    from PIL import Image, ImageTk
    HAS_QR = True
except ImportError:
    HAS_QR = False


class MainWindow(MainWindowLogic):
    def __init__(self, root):
        self.root = root
        self.root.title("🍕 Food Detection AI - YOLOv8 (Multi-Image)")
        self.root.geometry(f"{config.WINDOW_WIDTH}x{config.WINDOW_HEIGHT}")
        self.root.configure(bg=config.COLORS['bg_dark'])

        self._init_logic()

        self.main_frame = None
        self.loading_frame = None
        self.result_frame = None
        self.payment_frame = None
        self.payment_success_frame = None
        self.history_frame = None

        self.setup_ui()

    # ===================== SETUP =====================

    def setup_ui(self):
        self.container = Frame(self.root, bg=config.COLORS['bg_dark'])
        self.container.pack(fill=BOTH, expand=True)

        self.create_main_screen()
        self.create_loading_screen()
        self.create_result_screen()
        self.create_payment_screen()
        self.create_payment_success_screen()

        self.show_screen("main")

    # ===================== MAIN SCREEN =====================

    def create_main_screen(self):
        self.main_frame = Frame(self.container, bg=config.COLORS['bg_dark'])
        self.main_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        # --- HEADER ---
        header_frame = Frame(self.main_frame, bg=config.COLORS['bg_header'], height=80)
        header_frame.pack(fill=X, padx=10, pady=10)

        Label(
            header_frame,
            text="🍕 FOOD DETECTION AI - MULTI IMAGE",
            font=("Arial", 26, "bold"),
            bg=config.COLORS['bg_header'],
            fg=config.COLORS['accent_green']
        ).pack(pady=15)

        self.btn_see_result = Button(
            header_frame,
            text="📊 Xem kết quả",
            bg=config.COLORS['accent_green'],
            fg='white',
            font=('Arial', 10, 'bold'),
            bd=0, padx=16, pady=6, cursor='hand2',
            command=lambda: self.show_screen("result")
        )
        self.btn_see_result.place(relx=1.0, rely=0.5, anchor=E, x=-10)
        self.btn_see_result.place_forget()

        self.btn_history = Button(
            header_frame,
            text="📜 Lịch sử",
            bg=config.COLORS['accent_blue'],
            fg='white',
            font=('Arial', 10, 'bold'),
            bd=0, padx=16, pady=6, cursor='hand2',
            command=lambda: self.show_screen("history")
        )
        self.btn_history.place(relx=1.0, rely=0.5, anchor=E, x=-10)

        # --- MAIN CONTAINER ---
        main_container = Frame(self.main_frame, bg=config.COLORS['bg_dark'])
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=5)

        # LEFT: Display Area
        left_frame = Frame(main_container, bg=config.COLORS['bg_medium'], bd=2, relief=SOLID)
        left_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))

        self.image_counter_label = Label(
            left_frame,
            text="📸 Chưa có ảnh",
            font=("Arial", 11, "bold"),
            bg=config.COLORS['bg_medium'],
            fg=config.COLORS['accent_green']
        )
        self.image_counter_label.pack(pady=5)

        self.canvas = Canvas(
            left_frame,
            bg=config.COLORS['bg_dark'],
            width=config.CANVAS_WIDTH,
            height=config.CANVAS_HEIGHT
        )
        self.canvas.pack(padx=10, pady=5)

        # Navigation
        nav_frame = Frame(left_frame, bg=config.COLORS['bg_medium'])
        nav_frame.pack(pady=5)

        self.btn_prev = Button(
            nav_frame, text="⬅️ TRƯỚC",
            bg=config.COLORS['text_gray'], fg='white',
            font=('Arial', 10, 'bold'), width=12,
            command=self.prev_image, state=DISABLED, cursor='hand2', bd=0
        )
        self.btn_prev.pack(side=LEFT, padx=5)

        self.btn_next = Button(
            nav_frame, text="SAU ➡️",
            bg=config.COLORS['text_gray'], fg='white',
            font=('Arial', 10, 'bold'), width=12,
            command=self.next_image, state=DISABLED, cursor='hand2', bd=0
        )
        self.btn_next.pack(side=LEFT, padx=5)

        # --- CONTROL BUTTONS ---
        control_frame = Frame(left_frame, bg=config.COLORS['bg_medium'])
        control_frame.pack(pady=10)

        btn_style = {'font': ('Arial', 11, 'bold'), 'width': 15, 'height': 2, 'bd': 0, 'cursor': 'hand2'}

        # Hàng 1: Upload | Detect (ảnh) | Reset
        self.btn_upload = Button(
            control_frame, text="📁 UPLOAD ẢNH",
            bg=config.COLORS['accent_purple'], fg='white',
            command=self.upload_images, **btn_style
        )
        self.btn_upload.grid(row=0, column=0, padx=5, pady=3)

        self.btn_detect = Button(
            control_frame, text="⚡ DETECT (ẢNH)",
            bg=config.COLORS['accent_red'], fg='white',
            command=self.detect_food, **btn_style
        )
        self.btn_detect.grid(row=0, column=1, padx=5, pady=3)

        self.btn_reset = Button(
            control_frame, text="🔄 RESET",
            bg=config.COLORS['text_gray'], fg='white',
            command=self.reset, **btn_style
        )
        self.btn_reset.grid(row=0, column=2, padx=5, pady=3)

        # Hàng 2: Camera | Chụp & Detect | Realtime | Checkout
        self.btn_camera = Button(
            control_frame, text="📷 BẬT CAMERA",
            bg=config.COLORS['accent_blue'], fg='white',
            command=self.toggle_camera, **btn_style
        )
        self.btn_camera.grid(row=1, column=0, padx=5, pady=3)

        self.btn_detect_camera = Button(
            control_frame, text="📸 Chụp & Detect",
            bg=config.COLORS['text_gray'], fg='white',
            command=self.detect_once_from_camera,
            state=DISABLED,
            **btn_style
        )
        self.btn_detect_camera.grid(row=1, column=1, padx=5, pady=3)

        self.btn_realtime = Button(
            control_frame, text="🔴 REALTIME DETECT",
            bg=config.COLORS['text_gray'], fg='white',
            command=self.toggle_realtime_detection,
            state=DISABLED,
            **btn_style
        )
        self.btn_realtime.grid(row=1, column=2, padx=5, pady=3)

        self.btn_checkout_camera = Button(
            control_frame, text="🛒 CHECKOUT",
            bg=config.COLORS['accent_green'], fg='white',
            command=self.checkout_camera, **btn_style
        )
        self.btn_checkout_camera.grid(row=1, column=3, padx=5, pady=3)
        self.btn_checkout_camera.grid_remove()

        # Hint label
        self.camera_hint_label = Label(
            left_frame,
            text="",
            font=("Arial", 9),
            bg=config.COLORS['bg_medium'],
            fg=config.COLORS['accent_blue'],
            wraplength=500
        )
        self.camera_hint_label.pack(pady=2)

        # MIDDLE: Settings & Current Results
        middle_frame = Frame(main_container, bg=config.COLORS['bg_medium'], width=300, bd=2, relief=SOLID)
        middle_frame.pack(side=LEFT, fill=Y, padx=5)
        middle_frame.pack_propagate(False)

        Label(
            middle_frame, text="⚙️ CÀI ĐẶT",
            font=("Arial", 14, "bold"),
            bg=config.COLORS['bg_medium'], fg=config.COLORS['accent_green']
        ).pack(pady=10)

        conf_frame = Frame(middle_frame, bg=config.COLORS['bg_medium'])
        conf_frame.pack(pady=10, padx=20, fill=X)

        self.conf_label = Label(
            conf_frame,
            text=f"Confidence: {self.confidence_threshold}",
            font=("Arial", 10),
            bg=config.COLORS['bg_medium'], fg='white'
        )
        self.conf_label.pack()

        self.confidence_slider = Scale(
            conf_frame,
            from_=config.MIN_CONFIDENCE, to=config.MAX_CONFIDENCE,
            resolution=0.05, orient=HORIZONTAL,
            bg=config.COLORS['bg_medium'], fg='white',
            troughcolor=config.COLORS['bg_dark'],
            highlightthickness=0,
            command=self.update_confidence
        )
        self.confidence_slider.set(self.confidence_threshold)
        self.confidence_slider.pack(fill=X)

        Label(
            middle_frame, text="📊 KẾT QUẢ HIỆN TẠI",
            font=("Arial", 14, "bold"),
            bg=config.COLORS['bg_medium'], fg=config.COLORS['accent_green']
        ).pack(pady=(20, 10))

        self.detected_items_label = Label(
            middle_frame,
            text="🛒 Chưa phát hiện món nào",
            font=("Arial", 10),
            bg=config.COLORS['bg_dark'], fg=config.COLORS['accent_blue'],
            wraplength=280, justify=LEFT, padx=10, pady=10
        )
        self.detected_items_label.pack(fill=X, padx=10, pady=5)

        results_container = Frame(middle_frame, bg=config.COLORS['bg_dark'])
        results_container.pack(fill=BOTH, expand=True, padx=10, pady=5)

        scrollbar = Scrollbar(results_container)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.results_text = Text(
            results_container,
            bg=config.COLORS['bg_dark'], fg='white',
            font=('Courier New', 9),
            yscrollcommand=scrollbar.set,
            wrap=WORD, bd=0, padx=10, pady=10
        )
        self.results_text.pack(fill=BOTH, expand=True)
        scrollbar.config(command=self.results_text.yview)

        # Status bar
        self.status_label = Label(
            self.main_frame,
            text=" Ready! Upload ảnh hoặc dùng camera để detect",
            font=("Arial", 10),
            bg=config.COLORS['bg_header'], fg=config.COLORS['accent_green'],
            anchor=W
        )
        self.status_label.pack(side=BOTTOM, fill=X)

    # ===================== LOADING SCREEN =====================

    def create_loading_screen(self):
        self.loading_frame = Frame(self.container, bg=config.COLORS['bg_dark'])
        self.loading_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        main_container = Frame(self.loading_frame, bg=config.COLORS['bg_dark'])
        main_container.pack(expand=True, fill=BOTH)

        Label(
            main_container, text="🍕 FOOD DETECTION AI",
            font=("Arial", 28, "bold"),
            bg=config.COLORS['bg_dark'], fg=config.COLORS['accent_green']
        ).pack(pady=40)

        self.loading_canvas = Canvas(
            main_container, width=200, height=200,
            bg=config.COLORS['bg_dark'], highlightthickness=0
        )
        self.loading_canvas.pack(pady=20)

        self.loading_message_label = Label(
            main_container, text="Đang xử lý...",
            font=("Arial", 16),
            bg=config.COLORS['bg_dark'], fg=config.COLORS['text_white']
        )
        self.loading_message_label.pack(pady=20)

        self.loading_progress_label = Label(
            main_container, text="⚡ Đang phân tích hình ảnh...",
            font=("Arial", 12),
            bg=config.COLORS['bg_dark'], fg=config.COLORS['accent_purple']
        )
        self.loading_progress_label.pack(pady=10)

    def animate_spinner(self):
        if not self.is_loading_active or self.current_screen != "loading":
            return

        self.loading_canvas.delete("all")
        center_x, center_y = 100, 100
        radius = 50
        num_dots = 8

        for i in range(num_dots):
            angle = (self.loading_angle + i * 45) % 360
            rad = math.radians(angle)
            x = center_x + radius * math.cos(rad)
            y = center_y + radius * math.sin(rad)
            intensity = int(255 * (i + 1) / num_dots)
            color = f'#{intensity:02x}{intensity//2:02x}88'
            self.loading_canvas.create_oval(x - 8, y - 8, x + 8, y + 8, fill=color, outline=color)

        self.loading_angle = (self.loading_angle + 10) % 360
        self.root.after(50, self.animate_spinner)

    # ===================== RESULT SCREEN =====================

    def create_result_screen(self):
        self.result_frame = Frame(self.container, bg=config.COLORS['bg_dark'])
        self.result_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        header_frame = Frame(self.result_frame, bg=config.COLORS['bg_header'], height=80)
        header_frame.pack(fill=X, padx=10, pady=10)
        header_frame.pack_propagate(False)

        Button(
            header_frame, text="← Trở về",
            bg=config.COLORS['accent_blue'], fg='white',
            font=('Arial', 10, 'bold'),
            command=lambda: self.show_screen("main"),
            cursor='hand2', bd=0, padx=20, pady=10
        ).pack(side=LEFT, padx=10)

        Label(
            header_frame, text="📊 Kết quả nhận diện",
            font=("Arial", 20, "bold"),
            bg=config.COLORS['bg_header'], fg=config.COLORS['accent_green']
        ).pack(side=LEFT, expand=True)

        Button(
            header_frame, text="🗑️ Hủy kết quả nhận diện này",
            bg=config.COLORS['accent_orange'], fg='white',
            font=('Arial', 10, 'bold'),
            cursor='hand2', bd=0, padx=16, pady=10,
            command=self.cancel_result
        ).pack(side=RIGHT, padx=10)

        main_container = Frame(self.result_frame, bg=config.COLORS['bg_dark'])
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=5)

        self.result_canvas = Canvas(main_container, bg=config.COLORS['bg_dark'], highlightthickness=0)
        scrollbar = Scrollbar(main_container, orient="vertical", command=self.result_canvas.yview)
        self.result_scrollable_frame = Frame(self.result_canvas, bg=config.COLORS['bg_dark'])

        self.result_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.result_canvas.configure(scrollregion=self.result_canvas.bbox("all"))
        )
        self.result_canvas_window = self.result_canvas.create_window(
            (0, 0), window=self.result_scrollable_frame, anchor="nw"
        )
        self.result_canvas.configure(yscrollcommand=scrollbar.set)
        self.result_canvas.bind("<Configure>", self._on_result_canvas_configure)
        self.result_canvas.bind(
            "<MouseWheel>",
            lambda ev: self.result_canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units")
        )

        self.result_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

    def _on_result_canvas_configure(self, event):
        self.result_canvas.itemconfig(self.result_canvas_window, width=event.width)

    def display_result_screen(self):
        for widget in self.result_scrollable_frame.winfo_children():
            widget.destroy()
        self._result_image_refs = []

        if not self.current_detections:
            Label(
                self.result_scrollable_frame,
                text="❌ Không phát hiện món ăn nào!",
                font=("Arial", 14),
                bg=config.COLORS['bg_dark'], fg=config.COLORS['accent_red']
            ).pack(pady=20)
            return

        displayed_count = 0
        for detection in self.current_detections:
            class_name = detection['name']
            confidence = detection['confidence']
            food_key = self.normalize_food_key(class_name)
            food_info = self.food_data.get(food_key, {})

            if not food_info:
                food_info = {
                    'name_vi': class_name, 'price': 0, 'calories': 0,
                    'protein': 0, 'carbs': 0, 'fat': 0,
                    'description': f'Phát hiện: {class_name}'
                }

            displayed_count += 1

            food_frame = Frame(self.result_scrollable_frame, bg=config.COLORS['bg_medium'], bd=2, relief=SOLID)
            food_frame.pack(fill=X, padx=10, pady=10)

            header_frame = Frame(food_frame, bg=config.COLORS['bg_header'])
            header_frame.pack(fill=X, padx=10, pady=10)

            Label(
                header_frame,
                text=f"#{displayed_count} {food_info.get('name_vi', food_key)}",
                font=("Arial", 14, "bold"),
                bg=config.COLORS['bg_header'], fg=config.COLORS['accent_green']
            ).pack(side=LEFT)

            Label(
                header_frame,
                text=f"Confidence: {confidence:.1%}",
                font=("Arial", 10),
                bg=config.COLORS['bg_header'], fg='white'
            ).pack(side=RIGHT)

            content_frame = Frame(food_frame, bg=config.COLORS['bg_dark'])
            content_frame.pack(fill=X, padx=10, pady=10)

            preview_frame = Frame(content_frame, bg=config.COLORS['bg_dark'], width=400, height=300)
            preview_frame.pack_propagate(False)
            preview_frame.pack(side=LEFT, padx=(0, 20), pady=5)

            details_frame = Frame(content_frame, bg=config.COLORS['bg_dark'])
            details_frame.pack(side=LEFT, fill=BOTH, expand=True, pady=5)

            chart_frame = Frame(content_frame, bg=config.COLORS['bg_dark'])
            chart_frame.pack(side=RIGHT, padx=10, pady=5)

            if detection.get("crop_image") is not None:
                try:
                    img_tk, _, _ = resize_image_to_canvas(detection["crop_image"], 290, 220)
                    img_label = Label(preview_frame, image=img_tk, bg=config.COLORS['bg_dark'])
                    img_label.image = img_tk  # strong reference trên widget
                    img_label.pack(fill=BOTH, expand=True)
                    self._result_image_refs.append(img_tk)  # backup reference
                except Exception as e:
                    print(f"❌ Lỗi tạo thumbnail detection: {e}")
            else:
                Label(
                    preview_frame,
                    text="📷 Camera Realtime",
                    font=("Arial", 12),
                    bg=config.COLORS['bg_dark'],
                    fg=config.COLORS['text_gray']
                ).pack(expand=True)

            description = food_info.get('description', 'Không có mô tả')
            if detection.get('source_image'):
                description = f"📍 Nguồn: {detection['source_image']}\n" + description

            Label(
                details_frame,
                text=f"📝 {description}",
                font=("Arial", 10),
                bg=config.COLORS['bg_dark'], fg='white',
                wraplength=520, justify=LEFT
            ).pack(anchor=W, pady=5)

            left_frame = Frame(details_frame, bg=config.COLORS['bg_dark'])
            left_frame.pack(fill=BOTH, expand=True)

            nutrition_frame = Frame(left_frame, bg=config.COLORS['bg_dark'])
            nutrition_frame.pack(fill=X, pady=5)

            nutrition_data = [
                (f"💰 Giá: {food_info.get('price', 0):,} VNĐ", config.COLORS['accent_green']),
                (f"🔥 Calo: {food_info.get('calories', 0)} kcal", config.COLORS['accent_red']),
                (f"🥩 Protein: {food_info.get('protein', 0)}g", config.COLORS['accent_blue']),
                (f"🍚 Carbs: {food_info.get('carbs', 0)}g", config.COLORS['accent_purple']),
                (f"🥛 Fat: {food_info.get('fat', 0)}g", config.COLORS['accent_orange']),
            ]
            for text, color in nutrition_data:
                Label(
                    nutrition_frame, text=text,
                    font=("Arial", 9),
                    bg=config.COLORS['bg_dark'], fg=color
                ).pack(anchor=W)

            self.draw_nutrition_chart(
                chart_frame,
                food_info.get('protein', 0),
                food_info.get('carbs', 0),
                food_info.get('fat', 0)
            )

        # Summary
        total_items, total_price_cart, total_calories_cart = self._get_cart_totals()
        summary_frame = Frame(self.result_scrollable_frame, bg=config.COLORS['bg_header'], bd=2, relief=SOLID)
        summary_frame.pack(fill=X, padx=10, pady=10)

        Label(
            summary_frame, text="📊 TỔNG KẾT (GIỎ HÀNG)",
            font=("Arial", 14, "bold"),
            bg=config.COLORS['bg_header'], fg=config.COLORS['accent_green']
        ).pack(pady=10)

        for text in [
            f"🍽️  Tổng số phần: {total_items}",
            f"💰 Tổng giá tiền: {total_price_cart:,} VNĐ",
            f"🔥 Tổng calo: {total_calories_cart} kcal"
        ]:
            Label(
                summary_frame, text=text,
                font=("Arial", 11),
                bg=config.COLORS['bg_header'], fg='white'
            ).pack(anchor=W, padx=20, pady=5)

        # Cart table
        if self.cart:
            cart_frame = Frame(self.result_scrollable_frame, bg=config.COLORS['bg_dark'])
            cart_frame.pack(fill=X, padx=10, pady=(0, 16))

            header = Frame(cart_frame, bg=config.COLORS['bg_dark'])
            header.pack(fill=X, pady=(0, 4))
            cols = ["Món ăn", "SL", "Giá", "Thành tiền", "Conf"]
            widths = [30, 5, 10, 18, 8]
            for i, (c, w) in enumerate(zip(cols, widths)):
                Label(
                    header, text=c,
                    font=("Arial", 10, "bold"),
                    bg=config.COLORS['bg_dark'], fg=config.COLORS['accent_green'],
                    width=w, anchor=W
                ).grid(row=0, column=i, padx=4)

            for row_idx, item in enumerate(self.cart.values(), start=1):
                row = Frame(cart_frame, bg=config.COLORS['bg_medium'])
                row.pack(fill=X, pady=2)

                name = item["name_vi"]
                qty = int(item["quantity"])
                price = item["price"]
                total_line = price * qty
                conf = item.get("avg_conf", 0)
                excluded = bool(item.get("excluded", False))

                Label(row, text=name, font=("Arial", 10), bg=config.COLORS['bg_medium'],
                      fg='white', width=30, anchor=W).grid(row=0, column=0, padx=4, pady=2, sticky=W)

                Label(row, text=str(qty), width=5,
                      bg=config.COLORS['bg_medium'], fg='white').grid(row=0, column=1, padx=4)

                Label(row, text=f"{price:,}đ", font=("Arial", 10),
                      bg=config.COLORS['bg_medium'], fg=config.COLORS['accent_orange'],
                      width=10, anchor=E).grid(row=0, column=2, padx=4)

                total_text = f"{total_line:,}đ"
                total_fg = config.COLORS['accent_green']
                if excluded:
                    total_text += " (Không thanh toán)"
                    total_fg = config.COLORS['text_gray']
                Label(row, text=total_text, font=("Arial", 10, "bold"),
                      bg=config.COLORS['bg_medium'], fg=total_fg,
                      width=18, anchor=E).grid(row=0, column=3, padx=4)

                Label(row, text=f"{conf:.0%}", font=("Arial", 10),
                      bg=config.COLORS['bg_medium'], fg='white',
                      width=8, anchor=E).grid(row=0, column=4, padx=4)

        # Pay button
        btn_pay_frame = Frame(self.result_scrollable_frame, bg=config.COLORS['bg_dark'])
        btn_pay_frame.pack(fill=X, padx=10, pady=16)
        Button(
            btn_pay_frame, text="💳 THANH TOÁN",
            bg=config.COLORS['accent_green'], fg='white',
            font=('Arial', 12, 'bold'), width=20, height=2, bd=0, cursor='hand2',
            command=self.show_payment_dialog
        ).pack(pady=8)

    # ===================== PAYMENT SCREEN =====================

    def create_payment_screen(self):
        self.payment_frame = Frame(self.container, bg=config.COLORS['bg_dark'])
        self.payment_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        header_frame = Frame(self.payment_frame, bg=config.COLORS['bg_header'], height=80)
        header_frame.pack(fill=X, padx=10, pady=10)
        header_frame.pack_propagate(False)

        Button(
            header_frame, text="← Hủy thanh toán",
            bg=config.COLORS['accent_red'], fg='white',
            font=('Arial', 10, 'bold'),
            command=lambda: self.show_screen("result"),
            cursor='hand2', bd=0, padx=20, pady=10
        ).pack(side=LEFT, padx=10)

        Label(
            header_frame, text="💳 Thanh toán",
            font=("Arial", 20, "bold"),
            bg=config.COLORS['bg_header'], fg=config.COLORS['accent_green']
        ).pack(side=LEFT, expand=True)

        main_container = Frame(self.payment_frame, bg=config.COLORS['bg_dark'])
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=5)

        payment_canvas = Canvas(main_container, bg=config.COLORS['bg_dark'], highlightthickness=0)
        payment_scrollbar = Scrollbar(main_container, orient="vertical", command=payment_canvas.yview)
        payment_scrollable_frame = Frame(payment_canvas, bg=config.COLORS['bg_dark'])

        payment_scrollable_frame.bind(
            "<Configure>",
            lambda e: payment_canvas.configure(scrollregion=payment_canvas.bbox("all"))
        )
        payment_canvas_window = payment_canvas.create_window(
            (0, 0), window=payment_scrollable_frame, anchor="nw"
        )
        payment_canvas.configure(yscrollcommand=payment_scrollbar.set)
        payment_canvas.bind("<Configure>",
            lambda e: payment_canvas.itemconfig(payment_canvas_window, width=e.width))
        payment_canvas.bind("<MouseWheel>",
            lambda ev: payment_canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"))

        payment_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        payment_scrollbar.pack(side=RIGHT, fill=Y)

        self.payment_scrollable_frame = payment_scrollable_frame
        self.payment_canvas = payment_canvas

    def display_payment_screen(self):
        for widget in self.payment_scrollable_frame.winfo_children():
            widget.destroy()

        total = getattr(self, '_result_total_price', 0)
        total_cal = getattr(self, '_result_total_calories', 0)

        f_top = Frame(self.payment_scrollable_frame, bg=config.COLORS['bg_header'], padx=16, pady=12)
        f_top.pack(fill=X, padx=10, pady=10)
        Label(f_top, text="💳 THANH TOÁN HÓA ĐƠN",
              font=("Arial", 14, "bold"), bg=config.COLORS['bg_header'],
              fg=config.COLORS['accent_green']).pack(anchor=W)
        Label(f_top, text=f"💰 Tổng tiền: {total:,} VNĐ",
              font=("Arial", 12, "bold"), bg=config.COLORS['bg_header'],
              fg=config.COLORS['accent_orange']).pack(anchor=W, pady=4)
        Label(f_top, text=f"🔥 Tổng calo: {total_cal:,} kcal",
              font=("Arial", 10), bg=config.COLORS['bg_header'], fg='white').pack(anchor=W)

        method_var = StringVar(value="cash")
        methods = [
            ("cash",    "💵 Tiền mặt (thanh toán khi nhận)"),
            ("momo",    "📱 Momo"),
            ("zalopay", "📱 ZaloPay"),
            ("vietqr",  "🏦 VietQR (quét mã chuyển khoản)"),
        ]
        f_method = LabelFrame(
            self.payment_scrollable_frame,
            text="Chọn hình thức thanh toán",
            bg=config.COLORS['bg_medium'], fg=config.COLORS['accent_green'],
            font=("Arial", 10, "bold"), padx=10, pady=8
        )
        f_method.pack(fill=X, padx=16, pady=10)
        for val, label in methods:
            Radiobutton(
                f_method, text=label, variable=method_var, value=val,
                bg=config.COLORS['bg_medium'], fg='white',
                selectcolor=config.COLORS['bg_dark'],
                activebackground=config.COLORS['bg_medium'],
                font=("Arial", 10), command=lambda: None
            ).pack(anchor=W, pady=4)

        f_qr = Frame(self.payment_scrollable_frame, bg=config.COLORS['bg_dark'], pady=12)
        f_qr.pack(fill=X, padx=16)
        qr_label = Label(f_qr, text="Chọn hình thức thanh toán ở trên",
                         font=("Arial", 10), bg=config.COLORS['bg_dark'],
                         fg=config.COLORS['text_gray'])
        qr_label.pack(pady=8)

        def update_info():
            m = method_var.get()
            qr_label.config(text="Chọn hình thức thanh toán ở trên")
            for w in f_qr.winfo_children():
                if w != qr_label:
                    w.destroy()
            if m == "cash":
                qr_label.config(text="💵 Thanh toán khi nhận hàng. Không cần quét mã.")
            elif m == "vietqr":
                qr_label.config(
                    text="🏦 VietQR - Quét mã QR bằng ứng dụng ngân hàng\n\n"
                         "📱 Bấm 'XÁC NHẬN ĐÃ THANH TOÁN' → Hệ thống tạo QR từ SePay\n"
                         "📲 Quét QR bằng app Techcombank/MB/v.v.\n"
                         "✅ App sẽ tự xác nhận khi giao dịch thành công"
                )
            else:
                method_display = {"momo": "Momo", "zalopay": "ZaloPay"}.get(m, m)
                qr_label.config(
                    text=f"💳 {method_display}\n\nBấm 'XÁC NHẬN ĐÃ THANH TOÁN' để tiếp tục"
                )

        method_var.trace_add("write", lambda *a: update_info())
        update_info()

        def on_confirm():
            method = method_var.get()
            name_map = {"cash": "Tiền mặt", "momo": "Momo", "zalopay": "ZaloPay", "vietqr": "VietQR"}
            method_name = name_map.get(method, method)

            if method == "vietqr":
                if not config.SEPAY_API_KEY:
                    messagebox.showerror(
                        "Chưa cấu hình",
                        "Chưa điền SEPAY_API_KEY trong config.py\n\n"
                        "Vui lòng đăng ký tài khoản SePay"
                    )
                    return

                total_price = self._result_total_price

                try:
                    backend_url = config.SEPAY_BACKEND_URL
                    resp = requests.post(
                        f"{backend_url}/api/create-order",
                        json={"amount": total_price, "description": "Food Order"},
                        timeout=10
                    )
                    result = resp.json()
                except requests.exceptions.ConnectionError:
                    messagebox.showerror("Lỗi kết nối",
                        "Không thể kết nối đến SePay Backend.\n\n"
                        "Hãy chạy: python app/sepay_backend.py")
                    return
                except Exception as e:
                    messagebox.showerror("Lỗi", f"Lỗi tạo đơn hàng: {str(e)}")
                    return

                if not result.get('success'):
                    messagebox.showerror("Lỗi", f"Không tạo được đơn hàng: {result.get('error')}")
                    return

                order_id = result.get('order_id')
                qr_code = result.get('qr_code')

                if qr_code and HAS_QR:
                    try:
                        import qrcode as qrcode_lib
                        import base64, io, urllib.request, tempfile
                        from PIL import Image, ImageTk

                        img = None
                        if qr_code.startswith('data:image'):
                            header, encoded = qr_code.split(',', 1)
                            image_data = base64.b64decode(encoded)
                            img = Image.open(io.BytesIO(image_data))
                        elif qr_code.startswith('http'):
                            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                                qr_image_path = tmp.name
                            urllib.request.urlretrieve(qr_code, qr_image_path)
                            img = Image.open(qr_image_path)
                        else:
                            qr_img = qrcode_lib.QRCode(version=1, box_size=10, border=4)
                            qr_img.add_data(qr_code)
                            qr_img.make(fit=True)
                            img = qr_img.make_image(fill_color='black', back_color='white')

                        img = img.resize((400, 400)) if img.size[0] != 400 else img

                        qr_win = Toplevel(self.root)
                        qr_win.title("Quét mã QR Thanh toán VietQR")
                        qr_win.geometry("500x650")
                        qr_win.resizable(False, False)
                        #  gọi cancle giao dịch sepay
                        def on_qr_close():
                            self._payment_polling_active = False
                            try:
                                backend_url = config.SEPAY_BACKEND_URL
                                requests.post(
                                    f"{backend_url}/api/cancel-order/{order_id}",
                                    timeout=5
                                )
                            except Exception:
                                pass
                            qr_win.destroy()
                            self.show_screen("payment")
                            self.display_payment_screen()

                        qr_win.protocol("WM_DELETE_WINDOW", on_qr_close)

                        Label(qr_win, text="📱 Quét mã QR bằng ứng dụng ngân hàng",
                              font=("Arial", 12, "bold"), bg=config.COLORS['bg_header'],
                              fg=config.COLORS['accent_green']).pack(fill=X, padx=10, pady=10)
                        Label(qr_win, text="💳 MB Bank (Techcombank)",
                              font=("Arial", 10), bg=config.COLORS['bg_header'], fg='white').pack()
                        Label(qr_win, text=f"Số tiền: {total_price:,} VNĐ",
                              font=("Arial", 11, "bold"), fg=config.COLORS['accent_orange']).pack(pady=5)
                        Label(qr_win, text=f"Nội dung: OD{order_id}",
                              font=("Arial", 9), fg=config.COLORS['text_gray']).pack(pady=2)

                        photo = ImageTk.PhotoImage(img)
                        qr_label_img = Label(qr_win, image=photo, bg="white")
                        qr_label_img.image = photo  # strong reference
                        qr_label_img.pack(pady=10)

                        Label(qr_win, text="Đang chờ xác nhận giao dịch từ ngân hàng...",
                              font=("Arial", 10), fg=config.COLORS['text_gray']).pack(pady=10)
                        Label(qr_win, text="⏳", font=("Arial", 16)).pack(pady=5)

                        qr_win.update()
                    except Exception as e:
                        print(f"❌ Lỗi hiển thị QR: {e}")
                        messagebox.showwarning("Chú ý",
                            f"Không thể hiển thị QR: {e}\nNhưng đơn hàng đã được tạo.")

                def start_polling():
                    def on_payment_success():
                        if self.current_session:
                            self.current_session["status"] = "paid"
                        self._last_payment_method = method_name
                        self._last_invoice_path = None
                        self.show_screen("payment_success")

                    result_poll = self.poll_payment_status(
                        order_id, on_success_callback=on_payment_success, max_wait=120
                    )
                    if result_poll is False:
                        self.root.after(0, lambda: self.show_screen("payment"))
                    elif result_poll is None:
                        self.root.after(0, lambda: self.show_screen("payment"))

                self._payment_polling_active = True
                poll_thread = threading.Thread(target=start_polling, daemon=True)
                poll_thread.start()

                self.show_screen("loading")
                self.loading_message_label.config(text="Chờ xác nhận thanh toán...")
                self.loading_progress_label.config(text="⏳ Không đóng ứng dụng")

            else:
                if self.current_session:
                    self.current_session["status"] = "paid"
                self._last_payment_method = method_name
                self._last_invoice_path = None
                messagebox.showinfo("Thanh toán thành công",
                    f"Thanh toán bằng {method_name} đã được xác nhận.")
                self.show_screen("payment_success")

        btn_frame = Frame(self.payment_scrollable_frame, bg=config.COLORS['bg_dark'])
        btn_frame.pack(fill=X, padx=16, pady=16)
        Button(
            btn_frame, text="✅ XÁC NHẬN ĐÃ THANH TOÁN",
            bg=config.COLORS['accent_green'], fg='white',
            font=('Arial', 11, 'bold'), width=28, height=2, bd=0, cursor='hand2',
            command=on_confirm
        ).pack(pady=8)

    # ===================== PAYMENT SUCCESS SCREEN =====================

    def create_payment_success_screen(self):
        self.payment_success_frame = Frame(self.container, bg=config.COLORS['bg_dark'])
        self.payment_success_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        header_frame = Frame(self.payment_success_frame, bg=config.COLORS['bg_header'], height=80)
        header_frame.pack(fill=X, padx=10, pady=10)
        header_frame.pack_propagate(False)

        Label(
            header_frame, text="✅ Thanh toán thành công",
            font=("Arial", 20, "bold"),
            bg=config.COLORS['bg_header'], fg=config.COLORS['accent_green']
        ).pack(expand=True)

        main_container = Frame(self.payment_success_frame, bg=config.COLORS['bg_dark'])
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=5)

        success_canvas = Canvas(main_container, bg=config.COLORS['bg_dark'], highlightthickness=0)
        success_scrollbar = Scrollbar(main_container, orient="vertical", command=success_canvas.yview)
        success_scrollable_frame = Frame(success_canvas, bg=config.COLORS['bg_dark'])

        success_scrollable_frame.bind(
            "<Configure>",
            lambda e: success_canvas.configure(scrollregion=success_canvas.bbox("all"))
        )
        success_canvas_window = success_canvas.create_window(
            (0, 0), window=success_scrollable_frame, anchor="nw"
        )
        success_canvas.configure(yscrollcommand=success_scrollbar.set)
        success_canvas.bind("<Configure>",
            lambda e: success_canvas.itemconfig(success_canvas_window, width=e.width))
        success_canvas.bind("<MouseWheel>",
            lambda ev: success_canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"))

        success_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        success_scrollbar.pack(side=RIGHT, fill=Y)

        self.payment_success_scrollable_frame = success_scrollable_frame

    def display_payment_success_screen(self):
        for widget in self.payment_success_scrollable_frame.winfo_children():
            widget.destroy()

        payment_method = getattr(self, '_last_payment_method', 'Tiền mặt')

        success_header = Frame(
            self.payment_success_scrollable_frame,
            bg=config.COLORS['bg_header'], padx=20, pady=20
        )
        success_header.pack(fill=X, padx=10, pady=10)

        Label(success_header, text="✅ THANH TOÁN THÀNH CÔNG",
              font=("Arial", 18, "bold"), bg=config.COLORS['bg_header'],
              fg=config.COLORS['accent_green']).pack(pady=10)
        Label(success_header, text=f"Phương thức: {payment_method}",
              font=("Arial", 12), bg=config.COLORS['bg_header'], fg='white').pack()

        invoice_frame = Frame(self.payment_success_scrollable_frame, bg='white', padx=20, pady=20)
        invoice_frame.pack(fill=X, padx=20, pady=10)

        invoice_text = self._generate_invoice_text()
        Label(
            invoice_frame, text=invoice_text,
            font=("Courier New", 10), bg='white', fg='black',
            justify=LEFT, anchor=NW
        ).pack(fill=BOTH, expand=True)

        action_frame = Frame(self.payment_success_scrollable_frame,
                             bg=config.COLORS['bg_dark'], padx=20, pady=20)
        action_frame.pack(fill=X, padx=10, pady=10)

        def export_invoice():
            path = self.payment_handler.save_invoice_to_downloads(
                self.cart, self.current_detections, payment_method
            )
            self._last_invoice_path = path
            messagebox.showinfo("Thành công", f"Đã xuất hóa đơn:\n{path}")
            self._end_session()

        def skip_invoice():
            self._end_session()

        Button(
            action_frame, text="📄 XUẤT HÓA ĐƠN",
            bg=config.COLORS['accent_green'], fg='white',
            font=('Arial', 11, 'bold'), width=20, height=2, bd=0, cursor='hand2',
            command=export_invoice
        ).pack(side=LEFT, padx=10, pady=10)

        Button(
            action_frame, text="❌ KHÔNG XUẤT HÓA ĐƠN",
            bg=config.COLORS['accent_red'], fg='white',
            font=('Arial', 11, 'bold'), width=20, height=2, bd=0, cursor='hand2',
            command=skip_invoice
        ).pack(side=RIGHT, padx=10, pady=10)

    # ===================== HISTORY SCREEN =====================

    def create_history_screen(self):
        self.history_frame = Frame(self.container, bg=config.COLORS['bg_dark'])
        self.history_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        header_frame = Frame(self.history_frame, bg=config.COLORS['bg_header'], height=80)
        header_frame.pack(fill=X, padx=10, pady=10)
        header_frame.pack_propagate(False)

        Button(
            header_frame, text="← Trở về",
            bg=config.COLORS['accent_blue'], fg='white',
            font=('Arial', 10, 'bold'),
            command=lambda: self.show_screen("main"),
            cursor='hand2', bd=0, padx=20, pady=10
        ).pack(side=LEFT, padx=10)

        Label(
            header_frame, text="📜 Lịch sử nhận diện",
            font=("Arial", 20, "bold"),
            bg=config.COLORS['bg_header'], fg=config.COLORS['accent_green']
        ).pack(side=LEFT, expand=True)

        main_container = Frame(self.history_frame, bg=config.COLORS['bg_dark'])
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=5)

        history_canvas = Canvas(main_container, bg=config.COLORS['bg_dark'], highlightthickness=0)
        history_scrollbar = Scrollbar(main_container, orient="vertical", command=history_canvas.yview)
        history_scrollable_frame = Frame(history_canvas, bg=config.COLORS['bg_dark'])

        history_scrollable_frame.bind(
            "<Configure>",
            lambda e: history_canvas.configure(scrollregion=history_canvas.bbox("all"))
        )
        history_canvas_window = history_canvas.create_window(
            (0, 0), window=history_scrollable_frame, anchor="nw"
        )
        history_canvas.configure(yscrollcommand=history_scrollbar.set)
        history_canvas.bind("<Configure>",
            lambda e: history_canvas.itemconfig(history_canvas_window, width=e.width))
        history_canvas.bind("<MouseWheel>",
            lambda ev: history_canvas.yview_scroll(int(-1 * (ev.delta / 120)), "units"))

        history_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        history_scrollbar.pack(side=RIGHT, fill=Y)

        self.history_scrollable_frame = history_scrollable_frame
        self.history_canvas = history_canvas

    def display_history_screen(self):
        for widget in self.history_scrollable_frame.winfo_children():
            widget.destroy()

        self.history_current_page = 0
        history_data = self.history_manager.get_history()
        total_records = len(history_data)

        if total_records == 0:
            Label(
                self.history_scrollable_frame,
                text="📜 Chưa có lịch sử nhận diện nào",
                font=("Arial", 14),
                bg=config.COLORS['bg_dark'], fg=config.COLORS['text_gray']
            ).pack(pady=40)
            return

        total_pages = (total_records + self.history_items_per_page - 1) // self.history_items_per_page
        start_idx = self.history_current_page * self.history_items_per_page
        end_idx = min(start_idx + self.history_items_per_page, total_records)
        current_page_data = history_data[start_idx:end_idx]

        stats_frame = Frame(self.history_scrollable_frame, bg=config.COLORS['bg_header'], padx=20, pady=16)
        stats_frame.pack(fill=X, pady=(0, 16))

        Label(
            stats_frame,
            text=f"📊 Tổng số phiên: {total_records} | Trang {self.history_current_page + 1}/{total_pages}",
            font=("Arial", 14, "bold"),
            bg=config.COLORS['bg_header'], fg=config.COLORS['accent_green']
        ).pack(anchor=W)

        pagination_frame = Frame(stats_frame, bg=config.COLORS['bg_header'])
        pagination_frame.pack(fill=X, pady=(10, 0))

        Button(
            pagination_frame, text="⬅️ Trước",
            bg=config.COLORS['accent_blue'], fg='white',
            font=('Arial', 10, 'bold'),
            command=self.history_prev_page,
            state=NORMAL if self.history_current_page > 0 else DISABLED,
            cursor='hand2' if self.history_current_page > 0 else '',
            bd=0, padx=16, pady=8
        ).pack(side=LEFT, padx=(0, 10))

        Label(
            pagination_frame,
            text=f"{start_idx + 1}-{end_idx} / {total_records}",
            font=("Arial", 10),
            bg=config.COLORS['bg_header'], fg='white'
        ).pack(side=LEFT, expand=True)

        Button(
            pagination_frame, text="Sau ➡️",
            bg=config.COLORS['accent_blue'], fg='white',
            font=('Arial', 10, 'bold'),
            command=self.history_next_page,
            state=NORMAL if self.history_current_page < total_pages - 1 else DISABLED,
            cursor='hand2' if self.history_current_page < total_pages - 1 else '',
            bd=0, padx=16, pady=8
        ).pack(side=RIGHT)

        button_frame = Frame(stats_frame, bg=config.COLORS['bg_header'])
        button_frame.pack(fill=X, pady=(10, 0))

        Button(
            button_frame, text="💾 Xuất lịch sử",
            bg=config.COLORS['accent_blue'], fg='white',
            font=('Arial', 10, 'bold'),
            command=self.export_history,
            cursor='hand2', bd=0, padx=16, pady=8
        ).pack(side=LEFT, padx=(0, 10))

        Button(
            button_frame, text="🗑️ Xóa tất cả",
            bg=config.COLORS['accent_orange'], fg='white',
            font=('Arial', 10, 'bold'),
            command=self.clear_history,
            cursor='hand2', bd=0, padx=16, pady=8
        ).pack(side=LEFT)

        for i, record in enumerate(current_page_data):
            global_idx = start_idx + i + 1

            item_frame = Frame(
                self.history_scrollable_frame,
                bg=config.COLORS['bg_medium'], bd=2, relief=SOLID
            )
            item_frame.pack(fill=X, padx=10, pady=5)

            header = Frame(item_frame, bg=config.COLORS['bg_header'])
            header.pack(fill=X, padx=10, pady=8)

            timestamp = record.get('timestamp', 'Unknown')
            source = record.get('source', 'unknown')
            detections = record.get('items', record.get('detections', []))

            Label(
                header,
                text=f"#{global_idx} - {timestamp}",
                font=("Arial", 12, "bold"),
                bg=config.COLORS['bg_header'], fg=config.COLORS['accent_green']
            ).pack(side=LEFT)

            Label(
                header,
                text=f"📷 {source.upper()}",
                font=("Arial", 10),
                bg=config.COLORS['bg_header'], fg=config.COLORS['accent_blue']
            ).pack(side=RIGHT)

            content = Frame(item_frame, bg=config.COLORS['bg_medium'])
            content.pack(fill=X, padx=10, pady=8)

            if detections:
                total_items = len(detections)
                total_price = sum(
                    self.food_data.get(self.normalize_food_key(d['name']), {}).get('price', 0)
                    for d in detections
                )
                Label(
                    content,
                    text=f"🍽️ Phát hiện: {total_items} món | 💰 Tổng: {total_price:,}đ",
                    font=("Arial", 10),
                    bg=config.COLORS['bg_medium'], fg='white'
                ).pack(anchor=W, pady=(0, 5))

                detections_text = "📋 Chi tiết: "
                for j, det in enumerate(detections[:8]):
                    name = det.get('name', 'Unknown')
                    conf = det.get('confidence', 0)
                    detections_text += f"{name}({conf:.0%})"
                    if j < len(detections) - 1 and j < 7:
                        detections_text += ", "
                if len(detections) > 8:
                    detections_text += f"... (+{len(detections) - 8} món)"

                Label(
                    content, text=detections_text,
                    font=("Arial", 9),
                    bg=config.COLORS['bg_medium'], fg=config.COLORS['text_gray'],
                    wraplength=1000, justify=LEFT
                ).pack(anchor=W)
            else:
                Label(
                    content, text="❌ Không phát hiện món nào",
                    font=("Arial", 10),
                    bg=config.COLORS['bg_medium'], fg=config.COLORS['text_gray']
                ).pack(anchor=W)

    # ===================== SCREEN SWITCHER =====================

    def show_screen(self, screen_name):
        self.current_screen = screen_name

        self.main_frame.place_forget()
        self.loading_frame.place_forget()
        self.result_frame.place_forget()
        if self.payment_frame:
            self.payment_frame.place_forget()
        if self.payment_success_frame:
            self.payment_success_frame.place_forget()
        if self.history_frame:
            self.history_frame.place_forget()

        if screen_name == "main":
            self.main_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.is_loading_active = False
            self.update_result_button_visibility()
        elif screen_name == "loading":
            self.loading_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.is_loading_active = True
            self.animate_spinner()
        elif screen_name == "result":
            self.result_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.result_frame.update_idletasks()
            self.result_canvas.update_idletasks()
            canvas_width = self.result_canvas.winfo_width()
            if canvas_width > 1:
                self.result_canvas.itemconfig(self.result_canvas_window, width=canvas_width)
            self.display_result_screen()
        elif screen_name == "payment":
            self.payment_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.display_payment_screen()
        elif screen_name == "payment_success":
            self.payment_success_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.display_payment_success_screen()
        elif screen_name == "history":
            if not self.history_frame:
                self.create_history_screen()
            self.history_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
            self.display_history_screen()

    # ===================== CHART =====================

    def draw_nutrition_chart(self, parent, protein, carbs, fat):
        canvas = Canvas(
            parent, width=200, height=200,
            bg=config.COLORS['bg_dark'], highlightthickness=0
        )
        canvas.pack()

        total = protein + carbs + fat
        if total == 0:
            total = 1

        colors = ['#FF6B6B', '#4ECDC4', '#FFE66D']
        values = [protein, carbs, fat]
        center_x, center_y = 100, 100
        radius = 65
        inner_radius = 40
        start_angle = 0

        for value, color in zip(values, colors):
            if value > 0:
                extent = (value / total) * 360
                canvas.create_arc(
                    center_x - radius, center_y - radius,
                    center_x + radius, center_y + radius,
                    start=start_angle, extent=extent,
                    fill=color, outline='white', width=1
                )
                mid_angle = start_angle + extent / 2
                label_rad = math.radians(mid_angle)
                label_radius = (radius + inner_radius) / 2
                label_x = center_x + label_radius * math.cos(label_rad)
                label_y = center_y + label_radius * math.sin(label_rad)
                canvas.create_text(
                    label_x, label_y, text=f"{value}g",
                    fill='white', font=('Arial', 8, 'bold'), anchor="center"
                )
                start_angle += extent

        canvas.create_oval(
            center_x - inner_radius, center_y - inner_radius,
            center_x + inner_radius, center_y + inner_radius,
            fill=config.COLORS['bg_dark'], outline=''
        )

        legend_y = 118
        legend_items = [
            (f'Protein: {protein}g', colors[0]),
            (f'Carbs: {carbs}g',  colors[1]),
            (f'Fat: {fat}g',      colors[2])
        ]
        for i, (text, color) in enumerate(legend_items):
            canvas.create_rectangle(10, legend_y + i*14, 20, legend_y + i*14 + 10,
                                    fill=color, outline='white')
            canvas.create_text(26, legend_y + i*14 + 5, text=text,
                               anchor=W, fill='white', font=('Arial', 8, 'bold'))