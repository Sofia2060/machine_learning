import os

import pandas as pd
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import QMessageBox, QListWidgetItem, QLineEdit, QFileDialog, QApplication

from ui.DataManagementMainWindow import Ui_MainWindow
from ui.AdminNavigation import AdminNavigation
from app.dal.accountDAO import accountDAO
from app.dal.customerDAO import customerDAO
from app.dal.logDAO import logDAO
from app.dal.movieDAO import movieDAO
from app.dal.ratingDAO import ratingDAO
from app.models.customer import Customer
from app.models.movie import Movie
from app.utils.CatalogUtil import CatalogUtil
from app.utils.ChartUtil import ChartUtil
from app.utils.ConfigUtil import ConfigUtil
from app.utils.FormUtil import FormUtil
from app.utils.PosterUtil import PosterUtil
from app.utils.SecurityUtil import SecurityUtil
from app.utils.TableUtil import TableUtil


class ImportThread(QThread):
    # FR-23, NFR-24: nạp dữ liệu chạy nền, báo tiến độ theo từng tệp
    progress = pyqtSignal(str, int, int)
    done = pyqtSignal(list)

    def __init__(self,files):
        super().__init__()
        self.files=files            # [(loại, đường dẫn)] theo thứ tự users -> movies -> ratings
        self.stopRequested=False
    def run(self):
        from app.utils.DataImportUtil import DataImportUtil
        functions={"users":DataImportUtil.importUsers,"movies":DataImportUtil.importMovies,
                   "ratings":DataImportUtil.importRatings}
        results=[]
        for (kind,path) in self.files:
            if self.stopRequested:
                break
            name=os.path.basename(path)
            self.progress.emit(name,0,1)
            try:
                result=functions[kind](path,lambda d,t,n=name: self.progress.emit(n,d,t),lambda: self.stopRequested)
            except Exception as e:
                from app.utils.DataImportUtil import ImportResult
                result=ImportResult(name)
                result.addError(f"Không đọc được tệp: {e}",0)
                result.interrupted=True
            results.append(result)
        self.done.emit(results)


class DataManagementMainWindowEx(Ui_MainWindow, AdminNavigation):
    PAGE_SIZE = 50
    # Thứ tự khớp comboBoxMovieSort
    MOVIE_SORT_KEYS = ["id", "count", "rating", "year", "duration", "title"]

    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)
        self.MainWindow=MainWindow
        self.moviePage=0
        self.userPage=0
        self.ratingPage=0
        self.df_movies=None
        self.df_users=None
        self.df_ratings=None
        self.currentUserId=None
        self.importThread=None
        self.lineEditSearchMovie.addAction(QIcon("../images/ic_search_dark.png"), QLineEdit.ActionPosition.LeadingPosition)
        self.lineEditSearchUser.addAction(QIcon("../images/ic_search_dark.png"), QLineEdit.ActionPosition.LeadingPosition)
        FormUtil.fillProfileCombos(self.comboBoxGender,self.comboBoxAge,self.comboBoxOccupation)
        self.fillUserFilterCombos()
        self.pushButtonStopImport.setVisible(False)
        self.setupNavigation()
        self.setupSignalAndSlot()
    def showWindow(self):
        self.MainWindow.showMaximized()
    def fillUserFilterCombos(self):
        # Bộ lọc người dùng (FR-21): "Tất cả" + danh mục + "Chưa cung cấp"
        for (combo,items,first) in ((self.comboBoxUserGender,CatalogUtil.GENDERS.items(),"Tất cả giới tính"),
                                    (self.comboBoxUserAge,CatalogUtil.AGE_GROUPS.items(),"Tất cả nhóm tuổi"),
                                    (self.comboBoxUserOccupation,list(enumerate(CatalogUtil.OCCUPATIONS)),
                                     "Tất cả nghề nghiệp")):
            combo.clear()
            combo.addItem(first,None)
            for (code,label) in items:
                combo.addItem(label,code)
            combo.addItem("Chưa cung cấp",customerDAO.NOT_PROVIDED)
            combo.setToolTip(first.replace("Tất cả ","Lọc theo "))

    def setupSignalAndSlot(self):
        # Phim
        self.pushButtonSearchMovie.clicked.connect(self.searchMovies)
        self.lineEditSearchMovie.returnPressed.connect(self.searchMovies)
        self.comboBoxGenreFilter.currentIndexChanged.connect(self.searchMovies)
        self.comboBoxMovieStatus.currentIndexChanged.connect(self.searchMovies)
        self.comboBoxMovieSort.currentIndexChanged.connect(self.searchMovies)
        self.radioButtonMovieAsc.toggled.connect(lambda checked: self.searchMovies() if checked else None)
        self.radioButtonMovieDesc.toggled.connect(lambda checked: self.searchMovies() if checked else None)
        self.pushButtonClearMovieFilter.clicked.connect(self.clearMovieFilter)
        self.pushButtonMoviePrev.clicked.connect(lambda: self.changeMoviePage(-1))
        self.pushButtonMovieNext.clicked.connect(lambda: self.changeMoviePage(1))
        self.tableWidgetMovies.itemSelectionChanged.connect(self.showMovieDetail)
        self.pushButtonNewMovie.clicked.connect(self.clearMovieForm)
        self.pushButtonSaveMovie.clicked.connect(self.process_saveMovie)
        self.pushButtonDeleteMovie.clicked.connect(self.process_deleteMovie)
        # Người dùng
        self.pushButtonSearchUser.clicked.connect(self.searchUsers)
        self.lineEditSearchUser.returnPressed.connect(self.searchUsers)
        self.comboBoxUserStatus.currentIndexChanged.connect(self.searchUsers)
        for combo in (self.comboBoxUserGender,self.comboBoxUserAge,self.comboBoxUserOccupation):
            combo.currentIndexChanged.connect(self.searchUsers)
        self.pushButtonClearUserFilter.clicked.connect(self.clearUserFilter)
        self.pushButtonUserPrev.clicked.connect(lambda: self.changeUserPage(-1))
        self.pushButtonUserNext.clicked.connect(lambda: self.changeUserPage(1))
        self.tableWidgetUsers.itemSelectionChanged.connect(self.showUserDetail)
        self.pushButtonNewUser.clicked.connect(self.clearUserForm)
        self.pushButtonSaveUser.clicked.connect(self.process_saveUser)
        self.pushButtonResetPassword.clicked.connect(self.process_resetPassword)
        self.pushButtonLockUser.clicked.connect(lambda: self.process_lockUser(0))
        self.pushButtonUnlockUser.clicked.connect(lambda: self.process_lockUser(1))
        self.pushButtonViewRatings.clicked.connect(self.viewUserRatings)
        # Đánh giá
        self.pushButtonFilterRatings.clicked.connect(self.searchRatings)
        self.lineEditRatingUser.returnPressed.connect(self.searchRatings)
        self.lineEditRatingMovie.returnPressed.connect(self.searchRatings)
        self.pushButtonRatingPrev.clicked.connect(lambda: self.changeRatingPage(-1))
        self.pushButtonRatingNext.clicked.connect(lambda: self.changeRatingPage(1))
        self.pushButtonMarkInvalid.clicked.connect(lambda: self.process_setValid(0))
        self.pushButtonMarkValid.clicked.connect(lambda: self.process_setValid(1))
        self.pushButtonDeleteRating.clicked.connect(self.process_deleteRatings)
        # Nạp dữ liệu và nhật ký
        self.pushButtonBrowseUsers.clicked.connect(lambda: self.browseFile(self.lineEditFileUsers,"users.dat"))
        self.pushButtonBrowseMovies.clicked.connect(lambda: self.browseFile(self.lineEditFileMovies,"movies.dat"))
        self.pushButtonBrowseRatings.clicked.connect(lambda: self.browseFile(self.lineEditFileRatings,"ratings.dat"))
        self.pushButtonUseDefault.clicked.connect(self.useDefaultFiles)
        self.pushButtonImport.clicked.connect(self.process_import)
        self.pushButtonStopImport.clicked.connect(self.process_stopImport)
        self.pushButtonRefreshLogs.clicked.connect(self.loadLogs)
        self.comboBoxLogAction.currentIndexChanged.connect(self.loadLogs)
        self.tabWidgetData.currentChanged.connect(self.tabChanged)
    def loadData(self):
        df=movieDAO.getGenres()
        self.comboBoxGenreFilter.blockSignals(True)
        if df is not None:
            for item in df.iloc:
                label=f"{CatalogUtil.genreVi(item['genre_name'])} ({item['genre_name']})"
                self.comboBoxGenreFilter.addItem(CatalogUtil.genreVi(item["genre_name"]),int(item["genre_id"]))
                widget_item=QListWidgetItem(label)
                widget_item.setData(Qt.ItemDataRole.UserRole,int(item["genre_id"]))
                widget_item.setFlags(widget_item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
                widget_item.setCheckState(Qt.CheckState.Unchecked)
                self.listWidgetGenres.addItem(widget_item)
        self.comboBoxGenreFilter.blockSignals(False)
        for action in (logDAO.LOCK_USER,logDAO.UNLOCK_USER,logDAO.RESET_PASSWORD,logDAO.HIDE_MOVIE,logDAO.DELETE_MOVIE,
                       logDAO.INVALID_RATING,logDAO.DELETE_RATING,logDAO.CHANGE_MODEL,logDAO.RETRAIN_MODEL,logDAO.IMPORT_DATA):
            self.comboBoxLogAction.addItem(action,action)
        self.clearMovieForm()
        self.searchMovies()
        self.clearUserForm()
        self.searchUsers()
    def tabChanged(self,index):
        widget=self.tabWidgetData.widget(index)
        if widget==self.tabRatings and self.df_ratings is None:
            self.searchRatings()
        elif widget==self.tabLogs:
            self.loadLogs()
    def log(self,action,target,result):
        logDAO.log(self.loginUser.employee_id,action,target,result)
    # ======================= QUẢN LÝ PHIM (FR-20) =======================
    def searchMovies(self):
        self.moviePage=0
        self.loadMovies()
    def clearMovieFilter(self):
        widgets=(self.lineEditSearchMovie,self.comboBoxGenreFilter,self.comboBoxMovieStatus,self.comboBoxMovieSort,
                 self.radioButtonMovieAsc,self.radioButtonMovieDesc)
        for widget in widgets:
            widget.blockSignals(True)
        self.lineEditSearchMovie.clear()
        for combo in (self.comboBoxGenreFilter,self.comboBoxMovieStatus,self.comboBoxMovieSort):
            combo.setCurrentIndex(0)
        self.radioButtonMovieAsc.setChecked(True)
        for widget in widgets:
            widget.blockSignals(False)
        self.searchMovies()
    def changeMoviePage(self,step):
        self.moviePage=max(0,self.moviePage+step)
        self.loadMovies()
    def loadMovies(self):
        keyword=self.lineEditSearchMovie.text().strip()
        genre_id=self.comboBoxGenreFilter.currentData()
        status=self.comboBoxMovieStatus.currentIndex()        # 0 hiển thị, 1 đã ẩn, 2 tất cả
        if keyword.isdigit():
            mv=movieDAO.getMovieById(int(keyword))
            df=pd.DataFrame([mv]) if mv is not None else movieDAO.getMovies("#không-có#",limit=1)
            total=len(df)
        else:
            args=dict(keyword=keyword,genre_id=genre_id,include_hidden=status==2,hidden_only=status==1)
            total=movieDAO.countMovies(**args)
            pages=max(1,(total+self.PAGE_SIZE-1)//self.PAGE_SIZE)
            self.moviePage=min(self.moviePage,pages-1)
            df=movieDAO.getMovies(sort=self.MOVIE_SORT_KEYS[self.comboBoxMovieSort.currentIndex()],
                                  descending=self.radioButtonMovieDesc.isChecked(),
                                  limit=self.PAGE_SIZE,offset=self.moviePage*self.PAGE_SIZE,**args)
        self.df_movies=df
        if df is None:
            self.labelMoviePage.setText("Không thể truy xuất dữ liệu phim.")
            return
        df_show=pd.DataFrame({"Mã phim":df["movie_id"],
                              "Tên phim":[PosterUtil.titleWithoutYear(t) for t in df["title"]],
                              "Thể loại":[PosterUtil.genresVi(g) for g in df["genres"]],
                              "Năm":df["release_year"],
                              "Thời lượng":[f"{int(d)} phút" if d is not None and d==d else "—" for d in df["duration_minutes"]],
                              "Điểm TB":[ChartUtil.vn(x,2) if x is not None and x==x and int(c)>0 else "—"
                                         for (x,c) in zip(df["avg_rating"],df["rating_count"])],
                              "Lượt đánh giá":[ChartUtil.vn(x) for x in df["rating_count"]],
                              "Trạng thái":["Đã ẩn" if int(h)==1 else "Hiển thị" for h in df["is_hidden"]]})
        TableUtil.showDataIntoTableWidget(self.tableWidgetMovies,df_show,stretch_column=(1,2),center_columns=(0,3,4,5,6,7))
        for row in range(len(df)):
            for col in (1,2):
                self.tableWidgetMovies.item(row,col).setToolTip(self.tableWidgetMovies.item(row,col).text())
            if int(df["is_hidden"].iloc[row])==1:
                self.tableWidgetMovies.item(row,7).setForeground(QColor("#DC2626"))
        pages=max(1,(total+self.PAGE_SIZE-1)//self.PAGE_SIZE)
        self.labelMoviePage.setText(f"Trang {self.moviePage+1}/{pages} · {ChartUtil.vn(total)} phim")
        self.pushButtonMoviePrev.setEnabled(self.moviePage>0)
        self.pushButtonMovieNext.setEnabled(self.moviePage<pages-1)
    def showMovieDetail(self):
        row=self.tableWidgetMovies.currentRow()
        if row<0 or self.df_movies is None or row>=len(self.df_movies):
            return
        mv=self.df_movies.iloc[row]
        self.lineEditMovieId.setText(str(int(mv["movie_id"])))
        # Ô tên phim chỉ chứa tên, năm nhập riêng ở ô Năm phát hành
        self.lineEditTitle.setText(PosterUtil.titleWithoutYear(mv["title"]))
        self.spinBoxYear.setValue(int(mv["release_year"]) if mv["release_year"] is not None and mv["release_year"]==mv["release_year"] else 2000)
        duration=mv["duration_minutes"]
        self.spinBoxDuration.setValue(int(duration) if duration is not None and duration==duration else 0)
        genre_ids=set(movieDAO.getGenreIds(int(mv["movie_id"])))
        for i in range(self.listWidgetGenres.count()):
            item=self.listWidgetGenres.item(i)
            checked=item.data(Qt.ItemDataRole.UserRole) in genre_ids
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.checkBoxHidden.setChecked(int(mv["is_hidden"])==1)
        has_ratings=int(mv["rating_count"])>0
        self.pushButtonDeleteMovie.setEnabled(True)
        self.pushButtonDeleteMovie.setText("Ẩn phim" if has_ratings else "Xóa")
    def clearMovieForm(self):
        self.tableWidgetMovies.clearSelection()
        self.lineEditMovieId.clear()
        self.lineEditTitle.clear()
        self.spinBoxYear.setValue(2000)
        self.spinBoxDuration.setValue(0)
        for i in range(self.listWidgetGenres.count()):
            self.listWidgetGenres.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.checkBoxHidden.setChecked(False)
        self.pushButtonDeleteMovie.setEnabled(False)
        self.pushButtonDeleteMovie.setText("Xóa")
        self.lineEditTitle.setFocus()
    def process_saveMovie(self):
        name=PosterUtil.titleWithoutYear(self.lineEditTitle.text().strip()) if self.lineEditTitle.text().strip() else ""
        # CSDL lưu tên phim không kèm năm (như src/database.py), năm phát hành nằm ở cột riêng
        title=name
        genre_ids=[self.listWidgetGenres.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.listWidgetGenres.count())
                   if self.listWidgetGenres.item(i).checkState()==Qt.CheckState.Checked]
        if title=="":
            self.showMessage("Vui lòng nhập tên phim.")
            self.lineEditTitle.setFocus()
            return
        if len(genre_ids)==0:
            self.showMessage("Vui lòng chọn ít nhất một thể loại.")
            return
        mv=Movie(None,title,self.spinBoxYear.value(),self.spinBoxDuration.value() or None,genre_ids,
                 1 if self.checkBoxHidden.isChecked() else 0,self.loginUser.employee_id)
        if self.lineEditMovieId.text()=="":
            new_id=movieDAO.insertMovie(mv)
            if new_id is None:
                self.showMessage("Thêm phim thất bại.",QMessageBox.Icon.Critical)
                return
            self.lineEditMovieId.setText(str(new_id))
            self.showMessage(f"Đã thêm phim mới (MovieID {new_id}). Phim mới chỉ được gợi ý sau khi "
                             f"cập nhật bộ máy gợi ý.",QMessageBox.Icon.Information)
        else:
            mv.movie_id=int(self.lineEditMovieId.text())
            old=movieDAO.getMovieById(mv.movie_id)
            if not movieDAO.updateMovie(mv):
                self.showMessage("Cập nhật phim thất bại.",QMessageBox.Icon.Critical)
                return
            if old is not None and int(old["is_hidden"])!=mv.is_hidden:
                self.log(logDAO.HIDE_MOVIE,f"MovieID {mv.movie_id} - {title}","Ẩn phim" if mv.is_hidden else "Hiện lại phim")
        self.loadMovies()
    def process_deleteMovie(self):
        if self.lineEditMovieId.text()=="":
            return
        movie_id=int(self.lineEditMovieId.text())
        title=f"{self.lineEditTitle.text().strip()} ({self.spinBoxYear.value()})"
        count=movieDAO.countAllRatings(movie_id)
        if count is None:
            self.showMessage("Không thể truy xuất dữ liệu đánh giá của phim.",QMessageBox.Icon.Critical)
            return
        if count>0:
            # FR-20: phim đã có đánh giá chỉ được ẩn để giữ lịch sử đánh giá
            if not self.confirm("Ẩn phim",f"Phim \"{title}\" đã có {ChartUtil.vn(count)} đánh giá nên không được xóa.\n"
                                           f"Bạn có muốn ẩn phim khỏi người dùng (không xuất hiện trong tìm kiếm, phim nổi "
                                           f"bật và gợi ý)?"):
                return
            ret=movieDAO.setHidden(movie_id,1,self.loginUser.employee_id)
            self.log(logDAO.HIDE_MOVIE,f"MovieID {movie_id} - {title}","Thành công" if ret else "Thất bại")
        else:
            if not self.confirm("Xóa phim",f"Xóa vĩnh viễn phim \"{title}\" (chưa có đánh giá nào)?"):
                return
            ret=movieDAO.deleteMovie(movie_id)
            self.log(logDAO.DELETE_MOVIE,f"MovieID {movie_id} - {title}","Thành công" if ret else "Thất bại")
            if ret:
                self.clearMovieForm()
        self.loadMovies()
    # ======================= QUẢN LÝ NGƯỜI DÙNG (FR-21) =======================
    def searchUsers(self):
        self.userPage=0
        self.loadUsers()
    def changeUserPage(self,step):
        self.userPage=max(0,self.userPage+step)
        self.loadUsers()
    def loadUsers(self):
        keyword=self.lineEditSearchUser.text().strip()
        status={0:None,1:1,2:0}[self.comboBoxUserStatus.currentIndex()]
        demo=dict(gender=self.comboBoxUserGender.currentData(),age=self.comboBoxUserAge.currentData(),
                  occupation=self.comboBoxUserOccupation.currentData())
        total=customerDAO.countCustomers(keyword,status,**demo)
        pages=max(1,(total+self.PAGE_SIZE-1)//self.PAGE_SIZE)
        self.userPage=min(self.userPage,pages-1)
        df=customerDAO.getCustomers(keyword,status,self.PAGE_SIZE,self.userPage*self.PAGE_SIZE,**demo)
        self.df_users=df
        if df is None:
            self.labelUserPage.setText("Không thể truy xuất dữ liệu người dùng.")
            return
        df_show=pd.DataFrame({"Mã người dùng":df["customer_id"],
                              "Họ tên":[CatalogUtil.textOrDash(n) for n in df["full_name"]],
                              "Email":df["email"],"Giới tính":[CatalogUtil.genderLabel(g) for g in df["gender"]],
                              "Nhóm tuổi":[CatalogUtil.ageLabel(a) for a in df["age"]],
                              "Nghề nghiệp":[CatalogUtil.occupationLabel(o) for o in df["occupation"]],
                              "Số đánh giá":[ChartUtil.vn(x) for x in df["rating_count"]],
                              "Trạng thái":["Hoạt động" if int(a)==1 else "Đã khóa" for a in df["is_active"]]})
        TableUtil.showDataIntoTableWidget(self.tableWidgetUsers,df_show,stretch_column=(1,2,5),center_columns=(0,3,4,6,7))
        for row in range(len(df)):
            for col in (1,2,5):
                self.tableWidgetUsers.item(row,col).setToolTip(self.tableWidgetUsers.item(row,col).text())
            if int(df["is_active"].iloc[row])==0:
                self.tableWidgetUsers.item(row,7).setForeground(QColor("#DC2626"))
        filtered=any(v is not None for v in demo.values()) or status is not None or keyword!=""
        self.labelUserPage.setText(f"Trang {self.userPage+1}/{pages} · {ChartUtil.vn(total)} người dùng"
                                   + (" phù hợp bộ lọc" if filtered else ""))
        self.pushButtonUserPrev.setEnabled(self.userPage>0)
        self.pushButtonUserNext.setEnabled(self.userPage<pages-1)
    def clearUserFilter(self):
        widgets=(self.lineEditSearchUser,self.comboBoxUserGender,self.comboBoxUserAge,self.comboBoxUserOccupation,
                 self.comboBoxUserStatus)
        for widget in widgets:
            widget.blockSignals(True)
        self.lineEditSearchUser.clear()
        for combo in widgets[1:]:
            combo.setCurrentIndex(0)
        for widget in widgets:
            widget.blockSignals(False)
        self.searchUsers()
    def showUserDetail(self):
        row=self.tableWidgetUsers.currentRow()
        if row<0 or self.df_users is None or row>=len(self.df_users):
            return
        cus=customerDAO.getById(int(self.df_users.iloc[row]["customer_id"]))
        if cus is None:
            return
        self.currentUserId=cus.customer_id
        self.lineEditUserId.setText(str(cus.customer_id))
        self.lineEditUserName.setText(cus.username)
        self.setReadOnly(self.lineEditUserName,True)
        self.lineEditFullName.setText(cus.full_name or "")
        self.lineEditEmail.setText(cus.email or "")
        FormUtil.selectData(self.comboBoxGender,cus.gender)
        FormUtil.selectData(self.comboBoxAge,cus.age)
        FormUtil.selectData(self.comboBoxOccupation,cus.occupation)
        active=cus.is_active==1
        rating_count=int(self.df_users.iloc[row]["rating_count"])
        self.labelUserStatus.setText(f"Trạng thái: <b style='color:{'#15803D' if active else '#DC2626'}'>"
                                     f"{'Đang hoạt động' if active else 'Đã khóa'}</b> · {ChartUtil.vn(rating_count)} "
                                     f"đánh giá · tạo lúc {str(cus.created_at)[:16]}")
        for button in (self.pushButtonResetPassword,self.pushButtonViewRatings,self.pushButtonLockUser):
            button.setEnabled(True)
        # Chỉ hiện nút phù hợp với trạng thái hiện tại để thanh nút không bị chật
        self.pushButtonLockUser.setVisible(active)
        self.pushButtonUnlockUser.setVisible(not active)
    def clearUserForm(self):
        self.tableWidgetUsers.clearSelection()
        self.currentUserId=None
        for edit in (self.lineEditUserId,self.lineEditUserName,self.lineEditFullName,self.lineEditEmail):
            edit.clear()
        self.setReadOnly(self.lineEditUserName,False)
        for combo in (self.comboBoxGender,self.comboBoxAge,self.comboBoxOccupation):
            combo.setCurrentIndex(0)
        self.labelUserStatus.setText("Thêm người dùng mới: hệ thống tạo mật khẩu tạm và hiển thị 1 lần sau khi lưu.")
        for button in (self.pushButtonResetPassword,self.pushButtonViewRatings):
            button.setEnabled(False)
        self.pushButtonLockUser.setVisible(True)
        self.pushButtonLockUser.setEnabled(False)
        self.pushButtonUnlockUser.setVisible(False)
    def setReadOnly(self,lineEdit,value):
        # Đổi readOnly lúc chạy thì phải áp lại stylesheet để ô hiển thị đúng màu xám
        lineEdit.setReadOnly(value)
        lineEdit.style().unpolish(lineEdit)
        lineEdit.style().polish(lineEdit)
    def readUserForm(self):
        full_name=self.lineEditFullName.text().strip()
        email=self.lineEditEmail.text().strip().lower()
        if full_name=="" or email=="":
            self.showMessage("Họ tên và email là thông tin bắt buộc.")
            return None
        if not SecurityUtil.isValidEmail(email):
            self.showMessage("Email không đúng định dạng.")
            return None
        if accountDAO.isEmailExist(email,self.currentUserId):
            self.showMessage("Email đã được tài khoản khác sử dụng.")
            return None
        cus=Customer(self.currentUserId,self.lineEditUserName.text().strip(),email,full_name,
                     self.comboBoxGender.currentData(),self.comboBoxAge.currentData(),self.comboBoxOccupation.currentData())
        return cus
    def process_saveUser(self):
        cus=self.readUserForm()
        if cus is None:
            return
        if self.currentUserId is None:
            if not SecurityUtil.isValidUsername(cus.username):
                self.showMessage("Tên đăng nhập gồm 3–30 ký tự: chữ cái, chữ số hoặc dấu gạch dưới.")
                return
            if accountDAO.isUsernameExist(cus.username):
                self.showMessage("Tên đăng nhập đã tồn tại.")
                return
            temp=SecurityUtil.generateTempPassword()
            new_id=customerDAO.register(cus,temp)
            if new_id is None:
                self.showMessage("Thêm người dùng thất bại.",QMessageBox.Icon.Critical)
                return
            self.showMessage(f"Đã tạo tài khoản {cus.username} (ID {new_id}).\n\nMật khẩu tạm: {temp}\n\n"
                             f"Hãy gửi mật khẩu này cho người dùng; hệ thống không lưu và không hiển thị lại.",
                             QMessageBox.Icon.Information)
            self.lineEditSearchUser.setText(cus.username)
            self.searchUsers()
            return
        if customerDAO.updateByAdmin(cus):
            self.loadUsers()
        else:
            self.showMessage("Cập nhật thất bại.",QMessageBox.Icon.Critical)
    def process_resetPassword(self):
        if self.currentUserId is None:
            return
        username=self.lineEditUserName.text()
        if not self.confirm("Đặt lại mật khẩu",f"Tạo mật khẩu tạm mới cho tài khoản {username}?\n"
                                                f"Mật khẩu hiện tại sẽ không dùng được nữa."):
            return
        temp=SecurityUtil.generateTempPassword()
        ret=customerDAO.setPassword(self.currentUserId,temp)
        self.log(logDAO.RESET_PASSWORD,f"ID {self.currentUserId} - {username}","Thành công" if ret else "Thất bại")
        if ret:
            # NFR-17: Admin không xem được mật khẩu gốc, chỉ nhận mật khẩu tạm vừa tạo
            self.showMessage(f"Mật khẩu tạm của {username}: {temp}\n\nHãy gửi cho người dùng và đề nghị đổi mật khẩu "
                             f"trong Hồ sơ cá nhân.",QMessageBox.Icon.Information)
        else:
            self.showMessage("Đặt lại mật khẩu thất bại.",QMessageBox.Icon.Critical)
    def process_lockUser(self,is_active):
        if self.currentUserId is None:
            return
        username=self.lineEditUserName.text()
        if is_active==0 and not self.confirm("Khóa tài khoản",
                                             f"Khóa tài khoản {username}?\n\nNgười dùng không đăng nhập được, phiên đang mở "
                                             f"sẽ bị kết thúc; lịch sử đánh giá được giữ nguyên."):
            return
        ret=customerDAO.setActive(self.currentUserId,is_active)
        self.log(logDAO.LOCK_USER if is_active==0 else logDAO.UNLOCK_USER,f"ID {self.currentUserId} - {username}",
                 "Thành công" if ret else "Thất bại")
        if not ret:
            self.showMessage("Thao tác thất bại.",QMessageBox.Icon.Critical)
            return
        row=self.tableWidgetUsers.currentRow()
        self.loadUsers()
        if row>=0:
            self.tableWidgetUsers.selectRow(row)
    def viewUserRatings(self):
        if self.currentUserId is None:
            return
        self.lineEditRatingUser.setText(str(self.currentUserId))
        self.lineEditRatingMovie.clear()
        self.comboBoxRatingScore.setCurrentIndex(0)
        self.comboBoxRatingValid.setCurrentIndex(0)
        self.tabWidgetData.setCurrentWidget(self.tabRatings)
        self.searchRatings()
    # ======================= QUẢN LÝ ĐÁNH GIÁ (FR-22) =======================
    def ratingFilter(self):
        user=self.lineEditRatingUser.text().strip()
        return dict(customer_id=int(user) if user.isdigit() else None,
                    movie_keyword=self.lineEditRatingMovie.text().strip(),
                    score=self.comboBoxRatingScore.currentIndex() or None,
                    validity={0:None,1:1,2:0}[self.comboBoxRatingValid.currentIndex()])
    def searchRatings(self):
        self.ratingPage=0
        self.loadRatings()
    def changeRatingPage(self,step):
        self.ratingPage=max(0,self.ratingPage+step)
        self.loadRatings()
    def loadRatings(self):
        args=self.ratingFilter()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        total=ratingDAO.countRatings(**args)
        pages=max(1,(total+self.PAGE_SIZE-1)//self.PAGE_SIZE)
        self.ratingPage=min(self.ratingPage,pages-1)
        df=ratingDAO.getRatings(limit=self.PAGE_SIZE,offset=self.ratingPage*self.PAGE_SIZE,**args)
        QApplication.restoreOverrideCursor()
        self.df_ratings=df
        if df is None:
            self.labelRatingPage.setText("Không thể truy xuất dữ liệu đánh giá.")
            return
        df_show=pd.DataFrame({"Mã":df["rating_id"],"Mã người dùng":df["customer_id"],"Tên đăng nhập":df["username"],
                              "Mã phim":df["movie_id"],"Tên phim":[PosterUtil.titleWithoutYear(t) for t in df["title"]],
                              "Điểm":[f"{s} ★" for s in df["rating_score"]],
                              "Bình luận":[c if isinstance(c,str) and c.strip()!="" else "—" for c in df["comment_text"]],
                              "Thời gian":[str(t)[:16] for t in df["rating_time"]],
                              "Trạng thái":["Hợp lệ" if int(v)==1 else "Không hợp lệ" for v in df["is_valid"]]})
        TableUtil.showDataIntoTableWidget(self.tableWidgetRatings,df_show,stretch_column=(4,6),center_columns=(0,1,3,5,7,8))
        for row in range(len(df)):
            for col in (4,6):
                self.tableWidgetRatings.item(row,col).setToolTip(self.tableWidgetRatings.item(row,col).text())
            if int(df["is_valid"].iloc[row])==0:
                for col in range(self.tableWidgetRatings.columnCount()):
                    self.tableWidgetRatings.item(row,col).setForeground(QColor("#9CA3AF"))
                self.tableWidgetRatings.item(row,8).setForeground(QColor("#DC2626"))
        self.labelRatingPage.setText(f"Trang {self.ratingPage+1}/{pages} · {ChartUtil.vn(total)} đánh giá")
        self.pushButtonRatingPrev.setEnabled(self.ratingPage>0)
        self.pushButtonRatingNext.setEnabled(self.ratingPage<pages-1)
    def selectedRatingIds(self):
        rows=sorted(set(index.row() for index in self.tableWidgetRatings.selectionModel().selectedRows()))
        if self.df_ratings is None:
            return []
        return [int(self.df_ratings.iloc[r]["rating_id"]) for r in rows if r<len(self.df_ratings)]
    def process_setValid(self,is_valid):
        ids=self.selectedRatingIds()
        if len(ids)==0:
            self.showMessage("Hãy chọn ít nhất một đánh giá trong bảng.")
            return
        ret=ratingDAO.setValid(ids,is_valid)
        if is_valid==0:
            self.log(logDAO.INVALID_RATING,"Mã đánh giá "+", ".join(str(i) for i in ids[:20]),
                     f"Thành công ({ret} bản ghi)" if ret>=0 else "Thất bại")
        self.loadRatings()
    def process_deleteRatings(self):
        ids=self.selectedRatingIds()
        if len(ids)==0:
            self.showMessage("Hãy chọn ít nhất một đánh giá trong bảng.")
            return
        if not self.confirm("Xóa đánh giá",f"Xóa vĩnh viễn {len(ids)} đánh giá đã chọn? Thao tác không thể hoàn tác.\n\n"
                                           f"Nếu chỉ muốn loại khỏi thống kê, hãy dùng \"Đánh dấu không hợp lệ\"."):
            return
        ret=ratingDAO.deleteByIds(ids)
        self.log(logDAO.DELETE_RATING,"Mã đánh giá "+", ".join(str(i) for i in ids[:20]),
                 f"Thành công ({ret} bản ghi)" if ret>0 else "Thất bại")
        self.loadRatings()
    # ======================= NẠP DỮ LIỆU BAN ĐẦU (FR-23) =======================
    def browseFile(self,lineEdit,default_name):
        (path,_)=QFileDialog.getOpenFileName(self.MainWindow,f"Chọn tệp {default_name}","",
                                             "Tệp MovieLens (*.dat *.txt *.csv);;Tất cả tệp (*.*)")
        if path:
            lineEdit.setText(path)
    def useDefaultFiles(self):
        folder=ConfigUtil.rootPath(ConfigUtil.get("paths","dataset_dir","data/raw"))
        for (edit,name) in ((self.lineEditFileUsers,"users.dat"),(self.lineEditFileMovies,"movies.dat"),
                            (self.lineEditFileRatings,"ratings.dat")):
            edit.setText(os.path.join(folder,name))
    def process_import(self):
        files=[(kind,edit.text().strip()) for (kind,edit) in (("users",self.lineEditFileUsers),
                                                              ("movies",self.lineEditFileMovies),
                                                              ("ratings",self.lineEditFileRatings)) if edit.text().strip()!=""]
        if len(files)==0:
            self.showMessage("Hãy chọn ít nhất một tệp cần nạp.")
            return
        missing=[path for (kind,path) in files if not os.path.exists(path)]
        if missing:
            self.showMessage("Không tìm thấy tệp:\n"+"\n".join(missing))
            return
        self.pushButtonImport.setEnabled(False)
        self.pushButtonStopImport.setVisible(True)
        self.progressBarImport.setValue(0)
        self.importThread=ImportThread(files)
        self.importThread.progress.connect(self.importProgress)
        self.importThread.done.connect(self.importFinished)
        self.importThread.start()
    def process_stopImport(self):
        if self.importThread is not None:
            self.importThread.stopRequested=True
            self.labelImportStatus.setText("Đang dừng sau lô hiện tại...")
    def importProgress(self,name,done,total):
        self.progressBarImport.setMaximum(max(total,1))
        self.progressBarImport.setValue(done)
        self.labelImportStatus.setText(f"Đang nạp {name}: {ChartUtil.vn(done)}/{ChartUtil.vn(total)} bản ghi hợp lệ")
    def importFinished(self,results):
        self.pushButtonImport.setEnabled(True)
        self.pushButtonStopImport.setVisible(False)
        rows=[]
        errors=[]
        for r in results:
            rows.append({"Tệp":r.name+(" (bị dừng)" if r.interrupted else ""),"Tổng bản ghi":ChartUtil.vn(r.total),
                         "Thành công":ChartUtil.vn(r.success),"Trùng ID":ChartUtil.vn(r.duplicate),
                         "Lỗi":ChartUtil.vn(r.error)})
            for (reason,(count,line_no)) in r.reasons.items():
                errors.append({"Tệp":r.name,"Lý do":reason,"Số bản ghi":ChartUtil.vn(count),"Ví dụ dòng":line_no})
        TableUtil.showDataIntoTableWidget(self.tableWidgetImportResult,pd.DataFrame(rows),stretch_column=0,
                                          center_columns=(1,2,3,4))
        TableUtil.showDataIntoTableWidget(self.tableWidgetImportErrors,
                                          pd.DataFrame(errors,columns=["Tệp","Lý do","Số bản ghi","Ví dụ dòng"]),
                                          stretch_column=1,center_columns=(2,3))
        summary="; ".join(f"{r.name}: {r.success} thành công, {r.duplicate} trùng, {r.error} lỗi" for r in results)
        self.log(logDAO.IMPORT_DATA,", ".join(r.name for r in results),summary)
        interrupted=any(r.interrupted for r in results)
        self.labelImportStatus.setText(("Đã dừng nạp dữ liệu. " if interrupted else "Hoàn tất nạp dữ liệu. ")+summary)
        self.progressBarImport.setValue(self.progressBarImport.maximum())
        self.searchMovies()
        self.searchUsers()
    # ======================= NHẬT KÝ QUẢN TRỊ (NFR-23) =======================
    def loadLogs(self):
        df=logDAO.getLogs(self.comboBoxLogAction.currentData())
        if df is None:
            return
        df_show=pd.DataFrame({"Thời điểm":[str(t)[:19] for t in df["created_at"]],"Admin":df["username"],
                              "Thao tác":df["action"],"Đối tượng":df["target"],"Kết quả":df["result"]})
        TableUtil.showDataIntoTableWidget(self.tableWidgetLogs,df_show,stretch_column=(3,4),center_columns=(0,1))
