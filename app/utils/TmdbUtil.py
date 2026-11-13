import json
import os
import re
from urllib.parse import urlencode

from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from app.utils.ConfigUtil import ConfigUtil

# Lấy poster chính thức của phim từ TMDB (The Movie Database)
# Đăng ký miễn phí tại https://www.themoviedb.org/settings/api rồi dán API Key (v3) hoặc
# API Read Access Token (v4) vào config/config.json mục "tmdb" > "api_key". Để trống thì giao diện dùng ảnh bìa tự vẽ.
TMDB_API_KEY=ConfigUtil.get("tmdb","api_key","")
TMDB_API_URL="https://api.themoviedb.org/3"
TMDB_IMAGE_URL="https://image.tmdb.org/t/p/w342"
# Poster tải về được lưu ở thư mục posters (cạnh thư mục ui) để lần sau mở không phải tải lại
folder_posters=ConfigUtil.rootPath(ConfigUtil.get("paths","poster_dir","posters"))


class TmdbUtil:
    manager=None
    waiting={}          # movie_id -> danh sách hàm callback đang chờ ảnh
    not_found=None      # các movie_id đã tìm nhưng TMDB không có poster

    @staticmethod
    def isConfigured():
        return TMDB_API_KEY.strip()!=""
    @staticmethod
    def posterPath(movie_id):
        return os.path.join(folder_posters,f"{int(movie_id)}.jpg")
    @staticmethod
    def hasPoster(movie_id):
        return os.path.exists(TmdbUtil.posterPath(movie_id))
    @staticmethod
    def searchTitle(title):
        # "City of Lost Children, The (Cité des enfants perdus, La) (1995)" -> "The City of Lost Children"
        t=re.sub(r"\s*\([^)]*\)","",str(title)).strip()
        for art in (", The", ", A", ", An", ", Les", ", La", ", Il", ", Le", ", L'", ", Das", ", Der", ", Die", ", El"):
            if t.endswith(art):
                t=art[2:]+("" if art.endswith("'") else " ")+t[:-len(art)]
                break
        return t
    @staticmethod
    def buildSearchUrl(title,year=None):
        params={"query":TmdbUtil.searchTitle(title),"include_adult":"false","language":"en-US"}
        if year:
            params["year"]=int(year)
        key=TMDB_API_KEY.strip()
        if len(key)<=40:   # API Key v3 gửi qua tham số, Read Access Token v4 gửi qua header
            params["api_key"]=key
        return f"{TMDB_API_URL}/search/movie?{urlencode(params)}"
    @staticmethod
    def authHeaders():
        key=TMDB_API_KEY.strip()
        return {"Authorization":f"Bearer {key}"} if len(key)>40 else {}
    @staticmethod
    def pickPoster(data):
        for movie in data.get("results",[]):
            if movie.get("poster_path"):
                return movie["poster_path"]
        return None
    # ---------------- danh sách phim không có poster ----------------
    @staticmethod
    def loadNotFound():
        if TmdbUtil.not_found is None:
            TmdbUtil.not_found=set()
            path=os.path.join(folder_posters,"not_found.txt")
            if os.path.exists(path):
                TmdbUtil.not_found=set(int(x) for x in open(path).read().split() if x.isdigit())
        return TmdbUtil.not_found
    @staticmethod
    def markNotFound(movie_id):
        TmdbUtil.loadNotFound().add(int(movie_id))
        os.makedirs(folder_posters,exist_ok=True)
        with open(os.path.join(folder_posters,"not_found.txt"),"a") as f:
            f.write(f"{int(movie_id)}\n")
    # ---------------- tải bất đồng bộ (không làm đứng giao diện) ----------------
    @staticmethod
    def requestPoster(movie_id,title,year,callback):
        # callback(path) được gọi khi đã có file poster trên máy
        movie_id=int(movie_id)
        if TmdbUtil.hasPoster(movie_id):
            callback(TmdbUtil.posterPath(movie_id))
            return
        if not TmdbUtil.isConfigured() or movie_id in TmdbUtil.loadNotFound():
            return
        if movie_id in TmdbUtil.waiting:
            TmdbUtil.waiting[movie_id].append(callback)
            return
        TmdbUtil.waiting[movie_id]=[callback]
        if TmdbUtil.manager is None:
            TmdbUtil.manager=QNetworkAccessManager()
        TmdbUtil.sendSearch(movie_id,title,year,True)
    @staticmethod
    def createRequest(url):
        request=QNetworkRequest(QUrl(url))
        for (k,v) in TmdbUtil.authHeaders().items():
            request.setRawHeader(k.encode(),v.encode())
        request.setTransferTimeout(15000)
        return request
    @staticmethod
    def sendSearch(movie_id,title,year,with_year):
        reply=TmdbUtil.manager.get(TmdbUtil.createRequest(TmdbUtil.buildSearchUrl(title,year if with_year else None)))
        reply.finished.connect(lambda: TmdbUtil.onSearchFinished(reply,movie_id,title,year,with_year))
    @staticmethod
    def onSearchFinished(reply,movie_id,title,year,with_year):
        reply.deleteLater()
        if reply.error()!=QNetworkReply.NetworkError.NoError:
            # lỗi mạng / sai key: bỏ qua, lần mở sau sẽ thử lại
            TmdbUtil.waiting.pop(movie_id,None)
            return
        try:
            poster=TmdbUtil.pickPoster(json.loads(bytes(reply.readAll()).decode("utf-8")))
        except:
            poster=None
        if poster is None and with_year and year:
            # năm phát hành của MovieLens đôi khi lệch 1 năm so với TMDB -> tìm lại không kèm năm
            TmdbUtil.sendSearch(movie_id,title,year,False)
            return
        if poster is None:
            TmdbUtil.markNotFound(movie_id)
            TmdbUtil.waiting.pop(movie_id,None)
            return
        image_reply=TmdbUtil.manager.get(TmdbUtil.createRequest(TMDB_IMAGE_URL+poster))
        image_reply.finished.connect(lambda: TmdbUtil.onImageFinished(image_reply,movie_id))
    @staticmethod
    def onImageFinished(reply,movie_id):
        reply.deleteLater()
        callbacks=TmdbUtil.waiting.pop(movie_id,[])
        if reply.error()!=QNetworkReply.NetworkError.NoError:
            return
        pixmap=QPixmap()
        if not pixmap.loadFromData(bytes(reply.readAll())):
            return
        os.makedirs(folder_posters,exist_ok=True)
        pixmap.save(TmdbUtil.posterPath(movie_id),"JPG",90)
        for callback in callbacks:
            try:
                callback(TmdbUtil.posterPath(movie_id))
            except RuntimeError:
                # thẻ phim đã bị xóa (người dùng chuyển Top-5/Top-10) trước khi ảnh tải xong
                pass
