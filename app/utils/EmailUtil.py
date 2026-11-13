import smtplib
from email.mime.text import MIMEText

from app.utils.ConfigUtil import ConfigUtil

# Cấu hình Gmail gửi OTP trong config/config.json, mục "email".
# Bước 1: bật xác minh 2 bước cho tài khoản Gmail.
# Bước 2: vào https://myaccount.google.com/apppasswords tạo "App password" (16 ký tự).
# Bước 3: điền sender_email và app_password.
# Nếu để trống, hệ thống chạy chế độ DEMO: mã OTP hiện trên hộp thoại thay vì gửi email.
SENDER_EMAIL=ConfigUtil.get("email","sender_email","")
APP_PASSWORD=ConfigUtil.get("email","app_password","")


class EmailUtil:
    @staticmethod
    def isConfigured():
        return SENDER_EMAIL!="" and APP_PASSWORD!=""
    @staticmethod
    def sendOTP(receiver,otp):
        try:
            body=f"Mã OTP đặt lại mật khẩu CineMatch của bạn là: {otp}\n" \
                 f"Mã có hiệu lực trong {ConfigUtil.get('security','otp_expire_minutes',5)} phút và chỉ dùng được 1 lần."
            msg=MIMEText(body,"plain","utf-8")
            msg["Subject"]="CineMatch - Mã OTP đặt lại mật khẩu"
            msg["From"]=SENDER_EMAIL
            msg["To"]=receiver
            server=smtplib.SMTP("smtp.gmail.com",587,timeout=15)
            server.starttls()
            server.login(SENDER_EMAIL,APP_PASSWORD)
            server.sendmail(SENDER_EMAIL,[receiver],msg.as_string())
            server.quit()
            return True
        except Exception as e:
            print(str(e))
            return False
