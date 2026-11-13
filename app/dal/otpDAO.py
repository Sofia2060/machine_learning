from app.connectors.connector import Connector
from app.utils.ConfigUtil import ConfigUtil


class otpDAO:
    # NFR-18: OTP 6 số, hết hạn sau 5 phút, dùng 1 lần, sai 5 lần thì khóa luồng xác minh
    MAX_WRONG = int(ConfigUtil.get("security","otp_max_wrong",5))
    EXPIRE_MINUTES = int(ConfigUtil.get("security","otp_expire_minutes",5))

    @staticmethod
    def createOTP(email,otp):
        conn = Connector()
        conn.connect()
        # Vô hiệu các mã cũ chưa dùng của email này
        conn.executeNonQuery("update otp_codes set is_used=1 where email=%s AND is_used=0", (email,))
        sql = "insert into otp_codes (email,otp_code,expired_at) " \
              f"values (%s,%s,date_add(now(), interval {otpDAO.EXPIRE_MINUTES} minute))"
        ret = conn.executeNonQuery(sql, (email, otp))
        conn.disconnect()
        return ret>0
    @staticmethod
    def getRemainingSeconds(email):
        # Số giây còn lại của mã OTP mới nhất (đồng hồ đếm ngược trên giao diện)
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select greatest(timestampdiff(second, now(), expired_at),0) as s from otp_codes "
                               "where email=%s AND is_used=0 order by otp_id desc limit 1", (email,))
        conn.disconnect()
        if df is None or len(df)==0:
            return 0
        return int(df.iloc[0]["s"])
    @staticmethod
    def verifyOTP(email,otp):
        # Trả về (True/False, thông báo)
        conn = Connector()
        conn.connect()
        sql = "select otp_id, otp_code, wrong_count, (expired_at<now()) as is_expired from otp_codes " \
              "where email=%s AND is_used=0 order by otp_id desc limit 1"
        df = conn.queryDataset(sql, (email,))
        if df is None or len(df)==0:
            conn.disconnect()
            return False,"Mã OTP không còn hiệu lực. Vui lòng bấm \"Gửi lại mã\"."
        row = df.iloc[0]
        otp_id = int(row["otp_id"])
        if int(row["is_expired"])==1:
            conn.executeNonQuery("update otp_codes set is_used=1 where otp_id=%s", (otp_id,))
            conn.disconnect()
            return False,f"Mã OTP đã hết hạn ({otpDAO.EXPIRE_MINUTES} phút). Vui lòng bấm \"Gửi lại mã\"."
        if row["otp_code"]!=otp:
            wrong = int(row["wrong_count"])+1
            if wrong>=otpDAO.MAX_WRONG:
                conn.executeNonQuery("update otp_codes set wrong_count=%s, is_used=1 where otp_id=%s",
                                     (wrong, otp_id))
                conn.disconnect()
                return False,f"Bạn đã nhập sai {otpDAO.MAX_WRONG} lần, luồng xác minh bị khóa. Vui lòng bấm \"Gửi lại mã\" để nhận mã mới."
            conn.executeNonQuery("update otp_codes set wrong_count=%s where otp_id=%s", (wrong, otp_id))
            conn.disconnect()
            return False,f"Mã OTP không đúng (còn {otpDAO.MAX_WRONG-wrong} lần thử)."
        conn.executeNonQuery("update otp_codes set is_used=1 where otp_id=%s", (otp_id,))
        conn.disconnect()
        return True,"OK"
