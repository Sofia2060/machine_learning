from app.connectors.connector import Connector


class recommendationDAO:
    # ---------------- Lưu lịch sử gợi ý (FR-16) ----------------
    @staticmethod
    def getLastList(customer_id):
        # Danh sách gợi ý gần nhất của khách hàng: [(movie_id, rank, điểm)] theo thứ hạng
        conn = Connector()
        conn.connect()
        sql = "select movie_id, rank_position, predicted_score as predicted_rating, model_name from recommendations " \
              "where customer_id=%s and created_at=(select max(created_at) from recommendations where customer_id=%s) " \
              "order by rank_position"
        df = conn.queryDataset(sql, (customer_id, customer_id))
        conn.disconnect()
        return df
    @staticmethod
    def saveList(customer_id,items,model_name):
        # items: [(movie_id, điểm dự báo, thứ hạng)]. Chỉ lưu khi khác lần trước về phim, thứ tự hoặc điểm
        last = recommendationDAO.getLastList(customer_id)
        if last is not None and len(last)==len(items) and len(items)>0:
            same = all(int(last.iloc[k]["movie_id"])==int(items[k][0]) and
                       round(float(last.iloc[k]["predicted_rating"]),1)==round(float(items[k][1]),1) and
                       last.iloc[k]["model_name"]==model_name for k in range(len(items)))
            if same:
                return False
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select now() as t")
        created_at = df.iloc[0]["t"]
        sql = "insert into recommendations (customer_id,movie_id,predicted_score,rank_position,model_name,created_at) " \
              "values (%s,%s,%s,%s,%s,%s)"
        ret = conn.executeMany(sql, [(int(customer_id), int(m), float(round(s,1)), int(k), model_name, created_at)
                                     for (m,s,k) in items])
        conn.disconnect()
        return ret>0
    # ---------------- Thống kê gợi ý cho Admin (FR-19) ----------------
    @staticmethod
    def buildFilter(date_from=None,date_to=None,model_name=None,alias="r"):
        conds=[]
        val=[]
        if date_from is not None:
            conds.append(f"{alias}.created_at>=%s")
            val.append(date_from)
        if date_to is not None:
            conds.append(f"{alias}.created_at<%s")
            val.append(date_to)
        if model_name is not None:
            conds.append(f"{alias}.model_name=%s")
            val.append(model_name)
        return ("where "+" AND ".join(conds) if conds else "", val)
    @staticmethod
    def getSummary(date_from=None,date_to=None,model_name=None):
        conn = Connector()
        conn.connect()
        (where,val) = recommendationDAO.buildFilter(date_from,date_to,model_name)
        sql = "select count(distinct r.customer_id, r.created_at) as lists, count(distinct r.customer_id) as customers, " \
              "count(*) as appearances, count(distinct r.movie_id) as movies, avg(r.predicted_score) as avg_score " \
              f"from recommendations r {where}"
        df = conn.queryDataset(sql, val)
        # Gợi ý "trúng": phim được gợi ý mà khách hàng đánh giá sau thời điểm gợi ý
        sql = "select count(*) as hits, avg(t.rating_score) as hit_score from (select distinct r.customer_id, " \
              f"r.movie_id, min(r.created_at) as first_time from recommendations r {where} " \
              "group by r.customer_id, r.movie_id) x join ratings t on t.customer_id=x.customer_id " \
              "and t.movie_id=x.movie_id and t.rating_time>=x.first_time and t.is_valid=1"
        df2 = conn.queryDataset(sql, val)
        conn.disconnect()
        if df is None or df2 is None:
            return None
        row = df.iloc[0].to_dict()
        row.update(df2.iloc[0].to_dict())
        return row
    @staticmethod
    def getListsByDay(date_from=None,date_to=None,model_name=None):
        conn = Connector()
        conn.connect()
        (where,val) = recommendationDAO.buildFilter(date_from,date_to,model_name)
        sql = "select date(r.created_at) as day, count(distinct r.customer_id, r.created_at) as lists, " \
              f"count(distinct r.customer_id) as customers from recommendations r {where} group by day order by day"
        df = conn.queryDataset(sql, val)
        conn.disconnect()
        return df
    @staticmethod
    def getTopMovies(n=10,date_from=None,date_to=None,model_name=None):
        # Số danh sách đã lưu có chứa phim (khác với số lần tạo danh sách)
        conn = Connector()
        conn.connect()
        (where,val) = recommendationDAO.buildFilter(date_from,date_to,model_name)
        sql = "select r.movie_id, m.title, count(distinct r.customer_id, r.created_at) as lists, " \
              f"avg(r.rank_position) as avg_rank from recommendations r join movies m on m.movie_id=r.movie_id {where} " \
              "group by r.movie_id, m.title order by lists desc, avg_rank asc, m.title asc limit %s"
        df = conn.queryDataset(sql, val+[n])
        conn.disconnect()
        return df
    @staticmethod
    def getTopGenres(date_from=None,date_to=None,model_name=None):
        conn = Connector()
        conn.connect()
        (where,val) = recommendationDAO.buildFilter(date_from,date_to,model_name)
        sql = "select g.genre_name, count(*) as appearances from recommendations r " \
              "join movie_genres mg on mg.movie_id=r.movie_id join genres g on g.genre_id=mg.genre_id " \
              f"{where} group by g.genre_name order by appearances desc, g.genre_name asc"
        df = conn.queryDataset(sql, val)
        conn.disconnect()
        return df
    @staticmethod
    def getModelNames():
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select distinct model_name from recommendations where model_name is not null order by model_name")
        conn.disconnect()
        return [] if df is None else list(df["model_name"])
    @staticmethod
    def getDateRange():
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select min(created_at) as d1, max(created_at) as d2 from recommendations")
        conn.disconnect()
        if df is None or df.iloc[0]["d1"] is None:
            return (None, None)
        return (df.iloc[0]["d1"], df.iloc[0]["d2"])
