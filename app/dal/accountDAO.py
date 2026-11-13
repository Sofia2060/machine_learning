from app.connectors.connector import Connector


class accountDAO:
    # Truy xuất dữ liệu đăng nhập dùng chung cho 2 bảng tài khoản: employees (Admin) và customers (User)
    TABLES = {"admin": ("employees", "employee_id"), "user": ("customers", "customer_id")}

    @staticmethod
    def findAccount(login):
        # Tìm theo tên đăng nhập hoặc email ở cả 2 bảng; trả về (role, dòng dữ liệu) hoặc (None, None)
        conn = Connector()
        conn.connect()
        if not conn.isConnected():
            return ("error", None)
        for (role,(table,key)) in accountDAO.TABLES.items():
            sql = f"select *, {key} as account_id, (locked_until is not null and locked_until>now()) as is_locked, " \
                  f"timestampdiff(second, now(), locked_until) as locked_seconds " \
                  f"from {table} where username=%s OR email=%s"
            df = conn.queryDataset(sql, (login, login))
            if df is not None and len(df)>0:
                conn.disconnect()
                return (role, df.iloc[0])
        conn.disconnect()
        return (None, None)
    @staticmethod
    def registerFailed(role,account_id,max_fail,lock_minutes):
        # NFR-19: cộng số lần sai; đủ max_fail lần thì khóa tạm lock_minutes phút. Trả về số lần sai hiện tại
        (table,key) = accountDAO.TABLES[role]
        conn = Connector()
        conn.connect()
        conn.executeNonQuery(f"update {table} set failed_login_count=failed_login_count+1 where {key}=%s", (account_id,))
        df = conn.queryDataset(f"select failed_login_count from {table} where {key}=%s", (account_id,))
        count = int(df.iloc[0]["failed_login_count"])
        if count>=max_fail:
            conn.executeNonQuery(f"update {table} set failed_login_count=0, "
                                 f"locked_until=date_add(now(), interval %s minute) where {key}=%s",
                                 (lock_minutes, account_id))
        conn.disconnect()
        return count
    @staticmethod
    def resetFailed(role,account_id):
        (table,key) = accountDAO.TABLES[role]
        conn = Connector()
        conn.connect()
        conn.executeNonQuery(f"update {table} set failed_login_count=0, locked_until=null where {key}=%s",
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
        # Tên đăng nhập và email là duy nhất trên toàn hệ thống (cả Admin và User)
        conn = Connector()
        conn.connect()
        df1 = conn.queryDataset(f"select employee_id from employees where {column}=%s", (value,))
        sql = f"select customer_id from customers where {column}=%s"
        val = [value]
        if exclude_customer_id is not None:
            sql += " and customer_id<>%s"
            val.append(exclude_customer_id)
        df2 = conn.queryDataset(sql, val)
        conn.disconnect()
        return (df1 is not None and len(df1)>0) or (df2 is not None and len(df2)>0)
    @staticmethod
    def findByEmail(email):
        (role,row) = accountDAO.findAccount(email)
        if row is None or row["email"]!=email:
            return (None, None)
        return (role, row)
    @staticmethod
    def setPasswordHash(role,account_id,password_hash):
        (table,key) = accountDAO.TABLES[role]
        conn = Connector()
        conn.connect()
        ret = conn.executeNonQuery(f"update {table} set password_hash=%s, failed_login_count=0, locked_until=null "
                                   f"where {key}=%s", (password_hash, account_id))
        conn.disconnect()
        return ret>0
