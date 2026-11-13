from app.connectors.connector import Connector


class SchemaUtil:
    # CSDL movie_recommender_system do mysql/mrs_schema.sql + src/database.py tạo (8 bảng theo ERD).
    # Phần mềm cần thêm một số cột/bảng hỗ trợ cho các yêu cầu FR/NFR. SchemaUtil chỉ THÊM những gì còn thiếu,
    # không đổi tên, không xóa, không sửa dữ liệu sẵn có của 8 bảng gốc; chạy lại nhiều lần vẫn an toàn.
    COLUMNS = [
        ("customers", "full_name", "VARCHAR(100) NULL"),                              # FR-01, FR-05 họ tên
        ("customers", "failed_login_count", "INT NOT NULL DEFAULT 0"),                # NFR-19 khóa tạm 15 phút
        ("customers", "locked_until", "DATETIME NULL"),
        ("employees", "failed_login_count", "INT NOT NULL DEFAULT 0"),
        ("employees", "locked_until", "DATETIME NULL"),
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
        "customer_genres": """create table customer_genres (
            customer_id INT NOT NULL,
            genre_id INT NOT NULL,
            PRIMARY KEY (customer_id, genre_id),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
            FOREIGN KEY (genre_id) REFERENCES genres(genre_id) ON DELETE CASCADE)""",
        "otp_codes": """create table otp_codes (
            otp_id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(100) NOT NULL,
            otp_code CHAR(6) NOT NULL,
            expired_at DATETIME NOT NULL,
            is_used TINYINT(1) NOT NULL DEFAULT 0,
            wrong_count INT NOT NULL DEFAULT 0,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_otp_email (email, is_used))""",
        "admin_logs": """create table admin_logs (
            log_id INT AUTO_INCREMENT PRIMARY KEY,
            employee_id INT NOT NULL,
            action VARCHAR(50) NOT NULL,
            target VARCHAR(255) NOT NULL,
            result VARCHAR(255) NOT NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            KEY idx_logs_time (created_at),
            FOREIGN KEY (employee_id) REFERENCES employees(employee_id))""",
        "model_registry": """create table model_registry (
            model_id INT AUTO_INCREMENT PRIMARY KEY,
            model_name VARCHAR(50) NOT NULL,
            file_name VARCHAR(255) NOT NULL,
            file_hash CHAR(64) NOT NULL,
            calibration LONGTEXT NOT NULL,
            n_users INT NULL,
            n_items INT NULL,
            n_ratings INT NULL,
            exported_at DATETIME NULL,
            is_active TINYINT(1) NOT NULL DEFAULT 0,
            employee_id INT NULL,
            registered_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)""",
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
        conn.disconnect()
        existing=set() if cols is None else set(zip(cols.iloc[:,0].str.lower(),cols.iloc[:,1].str.lower()))
        tables=set(t for (t,c) in existing)
        missing=[f"bảng {t}" for t in ("customers","movies","ratings","recommendations") if t not in tables]
        if missing:
            return missing
        missing+=[f"{t}.{c}" for (t,c,d) in SchemaUtil.COLUMNS if (t,c) not in existing]
        missing+=[f"bảng {t}" for t in SchemaUtil.TABLES if t not in tables]
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
        for table in ("customers","employees","movies","genres","movie_genres","ratings","recommendations"):
            if not tableExists(table):
                log(f"CSDL {db} chưa có bảng {table}. Hãy chạy mysql/mrs_schema.sql rồi python src/database.py trước.")
                conn.disconnect()
                return False
        for (table,column,definition) in SchemaUtil.COLUMNS:
            if not columnExists(table,column):
                conn.executeNonQuery(f"alter table {table} add column {column} {definition}")
                log(f"   + thêm cột {table}.{column}")
        for (table,sql) in SchemaUtil.TABLES.items():
            if not tableExists(table):
                conn.executeNonQuery(sql)
                log(f"   + tạo bảng {table}")
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
