from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import QMessageBox

from ui.MovieDetailDialog import Ui_Dialog
from app.dal.movieDAO import movieDAO
from app.dal.ratingDAO import ratingDAO
from app.ml.MovieRecommender import MovieRecommender
from app.utils.ChartUtil import ChartUtil
from app.utils.PosterUtil import PosterUtil


class MovieDetailDialogEx(Ui_Dialog):
    # FR-10 chi tiết phim, FR-11 đánh giá + bình luận; độ tương thích dự báo (%) khi người dùng chưa đánh giá phim
    def setupUi(self, Dialog):
        super().setupUi(Dialog)
        self.Dialog=Dialog
        self.customerId=None
        self.movieId=None
        self.changed=False
        self.pushButtonClose.clicked.connect(self.Dialog.reject)
        self.pushButtonRate.clicked.connect(self.process_rate)
        self.pushButtonDeleteRating.clicked.connect(self.process_deleteRating)
        self.pushButtonRate.setDefault(True)
    def showMessage(self,text,icon=QMessageBox.Icon.Warning):
        self.msgBox=QMessageBox(self.Dialog)
        self.msgBox.setWindowTitle("Chi tiết phim")
        self.msgBox.setIcon(icon)
        self.msgBox.setText(text)
        self.msgBox.exec()
    def showMovie(self,customer_id,movie_id):
        mv=movieDAO.getMovieById(movie_id)
        if mv is None:
            return False
        self.customerId=customer_id
        self.movieId=movie_id
        title=PosterUtil.shortTitle(mv["title"])
        self.Dialog.setWindowTitle(f"CineMatch - {title}")
        PosterUtil.setPoster(self.labelPoster,movie_id,mv["title"],mv["genres"],176,260,mv["release_year"])
        # Tên rất dài: tối đa 3 dòng, phần thừa cắt bằng "…"; tên đầy đủ hiện khi rê chuột
        self.labelDetailTitle.ensurePolished()
        fm=QFontMetrics(self.labelDetailTitle.font())
        width=max(420,self.labelDetailTitle.width())
        self.labelDetailTitle.setText(fm.elidedText(title,Qt.TextElideMode.ElideRight,width*3-40))
        self.labelDetailTitle.setToolTip(str(mv["title"]))
        duration=f" · {int(mv['duration_minutes'])} phút" if mv["duration_minutes"] is not None and \
                                                           mv["duration_minutes"]==mv["duration_minutes"] else ""
        self.labelDetailMeta.setText(f"{mv['release_year']} · {PosterUtil.genresVi(mv['genres'])}{duration}")
        if int(mv["rating_count"])>0:
            self.labelDetailStats.setText(f"<span style='color:#B45309; font-weight:700'>★ {ChartUtil.vn(mv['avg_rating'],2)}"
                                          f"</span> / 5 điểm trung bình cộng đồng · {ChartUtil.vn(mv['rating_count'])} "
                                          f"lượt đánh giá")
        else:
            self.labelDetailStats.setText("Phim chưa có lượt đánh giá nào.")
        self.showRatingState()
        return True
    def showRatingState(self):
        my=ratingDAO.getRating(self.customerId,self.movieId)
        if my is not None:
            # FR-10: đã đánh giá -> hiển thị điểm hiện tại, cho phép sửa sao/bình luận hoặc xóa
            score=int(my["rating_score"])
            self.labelPredictCaption.setText("Bạn đã đánh giá phim này")
            self.labelPredictValue.setText(f"{score} ★")
            self.progressBarMatch.setVisible(False)
            self.labelPredictNote.setText(f"Đánh giá lúc {str(my['rating_time'])[:16]}.")
            self.comboBoxRating.setCurrentIndex(5-score)
            comment=my["comment_text"]
            self.lineEditComment.setText(comment if isinstance(comment,str) else "")
            self.lineEditComment.setCursorPosition(0)
            self.labelMyRating.setText("Bạn có thể đổi số sao, sửa bình luận rồi bấm \"Cập nhật đánh giá\".")
            self.pushButtonRate.setText("Cập nhật đánh giá")
            self.pushButtonDeleteRating.setVisible(True)
            return
        # Chưa đánh giá -> độ tương thích dự báo (%) giữa người dùng và phim, hoặc "Chưa đủ dữ liệu dự báo"
        match=MovieRecommender.compatibility(self.customerId,self.movieId) if MovieRecommender.isReady() else None
        self.labelPredictCaption.setText("Độ tương thích dự báo")
        if match is None:
            self.labelPredictValue.setText("Chưa đủ dữ liệu dự báo")
            self.labelPredictValue.setStyleSheet("font-size: 14pt;")
            self.progressBarMatch.setVisible(False)
            if MovieRecommender.isKnownMovie(self.movieId):
                self.labelPredictNote.setText("Hãy chấm từ 4 sao cho vài phim bạn thích để hệ thống dự báo mức độ phù "
                                              "hợp của các phim khác với bạn.")
            else:
                self.labelPredictNote.setText("Phim mới chưa có trong dữ liệu gợi ý; sẽ dự báo được sau lần cập nhật bộ "
                                              "máy gợi ý tiếp theo.")
        else:
            self.labelPredictValue.setStyleSheet("")
            self.labelPredictValue.setText("< 1%" if match<1 else f"{ChartUtil.vn(match,0)}%")
            self.progressBarMatch.setVisible(True)
            self.progressBarMatch.setValue(int(round(match)))
            level="rất phù hợp" if match>=70 else ("khá phù hợp" if match>=30 else "ít phù hợp")
            self.labelPredictNote.setText(f"Phim này {level} với gu của bạn, dựa trên các phim bạn đã đánh giá.")
        self.comboBoxRating.setCurrentIndex(0)
        self.lineEditComment.clear()
        self.labelMyRating.setText("Bạn chưa đánh giá phim này.")
        self.pushButtonRate.setText("Gửi đánh giá")
        self.pushButtonDeleteRating.setVisible(False)
    def process_rate(self):
        score=5-self.comboBoxRating.currentIndex()
        if ratingDAO.saveRating(self.customerId,self.movieId,score,self.lineEditComment.text()):
            self.changed=True
            self.showRatingState()
            self.labelMyRating.setText(f"Đã lưu đánh giá {score} ★ của bạn.")
        else:
            self.showMessage("Lưu đánh giá thất bại, vui lòng thử lại.",QMessageBox.Icon.Critical)
    def process_deleteRating(self):
        ret=QMessageBox.question(self.Dialog,"Xóa đánh giá","Bạn có chắc muốn xóa đánh giá của mình cho phim này?",
                                 QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if ret!=QMessageBox.StandardButton.Yes:
            return
        if ratingDAO.deleteRating(self.customerId,self.movieId):
            self.changed=True
            self.showRatingState()
        else:
            self.showMessage("Xóa đánh giá thất bại, vui lòng thử lại.",QMessageBox.Icon.Critical)
