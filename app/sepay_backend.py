"""
SePay Backend - Thanh toán VietQR
- Tạo QR: VietQR API (miễn phí)
- Check giao dịch: SePay API (chỉ match theo order_id trong nội dung)
"""

from flask import Flask, request, jsonify
from datetime import datetime
import requests
import re
import config

app = Flask(__name__)

SEPAY_API_KEY = config.SEPAY_API_KEY
SEPAY_API_URL = "https://my.sepay.vn/userapi"
VIETQR_API_URL = "https://api.vietqr.io/v2"

orders = {}


def normalize_text_for_matching(text):
    if not text:
        return ''
    return re.sub(r'[^a-z0-9]+', '', str(text).lower())

#  tạo qr , đơn hàng 
@app.route('/api/create-order', methods=['POST'])
def create_order():
    try:
        data = request.json
        order_id = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
        amount = int(data.get('amount', 0))
        description = data.get('description', 'Food Order')

        if amount <= 0:
            return {"error": "So tien khong hop le"}, 400

        orders[order_id] = {
            "id": order_id,
            "amount": amount,
            "description": description,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "transaction_id": None,
        }
        #  DỮ LIỆU TẠO QR CHO VIETQR    
        vietqr_payload = {
            "accountNo": config.SEPAY_ACCOUNT_NO,
            "accountName": config.SEPAY_ACCOUNT_NAME,
            "acqId": "970422",
            "amount": amount,
            "addInfo": f"OD{order_id}",
            "format": "text",
            "template": "compact"
        }

        print(f"Tao order: OD{order_id}, {amount}d")
        resp = requests.post(
            f"{VIETQR_API_URL}/generate",
            json=vietqr_payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        # Input là 1 http response, output là 1 dict c
        result = resp.json()
        print(f"VietQR: {result.get('code')} - {result.get('desc')}")

        if result.get('code') == '00':
            qr_data = result.get('data', {})
            qr_image_url = qr_data.get('qrDataURL') or qr_data.get('qrDataUrl') or qr_data.get('qrCode', '')
            orders[order_id]['qr_code'] = qr_image_url
            return {"success": True, "order_id": order_id, "amount": amount, "qr_code": qr_image_url}, 200
        else:
            return {"error": result.get('desc', 'Loi VietQR')}, 400

    except requests.exceptions.RequestException as e:
        return {"error": f"Loi ket noi VietQR: {str(e)}"}, 500
    except Exception as e:
        return {"error": str(e)}, 500


@app.route('/api/check-order/<order_id>', methods=['GET'])
def check_order(order_id):
    try:
        if order_id not in orders:
            return {"success": False, "error": "Khong tim thay don hang"}, 404
        #  lấy order 
        order = orders[order_id]

        if order['status'] == 'paid':
            return {"success": True, "order": order}, 200
        # gọi api sepay lấy id các giao dịch từ ngân hàng -> json
        resp = requests.get(
            f"{SEPAY_API_URL}/transactions/list?limit=20",
            headers={"Authorization": f"Bearer {SEPAY_API_KEY}", "Content-Type": "application/json"},
            timeout=10
        )

        result = resp.json()
        transactions = result.get('transactions', [])

        if not isinstance(transactions, list):
            return {"success": True, "order": order}, 200

        order_code_clean = normalize_text_for_matching(f"OD{order_id}")

        for tx in transactions:
            if not isinstance(tx, dict):
                continue

            content = tx.get('transaction_content') or tx.get('description') or ''
            content_clean = normalize_text_for_matching(content)

            print(f"  TX: {content} | amount_in: {tx.get('amount_in')}")

            # CHI match khi order_id co trong noi dung chuyen khoan
            if order_code_clean in content_clean:
                try:
                    tx_amount = int(float(tx.get('amount_in') or 0))
                except Exception:
                    tx_amount = 0

                if tx_amount >= order['amount']:
                    print(f"Match: {content} | {tx_amount}d")
                    order['status'] = 'paid'
                    order['transaction_id'] = tx.get('id') or tx.get('transaction_id')
                    return {"success": True, "order": order}, 200

        return {"success": True, "order": order}, 200

    except Exception as e:
        print(f"Check Error: {e}")
        return {"success": True, "order": orders.get(order_id, {})}, 200


@app.route('/api/cancel-order/<order_id>', methods=['POST'])
def cancel_order(order_id):
    try:
        if order_id in orders:
            orders[order_id]["status"] = "cancelled"
            print(f"✅ Order {order_id} cancelled")
            return {"success": True, "order_id": order_id, "status": "cancelled"}, 200
        else:
            return {"success": False, "error": "Order not found"}, 404
    except Exception as e:
        print(f"Cancel Error: {e}")
        return {"success": False, "error": str(e)}, 500


@app.route('/health', methods=['GET'])
def health():
    return {"status": "ok", "service": "sepay-backend"}, 200


if __name__ == '__main__':
    print(f"SePay Backend chay tai http://localhost:5000")
    print(f"API Key: {SEPAY_API_KEY[:10]}...")
    print(f"Account: {config.SEPAY_ACCOUNT_NO} - MB Bank")
    app.run(host='127.0.0.1', port=5000, debug=True)