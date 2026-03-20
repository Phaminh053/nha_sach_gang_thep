# Hướng dẫn tích hợp thanh toán MoMo (Flask)

Hướng dẫn này có thể áp dụng cho bất kỳ project Flask nào.

---

## 1. Cấu hình Environment

Thêm vào file `.env`:

```bash
# MoMo Payment - Sandbox (Test)
MOMO_PARTNER_CODE=MOMONPMB20210629
MOMO_ACCESS_KEY=Q2XhhSdgpKUlQ4Ky
MOMO_SECRET_KEY=k6B53GQKSjktZGJBK2MyrDa7w9S6RyCf
MOMO_ENDPOINT=https://test-payment.momo.vn/v2/gateway/api/create
MOMO_QUERY_ENDPOINT=https://test-payment.momo.vn/v2/gateway/api/query
```

> [!WARNING]
> Đây là credentials **sandbox công khai**. Khi lên Production, đăng ký với MoMo để nhận credentials riêng.

---

## 2. Config Class

Thêm vào `config.py`:

```python
import os

class Config:
    # MoMo Payment Configuration
    MOMO_PARTNER_CODE = os.environ.get('MOMO_PARTNER_CODE', 'MOMONPMB20210629')
    MOMO_ACCESS_KEY = os.environ.get('MOMO_ACCESS_KEY', 'Q2XhhSdgpKUlQ4Ky')
    MOMO_SECRET_KEY = os.environ.get('MOMO_SECRET_KEY', 'k6B53GQKSjktZGJBK2MyrDa7w9S6RyCf')
    MOMO_ENDPOINT = os.environ.get('MOMO_ENDPOINT', 'https://test-payment.momo.vn/v2/gateway/api/create')
    MOMO_QUERY_ENDPOINT = os.environ.get('MOMO_QUERY_ENDPOINT', 'https://test-payment.momo.vn/v2/gateway/api/query')
```

---

## 3. MoMo Service

Tạo file `services/momo_service.py`:

```python
"""MoMo Payment Service"""

import hashlib
import hmac
import uuid
import requests
from flask import current_app, url_for


class MoMoService:
    """Service for MoMo payment integration"""
    
    @staticmethod
    def get_config():
        """Get MoMo configuration from app config"""
        return {
            'partner_code': current_app.config.get('MOMO_PARTNER_CODE', ''),
            'access_key': current_app.config.get('MOMO_ACCESS_KEY', ''),
            'secret_key': current_app.config.get('MOMO_SECRET_KEY', ''),
            'endpoint': current_app.config.get('MOMO_ENDPOINT'),
            'query_endpoint': current_app.config.get('MOMO_QUERY_ENDPOINT')
        }
    
    @staticmethod
    def generate_signature(raw_signature: str, secret_key: str) -> str:
        """Generate HMAC-SHA256 signature"""
        return hmac.new(
            secret_key.encode('utf-8'),
            raw_signature.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def create_payment_request(order_id: str, amount: int, order_info: str,
                                return_url: str = None, notify_url: str = None) -> dict:
        """
        Create MoMo payment request
        
        Args:
            order_id: Unique order ID
            amount: Payment amount in VND (integer)
            order_info: Order description
            return_url: URL to redirect after payment
            notify_url: IPN callback URL
            
        Returns:
            dict with 'success', 'pay_url', 'request_id', 'error'
        """
        config = MoMoService.get_config()
        request_id = str(uuid.uuid4())
        
        # Build URLs - thay đổi theo route của bạn
        if return_url is None:
            return_url = url_for('payment.momo_return', _external=True)
        if notify_url is None:
            notify_url = url_for('payment.momo_ipn', _external=True)
        
        request_type = "captureWallet"
        extra_data = ""
        
        # Build raw signature (PHẢI theo thứ tự alphabetical)
        raw_signature = (
            f"accessKey={config['access_key']}"
            f"&amount={amount}"
            f"&extraData={extra_data}"
            f"&ipnUrl={notify_url}"
            f"&orderId={order_id}"
            f"&orderInfo={order_info}"
            f"&partnerCode={config['partner_code']}"
            f"&redirectUrl={return_url}"
            f"&requestId={request_id}"
            f"&requestType={request_type}"
        )
        
        signature = MoMoService.generate_signature(raw_signature, config['secret_key'])
        
        request_body = {
            "partnerCode": config['partner_code'],
            "accessKey": config['access_key'],
            "requestId": request_id,
            "amount": str(amount),
            "orderId": order_id,
            "orderInfo": order_info,
            "redirectUrl": return_url,
            "ipnUrl": notify_url,
            "extraData": extra_data,
            "requestType": request_type,
            "signature": signature,
            "lang": "vi"
        }
        
        try:
            response = requests.post(
                config['endpoint'],
                json=request_body,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            result = response.json()
            
            if result.get('resultCode') == 0:
                return {
                    'success': True,
                    'pay_url': result.get('payUrl'),
                    'qr_code_url': result.get('qrCodeUrl'),
                    'request_id': request_id,
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'pay_url': None,
                    'request_id': request_id,
                    'error': result.get('message', 'Unknown error'),
                    'result_code': result.get('resultCode')
                }
                
        except requests.RequestException as e:
            return {
                'success': False,
                'pay_url': None,
                'request_id': request_id,
                'error': str(e)
            }
    
    @staticmethod
    def verify_ipn_signature(data: dict) -> bool:
        """Verify IPN callback signature from MoMo"""
        config = MoMoService.get_config()
        received_signature = data.get('signature', '')
        
        # Build raw signature from IPN data (thứ tự alphabetical)
        raw_signature = (
            f"accessKey={config['access_key']}"
            f"&amount={data.get('amount', '')}"
            f"&extraData={data.get('extraData', '')}"
            f"&message={data.get('message', '')}"
            f"&orderId={data.get('orderId', '')}"
            f"&orderInfo={data.get('orderInfo', '')}"
            f"&orderType={data.get('orderType', '')}"
            f"&partnerCode={data.get('partnerCode', '')}"
            f"&payType={data.get('payType', '')}"
            f"&requestId={data.get('requestId', '')}"
            f"&responseTime={data.get('responseTime', '')}"
            f"&resultCode={data.get('resultCode', '')}"
            f"&transId={data.get('transId', '')}"
        )
        
        expected_signature = MoMoService.generate_signature(raw_signature, config['secret_key'])
        return hmac.compare_digest(received_signature, expected_signature)
    
    @staticmethod
    def is_payment_successful(result_code: int) -> bool:
        """Check if payment was successful (code 0)"""
        return result_code == 0
```

---

## 4. Routes

Tạo routes cho MoMo callback:

```python
from flask import Blueprint, request, jsonify, redirect, url_for, flash
from services.momo_service import MoMoService

payment_bp = Blueprint('payment', __name__)


@payment_bp.route('/momo/ipn', methods=['POST'])
def momo_ipn():
    """MoMo IPN callback - server to server"""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'message': 'Invalid data'}), 400
        
        # Verify signature
        if not MoMoService.verify_ipn_signature(data):
            return jsonify({'message': 'Invalid signature'}), 400
        
        order_id = data.get('orderId')
        result_code = data.get('resultCode')
        trans_id = data.get('transId')
        
        if MoMoService.is_payment_successful(result_code):
            # TODO: Cập nhật order trong database
            # order.payment_status = 'paid'
            # order.momo_trans_id = trans_id
            # db.session.commit()
            pass
        
        return jsonify({'message': 'Success'}), 200
        
    except Exception as e:
        return jsonify({'message': 'Internal error'}), 500


@payment_bp.route('/momo/return')
def momo_return():
    """MoMo return URL - user redirect after payment"""
    order_id = request.args.get('orderId')
    result_code = request.args.get('resultCode')
    
    if result_code and int(result_code) == 0:
        flash('Thanh toán MoMo thành công!', 'success')
    else:
        flash('Thanh toán chưa thành công. Vui lòng thử lại.', 'warning')
    
    return redirect(url_for('order.detail', order_id=order_id))
```

---

## 5. Database Migration

Thêm cột theo dõi MoMo vào bảng orders:

```sql
ALTER TABLE orders ADD COLUMN momo_request_id VARCHAR(50) NULL;
ALTER TABLE orders ADD COLUMN momo_trans_id VARCHAR(50) NULL;
```

---

## 6. Sử dụng trong Checkout

```python
from services.momo_service import MoMoService

# Trong checkout view
if payment_method == 'MOMO':
    result = MoMoService.create_payment_request(
        order_id=order.order_code,
        amount=int(total_amount),  # VND, số nguyên
        order_info=f'Thanh toán đơn hàng {order.order_code}'
    )
    
    if result['success']:
        order.momo_request_id = result['request_id']
        db.session.commit()
        return redirect(result['pay_url'])
    else:
        flash(f'Lỗi MoMo: {result["error"]}', 'error')
```

---

## 7. Production

Khi lên production:

1. Đăng ký tài khoản Business với MoMo
2. Nhận credentials production
3. Đổi endpoint:
   ```bash
   MOMO_ENDPOINT=https://payment.momo.vn/v2/gateway/api/create
   MOMO_QUERY_ENDPOINT=https://payment.momo.vn/v2/gateway/api/query
   ```
4. Đảm bảo IPN URL có HTTPS và accessible từ internet

---

## Mã lỗi phổ biến

| Code | Mô tả |
|------|-------|
| `0` | Thành công |
| `9000` | Đang xử lý |
| `1001` | Không đủ tiền |
| `1004` | Hết hạn thanh toán |
| `1005` | OTP không hợp lệ |
