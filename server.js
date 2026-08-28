// server.js
const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');
const PayOS = require('@payos/node');
const path = require('path');

dotenv.config();

const app = express();
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Serve website tĩnh (folder hiện tại)
app.use(express.static(__dirname));

// Khởi tạo PayOS
const payOS = new PayOS(
  process.env.PAYOS_CLIENT_ID,
  process.env.PAYOS_API_KEY,
  process.env.PAYOS_CHECKSUM_KEY
);

// ============ API THANH TOÁN ============

// Tạo link thanh toán
app.post('/api/payment/create', async (req, res) => {
  try {
    const { amount, description, buyerName, buyerEmail, buyerPhone } = req.body;
    
    const orderCode = Date.now();
    
    const paymentData = {
      orderCode: orderCode,
      amount: amount,
      description: description || `Thanh toan don hang ${orderCode}`,
      returnUrl: `${process.env.WEBSITE_URL}/payment/success`,
      cancelUrl: `${process.env.WEBSITE_URL}/payment/cancel`,
      buyerName: buyerName || 'Khách hàng',
      buyerEmail: buyerEmail || '',
      buyerPhone: buyerPhone || ''
    };
    
    const paymentLink = await payOS.createPaymentLink(paymentData);
    
    res.json({
      success: true,
      paymentUrl: paymentLink.checkoutUrl,
      qrCode: paymentLink.qrCode,
      orderCode: orderCode
    });
    
  } catch (error) {
    console.error('❌ Lỗi tạo thanh toán:', error);
    res.status(500).json({
      success: false,
      error: error.message
    });
  }
});

// Webhook
app.post('/api/payment/webhook', async (req, res) => {
  try {
    const { data, signature } = req.body;
    const isValid = payOS.verifyPaymentWebhookData(signature);
    
    if (isValid && data && data.status === 'PAID') {
      console.log('✅ Thanh toán thành công:', {
        orderCode: data.orderCode,
        amount: data.amount
      });
      
      // Xử lý tự động tại đây
      await handlePaymentSuccess(data);
    }
    
    res.json({ code: "00", message: "Success" });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Kiểm tra trạng thái
app.get('/api/payment/check/:orderCode', async (req, res) => {
  try {
    const paymentInfo = await payOS.getPaymentLinkInformation(Number(req.params.orderCode));
    res.json({
      success: true,
      status: paymentInfo.status
    });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Trang success
app.get('/payment/success', (req, res) => {
  res.send(`
    <h1 style="text-align:center;margin-top:100px;color:green;">✅ Thanh toán thành công!</h1>
    <p style="text-align:center;"><a href="/">Quay về trang chủ</a></p>
  `);
});

// Trang cancel
app.get('/payment/cancel', (req, res) => {
  res.send(`
    <h1 style="text-align:center;margin-top:100px;color:red;">❌ Thanh toán bị hủy</h1>
    <p style="text-align:center;"><a href="/">Quay về trang chủ</a></p>
  `);
});

// Hàm xử lý tự động
async function handlePaymentSuccess(paymentData) {
  console.log('🎯 Xử lý thanh toán:', paymentData);
  // Thêm logic của bạn tại đây
}

// Khởi động server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`🚀 Website chạy tại: http://localhost:${PORT}`);
});
