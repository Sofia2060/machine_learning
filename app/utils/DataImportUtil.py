import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from app.connectors.connector import Connector
from app.utils.CatalogUtil import CatalogUtil
from app.utils.SecurityUtil import SecurityUtil


class ImportResult:
    # Kết quả nạp 1 tệp (FR-23): số bản ghi thành công, trùng ID bị bỏ qua, lỗi và lý do
    def __init__(self,name):
        self.name=name
        self.total=0
        self.success=0
        self.duplicate=0
        self.error=0
        self.reasons={}       # lý do -> [số lượng, dòng ví dụ]
        self.interrupted=False
    def addError(self,reason,line_no):
        self.error+=1
        if reason not in self.reasons:
            self.reasons[reason]=[0,line_no]
        self.reasons[reason][0]+=1


class DataImportUtil:
    # Dùng chung cho script import_data.py và màn hình Nạp dữ liệu của Admin
    DEFAULT_PASSWORD = "123456"     # cùng mật khẩu mặc định với src/database.py
    BATCH = 5000

    @staticmethod
    def readLines(path):
        # Tệp MovieLens 1M dùng mã hóa latin-1, ngăn cách bằng "::"
        with open(path,encoding="latin-1") as f:
            return [line.rstrip("\n").rstrip("\r") for line in f]
    @staticmethod
    def insertRows(conn,sql,rows,result):
        # Ghi theo lô; lô lỗi thì ghi lại từng dòng để chỉ bỏ qua đúng bản ghi lỗi (NFR-27)
        if len(rows)==0:
            return
        values=[r[1] for r in rows]
        ret=conn.executeMany(sql,values)
        if ret>=0:
            result.success+=len(rows)
            return
        for (line_no,value) in rows:
            if conn.executeNonQuery(sql,value)>0:
                result.success+=1
            else:
                result.addError("Ghi vào CSDL thất bại",line_no)
    # ---------------------------------------------------------------- employees
    @staticmethod
    def ensureAdmin(conn,username,email,full_name,password):
        # Không tạo trùng tài khoản Admin mặc định khi chạy nạp nhiều lần (FR-23)
        df=conn.queryDataset("select employee_id from employees where username=%s or email=%s",(username,email))
        if df is not None and len(df)>0:
            return False
        sql="insert into employees (username,email,password_hash,full_name) values (%s,%s,%s,%s)"
        return conn.executeNonQuery(sql,(username,email,SecurityUtil.hashPassword(password),full_name))>0
    # ---------------------------------------------------------------- genres
    @staticmethod
    def ensureGenres(conn):
        conn.executeMany("insert ignore into genres (genre_name) values (%s)",[(g,) for g in CatalogUtil.GENRES])
        df=conn.queryDataset("select genre_id, genre_name from genres")
        return dict(zip(df["genre_name"],df["genre_id"]))
    # ---------------------------------------------------------------- movies
    @staticmethod
    def importMovies(path,progress=None,stop=None):
        result=ImportResult("movies.dat")
        conn=Connector()
        conn.connect()
        genre_ids=DataImportUtil.ensureGenres(conn)
        df=conn.queryDataset("select movie_id from movies")
        existing=set(int(x) for x in df["movie_id"])
        lines=DataImportUtil.readLines(path)
        movies=[]
        movie_genres=[]
        for (i,line) in enumerate(lines):
            if line.strip()=="":
                continue
            result.total+=1
            line_no=i+1
            parts=line.split("::")
            if len(parts)!=3:
                result.addError("Sai cấu trúc (cần MovieID::Title::Genres)",line_no)
                continue
            (movie_id,title,genres)=parts
            if not movie_id.isdigit() or int(movie_id)<=0:
                result.addError("MovieID không hợp lệ",line_no)
                continue
            movie_id=int(movie_id)
            if title.strip()=="":
                result.addError("Thiếu tên phim",line_no)
                continue
            genre_list=[g for g in genres.split("|") if g!=""]
            if len(genre_list)==0 or any(g not in genre_ids for g in genre_list):
                result.addError("Thể loại không thuộc danh mục 18 thể loại",line_no)
                continue
            if movie_id in existing:
                result.duplicate+=1
                continue
            existing.add(movie_id)
            # Như src/database.py: tên phim lưu không kèm năm, năm phát hành tách ra cột release_year
            year=re.search(r"\((\d{4})\)\s*$",title)
            clean=re.sub(r"\s*\(\d{4}\)\s*$","",title).strip() or title.strip()
            movies.append((line_no,(movie_id,clean,int(year.group(1)) if year else None)))
            movie_genres+=[(movie_id,genre_ids[g]) for g in genre_list]
        sql="insert into movies (movie_id,title,release_year) values (%s,%s,%s)"
        for start in range(0,len(movies),DataImportUtil.BATCH):
            if stop is not None and stop():
                result.interrupted=True
                break
            DataImportUtil.insertRows(conn,sql,movies[start:start+DataImportUtil.BATCH],result)
            if progress is not None:
                progress(min(start+DataImportUtil.BATCH,len(movies)),len(movies))
        conn.executeMany("insert ignore into movie_genres (movie_id,genre_id) values (%s,%s)",movie_genres)
        conn.disconnect()
        return result
    # ---------------------------------------------------------------- customers
    @staticmethod
    def importUsers(path,progress=None,stop=None):
        result=ImportResult("users.dat")
        conn=Connector()
        conn.connect()
        df=conn.queryDataset("select customer_id, username, email from customers")
        existing=set(int(x) for x in df["customer_id"])
        used_names=set(df["username"])
        used_emails=set(df["email"])
        lines=DataImportUtil.readLines(path)
        valid=[]
        for (i,line) in enumerate(lines):
            if line.strip()=="":
                continue
            result.total+=1
            line_no=i+1
            parts=line.split("::")
            if len(parts)!=5:
                result.addError("Sai cấu trúc (cần UserID::Gender::Age::Occupation::Zip-code)",line_no)
                continue
            (user_id,gender,age,occupation,zip_code)=parts
            if not user_id.isdigit() or int(user_id)<=0:
                result.addError("UserID không hợp lệ",line_no)
                continue
            user_id=int(user_id)
            if gender not in ("M","F"):
                result.addError("Giới tính không hợp lệ (chỉ M/F)",line_no)
                continue
            if not age.isdigit() or int(age) not in CatalogUtil.AGE_GROUPS:
                result.addError("Mã nhóm tuổi không hợp lệ",line_no)
                continue
            if not occupation.isdigit() or not 0<=int(occupation)<len(CatalogUtil.OCCUPATIONS):
                result.addError("Mã nghề nghiệp không hợp lệ (0–20)",line_no)
                continue
            if user_id in existing:
                result.duplicate+=1
                continue
            # Cùng quy ước với src/database.py: user_<id>, user_<id>@gmail.com
            username=f"user_{user_id}"
            email=f"user_{user_id}@gmail.com"
            if username in used_names or email in used_emails:
                result.addError("Tên đăng nhập/email tạo tự động đã được tài khoản khác dùng",line_no)
                continue
            existing.add(user_id)
            used_names.add(username)
            used_emails.add(email)
            valid.append((line_no,user_id,username,email,"Male" if gender=="M" else "Female",int(age),
                          int(occupation),zip_code.strip()))
        # Mỗi tài khoản có salt riêng nên phải băm từng mật khẩu; băm song song để nạp nhanh hơn
        with ThreadPoolExecutor(max_workers=max(2,os.cpu_count() or 2)) as executor:
            hashes=list(executor.map(lambda r: SecurityUtil.hashPassword(DataImportUtil.DEFAULT_PASSWORD),valid))
        rows=[(r[0],(r[1],r[2],r[3],hashes[k],None,r[4],r[5],r[6],r[7]))
              for (k,r) in enumerate(valid)]
        sql="insert into customers (customer_id,username,email,password_hash,full_name,gender,age,occupation_id,zip_code) " \
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s)"
        for start in range(0,len(rows),DataImportUtil.BATCH):
            if stop is not None and stop():
                result.interrupted=True
                break
            DataImportUtil.insertRows(conn,sql,rows[start:start+DataImportUtil.BATCH],result)
            if progress is not None:
                progress(min(start+DataImportUtil.BATCH,len(rows)),len(rows))
        conn.disconnect()
        return result
    # ---------------------------------------------------------------- ratings
    @staticmethod
    def importRatings(path,progress=None,stop=None):
        result=ImportResult("ratings.dat")
        conn=Connector()
        conn.connect()
        customers=set(int(x) for x in conn.queryDataset("select customer_id from customers")["customer_id"])
        movies=set(int(x) for x in conn.queryDataset("select movie_id from movies")["movie_id"])
        df=conn.queryDataset("select customer_id*100000+movie_id as k from ratings")
        existing=set(int(x) for x in df["k"])
        lines=DataImportUtil.readLines(path)
        rows=[]
        for (i,line) in enumerate(lines):
            if line.strip()=="":
                continue
            result.total+=1
            line_no=i+1
            parts=line.split("::")
            if len(parts)!=4 or not all(p.strip().isdigit() for p in parts):
                result.addError("Sai cấu trúc (cần UserID::MovieID::Rating::Timestamp)",line_no)
                continue
            (user_id,movie_id,score,ts)=(int(p) for p in parts)
            if not 1<=score<=5:
                result.addError("Điểm đánh giá ngoài khoảng 1–5",line_no)
                continue
            if user_id not in customers:
                result.addError("UserID chưa có trong bảng khách hàng",line_no)
                continue
            if movie_id not in movies:
                result.addError("MovieID chưa có trong bảng phim",line_no)
                continue
            key=user_id*100000+movie_id
            if key in existing:
                result.duplicate+=1
                continue
            existing.add(key)
            rows.append((line_no,(user_id,movie_id,score,datetime.fromtimestamp(ts))))
        sql="insert into ratings (customer_id,movie_id,rating_score,rating_time) values (%s,%s,%s,%s)"
        step=20000
        for start in range(0,len(rows),step):
            if stop is not None and stop():
                result.interrupted=True
                break
            DataImportUtil.insertRows(conn,sql,rows[start:start+step],result)
            if progress is not None:
                progress(min(start+step,len(rows)),len(rows))
        DataImportUtil.refreshMovieStats(conn)
        conn.disconnect()
        return result
    @staticmethod
    def refreshMovieStats(conn,movie_id=None):
        # Tính lại điểm TB và số lượt đánh giá hợp lệ của phim (đánh giá không hợp lệ bị loại, FR-22)
        where="" if movie_id is None else " where m.movie_id=%s"
        sql="update movies m left join (select movie_id, avg(rating_score) as a, count(*) as c from ratings " \
            "where is_valid=1" + ("" if movie_id is None else " and movie_id=%s") + " group by movie_id) s " \
            "on m.movie_id=s.movie_id set m.avg_rating=round(s.a,3), m.rating_count=coalesce(s.c,0)" + where
        val=None if movie_id is None else (movie_id,movie_id)
        return conn.executeNonQuery(sql,val)
