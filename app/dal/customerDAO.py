from app.connectors.connector import Connector
from app.models.customer import Customer
from app.utils.SecurityUtil import SecurityUtil


class customerDAO:
    NOT_PROVIDED = "__not_provided__"
    COLUMNS = "customer_id, username, email, full_name, gender, age, occupation_id as occupation, zip_code, is_active, created_at"

    @staticmethod
    def convertToCustomer(row):
        cus=Customer()
        cus.customer_id=int(row["customer_id"])
        cus.username=row["username"]
        cus.email=row["email"]
        cus.full_name=row["full_name"]
        cus.gender=row["gender"]
        cus.age=None if row["age"] is None or row["age"]!=row["age"] else int(row["age"])
        # Mã nghề nghiệp MovieLens 0–20 (bảng occupations); đổi sang int để so khớp với dữ liệu của combobox
        cus.occupation=None if row["occupation"] is None or row["occupation"]!=row["occupation"] else int(row["occupation"])
        cus.zip_code=row["zip_code"]
        cus.is_active=int(row["is_active"])
        cus.created_at=row["created_at"]
        return cus
    @staticmethod
    def getById(customer_id):
        conn = Connector()
        conn.connect()
        df = conn.queryDataset(f"select {customerDAO.COLUMNS} from customers where customer_id=%s", (customer_id,))
        conn.disconnect()
        if df is None or len(df)==0:
            return None
        return customerDAO.convertToCustomer(df.iloc[0])
    @staticmethod
    def isActive(customer_id):
        # Dùng để chấm dứt phiên đang mở khi Admin khóa tài khoản (FR-21)
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select is_active from customers where customer_id=%s", (customer_id,))
        conn.disconnect()
        if df is None:
            return None          # mất kết nối CSDL: không kết luận
        return len(df)>0 and int(df.iloc[0]["is_active"])==1
    @staticmethod
    def register(cus,password):
        conn = Connector()
        conn.connect()
        # customer_id trong mrs_schema.sql không tự tăng -> cấp mã kế tiếp (lớn nhất + 1) ngay trong câu lệnh
        sql = "insert into customers (customer_id,username,email,password_hash,full_name,gender,age,occupation_id) " \
              "select coalesce(max(customer_id),0)+1,%s,%s,%s,%s,%s,%s,%s from customers"
        val = (cus.username, cus.email, SecurityUtil.hashPassword(password), cus.full_name,
               cus.gender, cus.age, cus.occupation)
        ret = conn.executeNonQuery(sql, val)
        new_id = None
        if ret>0:
            df = conn.queryDataset("select customer_id from customers where username=%s", (cus.username,))
            new_id = int(df.iloc[0]["customer_id"])
        conn.disconnect()
        return new_id
    @staticmethod
    def updateProfile(cus):
        # FR-05: email và tên đăng nhập không được đổi
        conn = Connector()
        conn.connect()
        sql = "update customers set full_name=%s, gender=%s, age=%s, occupation_id=%s where customer_id=%s"
        ret = conn.executeNonQuery(sql, (cus.full_name, cus.gender, cus.age, cus.occupation, cus.customer_id))
        conn.disconnect()
        return ret>=0
    @staticmethod
    def updateByAdmin(cus):
        # FR-21: Admin sửa thông tin quản lý (không xem/sửa mật khẩu gốc)
        conn = Connector()
        conn.connect()
        sql = "update customers set full_name=%s, email=%s, gender=%s, age=%s, occupation_id=%s, zip_code=%s " \
              "where customer_id=%s"
        ret = conn.executeNonQuery(sql, (cus.full_name, cus.email, cus.gender, cus.age, cus.occupation,
                                         cus.zip_code, cus.customer_id))
        conn.disconnect()
        return ret>=0
    @staticmethod
    def setPassword(customer_id,password):
        conn = Connector()
        conn.connect()
        sql = "update customers set password_hash=%s, failed_login_count=0, locked_until=null where customer_id=%s"
        ret = conn.executeNonQuery(sql, (SecurityUtil.hashPassword(password), customer_id))
        conn.disconnect()
        return ret>0
    @staticmethod
    def checkPassword(customer_id,password):
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select password_hash from customers where customer_id=%s", (customer_id,))
        conn.disconnect()
        return df is not None and len(df)>0 and SecurityUtil.checkPassword(password, df.iloc[0]["password_hash"])
    @staticmethod
    def setActive(customer_id,is_active):
        conn = Connector()
        conn.connect()
        sql = "update customers set is_active=%s, failed_login_count=0, locked_until=null where customer_id=%s"
        ret = conn.executeNonQuery(sql, (is_active, customer_id))
        conn.disconnect()
        return ret>0
    @staticmethod
    def getCustomers(keyword="",status=None,limit=50,offset=0,gender=None,age=None,occupation=None):
        conn = Connector()
        conn.connect()
        (where,val) = customerDAO.buildFilter(keyword,status,gender,age,occupation)
        sql = f"select c.customer_id, c.username, c.full_name, c.email, c.gender, c.age, c.occupation_id as occupation, c.is_active, " \
              f"c.created_at, (select count(*) from ratings r where r.customer_id=c.customer_id) as rating_count " \
              f"from customers c {where} order by c.customer_id limit %s offset %s"
        df = conn.queryDataset(sql, val+[limit, offset])
        conn.disconnect()
        return df
    @staticmethod
    def countCustomers(keyword="",status=None,gender=None,age=None,occupation=None):
        conn = Connector()
        conn.connect()
        (where,val) = customerDAO.buildFilter(keyword,status,gender,age,occupation)
        df = conn.queryDataset(f"select count(*) as n from customers c {where}", val)
        conn.disconnect()
        return 0 if df is None else int(df.iloc[0]["n"])
    @staticmethod
    def buildFilter(keyword,status,gender=None,age=None,occupation=None):
        # FR-21: lọc theo từ khóa, trạng thái, giới tính, nhóm tuổi, nghề nghiệp.
        # Giá trị NOT_PROVIDED = lọc các khách hàng chưa cung cấp thông tin đó
        conds=[]
        val=[]
        keyword=keyword.strip()
        if keyword!="":
            if keyword.isdigit():
                conds.append("(c.customer_id=%s OR c.username like %s)")
                val+=[int(keyword), f"%{keyword}%"]
            else:
                conds.append("(c.username like %s OR c.full_name like %s OR c.email like %s)")
                val+=[f"%{keyword}%"]*3
        if status is not None:
            conds.append("c.is_active=%s")
            val.append(status)
        for (column,value) in (("gender",gender),("age",age),("occupation_id",occupation)):
            if value is None:
                continue
            if value==customerDAO.NOT_PROVIDED:
                conds.append(f"(c.{column} is null or c.{column}='')" if column=="gender" else f"c.{column} is null")
            else:
                conds.append(f"c.{column}=%s")
                val.append(value)
        return ("where "+" AND ".join(conds) if conds else "", val)
    # ---------------- Thể loại yêu thích (FR-15) ----------------
    @staticmethod
    def getFavoriteGenreIds(customer_id):
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select genre_id from customer_genres where customer_id=%s", (customer_id,))
        conn.disconnect()
        return [] if df is None else [int(x) for x in df["genre_id"]]
    @staticmethod
    def saveFavoriteGenres(customer_id,genre_ids):
        conn = Connector()
        conn.connect()
        conn.executeNonQuery("delete from customer_genres where customer_id=%s", (customer_id,))
        ret = conn.executeMany("insert into customer_genres (customer_id,genre_id) values (%s,%s)",
                               [(customer_id, g) for g in genre_ids])
        conn.disconnect()
        return ret==len(genre_ids)
