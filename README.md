# 🎓 Telegram Bot Tra Cứu Văn Bằng UTH (VPS Windows & PM2)

Bot tự động tra cứu thông tin văn bằng tốt nghiệp từ trang tra cứu của Trường Đại học Giao thông Vận tải TP.HCM (UTH) (`https://vanbang.ut.edu.vn/tracuu/`) và gửi thông báo qua Telegram. 

Dự án được tối ưu hóa để chạy liên tục 24/7 trên **Windows Server VPS** sử dụng cơ chế **Long Polling** kết hợp với **Background Scheduler**, tiến trình được quản lý chuyên nghiệp thông qua **PM2**.

---

## ✨ Các tính năng nổi bật

1. **Bàn phím nút bấm tiện lợi (ReplyKeyboardMarkup):** 
   - Tích hợp 4 nút bấm tương tác nhanh dưới khung chat: `🔍 Tra cứu ngay`, `📋 Trạng thái`, `❌ Hủy theo dõi`, `❓ Hướng dẫn`.
2. **Bộ lọc ngày sinh thông minh:**
   - Hỗ trợ so khớp chính xác ngày sinh để tránh trùng tên.
   - Nhận diện linh hoạt định dạng năm sinh 2 chữ số hoặc 4 chữ số (ví dụ: `08/04/1999` vẫn khớp với `08/04/99` trên hệ thống trường).
3. **Phân tách tính năng kiểm tra:**
   - **/kiemtra** (không tham số hoặc qua nút bấm): Quét theo tên + ngày sinh đã đăng ký trong cơ sở dữ liệu.
   - **/kiemtra Họ và Tên** (tra nhanh): Quét trực tiếp họ tên bất kỳ trên web trường (không lọc ngày sinh).
4. **Liên kết chi tiết trực tiếp:**
   - Tự động trích xuất liên kết chi tiết của từng văn bằng và gửi dưới dạng hyperlink `🔗 Xem chi tiết trên Web`.
5. **Cấu hình Menu lệnh bằng Code:**
   - Tự động đồng bộ các lệnh khả dụng lên nút Menu của Telegram chat.
6. **Lập lịch chạy tự động:**
   - Tự động quét và thông báo văn bằng mới vào lúc `08:00` sáng hằng ngày.

---

## 🛠️ Yêu cầu hệ thống

* **Python 3.8+** (Đã add vào PATH)
* **Node.js** (Để cài đặt và quản lý tiến trình bằng PM2)
* **Cơ sở dữ liệu:** SQLite (Tự động khởi tạo file `users.db` khi chạy)

---

## 🚀 Hướng dẫn cài đặt & Triển khai trên VPS Windows

### Bước 1: Cài đặt thư viện Python & PM2
1. Mở Command Prompt (CMD) với quyền Admin và cài đặt PM2 toàn cục:
   ```bash
   npm install -g pm2
   ```
2. Di chuyển đến thư mục code và cài đặt các thư viện cần thiết:
   ```bash
   pip install -r requirements.txt
   ```

### Bước 2: Cấu hình Bot Token
Mở tệp `app.py` và điền Telegram Bot Token của bạn ở dòng 22:
```python
BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'
```

### Bước 3: Khởi chạy Bot với PM2
Khởi chạy bot dưới dạng tiến trình ngầm để tự động chạy lại khi VPS khởi động lại hoặc khi ứng dụng crash:
```bash
pm2 start app.py --name uth-bot
```

---

## 📊 Các lệnh quản lý PM2 thông dụng

* **Xem danh sách tiến trình:** `pm2 list`
* **Xem log thời gian thực:** `pm2 logs uth-bot`
* **Khởi động lại Bot:** `pm2 restart uth-bot`
* **Dừng Bot:** `pm2 stop uth-bot`
* **Mở màn hình giám sát hiệu năng:** `pm2 monit`

---

## 📌 Hướng dẫn sử dụng các lệnh Bot

| Lệnh | Mô tả | Cú pháp ví dụ |
|---|---|---|
| `/start` hoặc nút `❓ Hướng dẫn` | Xem hướng dẫn sử dụng và danh sách lệnh | `/start` |
| `/dangky` | Đăng ký theo dõi văn bằng hàng ngày | `/dangky Nguyễn Văn A 08/04/1999` |
| `/huy` hoặc nút `❌ Hủy theo dõi` | Hủy đăng ký theo dõi hiện tại | `/huy` |
| `/trangthai` hoặc nút `📋 Trạng thái` | Kiểm tra từ khóa đang được theo dõi | `/trangthai` |
| `/kiemtra` (không tham số) | Quét kết quả ngay lập tức cho từ khóa đã đăng ký | `/kiemtra` |
| `/kiemtra Họ và Tên` (tra nhanh) | Tra cứu nhanh một người bất kỳ trực tiếp từ web trường | `/kiemtra Nguyễn Văn A` |
