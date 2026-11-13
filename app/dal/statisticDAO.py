from app.connectors.connector import Connector


class statisticDAO:
    # Số liệu tổng hợp cho Dashboard (FR-17, FR-18). Chỉ tính đánh giá hợp lệ (is_valid=1); bộ lọc duy nhất là
    # khoảng thời gian [date_from, date_to) trên rating_time. Không trả về thông tin nhận dạng cá nhân (NFR-22).

    @staticmethod
    def query(sql,val=None):
        conn = Connector()
        conn.connect()
        df = conn.queryDataset(sql, val)
        conn.disconnect()
        return df
    @staticmethod
    def hasFilter(date_from,date_to):
        return date_from is not None or date_to is not None
    @staticmethod
    def buildFilter(date_from=None,date_to=None,alias="r"):
        conds=[f"{alias}.is_valid=1"]
        val=[]
        if date_from is not None:
            conds.append(f"{alias}.rating_time>=%s")
            val.append(date_from)
        if date_to is not None:
            conds.append(f"{alias}.rating_time<%s")
            val.append(date_to)
        return ("where "+" AND ".join(conds), val)
    @staticmethod
    def getRatingTimeRange():
        df = statisticDAO.query("select min(rating_time) as d1, max(rating_time) as d2 from ratings where is_valid=1")
        if df is None or df.iloc[0]["d1"] is None:
            return (None, None)
        return (df.iloc[0]["d1"], df.iloc[0]["d2"])
    @staticmethod
    def getMonthlyScores(date_from=None,date_to=None):
        # Một lần quét chỉ mục cho cả phân bố điểm (FR-18 mục 1) và xu hướng theo tháng (FR-18 mục 5)
        (where,val) = statisticDAO.buildFilter(date_from,date_to)
        sql = "select extract(year_month from r.rating_time) as ym, r.rating_score as rating, count(*) as total " \
              f"from ratings r {where} group by ym, r.rating_score"
        return statisticDAO.query(sql, val)
    @staticmethod
    def getCustomerAggregates(date_from=None,date_to=None):
        # Gộp theo khách hàng trước (dùng chỉ mục bao phủ) rồi mới nối bảng customers:
        # một truy vấn phục vụ cả biểu đồ tuổi, giới tính, nghề nghiệp và mức độ hoạt động
        (where,val) = statisticDAO.buildFilter(date_from,date_to)
        sql = "select c.gender, c.age, c.occupation_id as occupation, s.total, s.score_sum from (select r.customer_id, count(*) as total, " \
              f"sum(r.rating_score) as score_sum from ratings r {where} group by r.customer_id) s " \
              "join customers c on c.customer_id=s.customer_id"
        return statisticDAO.query(sql, val)
    @staticmethod
    def getMovieAggregates(date_from=None,date_to=None):
        # Gộp theo phim: phục vụ biểu đồ thể loại, phim nổi bật và mức độ quan tâm tới từng phim
        (where,val) = statisticDAO.buildFilter(date_from,date_to)
        sql = "select m.movie_id, m.title, m.is_hidden, s.total, s.score_sum from (select r.movie_id, count(*) as total, " \
              f"sum(r.rating_score) as score_sum from ratings r {where} group by r.movie_id) s " \
              "join movies m on m.movie_id=s.movie_id"
        return statisticDAO.query(sql, val)
    @staticmethod
    def getMovieGenres():
        return statisticDAO.query("select mg.movie_id, g.genre_name from movie_genres mg join genres g on g.genre_id=mg.genre_id")
