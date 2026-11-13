from app.connectors.connector import Connector


class movieDAO:
    # Thể loại của phim được ghép từ bảng movie_genres thành chuỗi "Action|Comedy" để hiển thị
    GENRES = "(select group_concat(g.genre_name order by g.genre_name separator '|') from movie_genres mg " \
             "join genres g on g.genre_id=mg.genre_id where mg.movie_id=m.movie_id) as genres"
    # avg_rating, rating_count: tổng hợp từ các đánh giá hợp lệ, cập nhật mỗi khi đánh giá thay đổi
    COLUMNS = "m.movie_id, m.title, m.release_year, m.duration_minutes, round(m.avg_rating,2) as avg_rating, " \
              "m.rating_count, m.is_hidden, " + GENRES
    # FR-08: sắp xếp theo lượt đánh giá, điểm TB, năm, thời lượng, tên phim, mã phim; chiều tăng/giảm.
    # Phim chưa có đánh giá luôn xếp sau khi sắp theo điểm TB; phim chưa có thời lượng luôn xếp sau khi sắp theo thời lượng.
    SORT_COLUMNS = {"count": "m.rating_count", "rating": "m.avg_rating", "year": "m.release_year",
                    "duration": "m.duration_minutes", "title": "m.title", "id": "m.movie_id"}

    @staticmethod
    def orderBy(sort="count",descending=True):
        col=movieDAO.SORT_COLUMNS.get(sort,"m.rating_count")
        d="desc" if descending else "asc"
        if sort=="rating":
            return f"(m.rating_count=0) asc, m.avg_rating {d}, m.rating_count desc, m.title asc"
        if sort=="duration":
            return f"(m.duration_minutes is null) asc, m.duration_minutes {d}, m.title asc"
        if sort in ("title","id"):
            return f"{col} {d}"
        return f"{col} {d}, m.title asc"
    @staticmethod
    def buildFilter(keyword="",genre_id=None,year_from=None,year_to=None,include_hidden=False,hidden_only=False):
        # FR-09: tìm theo tên, khớp một phần, không phân biệt hoa thường (collation utf8mb4_unicode_ci)
        conds=["m.title like %s"]
        val=[f"%{keyword.strip()}%"]
        if genre_id is not None:
            conds.append("m.movie_id in (select movie_id from movie_genres where genre_id=%s)")
            val.append(genre_id)
        if year_from is not None:
            conds.append("m.release_year>=%s")
            val.append(year_from)
        if year_to is not None:
            conds.append("m.release_year<=%s")
            val.append(year_to)
        if hidden_only:
            conds.append("m.is_hidden=1")
        elif not include_hidden:
            conds.append("m.is_hidden=0")
        return ("where "+" AND ".join(conds), val)
    @staticmethod
    def getMovies(keyword="",genre_id=None,year_from=None,year_to=None,sort="count",limit=50,offset=0,
                  include_hidden=False,hidden_only=False,descending=True):
        conn = Connector()
        conn.connect()
        (where,val) = movieDAO.buildFilter(keyword,genre_id,year_from,year_to,include_hidden,hidden_only)
        sql = f"select {movieDAO.COLUMNS} from movies m {where} " \
              f"order by {movieDAO.orderBy(sort,descending)} limit %s offset %s"
        df = conn.queryDataset(sql, val+[limit, offset])
        conn.disconnect()
        return df
    @staticmethod
    def countMovies(keyword="",genre_id=None,year_from=None,year_to=None,include_hidden=False,hidden_only=False):
        conn = Connector()
        conn.connect()
        (where,val) = movieDAO.buildFilter(keyword,genre_id,year_from,year_to,include_hidden,hidden_only)
        df = conn.queryDataset(f"select count(*) as total from movies m {where}", val)
        conn.disconnect()
        return 0 if df is None else int(df.iloc[0]["total"])
    @staticmethod
    def getMovieById(movie_id):
        conn = Connector()
        conn.connect()
        df = conn.queryDataset(f"select {movieDAO.COLUMNS} from movies m where m.movie_id=%s", (movie_id,))
        conn.disconnect()
        if df is None or len(df)==0:
            return None
        return df.iloc[0]
    @staticmethod
    def getMoviesByIds(movie_ids):
        if len(movie_ids)==0:
            return None
        conn = Connector()
        conn.connect()
        marks = ",".join(["%s"]*len(movie_ids))
        df = conn.queryDataset(f"select {movieDAO.COLUMNS} from movies m where m.movie_id in ({marks})",
                               tuple(int(x) for x in movie_ids))
        conn.disconnect()
        return df
    @staticmethod
    def getFeaturedMovies(n=10,min_count=5,genre_ids=None,exclude_ids=()):
        # Phim nổi bật (FR-07, FR-18): phim đang hiển thị có ít nhất min_count lượt đánh giá hợp lệ,
        # xếp theo điểm TB giảm dần, hòa thì số lượt đánh giá giảm dần, sau đó tên phim A-Z
        conn = Connector()
        conn.connect()
        sql = f"select {movieDAO.COLUMNS} from movies m where m.is_hidden=0 and m.rating_count>=%s "
        val = [min_count]
        if genre_ids:
            sql += f"and m.movie_id in (select movie_id from movie_genres where genre_id in " \
                   f"({','.join(['%s']*len(genre_ids))})) "
            val += list(genre_ids)
        if exclude_ids:
            sql += f"and m.movie_id not in ({','.join(['%s']*len(exclude_ids))}) "
            val += [int(x) for x in exclude_ids]
        sql += "order by m.avg_rating desc, m.rating_count desc, m.title asc limit %s"
        df = conn.queryDataset(sql, val+[n])
        conn.disconnect()
        return df
    @staticmethod
    def getPopularMovies(n=10,genre_ids=None,exclude_ids=()):
        # Danh sách phổ biến thay thế khi chưa cá nhân hóa được (FR-07, FR-15): nhiều lượt đánh giá nhất,
        # ưu tiên các thể loại người dùng mới đã chọn
        conn = Connector()
        conn.connect()
        sql = f"select {movieDAO.COLUMNS} from movies m where m.is_hidden=0 and m.rating_count>0 "
        val = []
        if genre_ids:
            sql += f"and m.movie_id in (select movie_id from movie_genres where genre_id in " \
                   f"({','.join(['%s']*len(genre_ids))})) "
            val += list(genre_ids)
        if exclude_ids:
            sql += f"and m.movie_id not in ({','.join(['%s']*len(exclude_ids))}) "
            val += [int(x) for x in exclude_ids]
        sql += "order by m.rating_count desc, m.avg_rating desc limit %s"
        df = conn.queryDataset(sql, val+[n])
        conn.disconnect()
        return df
    @staticmethod
    def getHiddenMovieIds():
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select movie_id from movies where is_hidden=1")
        conn.disconnect()
        return set() if df is None else set(int(x) for x in df["movie_id"])
    @staticmethod
    def getGenres():
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select genre_id, genre_name from genres order by genre_name")
        conn.disconnect()
        return df
    @staticmethod
    def getGenreIds(movie_id):
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select genre_id from movie_genres where movie_id=%s", (movie_id,))
        conn.disconnect()
        return [] if df is None else [int(x) for x in df["genre_id"]]
    @staticmethod
    def getYearRange():
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select min(release_year) as y1, max(release_year) as y2 from movies")
        conn.disconnect()
        if df is None or df.iloc[0]["y1"] is None:
            return (1919, 2000)
        return (int(df.iloc[0]["y1"]), int(df.iloc[0]["y2"]))
    # ---------------- Quản lý phim (FR-20) ----------------
    @staticmethod
    def insertMovie(mv):
        conn = Connector()
        conn.connect()
        # movie_id trong mrs_schema.sql không tự tăng -> cấp mã kế tiếp (lớn nhất + 1) ngay trong câu lệnh
        sql = "insert into movies (movie_id,title,release_year,duration_minutes,is_hidden,employee_id) " \
              "select coalesce(max(movie_id),0)+1,%s,%s,%s,%s,%s from movies"
        ret = conn.executeNonQuery(sql, (mv.title, mv.release_year, mv.duration_minutes, mv.is_hidden, mv.employee_id))
        new_id = None
        if ret>0:
            df = conn.queryDataset("select max(movie_id) as id from movies where title=%s", (mv.title,))
            new_id = int(df.iloc[0]["id"])
            conn.executeMany("insert into movie_genres (movie_id,genre_id) values (%s,%s)",
                             [(new_id, g) for g in mv.genre_ids])
        conn.disconnect()
        return new_id
    @staticmethod
    def updateMovie(mv):
        # Chỉ sửa thông tin phim, không đụng tới bảng ratings nên không mất lịch sử đánh giá
        conn = Connector()
        conn.connect()
        sql = "update movies set title=%s, release_year=%s, duration_minutes=%s, is_hidden=%s, employee_id=%s " \
              "where movie_id=%s"
        ret = conn.executeNonQuery(sql, (mv.title, mv.release_year, mv.duration_minutes, mv.is_hidden,
                                         mv.employee_id, mv.movie_id))
        if ret>=0:
            conn.executeNonQuery("delete from movie_genres where movie_id=%s", (mv.movie_id,))
            conn.executeMany("insert into movie_genres (movie_id,genre_id) values (%s,%s)",
                             [(mv.movie_id, g) for g in mv.genre_ids])
        conn.disconnect()
        return ret>=0
    @staticmethod
    def setHidden(movie_id,is_hidden,employee_id):
        conn = Connector()
        conn.connect()
        ret = conn.executeNonQuery("update movies set is_hidden=%s, employee_id=%s where movie_id=%s",
                                   (is_hidden, employee_id, movie_id))
        conn.disconnect()
        return ret>=0
    @staticmethod
    def countAllRatings(movie_id):
        # Đếm cả đánh giá không hợp lệ: phim đã có bất kỳ đánh giá nào thì không được xóa
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select count(*) as n from ratings where movie_id=%s", (movie_id,))
        conn.disconnect()
        return None if df is None else int(df.iloc[0]["n"])
    @staticmethod
    def deleteMovie(movie_id):
        # FR-20: chỉ xóa được phim chưa có đánh giá (lời gọi phải kiểm tra countAllRatings trước)
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select count(*) as n from ratings where movie_id=%s", (movie_id,))
        if df is None or int(df.iloc[0]["n"])>0:
            conn.disconnect()
            return False
        conn.executeNonQuery("delete from recommendations where movie_id=%s", (movie_id,))
        ret = conn.executeNonQuery("delete from movies where movie_id=%s", (movie_id,))
        conn.disconnect()
        return ret>0
