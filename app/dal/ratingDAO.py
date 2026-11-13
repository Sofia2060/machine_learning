from app.connectors.connector import Connector
from app.utils.DataImportUtil import DataImportUtil


class ratingDAO:
    @staticmethod
    def getRating(customer_id,movie_id):
        conn = Connector()
        conn.connect()
        sql = "select rating_id, rating_score, comment_text, rating_time, is_valid from ratings " \
              "where customer_id=%s AND movie_id=%s"
        df = conn.queryDataset(sql, (customer_id, movie_id))
        conn.disconnect()
        if df is None or len(df)==0:
            return None
        return df.iloc[0]
    @staticmethod
    def saveRating(customer_id,movie_id,score,comment=None):
        # FR-11, NFR-13: mỗi cặp (khách hàng, phim) chỉ có 1 đánh giá hiện hành -> chấm lại thì cập nhật.
        # comment: bình luận của người dùng (chuỗi rỗng = không có bình luận)
        if not 1<=int(score)<=5:
            return False
        comment=(comment or "").strip() or None
        conn = Connector()
        conn.connect()
        sql = "insert into ratings (customer_id,movie_id,rating_score,comment_text,rating_time) values (%s,%s,%s,%s,now()) " \
              "on duplicate key update rating_score=values(rating_score), comment_text=values(comment_text), " \
              "rating_time=now(), is_valid=1"
        ret = conn.executeNonQuery(sql, (customer_id, movie_id, int(score), comment))
        if ret is not None and ret>=0:
            DataImportUtil.refreshMovieStats(conn, movie_id)
        conn.disconnect()
        return ret is not None and ret>=0
    @staticmethod
    def deleteRating(customer_id,movie_id):
        conn = Connector()
        conn.connect()
        ret = conn.executeNonQuery("delete from ratings where customer_id=%s AND movie_id=%s", (customer_id, movie_id))
        if ret>0:
            DataImportUtil.refreshMovieStats(conn, movie_id)
        conn.disconnect()
        return ret>0
    @staticmethod
    def getRatingsByCustomer(customer_id):
        # FR-12: các phim User hiện đang có đánh giá, mới nhất trước
        conn = Connector()
        conn.connect()
        sql = "select r.movie_id, m.title, m.release_year, m.duration_minutes, " \
              "(select group_concat(g.genre_name order by g.genre_name separator '|') from movie_genres mg " \
              "join genres g on g.genre_id=mg.genre_id where mg.movie_id=m.movie_id) as genres, " \
              "r.rating_score, r.comment_text, r.rating_time, r.is_valid " \
              "from ratings r join movies m on m.movie_id=r.movie_id where r.customer_id=%s " \
              "order by r.rating_time desc, r.rating_id desc"
        df = conn.queryDataset(sql, (customer_id,))
        conn.disconnect()
        return df
    @staticmethod
    def getValidRatingPairs(customer_id):
        # [(movie_id, số sao)] các đánh giá hợp lệ của khách hàng (dữ liệu cho fold-in)
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select movie_id, rating_score from ratings where customer_id=%s and is_valid=1",
                               (customer_id,))
        conn.disconnect()
        return [] if df is None else [(int(m), int(r)) for (m, r) in zip(df["movie_id"], df["rating_score"])]
    @staticmethod
    def getRatedMovieIds(customer_id):
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select movie_id from ratings where customer_id=%s", (customer_id,))
        conn.disconnect()
        return [] if df is None else [int(x) for x in df["movie_id"]]
    # ---------------- Quản lý đánh giá của Admin (FR-22) ----------------
    @staticmethod
    def buildFilter(customer_id=None,movie_keyword="",score=None,validity=None):
        conds=[]
        val=[]
        if customer_id is not None:
            conds.append("r.customer_id=%s")
            val.append(customer_id)
        movie_keyword=movie_keyword.strip()
        if movie_keyword!="":
            if movie_keyword.isdigit():
                conds.append("r.movie_id=%s")
                val.append(int(movie_keyword))
            else:
                conds.append("r.movie_id in (select movie_id from movies where title like %s)")
                val.append(f"%{movie_keyword}%")
        if score is not None:
            conds.append("r.rating_score=%s")
            val.append(score)
        if validity is not None:
            conds.append("r.is_valid=%s")
            val.append(validity)
        return ("where "+" AND ".join(conds) if conds else "", val)
    @staticmethod
    def getRatings(customer_id=None,movie_keyword="",score=None,validity=None,limit=50,offset=0):
        conn = Connector()
        conn.connect()
        (where,val) = ratingDAO.buildFilter(customer_id,movie_keyword,score,validity)
        sql = "select r.rating_id, r.customer_id, c.username, r.movie_id, m.title, r.rating_score, r.comment_text, " \
              "r.rating_time, r.is_valid from ratings r join customers c on c.customer_id=r.customer_id " \
              f"join movies m on m.movie_id=r.movie_id {where} " \
              "order by r.rating_time desc, r.rating_id desc limit %s offset %s"
        df = conn.queryDataset(sql, val+[limit, offset])
        conn.disconnect()
        return df
    @staticmethod
    def countRatings(customer_id=None,movie_keyword="",score=None,validity=None):
        conn = Connector()
        conn.connect()
        (where,val) = ratingDAO.buildFilter(customer_id,movie_keyword,score,validity)
        df = conn.queryDataset(f"select count(*) as n from ratings r {where}", val)
        conn.disconnect()
        return 0 if df is None else int(df.iloc[0]["n"])
    @staticmethod
    def setValid(rating_ids,is_valid):
        # Đánh dấu (không) hợp lệ: bản ghi vẫn giữ để kiểm tra nhưng bị loại khỏi thống kê và huấn luyện
        if len(rating_ids)==0:
            return 0
        conn = Connector()
        conn.connect()
        marks = ",".join(["%s"]*len(rating_ids))
        df = conn.queryDataset(f"select distinct movie_id from ratings where rating_id in ({marks})", tuple(rating_ids))
        ret = conn.executeNonQuery(f"update ratings set is_valid=%s where rating_id in ({marks})",
                                   tuple([is_valid]+list(rating_ids)))
        if ret>=0 and df is not None:
            for movie_id in df["movie_id"]:
                DataImportUtil.refreshMovieStats(conn, int(movie_id))
        conn.disconnect()
        return ret
    @staticmethod
    def deleteByIds(rating_ids):
        if len(rating_ids)==0:
            return 0
        conn = Connector()
        conn.connect()
        marks = ",".join(["%s"]*len(rating_ids))
        df = conn.queryDataset(f"select distinct movie_id from ratings where rating_id in ({marks})", tuple(rating_ids))
        ret = conn.executeNonQuery(f"delete from ratings where rating_id in ({marks})", tuple(rating_ids))
        if ret>0 and df is not None:
            for movie_id in df["movie_id"]:
                DataImportUtil.refreshMovieStats(conn, int(movie_id))
        conn.disconnect()
        return ret
    @staticmethod
    def getValidRatings():
        # Dữ liệu huấn luyện lại mô hình (FR-27): chỉ lấy đánh giá hợp lệ
        conn = Connector()
        conn.connect()
        df = conn.queryDataset("select customer_id as user_id, movie_id, rating_score as rating, "
                               "unix_timestamp(rating_time) as timestamp from ratings where is_valid=1")
        conn.disconnect()
        return df
