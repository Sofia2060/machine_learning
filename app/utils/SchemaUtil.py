from app.connectors.connector import Connector


class SchemaUtil:
    # CSDL movie_recommender_system do mysql/mrs_schema.sql (13 bảng theo ERD) + src/database.py tạo.
    # Bảng cha accounts giữ thông tin đăng nhập; customers / employees là bảng con 1-1 qua account_id.
    # SchemaUtil chỉ kiểm tra và THÊM những gì còn thiếu (CSDL tạo từ bản schema cũ hơn), không sửa dữ liệu sẵn có;
    # chạy lại nhiều lần vẫn an toàn.
    REQUIRED_TABLES = ("accounts","customers","employees","movies","genres","movie_genres","ratings","recommendations")
    COLUMNS = [
        ("movies", "avg_rating", "DECIMAL(4,3) NULL"),                                # NFR-04 số liệu tính sẵn
        ("movies", "rating_count", "INT NOT NULL DEFAULT 0"),
        ("ratings", "is_valid", "TINYINT(1) NOT NULL DEFAULT 1"),                    # FR-22 đánh dấu không hợp lệ
        ("recommendations", "model_name", "VARCHAR(30) NULL"),                        # FR-19 thống kê theo mô hình
    ]
    INDEXES = [
        ("ratings", "idx_ratings_stats", "(is_valid, rating_time, rating_score, customer_id, movie_id)"),
        ("ratings", "idx_ratings_movie", "(movie_id, is_valid, rating_score)"),
        ("movies", "idx_movies_stats", "(is_hidden, rating_count)"),
        ("movies", "idx_movies_year", "(release_year)"),
        ("recommendations", "idx_rec_customer", "(customer_id, created_at)"),
        ("recommendations", "idx_rec_time", "(created_at)"),
        ("customers", "idx_customers_demo", "(gender, age)"),
    ]
    TABLES = {
        # Giống hệt định nghĩa trong mysql/mrs_schema.sql (dùng khi CSDL được tạo từ bản schema cũ chưa có bảng)
        "customer_genres": """create table customer_genres (
            customer_id INT NOT NULL,
            genre_id INT NOT NULL,
            PRIMARY KEY (customer_id, genre_id),
            CONSTRAINT fk_customer_genres_customer FOREIGN KEY (customer_id)
                REFERENCES customers(customer_id) ON DELETE CASCADE,
            CONSTRAINT fk_customer_genres_genre FOREIGN KEY (genre_id)
                REFERENCES genres(genre_id) ON DELETE CASCADE)""",
        "otp_codes": """create table otp_codes (
            otp_id INT PRIMARY KEY AUTO_INCREMENT,
            account_id INT NOT NULL,
            otp_code CHAR(6) NOT NULL,
            expired_at DATETIME NOT NULL,
            is_used BOOLEAN NOT NULL DEFAULT FALSE,
            wrong_count INT NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_otp_account (account_id, is_used),
            CONSTRAINT chk_otp_wrong_count CHECK (wrong_count >= 0),
            CONSTRAINT fk_otp_codes_account FOREIGN KEY (account_id)
                REFERENCES accounts(account_id) ON DELETE CASCADE)""",
        "admin_logs": """create table admin_logs (
            log_id INT PRIMARY KEY AUTO_INCREMENT,
            employee_id INT NOT NULL,
            action VARCHAR(50) NOT NULL,
            target VARCHAR(255) NOT NULL,
            result VARCHAR(255) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_logs_time (created_at),
            CONSTRAINT fk_admin_logs_employee FOREIGN KEY (employee_id)
                REFERENCES employees(employee_id) ON DELETE CASCADE)""",
        "model_registry": """create table model_registry (
            model_id INT PRIMARY KEY AUTO_INCREMENT,
            model_name VARCHAR(50) NOT NULL,
            file_name VARCHAR(255) NOT NULL,
            file_hash CHAR(64) NOT NULL,
            n_users INT DEFAULT NULL,
            n_items INT DEFAULT NULL,
            n_ratings INT DEFAULT NULL,
            exported_at DATETIME DEFAULT NULL,
            is_active BOOLEAN NOT NULL DEFAULT FALSE,
            employee_id INT DEFAULT NULL,
            registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_model_registry_employee FOREIGN KEY (employee_id)
                REFERENCES employees(employee_id) ON DELETE SET NULL)""",
    }
    SAMPLE_MODEL_NAME = "Dữ liệu mẫu"

    @staticmethod
    def missingParts():
        # Trả về danh sách phần còn thiếu (rỗng = đã đủ), hoặc None nếu không kết nối được CSDL
        conn=Connector()
        conn.connect()
        if not conn.isConnected():
            return None
        db=conn.queryDataset("select database() as db").iloc[0]["db"]
        cols=conn.queryDataset("select table_name, column_name from information_schema.columns where table_schema=%s",(db,))
        existing=set() if cols is None else set(zip(cols.iloc[:,0].str.lower(),cols.iloc[:,1].str.lower()))
        tables=set(t for (t,c) in existing)
        missing=[f"bảng {t}" for t in SchemaUtil.REQUIRED_TABLES if t not in tables]
        if missing:
            conn.disconnect()
            return missing
        missing+=[f"{t}.{c}" for (t,c,d) in SchemaUtil.COLUMNS if (t,c) not in existing]
        missing+=[f"bảng {t}" for t in SchemaUtil.TABLES if t not in tables]
        # Bảng đã đủ (vd. tạo sẵn bằng mrs_schema.sql) nhưng chưa có mô hình đang hoạt động -> vẫn chạy setup để đăng ký mô hình
        # Cột calibration (quy đổi điểm sang số sao) của phiên bản cũ không còn dùng -> chạy setup để xóa
        # otp_codes của bản cũ gắn theo email -> bản mới gắn theo account_id (khóa ngoại tới accounts)
        if "otp_codes" in tables and ("otp_codes","account_id") not in existing:
            missing.append("bảng otp_codes chưa liên kết accounts")
        if ("model_registry","calibration") in existing:
            missing.append("cột model_registry.calibration không còn dùng")
        if "model_registry" in tables:
            df=conn.queryDataset("select count(*) as n from model_registry where is_active=1")
            if df is None or int(df.iloc[0]["n"])==0:
                missing.append("mô hình gợi ý chưa được đăng ký")
        conn.disconnect()
        return missing
    @staticmethod
    def ensureSchema(log=print):
        conn=Connector()
        conn.connect()
        if not conn.isConnected():
            log("Không kết nối được MySQL. Kiểm tra MySQL đã chạy và mục \"database\" trong app/config/config.json")
            return False
        db=conn.queryDataset("select database() as db").iloc[0]["db"]
        def columnExists(table,column):
            df=conn.queryDataset("select count(*) as n from information_schema.columns "
                                 "where table_schema=%s and table_name=%s and column_name=%s",(db,table,column))
            return df is not None and int(df.iloc[0]["n"])>0
        def indexExists(table,index):
            df=conn.queryDataset("select count(*) as n from information_schema.statistics "
                                 "where table_schema=%s and table_name=%s and index_name=%s",(db,table,index))
            return df is not None and int(df.iloc[0]["n"])>0
        def tableExists(table):
            df=conn.queryDataset("select count(*) as n from information_schema.tables where table_schema=%s and table_name=%s",
                                 (db,table))
            return df is not None and int(df.iloc[0]["n"])>0
        for table in SchemaUtil.REQUIRED_TABLES:
            if not tableExists(table):
                log(f"CSDL {db} chưa có bảng {table} (CSDL tạo từ bản schema cũ hoặc chưa tạo). "
                    f"Hãy chạy lại mysql/mrs_schema.sql rồi python src/database.py.")
                conn.disconnect()
                return False
        if tableExists("otp_codes") and not columnExists("otp_codes","account_id"):
            # Mã OTP chỉ là dữ liệu tạm (hết hạn sau 5 phút) nên tạo lại bảng theo cấu trúc mới là an toàn
            conn.executeNonQuery("drop table otp_codes")
            log("   - tạo lại bảng otp_codes theo cấu trúc mới (liên kết accounts.account_id)")
        for (table,column,definition) in SchemaUtil.COLUMNS:
            if not columnExists(table,column):
                conn.executeNonQuery(f"alter table {table} add column {column} {definition}")
                log(f"   + thêm cột {table}.{column}")
        for (table,sql) in SchemaUtil.TABLES.items():
            if not tableExists(table):
                conn.executeNonQuery(sql)
                log(f"   + tạo bảng {table}")
        if columnExists("model_registry","calibration"):
            # Phiên bản cũ lưu bảng quy đổi điểm -> số sao; nay hệ thống chỉ gợi ý Top-N kèm độ phù hợp (%) nên bỏ cột
            conn.executeNonQuery("alter table model_registry drop column calibration")
            log("   - xóa cột model_registry.calibration (không còn quy đổi sang số sao)")
        for (table,index,columns) in SchemaUtil.INDEXES:
            if not indexExists(table,index):
                log(f"   + tạo chỉ mục {index} (bảng {table}) ...")
                conn.executeNonQuery(f"create index {index} on {table} {columns}")
        # Gợi ý mẫu do src/database.py sinh ngẫu nhiên: gắn nhãn để Admin lọc riêng ở trang Hiệu quả gợi ý
        conn.executeNonQuery("update recommendations set model_name=%s where model_name is null",(SchemaUtil.SAMPLE_MODEL_NAME,))
        df=conn.queryDataset("select count(*) as n from movies where rating_count=0 and exists "
                             "(select 1 from ratings r where r.movie_id=movies.movie_id)")
        if df is not None and int(df.iloc[0]["n"])>0:
            from app.utils.DataImportUtil import DataImportUtil
            log("   + tính điểm trung bình và số lượt đánh giá của từng phim ...")
            DataImportUtil.refreshMovieStats(conn)
        conn.disconnect()
        return True
