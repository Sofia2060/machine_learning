import re
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QLinearGradient, QColor, QFont, QPainterPath


class PosterUtil:
    # Ưu tiên poster chính thức tải từ TMDB (xem TmdbUtil); phim chưa có poster thì tự vẽ ảnh bìa theo thể loại
    GENRE_COLORS = {"Action": ("#EF4444", "#B91C1C"), "Adventure": ("#F97316", "#C2410C"),
                    "Animation": ("#22C55E", "#15803D"), "Children's": ("#84CC16", "#4D7C0F"),
                    "Comedy": ("#F59E0B", "#D97706"), "Crime": ("#475569", "#1E293B"),
                    "Documentary": ("#0EA5E9", "#0369A1"), "Drama": ("#6366F1", "#4338CA"),
                    "Fantasy": ("#A855F7", "#7E22CE"), "Film-Noir": ("#334155", "#0F172A"),
                    "Horror": ("#7F1D1D", "#450A0A"), "Musical": ("#EC4899", "#BE185D"),
                    "Mystery": ("#6D28D9", "#3B0764"), "Romance": ("#F43F5E", "#BE123C"),
                    "Sci-Fi": ("#06B6D4", "#0E7490"), "Thriller": ("#64748B", "#334155"),
                    "War": ("#78716C", "#44403C"), "Western": ("#B45309", "#78350F")}
    GENRE_VI = {"Action": "Hành động", "Adventure": "Phiêu lưu", "Animation": "Hoạt hình",
                "Children's": "Thiếu nhi", "Comedy": "Hài", "Crime": "Hình sự", "Documentary": "Tài liệu",
                "Drama": "Chính kịch", "Fantasy": "Giả tưởng", "Film-Noir": "Phim đen", "Horror": "Kinh dị",
                "Musical": "Nhạc kịch", "Mystery": "Bí ẩn", "Romance": "Lãng mạn", "Sci-Fi": "Khoa học viễn tưởng",
                "Thriller": "Giật gân", "War": "Chiến tranh", "Western": "Viễn Tây"}

    @staticmethod
    def shortTitle(title):
        # "Toy Story (1995)" -> "Toy Story" ; "Godfather, The (1972)" -> "The Godfather"
        # Bỏ năm và tên phụ trong ngoặc: "Seven Samurai (The Magnificent Seven) (Shichinin no samurai) (1954)" -> "Seven Samurai"
        t = re.sub(r"\s*\([^()]*\)", "", str(title)).strip() or str(title)
        for art in (", The", ", A", ", An", ", Les", ", La", ", Il", ", Le", ", Das", ", Der", ", Die"):
            if t.endswith(art):
                t = art[2:] + " " + t[:-len(art)]
                break
        return t
    @staticmethod
    def titleWithoutYear(title):
        # "Toy Story (1995)" -> "Toy Story": chỉ bỏ năm ở cuối, giữ nguyên phần còn lại (dùng cho màn hình quản trị)
        return re.sub(r"\s*\(\d{4}\)\s*$", "", str(title)).strip() or str(title)
    @staticmethod
    def withYear(name,year):
        # Ghép lại theo định dạng MovieLens "Tên phim (Năm)" để lưu thống nhất với dữ liệu gốc
        return f"{PosterUtil.titleWithoutYear(name)} ({int(year)})"
    @staticmethod
    def ratio():
        # Mật độ điểm ảnh của màn hình (125%, 150%...) để ảnh bìa không bị mờ khi Windows phóng to giao diện
        from PyQt6.QtWidgets import QApplication
        screen=QApplication.primaryScreen()
        return max(1.0,float(screen.devicePixelRatio())) if screen is not None else 1.0
    @staticmethod
    def initials(title):
        words = [w for w in re.split(r"[^\w']+", PosterUtil.shortTitle(title))
                 if w and w.lower() not in ("the", "a", "an", "of", "and")]
        if len(words) == 0:
            return "?"
        return "".join(w[0] for w in words[:2]).upper()
    @staticmethod
    def genresVi(genres,sep=", "):
        return sep.join(PosterUtil.GENRE_VI.get(g, g) for g in str(genres).split("|"))
    @staticmethod
    def createPoster(title,genres,width,height,year=None):
        genre = str(genres).split("|")[0]
        c1, c2 = PosterUtil.GENRE_COLORS.get(genre, ("#3B82F6", "#1D4ED8"))
        dpr = PosterUtil.ratio()
        pixmap = QPixmap(int(width*dpr), int(height*dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, width, height), 12, 12)
        gradient = QLinearGradient(0, 0, width, height)
        gradient.setColorAt(0, QColor(c1))
        gradient.setColorAt(1, QColor(c2))
        painter.fillPath(path, gradient)
        # Vòng tròn trang trí
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 28))
        painter.drawEllipse(QRectF(width*0.55, -height*0.35, width*0.7, width*0.7))
        painter.setBrush(QColor(255, 255, 255, 18))
        painter.drawEllipse(QRectF(-width*0.25, height*0.45, width*0.6, width*0.6))
        # Chữ viết tắt tên phim
        font = QFont()
        font.setPixelSize(int(min(width, height)*0.36))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 235))
        painter.drawText(QRectF(0, 0, width, height*0.82), Qt.AlignmentFlag.AlignCenter, PosterUtil.initials(title))
        # Nhãn thể loại
        font.setPixelSize(max(11, int(min(width, height)*0.06)))
        font.setBold(True)
        painter.setFont(font)
        # Poster nhỏ: cắt bớt nhãn thể loại dài để không tràn ra ngoài ảnh
        label = painter.fontMetrics().elidedText(PosterUtil.GENRE_VI.get(genre, genre), Qt.TextElideMode.ElideRight,
                                                 int(width-38))
        tw = painter.fontMetrics().horizontalAdvance(label) + 18
        th = painter.fontMetrics().height() + 6
        pill = QPainterPath()
        pill.addRoundedRect(QRectF(10, height-th-10, tw, th), th/2, th/2)
        painter.fillPath(pill, QColor(0, 0, 0, 70))
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(QRectF(10, height-th-10, tw, th), Qt.AlignmentFlag.AlignCenter, label)
        if year is not None:
            painter.setPen(QColor(255, 255, 255, 200))
            painter.drawText(QRectF(0, 8, width-12, th), Qt.AlignmentFlag.AlignRight, str(year))
        painter.end()
        return pixmap
    @staticmethod
    def loadImagePoster(path,width,height):
        # Đọc poster từ file, phóng to vừa khung rồi cắt phần giữa, bo góc giống ảnh tự vẽ
        image=QPixmap(path)
        if image.isNull():
            return None
        dpr=PosterUtil.ratio()
        (pw,ph)=(int(width*dpr),int(height*dpr))
        image=image.scaled(pw,ph,Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                           Qt.TransformationMode.SmoothTransformation)
        x=(image.width()-pw)//2
        y=(image.height()-ph)//2
        pixmap=QPixmap(pw,ph)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter=QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path_clip=QPainterPath()
        path_clip.addRoundedRect(QRectF(0,0,pw,ph),12*dpr,12*dpr)
        painter.setClipPath(path_clip)
        painter.drawPixmap(0,0,image,x,y,pw,ph)
        painter.end()
        pixmap.setDevicePixelRatio(dpr)
        return pixmap
    @staticmethod
    def setPoster(label,movie_id,title,genres,width,height,year=None):
        # Hiện ngay ảnh tự vẽ (hoặc poster đã lưu), poster TMDB tải xong sẽ tự thay vào
        from app.utils.TmdbUtil import TmdbUtil
        label.setProperty("movie_id",int(movie_id))
        pixmap=None
        if TmdbUtil.hasPoster(movie_id):
            pixmap=PosterUtil.loadImagePoster(TmdbUtil.posterPath(movie_id),width,height)
        if pixmap is not None:
            label.setPixmap(pixmap)
            return
        label.setPixmap(PosterUtil.createPoster(title,genres,width,height,year))
        def update(path):
            # bảng chi tiết có thể đã chuyển sang phim khác trong lúc chờ tải
            if label.property("movie_id")==int(movie_id):
                image=PosterUtil.loadImagePoster(path,width,height)
                if image is not None:
                    label.setPixmap(image)
        TmdbUtil.requestPoster(movie_id,title,year,update)
