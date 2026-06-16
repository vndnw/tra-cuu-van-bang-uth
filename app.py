import sqlite3
import logging
import traceback
import time
import threading
import re
import cloudscraper
import telebot
import schedule
from bs4 import BeautifulSoup
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

# --- CẤU HÌNH LOGGING SYSTEM ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# --- CẤU HÌNH BOT TELEGRAM ---
# Điền Token Bot của bạn ở đây (Không chia sẻ file này khi có token lên GitHub)
BOT_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN_HERE'
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

DATABASE = 'users.db'


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Khởi tạo cơ sở dữ liệu và nâng cấp bảng (Migration) nếu cần"""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS subscribers (
            chat_id TEXT PRIMARY KEY,
            keyword TEXT NOT NULL
        )
    ''')
    conn.commit()

    # Tự động thêm cột dob (ngày sinh) nếu DB cũ chưa có
    try:
        conn.execute("ALTER TABLE subscribers ADD COLUMN dob TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        # Cột dob đã tồn tại, bỏ qua
        pass
    conn.close()
    logger.info("Khoi tao va cap nhat SQLite Database thanh cong.")


init_db()


def setup_bot_commands():
    """Tự động đồng bộ Menu lệnh hiển thị trên Telegram chat"""
    try:
        bot.set_my_commands([
            telebot.types.BotCommand("start", "Xem hướng dẫn sử dụng"),
            telebot.types.BotCommand("dangky", "Đăng ký tra cứu hằng ngày"),
            telebot.types.BotCommand("huy", "Hủy đăng ký theo dõi"),
            telebot.types.BotCommand("trangthai", "Kiểm tra trạng thái đăng ký"),
            telebot.types.BotCommand("kiemtra", "Tra cứu văn bằng ngay lập tức")
        ])
        logger.info("Da dong bo Menu lenh (Bot Commands) len Telegram.")
    except Exception as e:
        logger.error(f"Khong the dong bo Menu lenh: {e}")


# Đồng bộ Menu lệnh khi khởi động
setup_bot_commands()


# ============================================================
# CẤU HÌNH BÀN PHÍM TÙY CHỈNH (REPLY KEYBOARD MARKUP)
# ============================================================

def get_main_keyboard():
    """Tạo bàn phím nút bấm dưới khung chat của người dùng"""
    markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    btn_check = KeyboardButton("🔍 Tra cứu ngay")
    btn_status = KeyboardButton("📋 Trạng thái")
    btn_cancel = KeyboardButton("❌ Hủy theo dõi")
    btn_help = KeyboardButton("❓ Hướng dẫn")
    
    # Bố trí 2 dòng nút
    markup.row(btn_check, btn_status)
    markup.row(btn_cancel, btn_help)
    return markup


# ============================================================
# CÁC HÀM TRỢ GIÚP TRA CỨU & BÓC TÁCH (PARSING & MATCHING ENGINE)
# ============================================================

def parse_register_text(text):
    """Tách Họ tên và Ngày sinh bằng Regex"""
    text = text.strip()
    match = re.search(r'\s+(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})$', text)
    if match:
        dob = match.group(1).strip()
        keyword = text[:match.start()].strip()
        return keyword, dob
    return text, ""


def match_dob(user_dob, web_dob):
    """Thuật toán so khớp ngày sinh thông minh"""
    if not user_dob or not web_dob:
        return True

    u = user_dob.strip().replace('-', '/').replace(' ', '')
    w = web_dob.strip().replace('-', '/').replace(' ', '')

    if u == w:
        return True

    u_parts = u.split('/')
    w_parts = w.split('/')

    if len(u_parts) == 3 and len(w_parts) == 3:
        try:
            u_day, u_month = int(u_parts[0]), int(u_parts[1])
            w_day, w_month = int(w_parts[0]), int(w_parts[1])
            if u_day == w_day and u_month == w_month:
                if u_parts[2][-2:] == w_parts[2][-2:]:
                    return True
        except ValueError:
            pass

    return False


def parse_results(html_content):
    """Bóc tách thông tin văn bằng từ HTML kết quả bằng BeautifulSoup"""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table', class_='main-table__result')
        if not table:
            return []

        results = []
        rows = table.find_all('tr')[1:]
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 9:
                detail_link = ""
                if len(cols) >= 10:
                    link_tag = cols[9].find('a')
                    if link_tag and link_tag.get('href'):
                        href = link_tag.get('href')
                        if href.startswith('/'):
                            href = href[1:]
                        detail_link = f"https://vanbang.ut.edu.vn/tracuu/{href}"

                item = {
                    'so_hieu': cols[1].text.strip(),
                    'ho_ten': cols[2].text.strip(),
                    'gioi_tinh': cols[3].text.strip(),
                    'ngay_sinh': cols[4].text.strip(),
                    'noi_sinh': cols[5].text.strip(),
                    'nganh': cols[6].text.strip(),
                    'xep_loai': cols[7].text.strip(),
                    'so_vao_so': cols[8].text.strip(),
                    'link': detail_link
                }
                results.append(item)
        return results
    except Exception as e:
        logger.error(f"Loi khi parse HTML bang BeautifulSoup: {e}")
        return []


def query_degree_web(keyword):
    """Gửi request tới web trường bypass Cloudflare & Captcha"""
    scraper = cloudscraper.create_scraper()
    url = 'https://vanbang.ut.edu.vn/tracuu/'
    payload = {'he': '2', 'keyword': keyword, 'captcha': ''}
    return scraper.post(url, data=payload, timeout=30)


def format_degree_message(keyword, degrees, user_dob=""):
    """Định dạng kết quả trả về thành tin nhắn HTML"""
    msg = f"🔍 <b>KẾT QUẢ TRA CỨU VĂN BẰNG UTH</b>\n"
    msg += f"Từ khóa: <b>{keyword}</b>"
    if user_dob:
        msg += f" (Ngày sinh: <b>{user_dob}</b>)"
    msg += f"\nTìm thấy: <b>{len(degrees)}</b> kết quả khớp\n"
    msg += "───────────────────\n\n"

    for idx, deg in enumerate(degrees, 1):
        msg += f"<b>{idx}. Họ và tên: {deg['ho_ten']}</b>\n"
        msg += f"🎓 <b>Ngành học:</b> {deg['nganh']}\n"
        msg += f"🏆 <b>Xếp loại:</b> {deg['xep_loai']}\n"
        msg += f"🏷️ <b>Số hiệu bằng:</b> <code>{deg['so_hieu']}</code>\n"
        msg += f"📘 <b>Số vào sổ:</b> <code>{deg['so_vao_so']}</code>\n"
        msg += f"📅 <b>Ngày sinh:</b> {deg['ngay_sinh']} | <b>Nơi sinh:</b> {deg['noi_sinh']}\n"
        if deg['link']:
            msg += f"🔗 <a href='{deg['link']}'>Xem chi tiết trên Web</a>\n"
        msg += "───────────────────\n\n"

    return msg.strip()


# ============================================================
# CÁC XỬ LÝ LỆNH BOT (TELEGRAM TELEBOT HANDLERS)
# ============================================================

# --- Lệnh /start & Nút "❓ Hướng dẫn" ---
@bot.message_handler(commands=['start'])
@bot.message_handler(func=lambda m: m.text == "❓ Hướng dẫn")
def start_command(message):
    try:
        bot.send_message(
            message.chat.id,
            "👋 <b>Chào mừng bạn đến với Bot Tra Cứu Văn Bằng UTH!</b>\n\n"
            "📌 <b>Các lệnh khả dụng:</b>\n"
            "<code>/dangky Họ và Tên Ngày sinh</code> — Đăng ký tra cứu hằng ngày\n"
            "<code>/huy</code> — Hủy đăng ký theo dõi\n"
            "<code>/trangthai</code> — Kiểm tra trạng thái đăng ký\n"
            "<code>/kiemtra</code> — Tra cứu ngay lập tức từ khóa đã đăng ký\n"
            "<code>/kiemtra Họ và Tên</code> — Tra cứu nhanh một người bất kỳ\n\n"
            "Ví dụ:\n"
            "👉 Đăng ký: <code>/dangky Nguyễn Văn A 08/04/1999</code>\n"
            "👉 Tra nhanh: <code>/kiemtra Nguyễn Văn A</code>",
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        logger.error(f"[CMD /start] Loi gui tin: {e}")


# --- Lệnh /dangky ---
@bot.message_handler(commands=['dangky'])
def register_user(message):
    chat_id = str(message.chat.id)
    raw_text = message.text.replace('/dangky', '').strip()

    if not raw_text:
        bot.send_message(
            message.chat.id,
            "❌ Vui lòng nhập kèm họ tên.\nVí dụ: <code>/dangky Nguyễn Văn A 08/04/1999</code>",
            parse_mode='HTML',
            reply_markup=get_main_keyboard()
        )
        return

    keyword, dob = parse_register_text(raw_text)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO subscribers (chat_id, keyword, dob) VALUES (?, ?, ?)',
            (chat_id, keyword, dob)
        )
        conn.commit()
        conn.close()

        success_msg = f"✅ Đã đăng ký theo dõi hằng ngày cho từ khóa: <b>{keyword}</b>"
        if dob:
            success_msg += f" (Ngày sinh: <b>{dob}</b>)"
        success_msg += ".\nBot sẽ tự động thông báo ngay khi phát hiện văn bằng mới!"

        bot.send_message(message.chat.id, success_msg, parse_mode='HTML', reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"[CMD /dangky] Loi: {e}")
        bot.send_message(message.chat.id, "❌ Đã xảy ra lỗi, vui lòng thử lại sau.", reply_markup=get_main_keyboard())


# --- Lệnh /huy & Nút "❌ Hủy theo dõi" ---
@bot.message_handler(commands=['huy'])
@bot.message_handler(func=lambda m: m.text == "❌ Hủy theo dõi")
def unregister_user(message):
    chat_id = str(message.chat.id)

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM subscribers WHERE chat_id = ?', (chat_id,))
        deleted = cursor.rowcount
        conn.commit()
        conn.close()

        if deleted > 0:
            bot.send_message(message.chat.id, "✅ Đã hủy đăng ký theo dõi thành công.", reply_markup=get_main_keyboard())
        else:
            bot.send_message(message.chat.id, "⚠️ Bạn chưa đăng ký theo dõi từ khóa nào.", reply_markup=get_main_keyboard())
    except Exception as e:
        logger.error(f"[CMD /huy] Loi: {e}")
        bot.send_message(message.chat.id, "❌ Đã xảy ra lỗi, vui lòng thử lại sau.", reply_markup=get_main_keyboard())


# --- Lệnh /trangthai & Nút "📋 Trạng thái" ---
@bot.message_handler(commands=['trangthai'])
@bot.message_handler(func=lambda m: m.text == "📋 Trạng thái")
def check_status(message):
    chat_id = str(message.chat.id)

    try:
        conn = get_db_connection()
        user = conn.execute(
            'SELECT keyword, dob FROM subscribers WHERE chat_id = ?', (chat_id,)
        ).fetchone()
        conn.close()

        if user:
            status_msg = f"📋 Bạn đang theo dõi từ khóa: <b>{user['keyword']}</b>"
            if user['dob']:
                status_msg += f" (Ngày sinh: <b>{user['dob']}</b>)"
            status_msg += "\nBot sẽ tự động quét hằng ngày."
            bot.send_message(message.chat.id, status_msg, parse_mode='HTML', reply_markup=get_main_keyboard())
        else:
            bot.send_message(
                message.chat.id,
                "⚠️ Bạn chưa đăng ký theo dõi. Dùng lệnh <code>/dangky Họ Tên Ngày sinh</code> để đăng ký.",
                parse_mode='HTML',
                reply_markup=get_main_keyboard()
            )
    except Exception as e:
        logger.error(f"[CMD /trangthai] Loi: {e}")
        bot.send_message(message.chat.id, "❌ Đã xảy ra lỗi, vui lòng thử lại sau.", reply_markup=get_main_keyboard())


# --- Lệnh /kiemtra & Nút "🔍 Tra cứu ngay" ---
@bot.message_handler(commands=['kiemtra'])
@bot.message_handler(func=lambda m: m.text == "🔍 Tra cứu ngay")
def check_now(message):
    chat_id = str(message.chat.id)
    
    # Lấy text và lọc lệnh/nút bấm để lấy thông tin nhập kèm (nếu có)
    raw_text = message.text
    if raw_text.startswith('/kiemtra'):
        raw_text = raw_text.replace('/kiemtra', '').strip()
    elif raw_text == "🔍 Tra cứu ngay":
        raw_text = ""

    keyword = ""
    dob = ""

    if raw_text:
        # Kiểm tra nhanh (có tham số)
        keyword = raw_text
        dob = ""
        logger.info(f"[LỆNH /kiemtra nhanh] chat_id={chat_id}, keyword='{keyword}'")
    else:
        # Kiểm tra theo DB (nút bấm hoặc gõ /kiemtra trơn)
        try:
            conn = get_db_connection()
            user = conn.execute(
                'SELECT keyword, dob FROM subscribers WHERE chat_id = ?', (chat_id,)
            ).fetchone()
            conn.close()
            if user:
                keyword = user['keyword']
                dob = user['dob']
                logger.info(f"[LỆNH /kiemtra DB] chat_id={chat_id}, keyword='{keyword}', dob='{dob}'")
            else:
                bot.send_message(
                    message.chat.id,
                    "⚠️ Bạn chưa đăng ký theo dõi hằng ngày.\n"
                    "👉 Đăng ký: <code>/dangky Họ và Tên Ngày sinh</code>\n"
                    "👉 Tra nhanh: <code>/kiemtra Họ và Tên</code>",
                    parse_mode='HTML',
                    reply_markup=get_main_keyboard()
                )
                return
        except Exception as e:
            logger.error(f"[LỆNH /kiemtra] Loi doc DB: {e}")
            bot.send_message(message.chat.id, "❌ Đã xảy ra lỗi, vui lòng thử lại sau.", reply_markup=get_main_keyboard())
            return

    # Thông báo trạng thái đang tra cứu
    loading_text = f"🔍 Đang tra cứu dữ liệu cho từ khóa: <b>{keyword}</b>"
    if dob:
        loading_text += f" (Ngày sinh: <b>{dob}</b>)"
    loading_text += ". Vui lòng đợi..."

    status_msg = bot.send_message(message.chat.id, loading_text, parse_mode='HTML')

    try:
        response = query_degree_web(keyword)

        if "Just a moment..." in response.text:
            bot.edit_message_text(
                "⚠️ Hệ thống tra cứu của trường đang bận hoặc tạm thời không thể kết nối. Vui lòng thử lại sau.",
                chat_id=chat_id,
                message_id=status_msg.message_id
            )
        elif "Không tìm thấy" in response.text or "Không có dữ liệu" in response.text:
            bot.edit_message_text(
                f"❌ Không tìm thấy thông tin văn bằng cho từ khóa: <b>{keyword}</b>.",
                chat_id=chat_id,
                message_id=status_msg.message_id,
                parse_mode='HTML'
            )
        else:
            degrees = parse_results(response.text)
            if dob:
                degrees = [d for d in degrees if match_dob(dob, d['ngay_sinh'])]

            if degrees:
                formatted_msg = format_degree_message(keyword, degrees, dob)
                bot.delete_message(chat_id=chat_id, message_id=status_msg.message_id)
                bot.send_message(chat_id, formatted_msg, parse_mode='HTML', reply_markup=get_main_keyboard())
            else:
                bot.edit_message_text(
                    f"❌ Không tìm thấy thông tin văn bằng khớp với ngày sinh <b>{dob}</b> cho từ khóa <b>{keyword}</b>.",
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    parse_mode='HTML'
                )

    except Exception as e:
        logger.error(f"[CMD /kiemtra] Loi ket noi he thong truong: {e}")
        logger.error(traceback.format_exc())
        bot.edit_message_text(
            "❌ Đã xảy ra lỗi khi kết nối tới hệ thống. Vui lòng thử lại sau.",
            chat_id=chat_id,
            message_id=status_msg.message_id
        )


# ============================================================
# TIẾN TRÌNH QUÉT DỮ LIỆU TỰ ĐỘNG (SCANNING ENGINE)
# ============================================================

def scan_job():
    """Hàm quét chính được scheduler kích hoạt hằng ngày"""
    logger.info("=== BAT DAU QUET VAN BANG TU DONG HANG NGAY ===")

    try:
        conn = get_db_connection()
        users = conn.execute('SELECT chat_id, keyword, dob FROM subscribers').fetchall()
        conn.close()
    except Exception as e:
        logger.error(f"Loi doc Database quet tu dong: {e}")
        return

    if not users:
        logger.info("Khong co nguoi dung dang ky. Bo qua luot quet.")
        return

    for user in users:
        chat_id = user['chat_id']
        keyword = user['keyword']
        dob = user['dob']

        try:
            response = query_degree_web(keyword)

            if "Just a moment..." in response.text:
                logger.warning(f"Bi Cloudflare chan khi quet tu dong cho user {chat_id}")
                bot.send_message(
                    chat_id,
                    "⚠️ Hệ thống tra cứu của trường đang bận hoặc tạm thời không thể kết nối. Bot sẽ tự động thử lại vào ngày mai."
                )
            elif "Không tìm thấy" in response.text or "Không có dữ liệu" in response.text:
                logger.info(f"Ket qua tu dong '{keyword}': Chua co van bang.")
            else:
                degrees = parse_results(response.text)
                if dob:
                    degrees = [d for d in degrees if match_dob(dob, d['ngay_sinh'])]

                if degrees:
                    formatted_msg = format_degree_message(keyword, degrees, dob)
                    bot.send_message(
                        chat_id,
                        f"🎉 <b>THÔNG BÁO: ĐÃ TÌM THẤY DỮ LIỆU VĂN BẰNG MỚI!</b>\n\n{formatted_msg}",
                        parse_mode='HTML',
                        reply_markup=get_main_keyboard()
                    )
        except Exception as e:
            logger.error(f"Loi khi quet tu dong cho user {chat_id} (tu khoa '{keyword}'): {e}")

    logger.info("=== KET THUC LUOT QUET HANG NGAY ===")


# ============================================================
# BỘ LẬP LỊCH THỜI GIAN CHẠY NGẦM (BACKGROUND SCHEDULER)
# ============================================================

def run_scheduler():
    logger.info("Bo lap lich tu dong quet hang ngay da khoi dong.")
    schedule.every().day.at("08:00").do(scan_job)

    while True:
        schedule.run_pending()
        time.sleep(1)


# ============================================================
# KHỞI CHẠY BOT TREN VPS WINDOWS
# ============================================================

if __name__ == '__main__':
    # 1. Kích hoạt Scheduler trong background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

    logger.info("Bot dang khoi dong che do Long Polling...")
    print("-------------------------------------------------------------")
    print(">>> BOT TRA CUU VAN BANG UTH DANG CHAY 24/7 TREN VPS WINDOWS...")
    print(">>> Tu dong quet hang ngay luc 08:00 Sang.")
    print(">>> Hay tat cua so CMD nay neu muon dung Bot.")
    print("-------------------------------------------------------------")

    # 2. Chạy Long Polling ở luồng chính
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n👋 Bot da dung.")
    except Exception as e:
        logger.error(f"Bot gap su co dot ngot: {e}")
        logger.error(traceback.format_exc())
