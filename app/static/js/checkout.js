$(document).ready(function() {
    // Shipping fee disabled - always 0
    function updateShippingFee() {
        const subtotal = parseFloat($('#subtotal').text().replace(/[^0-9]/g, '')) || 0;
        
        // No shipping fee calculation needed
        const shippingFee = 0;
        const grandTotal = subtotal;
        
        // Update display (if elements exist)
        if ($('#shipping-fee').length) {
            $('#shipping-fee').text(formatCurrency(shippingFee));
        }
        if ($('#grand-total').length) {
            $('#grand-total').text(formatCurrency(grandTotal));
        }
        if ($('#shipping-info').length) {
            $('#shipping-info').html('<small class="text-success">🎉 Miễn phí vận chuyển!</small>');
        }
    }
    
    // Format số tiền
    function formatCurrency(amount) {
        return new Intl.NumberFormat('vi-VN', {
            style: 'currency',
            currency: 'VND'
        }).format(amount);
    }
    
    // Lắng nghe sự kiện thay đổi địa chỉ (không cần thiết nhưng giữ lại để tránh lỗi)
    $('#province, #district, #ward').on('change', function() {
        updateShippingFee();
    });
    
    // Khởi tạo
    updateShippingFee();
});