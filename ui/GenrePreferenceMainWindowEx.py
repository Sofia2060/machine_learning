from PyQt6.QtWidgets import QMessageBox, QMainWindow

from ui.GenrePreferenceMainWindow import Ui_MainWindow
from app.utils.CatalogUtil import CatalogUtil


class GenrePreferenceMainWindowEx(Ui_MainWindow):
    # FR-15: chọn ít nhất 3 thể loại yêu thích (lần đầu sử dụng hoặc chỉnh sửa từ Hồ sơ cá nhân)
    MIN_GENRES = 3

    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)
        self.MainWindow=MainWindow
        self.loginUser=None
        self.fromProfile=False
        self.parentUI=None
        # Nút trên giao diện đặt tên theo thể loại MovieLens, vd pushButtonGenreSciFi <-> "Sci-Fi"
        self.genreButtons={g: getattr(self,"pushButtonGenre"+g.replace("'","").replace("-","")) for g in CatalogUtil.GENRES}
        self.pushButtonCancel.setVisible(False)
        self.setupSignalAndSlot()
    def showWindow(self):
        self.MainWindow.show()

    def setupSignalAndSlot(self):
        for button in self.genreButtons.values():
            button.toggled.connect(self.updateCount)
        self.pushButtonSaveGenres.clicked.connect(self.process_save)
        self.pushButtonCancel.clicked.connect(self.process_cancel)
    def setLoginUser(self,us,fromProfile=False,parentUI=None):
        from app.dal.customerDAO import customerDAO
        from app.dal.movieDAO import movieDAO

        self.loginUser=us
        self.fromProfile=fromProfile
        self.parentUI=parentUI
        self.genreIds={}
        df=movieDAO.getGenres()
        if df is not None:
            self.genreIds=dict(zip(df["genre_name"],[int(x) for x in df["genre_id"]]))
        selected=set(customerDAO.getFavoriteGenreIds(us.customer_id))
        for (genre,button) in self.genreButtons.items():
            button.setChecked(self.genreIds.get(genre) in selected)
        if fromProfile:
            from PyQt6.QtCore import Qt
            self.MainWindow.setWindowModality(Qt.WindowModality.ApplicationModal)
            self.pushButtonCancel.setVisible(True)
            self.pushButtonSaveGenres.setText("Lưu thể loại")
            self.labelTitle.setText("Chọn lại thể loại yêu thích")
        else:
            name=us.full_name if us.full_name else us.username
            self.labelTitle.setText(f"Chào {name}, bạn thích xem thể loại nào?")
        self.updateCount()
    def selectedGenreIds(self):
        return [self.genreIds[g] for (g,b) in self.genreButtons.items() if b.isChecked() and g in self.genreIds]
    def updateCount(self):
        n=len([b for b in self.genreButtons.values() if b.isChecked()])
        if n<self.MIN_GENRES:
            self.labelSelectedCount.setText(f"Đã chọn {n} thể loại · cần chọn thêm {self.MIN_GENRES-n} thể loại")
        else:
            self.labelSelectedCount.setText(f"Đã chọn {n} thể loại")
        self.pushButtonSaveGenres.setEnabled(n>=self.MIN_GENRES)
    def process_save(self):
        from app.dal.customerDAO import customerDAO

        genre_ids=self.selectedGenreIds()
        if len(genre_ids)<self.MIN_GENRES:
            return
        if not customerDAO.saveFavoriteGenres(self.loginUser.customer_id,genre_ids):
            self.msgBox=QMessageBox(self.MainWindow)
            self.msgBox.setWindowTitle("Thể loại yêu thích")
            self.msgBox.setIcon(QMessageBox.Icon.Critical)
            self.msgBox.setText("Không lưu được lựa chọn, vui lòng thử lại.")
            self.msgBox.exec()
            return
        if self.fromProfile and self.parentUI is not None:
            self.parentUI.favoriteGenresChanged()
            self.MainWindow.close()
            return
        from ui.UserMainWindowEx import UserMainWindowEx
        self.myui=UserMainWindowEx()
        self.myui.setupUi(QMainWindow())
        self.myui.setLoginUser(self.loginUser)
        self.myui.showWindow()
        self.MainWindow.close()
    def process_cancel(self):
        self.MainWindow.close()
