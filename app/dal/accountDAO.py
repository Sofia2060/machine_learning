from app.connectors.connector import Connector


class accountDAO:
    # Truy xuất dữ liệu đăng nhập dùng chung cho Admin và User.
    # Thông tin đăng nhập nằm ở bảng cha accounts (role = 'Admin' / 'Customer'); bảng con employees / customers
    # liên kết 1-1 qua account_id. Mọi thao tác đăng nhập, khóa tạm, đổi mật khẩu đều làm trên bảng accounts.
    ROLES = {"Admin": "admin", "Customer": "user"}

    @staticmethod
    def findAccount(login):
        # Tìm theo tên đăng nhập hoặc email; trả về (role, dòng dữ liệu) hoặc (None, None).
        # Dòng dữ liệu có: account_id (bảng accounts), entity_id (employee_id hoặc customer_id) và thông tin hồ sơ
        conn = Connector()
        conn.connect()
        if not conn.isConnected():
            return ("error", None)
        sql = "select a.account_id, a.username, a.email, a.password_hash, a.full_name, a.role, a.is_active, " \
              "a.created_at, (a.locked_until is not null and a.locked_until>now()) as is_locked, " \
              "timestampdiff(second, now(), a.locked_until) as locked_seconds, " \
              "e.employee_id, c.customer_id, c.gender, c.age, c.occupation_id, c.zip_code " \
              "from accounts a left join employees e on e.account_id=a.account_id " \
              "left join customers c on c.account_id=a.account_id " \
              "where a.username=%s OR a.email=%s"
        df = conn.queryDataset(sql, (login, login))
        conn.disconnect()
        if df is None or len(df)==0:
            return (None, None)
        row = df.iloc[0].copy()
        role = accountDAO.ROLES.get(row["role"])
        entity = row["employee_id"] if role=="admin" else row["customer_id"]
        if role is None or entity is None or entity!=entity:
            # tài khoản chưa gắn với nhân viên / khách hàng nào -> coi như không tồn tại
            return (None, None)
        row["entity_id"] = int(entity)
        return (role, row)
    @staticmethod
    def registerFailed(account_id,max_fail,lock_minutes):
        # NFR-19: cộng số lần sai; đủ max_fail lần thì khóa tạm lock_minutes phút. Trả về số lần sai hiện tại
        conn = Connector()
        conn.connect()
        conn.executeNonQuery("update accounts set failed_login_count=failed_login_count+1 where account_id=%s",
                             (account_id,))
        df = conn.queryDataset("select failed_login_count from accounts where account_id=%s", (account_id,))
        count = int(df.iloc[0]["failed_login_count"])
        if count>=max_fail:
            conn.executeNonQuery("update accounts set failed_login_count=0, "
                                 "locked_until=date_add(now(), interval %s minute) where account_id=%s",
                                 (lock_minutes, account_id))
        conn.disconnect()
        return count
    @staticmethod
    def resetFailed(account_id):
        conn = Connector()
        conn.connect()
        conn.executeNonQuery("update accounts set failed_login_count=0, locked_until=null where account_id=%s",
                             (account_id,))
        conn.disconnect()
    @staticmethod
    def isUsernameExist(username):
        return accountDAO.exists("username", username)
    @staticmethod
    def isEmailExist(email,exclude_customer_id=None):
        return accountDAO.exists("email", email, exclude_customer_id)
    @staticmethod
    def exists(column,value,exclude_customer_id=None):
        # Tên đăng nhập và email là duy nhất trên toàn hệ thống (cột UNIQUE của bảng accounts, cả Admin và User)
        conn = Connector()
        conn.connect()
        sql = f"select a.account_id from accounts a left join customers c on c.account_id=a.account_id " \
              f"where a.{column}=%s"
        val = [value]
        if exclude_customer_id is not None:
            sql += " and (c.customer_id is null or c.customer_id<>%s)"
            val.append(exclude_customer_id)
        df = conn.queryDataset(sql, val)
        conn.disconnect()
        return df is not None and len(df)>0
    @staticmethod
    def findByEmail(email):
        (role,row) = accountDAO.findAccount(email)
        if row is None or row["email"]!=email:
            return (None, None)
        return (role, row)
    @staticmethod
    def setPasswordHash(account_id,password_hash):
        conn = Connector()
        conn.connect()
        ret = conn.executeNonQuery("update accounts set password_hash=%s, failed_login_count=0, locked_until=null "
                                   "where account_id=%s", (password_hash, account_id))
        conn.disconnect()
        return ret>0
