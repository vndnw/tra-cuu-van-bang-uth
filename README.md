# Telegram Bot Tra Cứu Văn Bằng

Bot tự động tra cứu thông tin văn bằng từ `vanbang.ut.edu.vn` và gửi thông báo qua Telegram.

## Cài đặt

```bash
pip install -r requirements.txt
```

## Cấu hình

Mở file `app.py` và điền 2 giá trị:

```python
BOT_TOKEN = 'token_telegram_bot_của_bạn'
SECRET_KEY = 'mã_bảo_mật_cronjob_tùy_chọn'
```

## Triển khai trên PythonAnywhere

1. Upload `app.py`, `requirements.txt` lên PythonAnywhere
2. Cài dependencies: `pip install -r requirements.txt`
3. Tạo Web App (Flask) trỏ đến `app.py`
4. Đặt Webhook Telegram:
   ```
   https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<username>.pythonanywhere.com/telegram-webhook
   ```
5. Cấu hình Cron-job (cron-job.org) gọi:
   ```
   GET https://<username>.pythonanywhere.com/trigger-scan?key=<SECRET_KEY>
   ```

## Lệnh Bot

| Lệnh | Mô tả |
|---|---|
| `/start` | Xem hướng dẫn sử dụng |
| `/dangky Họ Tên` | Đăng ký tra cứu hằng ngày |
| `/huy` | Hủy đăng ký theo dõi |
| `/trangthai` | Kiểm tra trạng thái đăng ký |
