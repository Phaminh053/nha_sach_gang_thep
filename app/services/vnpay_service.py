"""VNPay Payment Service - Sandbox Integration"""

import hashlib
import hmac
import urllib.parse
from datetime import datetime
from flask import current_app, url_for


class VNPayService:
    """Service for VNPay payment integration"""
    
    @staticmethod
    def get_config():
        """Get VNPay configuration from app config"""
        return {
            'tmn_code': current_app.config.get('VNPAY_TMN_CODE', ''),
            'hash_secret': current_app.config.get('VNPAY_HASH_SECRET', ''),
            'vnpay_url': current_app.config.get('VNPAY_URL', 'https://sandbox.vnpayment.vn/paymentv2/vpcpay.html')
        }
    
    @staticmethod
    def generate_signature(data: dict, secret_key: str) -> str:
        """
        Generate HMAC-SHA512 signature for VNPay API
        
        Args:
            data: Dictionary of parameters to sign (sorted alphabetically)
            secret_key: VNPay hash secret key
            
        Returns:
            Hex-encoded signature string
        """
        # Sort data by key and build query string
        sorted_data = sorted(data.items())
        query_string = '&'.join([f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in sorted_data])
        
        # Generate HMAC-SHA512 signature
        signature = hmac.new(
            secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return signature
    
    @staticmethod
    def create_payment_url(order_code: str, amount: int, order_info: str,
                           return_url: str = None, client_ip: str = '127.0.0.1') -> dict:
        """
        Create a VNPay payment URL
        
        Args:
            order_code: Unique order code (will be used as vnp_TxnRef)
            amount: Payment amount in VND (integer)
            order_info: Order description
            return_url: URL to redirect after payment (optional)
            client_ip: Client IP address
            
        Returns:
            dict with 'success', 'payment_url', 'error'
        """
        config = VNPayService.get_config()
        
        if not config['tmn_code'] or not config['hash_secret']:
            return {
                'success': False,
                'payment_url': None,
                'error': 'VNPay configuration is missing'
            }
        
        # Build return URL
        if return_url is None:
            return_url = url_for('site.vnpay_return', _external=True)
        
        # Create timestamp
        create_date = datetime.now().strftime('%Y%m%d%H%M%S')
        
        # VNPay requires amount in VND * 100
        vnp_amount = amount * 100
        
        # Build payment data
        vnp_params = {
            'vnp_Version': '2.1.0',
            'vnp_Command': 'pay',
            'vnp_TmnCode': config['tmn_code'],
            'vnp_Amount': str(vnp_amount),
            'vnp_CurrCode': 'VND',
            'vnp_TxnRef': order_code,
            'vnp_OrderInfo': order_info,
            'vnp_OrderType': 'other',
            'vnp_Locale': 'vn',
            'vnp_ReturnUrl': return_url,
            'vnp_IpAddr': client_ip,
            'vnp_CreateDate': create_date,
        }
        
        try:
            # Generate signature
            signature = VNPayService.generate_signature(vnp_params, config['hash_secret'])
            vnp_params['vnp_SecureHash'] = signature
            
            # Build payment URL
            query_string = '&'.join([f"{k}={urllib.parse.quote_plus(str(v))}" for k, v in sorted(vnp_params.items())])
            payment_url = f"{config['vnpay_url']}?{query_string}"
            
            return {
                'success': True,
                'payment_url': payment_url,
                'txn_ref': order_code,
                'error': None
            }
            
        except Exception as e:
            current_app.logger.error(f"VNPay create payment URL failed: {e}")
            return {
                'success': False,
                'payment_url': None,
                'error': str(e)
            }
    
    @staticmethod
    def verify_return_signature(query_params: dict) -> bool:
        """
        Verify VNPay return URL signature
        
        Args:
            query_params: Query parameters from VNPay redirect
            
        Returns:
            True if signature is valid, False otherwise
        """
        config = VNPayService.get_config()
        
        # Get received signature
        received_signature = query_params.get('vnp_SecureHash', '')
        
        # Remove signature fields from params for verification
        verify_params = {k: v for k, v in query_params.items() 
                        if k not in ['vnp_SecureHash', 'vnp_SecureHashType']}
        
        # Generate expected signature
        expected_signature = VNPayService.generate_signature(verify_params, config['hash_secret'])
        
        return hmac.compare_digest(received_signature.lower(), expected_signature.lower())
    
    @staticmethod
    def is_payment_successful(response_code: str) -> bool:
        """
        Check if payment was successful based on VNPay response code
        
        Args:
            response_code: VNPay vnp_ResponseCode
            
        Returns:
            True if payment successful (code "00"), False otherwise
        """
        return response_code == '00'
    
    @staticmethod
    def get_response_message(response_code: str) -> str:
        """
        Get Vietnamese message for VNPay response code
        
        Args:
            response_code: VNPay vnp_ResponseCode
            
        Returns:
            Human-readable message in Vietnamese
        """
        messages = {
            '00': 'Giao dịch thành công',
            '07': 'Trừ tiền thành công. Giao dịch bị nghi ngờ (liên quan tới lừa đảo, giao dịch bất thường)',
            '09': 'Giao dịch không thành công do: Thẻ/Tài khoản của khách hàng chưa đăng ký dịch vụ InternetBanking tại ngân hàng',
            '10': 'Giao dịch không thành công do: Khách hàng xác thực thông tin thẻ/tài khoản không đúng quá 3 lần',
            '11': 'Giao dịch không thành công do: Đã hết hạn chờ thanh toán. Xin quý khách vui lòng thực hiện lại giao dịch',
            '12': 'Giao dịch không thành công do: Thẻ/Tài khoản của khách hàng bị khóa',
            '13': 'Giao dịch không thành công do Quý khách nhập sai mật khẩu xác thực giao dịch (OTP)',
            '24': 'Giao dịch không thành công do: Khách hàng hủy giao dịch',
            '51': 'Giao dịch không thành công do: Tài khoản của quý khách không đủ số dư để thực hiện giao dịch',
            '65': 'Giao dịch không thành công do: Tài khoản của Quý khách đã vượt quá hạn mức giao dịch trong ngày',
            '75': 'Ngân hàng thanh toán đang bảo trì',
            '79': 'Giao dịch không thành công do: KH nhập sai mật khẩu thanh toán quá số lần quy định',
            '99': 'Các lỗi khác',
        }
        return messages.get(response_code, f'Lỗi không xác định (Mã: {response_code})')
