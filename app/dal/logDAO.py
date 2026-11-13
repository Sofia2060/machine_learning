from app.connectors.connector import Connector


class logDAO:
    # NFR-23: nhật ký thao tác quản trị (loại thao tác, Admin, đối tượng, thời điểm, kết quả)
    LOCK_USER = "Khóa tài khoản"
    UNLOCK_USER = "Mở khóa tài khoản"
    RESET_PASSWORD = "Đặt lại mật khẩu"
    DELETE_MOVIE = "Xóa phim"
    HIDE_MOVIE = "Ẩn phim"
    DELETE_RATING = "Xóa đánh giá"
    INVALID_RATING = "Đánh dấu đánh giá không hợp lệ"
    CHANGE_MODEL = "Chuyển mô hình hoạt động"
    RETRAIN_MODEL = "Huấn luyện lại mô hình"
    IMPORT_DATA = "Nạp dữ liệu"

    @staticmethod
    def log(employee_id,action,target,result):
        conn = Connector()
        conn.connect()
        ret = conn.executeNonQuery("insert into admin_logs (employee_id,action,target,result) values (%s,%s,%s,%s)",
                                   (employee_id, action, str(target)[:255], str(result)[:255]))
        conn.disconnect()
        return ret>0
    @staticmethod
    def getLogs(action=None,limit=200):
        conn = Connector()
        conn.connect()
        sql = "select l.created_at, e.username, l.action, l.target, l.result from admin_logs l " \
              "join employees e on e.employee_id=l.employee_id "
        val = []
        if action is not None:
            sql += "where l.action=%s "
            val.append(action)
        sql += "order by l.log_id desc limit %s"
        df = conn.queryDataset(sql, val+[limit])
        conn.disconnect()
        return df
