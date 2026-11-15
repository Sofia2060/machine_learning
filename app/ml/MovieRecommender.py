import hashlib
import json
import os
import sys
import time

import numpy as np
import pandas as pd

from app.dal.customerDAO import customerDAO
from app.dal.modelDAO import modelDAO
from app.dal.movieDAO import movieDAO
from app.dal.ratingDAO import ratingDAO
from app.dal.recommendationDAO import recommendationDAO
from app.utils.ConfigUtil import ConfigUtil, folder_root

# Mô hình do nhóm huấn luyện và xuất bằng `python main.py export` (models/main_model/neumf.npz);
# src.inference chỉ cần numpy nên phần mềm không phải cài torch
if folder_root not in sys.path:
    sys.path.insert(0, folder_root)
from src.inference import NeuMFRecommender


class MovieRecommender:
    # Giao diện dự báo chung (NFR-14): giao diện chỉ gọi các hàm dưới đây, đổi mô hình không phải sửa giao diện
    model = None            # NeuMFRecommender đang dùng
    model_name = None
    model_info = None       # dòng model_registry đang hoạt động
    last_error = ""

    # ======================= NẠP MÔ HÌNH =======================
    @staticmethod
    def modelHash(npz_path):
        # NFR-21: mã băm SHA-256 của tệp trọng số .npz và tệp mô tả _meta.json
        h=hashlib.sha256()
        for path in (npz_path, MovieRecommender.metaPath(npz_path)):
            with open(path,"rb") as f:
                for block in iter(lambda: f.read(1024*1024), b""):
                    h.update(block)
        return h.hexdigest()
    @staticmethod
    def metaPath(npz_path):
        return os.path.splitext(npz_path)[0]+"_meta.json"
    @staticmethod
    def loadModel(force=False):
        # Nạp mô hình đang hoạt động 1 lần duy nhất và giữ trong bộ nhớ (NFR-04: <= 5 giây)
        info=modelDAO.getActiveModel()
        if info is None:
            MovieRecommender.last_error="Chưa có mô hình nào được đăng ký. Hãy chạy python app/setup_database.py."
            return False
        if not force and MovieRecommender.model is not None and MovieRecommender.model_info is not None \
                and int(MovieRecommender.model_info["model_id"])==int(info["model_id"]):
            return True
        return MovieRecommender.loadFromInfo(info)
    @staticmethod
    def loadFromInfo(info):
        # Xác minh mã băm rồi mới nạp; lỗi thì giữ nguyên mô hình đang chạy (NFR-21, FR-25)
        path=ConfigUtil.rootPath(info["file_name"])
        try:
            if MovieRecommender.modelHash(path)!=info["file_hash"]:
                MovieRecommender.last_error=f"Tệp mô hình {info['file_name']} không khớp mã băm đã đăng ký. " \
                                            f"Từ chối nạp mô hình."
                return False
            model=NeuMFRecommender(path)
        except Exception as e:
            MovieRecommender.last_error=f"Không nạp được mô hình {info['file_name']}: {e}"
            return False
        MovieRecommender.model=model
        MovieRecommender.model_name=info["model_name"]
        MovieRecommender.model_info=info
        MovieRecommender.foldin_cache={}
        MovieRecommender.last_error=""
        return True
    @staticmethod
    def activateModel(model_id):
        # FR-25: Admin chọn một phiên bản mô hình đã đăng ký -> nạp thử; chỉ chuyển trạng thái hoạt động khi nạp thành công
        info=modelDAO.getModelById(model_id)
        if info is None:
            MovieRecommender.last_error="Không tìm thấy phiên bản mô hình đã chọn."
            return False
        if not MovieRecommender.loadFromInfo(info):
            return False
        return modelDAO.setActive(model_id)
    @staticmethod
    def isReady():
        return MovieRecommender.model is not None
    @staticmethod
    def isKnownUser(customer_id):
        # Khách hàng có vector trong mô hình đã huấn luyện (MovieLens 1-6040 hoặc đã có ở lần cập nhật gần nhất)
        return MovieRecommender.isReady() and MovieRecommender.model.is_personalized(int(customer_id))
    @staticmethod
    def isKnownMovie(movie_id):
        return MovieRecommender.isReady() and int(movie_id) in MovieRecommender.model.movie_index
    # ======================= ĐIỂM CỦA MỘT KHÁCH HÀNG =======================
    foldin_cache = {}       # customer_id -> (chữ ký các đánh giá, điểm NeuMF của mọi phim)

    @staticmethod
    def userScores(customer_id):
        # Trả về điểm NeuMF (logit) của mọi phim theo thứ tự model.movie_ids, hoặc None nếu chưa đủ dữ liệu.
        # - Khách hàng có trong mô hình: dùng vector đã huấn luyện.
        # - Khách hàng mới: fold-in của src/inference.py (giữ nguyên trọng số mô hình, chỉ học vector của khách từ các
        #   phim họ chấm >= 4 sao) -> gợi ý cá nhân hóa ngay, không cần huấn luyện lại (FR-15).
        if not MovieRecommender.isReady():
            return None
        model=MovieRecommender.model
        customer_id=int(customer_id)
        if model.is_personalized(customer_id):
            return model.scores(customer_id)
        ratings=ratingDAO.getValidRatingPairs(customer_id)
        signature=tuple(sorted(ratings))
        cached=MovieRecommender.foldin_cache.get(customer_id)
        if cached is not None and cached[0]==signature:
            return cached[1]
        vec=model.fold_in(ratings) if len(ratings)>0 else None
        result=None if vec is None else model._forward(*vec)[0]
        MovieRecommender.foldin_cache[customer_id]=(signature,result)
        return result
    @staticmethod
    def isPersonalized(customer_id):
        return MovieRecommender.userScores(customer_id) is not None
    # ======================= ĐỘ PHÙ HỢP =======================
    @staticmethod
    def toCompatibility(scores):
        # Độ phù hợp (%): NeuMF huấn luyện bằng BCE với phản hồi dương là các phim được chấm từ 4 sao, nên
        # sigmoid(điểm) là xác suất mô hình dự đoán người dùng sẽ thích phim -> hiển thị dưới dạng % phù hợp
        z=np.clip(np.asarray(scores,dtype=np.float64),-30.0,30.0)
        return np.round(100.0/(1.0+np.exp(-z)),1)
    @staticmethod
    def compatibility(customer_id,movie_id):
        # % phù hợp của một phim với người dùng; None nếu chưa đủ dữ liệu dự báo
        if not MovieRecommender.isKnownMovie(movie_id):
            return None
        scores=MovieRecommender.userScores(customer_id)
        if scores is None:
            return None
        score=scores[MovieRecommender.model.movie_index[int(movie_id)]]
        return float(MovieRecommender.toCompatibility([score])[0])
    # ======================= GỢI Ý TOP-N =======================
    @staticmethod
    def recommendTopN(customer_id,n=10,save=True):
        # FR-14: Top-N phim có điểm cao nhất, loại phim đã đánh giá (lấy từ MySQL, kể cả vừa chấm) và phim bị ẩn.
        # Kết quả là danh sách xếp hạng kèm độ phù hợp (%), không dự báo số sao.
        # Trả về None nếu chưa cá nhân hóa được -> giao diện dùng danh sách phổ biến thay thế
        scores=MovieRecommender.userScores(customer_id)
        if scores is None:
            return None
        model=MovieRecommender.model
        s=np.array(scores,dtype=np.float64)
        seen=set(ratingDAO.getRatedMovieIds(customer_id))|movieDAO.getHiddenMovieIds()
        drop=[model.movie_index[m] for m in seen if m in model.movie_index]
        s[drop]=-np.inf
        order=[j for j in np.argsort(-s,kind="stable")[:n] if np.isfinite(s[j])]
        if len(order)==0:
            return pd.DataFrame(columns=["rank_no","movie_id","compatibility"])
        movie_ids=[int(model.movie_ids[j]) for j in order]
        df=pd.DataFrame({"rank_no":range(1,len(order)+1),"movie_id":movie_ids,
                         "compatibility":MovieRecommender.toCompatibility(s[order])})
        df_movies=movieDAO.getMoviesByIds(movie_ids)
        df=df.merge(df_movies,on="movie_id",how="inner").sort_values("rank_no").reset_index(drop=True)
        if save:
            recommendationDAO.saveList(customer_id,[(r.movie_id,r.compatibility,r.rank_no) for r in df.itertuples()],
                                       MovieRecommender.model_name)
        return df
    @staticmethod
    def fallbackMovies(customer_id,n=10):
        # FR-15: người dùng mới -> phim phổ biến, ưu tiên thể loại yêu thích đã chọn
        rated=ratingDAO.getRatedMovieIds(customer_id)
        genre_ids=customerDAO.getFavoriteGenreIds(customer_id)
        df=movieDAO.getPopularMovies(n,genre_ids,rated)
        if df is not None and len(df)<n and genre_ids:
            more=movieDAO.getPopularMovies(n-len(df),None,rated+list(df["movie_id"]))
            df=pd.concat([df,more],ignore_index=True)
        return df,genre_ids
    # ======================= ĐĂNG KÝ MÔ HÌNH =======================
    @staticmethod
    def registerModel(npz_path,employee_id=None,activate=True):
        # Đăng ký tệp mô hình đã xuất: nạp thử để chắc tệp đọc được, tính mã băm rồi ghi vào model_registry
        NeuMFRecommender(npz_path)
        meta=json.load(open(MovieRecommender.metaPath(npz_path),encoding="utf-8"))
        relative=os.path.relpath(os.path.abspath(npz_path),folder_root).replace("\\","/")
        ret=modelDAO.registerModel(meta.get("model","NeuMF"),relative,MovieRecommender.modelHash(npz_path),
                                   meta.get("n_users"),meta.get("n_items"),
                                   meta.get("n_ratings"),meta.get("created_at"),employee_id,activate)
        return ret
    @staticmethod
    def retrainModel(progress=None):
        # FR-27: huấn luyện lại NeuMF trên dữ liệu hợp lệ hiện tại và lưu thành phiên bản mới (cần torch)
        from src.models.neural import NeuMF
        from src.export import export_neumf
        from src import recommender
        df=ratingDAO.getValidRatings()
        df_movies=movieDAO.getMovies(limit=100000,include_hidden=True)
        user2idx={int(u): k for (k,u) in enumerate(np.sort(df["user_id"].unique()))}
        item2idx={int(m): k for (k,m) in enumerate(np.sort(df["movie_id"].unique()))}
        if progress is not None:
            progress(f"Đang huấn luyện trên {len(df):,} đánh giá hợp lệ của {len(user2idx):,} người dùng".replace(",","."))
        model=recommender.create_model("neumf")
        start=time.time()
        model.fit(df[["user_id","movie_id","rating"]],user2idx,item2idx,df_movies)
        path=ConfigUtil.rootPath(f"models/main_model/neumf_{time.strftime('%Y%m%d_%H%M%S')}.npz")
        export_neumf(model,path,{"trained_on":"mysql"})
        if progress is not None:
            progress(f"Đã huấn luyện xong sau {time.time()-start:.0f} giây, đang kiểm tra và đăng ký mô hình")
        return path
