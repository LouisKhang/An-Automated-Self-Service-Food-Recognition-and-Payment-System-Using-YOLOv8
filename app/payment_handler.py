"""
Xử lý thanh toán và hóa đơn
"""
import socket
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
from tkinter import Toplevel, Frame, Label, LabelFrame, Radiobutton, StringVar, Button, messagebox

try:
    import qrcode
    from PIL import Image, ImageTk
    HAS_QR = True
except ImportError:
    HAS_QR = False

import config

# Thư mục gốc project (chứa app/ và web/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PAYMENT_HTML_PATH = PROJECT_ROOT / "web" / "payment_success.html"
PAYMENT_SERVER_PORT = 8765
PAYMENT_QR_TEXT = "THANHTOANTHANHCON"


def get_local_ip():
    """Lấy IP nội bộ (Wi‑Fi/LAN) để điện thoại cùng mạng mở được link trong QR."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def make_payment_handler(app_ref):
    """Tạo lớp Handler có tham chiếu tới MainWindow."""
    class PaymentHTTPHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Tắt log request
        
        def do_GET(self):
            path = urlparse(self.path).path
            query = parse_qs(urlparse(self.path).query)
            method = (query.get("m") or ["vietqr"])[0]
            if path in ("/success", "/"):
                try:
                    html_path = PAYMENT_HTML_PATH
                    if html_path.exists():
                        body = html_path.read_bytes()
                    else:
                        body = b"<h1>Thanh toan thanh cong!</h1>"
                except Exception:
                    body = b"<h1>Thanh toan thanh cong!</h1>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                if app_ref and getattr(app_ref, "root", None):
                    app_ref.root.after(0, lambda: app_ref.on_payment_success_from_web(method))
                return
            self.send_response(404)
            self.end_headers()
    return PaymentHTTPHandler


class PaymentHandler:
    """Xử lý thanh toán và hóa đơn"""
    
    def __init__(self, root, cart_manager, get_cart_totals_func, normalize_food_key_func, food_data):
        self.root = root
        self.cart_manager = cart_manager
        self.get_cart_totals_func = get_cart_totals_func
        self.normalize_food_key_func = normalize_food_key_func
        self.food_data = food_data
        self._payment_window = None
        self._payment_server_url = None
        self._httpd = None
    
    def start_payment_server(self, app_ref):
        """Chạy server HTTP nền để phục vụ trang thanh toán thành công khi quét QR."""
        try:
            local_ip = get_local_ip()
            handler = make_payment_handler(app_ref)
            self._httpd = HTTPServer(("0.0.0.0", PAYMENT_SERVER_PORT), handler)
            self._payment_server_url = f"http://{local_ip}:{PAYMENT_SERVER_PORT}/success"
            import threading
            t = threading.Thread(target=self._httpd.serve_forever, daemon=True)
            t.start()
            print(f"✅ Payment server: {self._payment_server_url}")
        except Exception as e:
            print(f"⚠️ Không chạy được payment server: {e}")
            self._payment_server_url = None
    
    def make_qr_image(self, data, size=200):
        """Tạo ảnh QR (PIL) từ chuỗi. Trả về ImageTk hoặc None nếu không có thư viện."""
        if not HAS_QR:
            return None
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        try:
            img = img.resize((size, size), Image.Resampling.LANCZOS)
        except AttributeError:
            img = img.resize((size, size), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    
    def show_payment_dialog(self, cart, current_detections, current_session, 
                           result_total_price, result_total_calories,
                           on_payment_success_callback, validate_cart_func):
        """
        Hiện hộp thoại thanh toán: chọn hình thức -> hiện QR (nếu có) -> xác nhận -> xuất hóa đơn.
        
        Args:
            cart: Giỏ hàng hiện tại
            current_detections: Danh sách detections gốc
            current_session: Session hiện tại
            result_total_price: Tổng tiền
            result_total_calories: Tổng calo
            on_payment_success_callback: Callback khi thanh toán thành công (method_name, invoice_path)
            validate_cart_func: Hàm validate cart trước khi thanh toán
        """
        # Validate giỏ hàng trước khi cho phép thanh toán
        if not validate_cart_func():
            return
        
        total = result_total_price
        total_cal = result_total_calories
        pay_win = Toplevel(self.root)
        self._payment_window = pay_win
        pay_win.title("💳 Thanh toán")
        pay_w, pay_h = 500, 780
        pay_win.geometry(f"{pay_w}x{pay_h}")
        
        def _on_close():
            self._payment_window = None
            pay_win.destroy()
        
        pay_win.protocol("WM_DELETE_WINDOW", _on_close)
        pay_win.configure(bg=config.COLORS['bg_dark'])
        pay_win.transient(self.root)
        pay_win.resizable(False, False)
        pay_win.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (pay_w // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (pay_h // 2)
        pay_win.geometry(f"+{max(0, x)}+{max(0, y)}")
        
        # Tổng tiền
        f_top = Frame(pay_win, bg=config.COLORS['bg_header'], padx=16, pady=12)
        f_top.pack(fill="x")
        Label(f_top, text="💳 THANH TOÁN HÓA ĐƠN", font=("Arial", 14, "bold"),
              bg=config.COLORS['bg_header'], fg=config.COLORS['accent_green']).pack(anchor="w")
        Label(f_top, text=f"💰 Tổng tiền: {total:,} VNĐ", font=("Arial", 12, "bold"),
              bg=config.COLORS['bg_header'], fg=config.COLORS['accent_orange']).pack(anchor="w", pady=4)
        Label(f_top, text=f"🔥 Tổng calo: {total_cal:,} kcal", font=("Arial", 10),
              bg=config.COLORS['bg_header'], fg='white').pack(anchor="w")
        
        method_var = StringVar(value="cash")
        methods = [
            ("cash", "💵 Tiền mặt (thanh toán khi nhận)"),
            ("momo", "📱 Momo"),
            ("zalopay", "📱 ZaloPay"),
            ("vietqr", "🏦 VietQR (quét mã chuyển khoản)"),
        ]
        f_method = LabelFrame(pay_win, text="Chọn hình thức thanh toán", bg=config.COLORS['bg_medium'],
                              fg=config.COLORS['accent_green'], font=("Arial", 10, "bold"), padx=10, pady=8)
        f_method.pack(fill="x", padx=16, pady=10)
        for val, label in methods:
            Radiobutton(
                f_method, text=label, variable=method_var, value=val,
                bg=config.COLORS['bg_medium'], fg='white', selectcolor=config.COLORS['bg_dark'],
                activebackground=config.COLORS['bg_medium'], font=("Arial", 10),
                command=lambda: None
            ).pack(anchor="w", pady=4)
        
        # Vùng hiển thị QR
        f_qr = Frame(pay_win, bg=config.COLORS['bg_dark'], pady=12)
        f_qr.pack(fill="x")
        qr_label = Label(f_qr, text="Chọn hình thức thanh toán để hiển thị mã QR",
                         font=("Arial", 10), bg=config.COLORS['bg_dark'], fg=config.COLORS['text_gray'])
        qr_label.pack(pady=8)
        qr_photo_holder = [None]
        
        def update_qr():
            m = method_var.get()
            qr_label.config(text="Chọn hình thức thanh toán để hiển thị mã QR")
            for w in f_qr.winfo_children():
                if w != qr_label:
                    w.destroy()
            if m == "cash":
                qr_label.config(text="💵 Thanh toán khi nhận hàng. Không cần quét mã.")
                return
            if self._payment_server_url:
                qr_content = f"{self._payment_server_url}?m={m}"
            else:
                qr_content = PAYMENT_QR_TEXT
            if HAS_QR:
                photo = self.make_qr_image(qr_content, size=400)
                if photo:
                    qr_photo_holder[0] = photo
                    lab = Label(f_qr, image=photo, bg="white", padx=12, pady=12)
                    lab.pack(pady=6)
                if self._payment_server_url:
                    qr_label.config(
                        text="Quét mã QR bằng điện thoại (cùng Wi‑Fi với máy tính).\n"
                             "Trình duyệt mở trang 'Thanh toán thành công' → App tự xuất hóa đơn.\n"
                             "Hoặc bấm 'Xác nhận đã thanh toán' bên dưới để xuất ngay."
                    )
                else:
                    qr_label.config(
                        text="Quét mã QR (mã chữ). Hoặc bấm 'Xác nhận đã thanh toán' để xuất hóa đơn."
                    )
            else:
                qr_label.config(text="Cài: pip install qrcode[pil] để hiện QR.")
        
        method_var.trace_add("write", lambda *a: update_qr())
        update_qr()
        
        def on_confirm():
            method = method_var.get()
            name_map = {"cash": "Tiền mặt", "momo": "Momo", "zalopay": "ZaloPay", "vietqr": "VietQR"}
            method_name = name_map.get(method, method)
            path = self.save_invoice_to_downloads(cart, current_detections, method_name)
            self._payment_window = None
            pay_win.destroy()
            messagebox.showinfo("Thanh toán thành công", 
                              f"Đã thanh toán bằng {method_name}.\n\nHóa đơn đã lưu:\n{path}")
            if on_payment_success_callback:
                on_payment_success_callback(method_name, path)
        
        Button(pay_win, text="✅ XÁC NHẬN ĐÃ THANH TOÁN", bg=config.COLORS['accent_green'], fg='white',
               font=('Arial', 11, 'bold'), width=28, height=2, bd=0, cursor='hand2', command=on_confirm).pack(pady=16)
        Button(pay_win, text="Đóng", bg=config.COLORS['text_gray'], fg='white', font=('Arial', 10),
               bd=0, padx=20, pady=6, cursor='hand2', command=_on_close).pack(pady=0)
    
    def save_invoice_to_downloads(self, cart, current_detections, payment_method_name):
        """
        Tạo nội dung hóa đơn và lưu vào thư mục Downloads. Trả về đường dẫn file.
        
        Args:
            cart: Giỏ hàng hiện tại
            current_detections: Danh sách detections gốc (fallback)
            payment_method_name: Tên phương thức thanh toán
        """
        # Ưu tiên lấy theo CART (đã được user xác nhận)
        if cart:
            total_items, total, total_cal = self.get_cart_totals_func()
            items_iter = list(cart.values())
        else:
            # Fallback: dùng raw detections nếu chưa có cart
            total_items = len(current_detections)
            total = 0
            total_cal = 0
            for det in current_detections:
                key = self.normalize_food_key_func(det['name'])
                info = self.food_data.get(key, {})
                total += info.get('price', 0)
                total_cal += info.get('calories', 0)
            items_iter = None
        
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        downloads = Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        path = downloads / f"HoaDon_Food_{ts}.txt"
        
        # Format hóa đơn đẹp như siêu thị
        lines = []
        lines.append(" " * 20 + "🍕 FOOD DETECTION AI")
        lines.append(" " * 18 + "=" * 30)
        lines.append(" " * 20 + "HÓA ĐƠN BÁN HÀNG")
        lines.append(" " * 18 + "=" * 30)
        lines.append("")
        lines.append(f"Ngày: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        lines.append(f"Mã HĐ: INV_{ts}")
        lines.append(f"Phương thức: {payment_method_name}")
        lines.append("-" * 50)
        lines.append(f"{'Tên món':<25} {'SL':>3} {'Giá':>12} {'TT':>12}")
        lines.append("-" * 50)
        
        if items_iter is not None:
            for item in items_iter:
                qty = int(item.get("quantity", 0))
                if item.get("excluded") or qty <= 0:
                    continue
                name = (item.get("name_vi") or item.get("key"))[:23]
                price = item.get("price", 0)
                total_line = price * qty
                lines.append(f"{name:<25} {qty:>3} {price:>11,}đ {total_line:>11,}đ")
        else:
            for det in current_detections:
                key = self.normalize_food_key_func(det['name'])
                info = self.food_data.get(key, {})
                name = (info.get('name_vi') or det['name'])[:23]
                price = info.get('price', 0)
                total_line = price
                lines.append(f"{name:<25} {1:>3} {price:>11,}đ {total_line:>11,}đ")
        
        lines.append("-" * 50)
        lines.append(f"{'Tổng số phần:':<25} {total_items:>3}")
        lines.append(f"{'Tổng calo:':<25} {total_cal:,} kcal")
        lines.append("")
        lines.append(f"{'TỔNG TIỀN:':<25} {total:>11,}đ")
        lines.append("")
        lines.append(" " * 15 + "Cảm ơn quý khách!")
        lines.append(" " * 12 + "Hẹn gặp lại 🎉")
        lines.append("=" * 50)
        
        path.write_text("\n".join(lines), encoding="utf-8")
        return str(path)
    
    def close_payment_window(self):
        """Đóng cửa sổ thanh toán nếu đang mở"""
        if self._payment_window:
            try:
                if self._payment_window.winfo_exists():
                    self._payment_window.destroy()
            except Exception:
                pass
            self._payment_window = None
