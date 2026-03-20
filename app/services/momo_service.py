"""MoMo Payment Service - Sandbox Integration"""

import hashlib
import hmac
import json
import uuid
import requests
from datetime import datetime
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
            'endpoint': current_app.config.get('MOMO_ENDPOINT', 'https://test-payment.momo.vn/v2/gateway/api/create'),
            'query_endpoint': current_app.config.get('MOMO_QUERY_ENDPOINT', 'https://test-payment.momo.vn/v2/gateway/api/query')
        }
    
    @staticmethod
    def generate_signature(raw_signature: str, secret_key: str) -> str:
        """
        Generate HMAC-SHA256 signature for MoMo API
        
        Args:
            raw_signature: The raw signature string to sign
            secret_key: MoMo secret key
            
        Returns:
            Hex-encoded signature string
        """
        signature = hmac.new(
            secret_key.encode('utf-8'),
            raw_signature.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    @staticmethod
    def create_payment_request(order_id: str, order_code: str, amount: int, 
                                order_info: str, return_url: str = None, 
                                notify_url: str = None) -> dict:
        """
        Create a MoMo payment request
        
        Args:
            order_id: Unique order ID (will be used as orderId in MoMo)
            order_code: Order code for display
            amount: Payment amount in VND (integer)
            order_info: Order description
            return_url: URL to redirect after payment (optional)
            notify_url: IPN callback URL (optional)
            
        Returns:
            dict with 'success', 'pay_url', 'qr_code_url', 'request_id', 'error'
        """
        config = MoMoService.get_config()
        
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        # Build URLs
        if return_url is None:
            return_url = url_for('site.momo_return', _external=True)
        if notify_url is None:
            notify_url = url_for('site.momo_ipn', _external=True)
        
        # Prepare request data
        request_type = "captureWallet"
        extra_data = ""  # Base64 encoded JSON, empty for now
        
        # Build raw signature string (must be in exact order!)
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
        
        # Generate signature
        signature = MoMoService.generate_signature(raw_signature, config['secret_key'])
        
        # Build request body
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
            # Call MoMo API
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
                    'deeplink': result.get('deeplink'),
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'pay_url': None,
                    'qr_code_url': None,
                    'request_id': request_id,
                    'error': result.get('message', 'Unknown error'),
                    'result_code': result.get('resultCode')
                }
                
        except requests.RequestException as e:
            current_app.logger.error(f"MoMo API request failed: {e}")
            return {
                'success': False,
                'pay_url': None,
                'qr_code_url': None,
                'request_id': request_id,
                'error': str(e)
            }
    
    @staticmethod
    def verify_ipn_signature(data: dict) -> bool:
        """
        Verify IPN callback signature from MoMo
        
        Args:
            data: IPN callback data from MoMo
            
        Returns:
            True if signature is valid, False otherwise
        """
        config = MoMoService.get_config()
        
        # Extract signature from data
        received_signature = data.get('signature', '')
        
        # Build raw signature from IPN data (must be in exact order!)
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
        
        # Generate expected signature
        expected_signature = MoMoService.generate_signature(raw_signature, config['secret_key'])
        
        return hmac.compare_digest(received_signature, expected_signature)
    
    @staticmethod
    def query_transaction_status(order_id: str, request_id: str) -> dict:
        """
        Query transaction status from MoMo
        
        Args:
            order_id: The order ID used in payment request
            request_id: The request ID used in payment request
            
        Returns:
            dict with transaction status details
        """
        config = MoMoService.get_config()
        
        # Build raw signature
        raw_signature = (
            f"accessKey={config['access_key']}"
            f"&orderId={order_id}"
            f"&partnerCode={config['partner_code']}"
            f"&requestId={request_id}"
        )
        
        signature = MoMoService.generate_signature(raw_signature, config['secret_key'])
        
        request_body = {
            "partnerCode": config['partner_code'],
            "accessKey": config['access_key'],
            "requestId": request_id,
            "orderId": order_id,
            "signature": signature,
            "lang": "vi"
        }
        
        try:
            response = requests.post(
                config['query_endpoint'],
                json=request_body,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            return response.json()
            
        except requests.RequestException as e:
            current_app.logger.error(f"MoMo query failed: {e}")
            return {'error': str(e)}
    
    @staticmethod
    def is_payment_successful(result_code: int) -> bool:
        """
        Check if payment was successful based on MoMo result code
        
        Args:
            result_code: MoMo result code
            
        Returns:
            True if payment successful (code 0), False otherwise
        """
        return result_code == 0
