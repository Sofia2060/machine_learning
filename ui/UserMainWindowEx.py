import pandas as pd
from PyQt6.QtCore import Qt, QTimer, QEvent, QObject
from PyQt6.QtGui import QIcon, QFontMetrics
from PyQt6.QtWidgets import (QMainWindow, QMessageBox, QFrame, QVBoxLayout, QHBoxLayout, QLabel,
                             QApplication, QLineEdit, QSizePolicy)

from ui.UserMainWindow import Ui_MainWindow
from app.dal.customerDAO import customerDAO
from app.dal.movieDAO import movieDAO
from app.dal.ratingDAO import ratingDAO
from app.ml.MovieRecommender import MovieRecommender
from app.utils.CatalogUtil import CatalogUtil
from app.utils.ChartUtil import ChartUtil
from app.utils.ConfigUtil import ConfigUtil
from app.utils.FormUtil import FormUtil
from app.utils.PosterUtil import PosterUtil
from app.utils.SessionUtil import SessionUtil
from app.utils.TableUtil import TableUtil


class ResizeWatcher(QObject):
    # Khi khung cuộn đổi kích thước (phóng to/thu nhỏ cửa sổ) -> sắp xếp lại số thẻ phim trên mỗi hàng
    def __init__(self,callback):
        super().__init__()
        self.callback=callback
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.Resize:
            self.callback()
        return False


class UserMainWindowEx(Ui_MainWindow):
    PAGE_SIZE = 24                      # số phim mỗi trang kết quả tìm kiếm
    CARD_WIDTH = 196
    POSTER_WIDTH = 172
    POSTER_HEIGHT = 244
    GRID_SPACING = 14
    # FR-08: tiêu chí sắp xếp, theo đúng thứ tự trong comboBoxSort
    SORT_KEYS = ["count", "rating", "year", "duration", "title"]

    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)
        self.MainWindow=MainWindow
        self.loginUser=None
        self.session=None
        self.page=0
        self.df_history=None
        self.df_history_view=None
        self.historyMovieId=None
        self.detailUI=None
        self.yearRange=(1919,2000)
        self.cards={"recommend":[],"popular":[],"results":[]}
        self.grids={"recommend":self.gridLayoutRecommend,"popular":self.gridLayoutPopular,"results":self.gridLayoutResults}
        self.labelColdStart.setVisible(False)
        self.lineEditSearch.addAction(QIcon("../images/ic_search_dark.png"), QLineEdit.ActionPosition.LeadingPosition)
        self.lineEditHistorySearch.addAction(QIcon("../images/ic_search_dark.png"), QLineEdit.ActionPosition.LeadingPosition)
        # Gõ từ khóa: đợi người dùng ngừng gõ 0,35 giây rồi mới tìm (không truy vấn theo từng phím)
        self.searchTimer=QTimer(self.MainWindow)
        self.searchTimer.setSingleShot(True)
        self.searchTimer.setInterval(350)
        self.searchTimer.timeout.connect(self.applyFilter)
        # Sắp xếp lại lưới thẻ phim khi cửa sổ đổi kích thước
        self.relayoutTimer=QTimer(self.MainWindow)
        self.relayoutTimer.setSingleShot(True)
        self.relayoutTimer.setInterval(80)
        self.relayoutTimer.timeout.connect(self.relayoutAll)
        self.resizeWatcher=ResizeWatcher(self.relayoutTimer.start)
        self.scrollAreaHome.viewport().installEventFilter(self.resizeWatcher)
        self.scrollAreaResults.viewport().installEventFilter(self.resizeWatcher)
        # NFR-15: các lựa chọn N của Top-N lấy từ cấu hình
        options=ConfigUtil.topNOptions()
        self.topNOptions=(options+options)[:2]
        self.radioButtonTop5.setText(f"Top {self.topNOptions[0]}")
        self.radioButtonTop10.setText(f"Top {self.topNOptions[1]}")
        default=ConfigUtil.get("recommendation","top_n_default",10)
        self.radioButtonTop5.setChecked(default==self.topNOptions[0])
        self.radioButtonTop10.setChecked(default!=self.topNOptions[0])
        FormUtil.fillProfileCombos(self.comboBoxProfileGender,self.comboBoxProfileAge,self.comboBoxProfileOccupation)
        self.stackedWidgetHome.setCurrentWidget(self.pageBrowse)
        self.setHistoryEditEnabled(False)
        self.setupSignalAndSlot()
    def showWindow(self):
        self.MainWindow.showMaximized()

    def setupSignalAndSlot(self):
        self.pushButtonLogout.clicked.connect(self.process_logout)
        # Trang chủ & Khám phá phim
        self.lineEditSearch.textChanged.connect(lambda text: self.searchTimer.start())
        self.lineEditSearch.returnPressed.connect(self.applyFilter)
        self.comboBoxGenre.currentIndexChanged.connect(self.applyFilter)
        self.spinBoxYearFrom.editingFinished.connect(self.applyFilter)
        self.spinBoxYearTo.editingFinished.connect(self.applyFilter)
        self.comboBoxSort.currentIndexChanged.connect(self.applyFilter)
        self.radioButtonSortDesc.toggled.connect(lambda checked: self.applyFilter() if checked else None)
        self.radioButtonSortAsc.toggled.connect(lambda checked: self.applyFilter() if checked else None)
        self.pushButtonClearFilter.clicked.connect(self.clearFilter)
        self.pushButtonPrev.clicked.connect(lambda: self.changePage(-1))
        self.pushButtonNext.clicked.connect(lambda: self.changePage(1))
        self.radioButtonTop5.toggled.connect(self.loadRecommendations)
        self.pushButtonRefresh.clicked.connect(self.loadRecommendations)
        # Lịch sử đánh giá của tôi
        self.lineEditHistorySearch.textChanged.connect(self.showHistory)
        self.comboBoxHistoryGenre.currentIndexChanged.connect(self.showHistory)
        self.comboBoxHistorySort.currentIndexChanged.connect(self.showHistory)
        self.radioButtonHistoryDesc.toggled.connect(lambda checked: self.showHistory() if checked else None)
        self.radioButtonHistoryAsc.toggled.connect(lambda checked: self.showHistory() if checked else None)
        self.pushButtonHistoryClear.clicked.connect(self.clearHistoryFilter)
        self.tableWidgetHistory.itemSelectionChanged.connect(self.selectHistoryRow)
        self.tableWidgetHistory.cellDoubleClicked.connect(lambda row,col: self.openMovieDetail(self.historyMovieId))
        self.pushButtonUpdateRating.clicked.connect(self.process_updateRating)
        self.pushButtonDeleteHistory.clicked.connect(self.process_deleteHistory)
        self.pushButtonOpenDetail.clicked.connect(lambda: self.openMovieDetail(self.historyMovieId))
        # Hồ sơ cá nhân
        self.pushButtonSaveProfile.clicked.connect(self.process_saveProfile)
        self.pushButtonEditGenres.clicked.connect(self.showGenrePreferenceUI)
        self.pushButtonChangePassword.clicked.connect(self.process_changePassword)
    def setLoginUser(self,us):
        if getattr(us,"role",None)!="user":
            raise PermissionError("Màn hình này dành cho tài khoản người dùng.")
        self.loginUser=us
        self.labelWelcome.setText(f"Xin chào, {us.full_name if us.full_name else us.username}")
        self.labelUserId.setText(f"@{us.username}")
        # NFR-19, FR-21: tự đăng xuất khi không thao tác 30 phút hoặc khi Admin khóa tài khoản
        self.session=SessionUtil(self.MainWindow,self.forceLogout,lambda: customerDAO.isActive(us.customer_id))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        MovieRecommender.loadModel()
        QApplication.restoreOverrideCursor()
        self.loadGenres()
        self.loadHome()
        self.loadHistory()
        self.loadProfile()
    def showMessage(self,text,icon=QMessageBox.Icon.Warning,title="CineMatch"):
        self.msgBox=QMessageBox(self.MainWindow)
        self.msgBox.setWindowTitle(title)
        self.msgBox.setIcon(icon)
        self.msgBox.setText(text)
        self.msgBox.exec()
    # ======================= THẺ PHIM =======================
    def clearCards(self,key):
        grid=self.grids[key]
        while grid.count()>0:
            item=grid.takeAt(0)
            widget=item.widget()
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.cards[key]=[]
    def elide(self,text,font,width):
        return QFontMetrics(font).elidedText(str(text),Qt.TextElideMode.ElideRight,width)
    def createMovieCard(self,item,mode,rank=None):
        # mode: "match" = gợi ý (độ tương thích %), "community" = phim nổi bật/kết quả tìm kiếm (điểm TB cộng đồng)
        movie_id=int(item["movie_id"])
        card=QFrame()
        card.setProperty("movieCard",True)
        card.setFixedWidth(self.CARD_WIDTH)
        card.setSizePolicy(QSizePolicy.Policy.Fixed,QSizePolicy.Policy.Fixed)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setToolTip(f"{PosterUtil.shortTitle(item['title'])} ({item['release_year']})\n"
                        f"{PosterUtil.genresVi(item['genres'])}\nNhấp để xem chi tiết và đánh giá")
        card.mousePressEvent=lambda event, mid=movie_id: self.openMovieDetail(mid)
        layout=QVBoxLayout(card)
        layout.setContentsMargins(12,12,12,12)
        layout.setSpacing(6)
        poster=QLabel()
        poster.setFixedSize(self.POSTER_WIDTH,self.POSTER_HEIGHT)
        PosterUtil.setPoster(poster,movie_id,item["title"],item["genres"],self.POSTER_WIDTH,self.POSTER_HEIGHT,
                             item["release_year"])
        layout.addWidget(poster)
        inner=self.CARD_WIDTH-24
        # Tên phim tối đa 2 dòng; dài hơn thì cắt bằng "…" theo đúng độ rộng chữ (không tràn khung)
        title=("#"+str(rank)+"  " if rank else "")+PosterUtil.shortTitle(item["title"])
        labelTitle=QLabel()
        # Cỡ chữ đặt bằng stylesheet (bộ QSS chung có QWidget { font-size }), đo độ rộng bằng đúng font sau khi áp style
        labelTitle.setStyleSheet("color: #111827; font-size: 10pt; font-weight: 700;")
        labelTitle.ensurePolished()
        font=labelTitle.font()
        labelTitle.setWordWrap(True)
        labelTitle.setText(self.twoLines(title,font,inner))
        labelTitle.setFixedHeight(QFontMetrics(font).lineSpacing()*2+2)
        labelTitle.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(labelTitle)
        labelMeta=QLabel()
        labelMeta.setStyleSheet("color: #6B7280; font-size: 9pt;")
        labelMeta.ensurePolished()
        labelMeta.setText(self.elide(f"{item['release_year']} · {PosterUtil.genresVi(item['genres'],', ')}",
                                     labelMeta.font(),inner))
        layout.addWidget(labelMeta)
        if mode=="match":
            labelScore=QLabel(f"{ChartUtil.vn(item['compatibility'],0)}% phù hợp")
            labelScore.setProperty("role","match")
            row=QHBoxLayout()
            row.addWidget(labelScore)
            row.addStretch()
            layout.addLayout(row)
        else:
            count=int(item["rating_count"]) if item["rating_count"]==item["rating_count"] else 0
            text=f"★ {ChartUtil.vn(item['avg_rating'],2)} · {ChartUtil.vn(count)} lượt" if count>0 else "Chưa có đánh giá"
            labelScore=QLabel(text)
            labelScore.setProperty("role","cardScore")
            layout.addWidget(labelScore)
        return card
    def twoLines(self,text,font,width):
        # Ngắt tên phim thành tối đa 2 dòng vừa độ rộng thẻ
        fm=QFontMetrics(font)
        words=str(text).split()
        line1=""
        while words and fm.horizontalAdvance((line1+" "+words[0]).strip())<=width:
            line1=(line1+" "+words.pop(0)).strip()
        if line1=="":
            return fm.elidedText(str(text),Qt.TextElideMode.ElideRight,width)
        if not words:
            return line1
        return line1+"\n"+fm.elidedText(" ".join(words),Qt.TextElideMode.ElideRight,width)
    def cardsPerRow(self,key):
        area=self.scrollAreaResults if key=="results" else self.scrollAreaHome
        width=area.viewport().width()-14
        return max(2,(width+self.GRID_SPACING)//(self.CARD_WIDTH+self.GRID_SPACING))
    def fillCards(self,key,df,mode,show_rank=False):
        self.clearCards(key)
        for item in df.iloc:
            self.cards[key].append(self.createMovieCard(item,mode,int(item["rank_no"]) if show_rank else None))
        self.relayout(key)
    def relayout(self,key):
        grid=self.grids[key]
        cards=self.cards[key]
        per_row=self.cardsPerRow(key)
        # Phim nổi bật luôn hiển thị đúng 2 hàng đầy đủ theo độ rộng màn hình
        limit=per_row*2 if key=="popular" else len(cards)
        for card in cards:
            grid.removeWidget(card)
        for (i,card) in enumerate(cards):
            if i>=limit:
                card.hide()
                continue
            grid.addWidget(card,i//per_row,i%per_row,Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignTop)
            card.show()
        # Chia đều phần dư cho khoảng cách giữa các thẻ để lưới phủ kín chiều ngang, các hàng thẳng cột với nhau
        area=self.scrollAreaResults if key=="results" else self.scrollAreaHome
        free=area.viewport().width()-14-per_row*self.CARD_WIDTH
        grid.setHorizontalSpacing(max(self.GRID_SPACING,free//max(1,per_row-1)) if per_row>1 else self.GRID_SPACING)
        for c in range(max(grid.columnCount(),per_row+1)):
            grid.setColumnStretch(c,0)
        grid.setColumnStretch(per_row,1)
    def relayoutAll(self):
        for key in self.cards:
            if self.cards[key]:
                self.relayout(key)
    # ======================= TRANG CHỦ (FR-07, FR-14, FR-15) =======================
    def loadHome(self):
        self.loadRecommendations()
        self.loadFeaturedMovies()
    def currentTopN(self):
        return self.topNOptions[0] if self.radioButtonTop5.isChecked() else self.topNOptions[1]
    def loadRecommendations(self):
        if self.loginUser is None:
            return
        customer_id=self.loginUser.customer_id
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        df=MovieRecommender.recommendTopN(customer_id,self.currentTopN()) if MovieRecommender.isReady() else None
        QApplication.restoreOverrideCursor()
        if df is None:
            # Người mới chưa có đánh giá (hoặc chưa đủ dữ liệu cá nhân hóa): trang chủ chỉ hiện phim nổi bật
            self.clearCards("recommend")
            self.widgetRecommendSection.setVisible(False)
            self.labelColdStart.setVisible(True)
            if not MovieRecommender.isReady():
                self.labelColdStart.setText("Hệ thống gợi ý cá nhân hóa tạm thời không khả dụng. Bạn vẫn có thể tìm "
                                            "kiếm, xem chi tiết và đánh giá phim như bình thường.")
            elif len(ratingDAO.getRatedMovieIds(customer_id))==0:
                self.labelColdStart.setText("Chào mừng bạn đến với CineMatch! Hãy tìm và đánh giá vài bộ phim bạn đã xem "
                                            "(nhấp vào một phim để chấm sao). Mục \"Gợi ý dành riêng cho bạn\" sẽ xuất "
                                            "hiện ngay sau khi bạn chấm từ 4 sao cho một phim.")
            else:
                self.labelColdStart.setText("Hệ thống chưa biết gu của bạn vì bạn chưa chấm phim nào từ 4 sao trở lên. "
                                            "Hãy chấm điểm cao cho vài phim bạn thích để nhận gợi ý dành riêng cho bạn.")
            return
        self.labelColdStart.setVisible(False)
        self.widgetRecommendSection.setVisible(True)
        rated=len(ratingDAO.getRatedMovieIds(customer_id))
        if len(df)==0:
            self.clearCards("recommend")
            self.labelRecommendSub.setText("Bạn đã đánh giá hết các phim mà hệ thống có thể gợi ý.")
            return
        self.labelRecommendSub.setText(f"{len(df)} phim phù hợp với bạn nhất, xếp hạng từ {rated} phim bạn đã đánh giá · "
                                       f"% là độ tương thích dự báo giữa bạn và phim")
        self.fillCards("recommend",df,"match",show_rank=True)
    def loadFeaturedMovies(self):
        threshold=ConfigUtil.featuredMinRatings()
        df=movieDAO.getFeaturedMovies(14,threshold)
        if df is None or len(df)==0:
            self.clearCards("popular")
            self.labelPopularSub.setText("Chưa đủ dữ liệu để xếp hạng phim nổi bật." if df is not None else
                                         "Không thể truy xuất dữ liệu phim. Vui lòng kiểm tra kết nối cơ sở dữ liệu.")
            return
        self.labelPopularSub.setText(f"Điểm trung bình cộng đồng cao nhất trong các phim có từ {threshold} lượt đánh giá trở lên")
        self.fillCards("popular",df,"community")
    # ======================= KHÁM PHÁ PHIM (FR-08, FR-09) =======================
    def loadGenres(self):
        df=movieDAO.getGenres()
        for combo in (self.comboBoxGenre,self.comboBoxHistoryGenre):
            combo.blockSignals(True)
            if df is not None:
                for item in df.iloc:
                    combo.addItem(CatalogUtil.genreVi(item["genre_name"]),item["genre_name"])
            combo.blockSignals(False)
        (y1,y2)=movieDAO.getYearRange()
        self.yearRange=(y1,y2)
        for spin in (self.spinBoxYearFrom,self.spinBoxYearTo):
            spin.blockSignals(True)
            spin.setRange(y1,y2)
        self.spinBoxYearFrom.setValue(y1)
        self.spinBoxYearTo.setValue(y2)
        for spin in (self.spinBoxYearFrom,self.spinBoxYearTo):
            spin.blockSignals(False)
    def isDefaultFilter(self):
        return self.lineEditSearch.text().strip()=="" and self.comboBoxGenre.currentIndex()==0 \
               and self.spinBoxYearFrom.value()==self.yearRange[0] and self.spinBoxYearTo.value()==self.yearRange[1] \
               and self.comboBoxSort.currentIndex()==0 and self.radioButtonSortDesc.isChecked()
    def applyFilter(self):
        # Ô tìm kiếm trống, chưa chọn bộ lọc -> trang chủ (Gợi ý + Phim nổi bật);
        # gõ từ khóa hoặc chọn bộ lọc -> khu vực bên dưới chuyển sang lưới kết quả tìm kiếm
        self.searchTimer.stop()
        if self.isDefaultFilter():
            self.stackedWidgetHome.setCurrentWidget(self.pageBrowse)
            return
        self.stackedWidgetHome.setCurrentWidget(self.pageResults)
        self.page=0
        self.loadMovies()
    def clearFilter(self):
        widgets=(self.lineEditSearch,self.comboBoxGenre,self.comboBoxSort,self.spinBoxYearFrom,self.spinBoxYearTo,
                 self.radioButtonSortDesc,self.radioButtonSortAsc)
        for widget in widgets:
            widget.blockSignals(True)
        self.lineEditSearch.clear()
        self.comboBoxGenre.setCurrentIndex(0)
        self.comboBoxSort.setCurrentIndex(0)
        self.spinBoxYearFrom.setValue(self.yearRange[0])
        self.spinBoxYearTo.setValue(self.yearRange[1])
        self.radioButtonSortDesc.setChecked(True)
        for widget in widgets:
            widget.blockSignals(False)
        self.applyFilter()
    def changePage(self,step):
        self.page=max(0,self.page+step)
        self.loadMovies()
        self.scrollAreaResults.verticalScrollBar().setValue(0)
    def loadMovies(self):
        keyword=self.lineEditSearch.text().strip()
        genre_name=self.comboBoxGenre.currentData()
        genre_id=None
        if genre_name is not None:
            df_genres=movieDAO.getGenres()
            match=df_genres[df_genres["genre_name"]==genre_name] if df_genres is not None else []
            genre_id=int(match.iloc[0]["genre_id"]) if len(match)>0 else None
        year_from=self.spinBoxYearFrom.value()
        year_to=self.spinBoxYearTo.value()
        if year_from>year_to:
            (year_from,year_to)=(year_to,year_from)
        sort=self.SORT_KEYS[self.comboBoxSort.currentIndex()]
        descending=self.radioButtonSortDesc.isChecked()
        total=movieDAO.countMovies(keyword,genre_id,year_from,year_to)
        pages=max(1,(total+self.PAGE_SIZE-1)//self.PAGE_SIZE)
        self.page=min(self.page,pages-1)
        df=movieDAO.getMovies(keyword,genre_id,year_from,year_to,sort,self.PAGE_SIZE,self.page*self.PAGE_SIZE,
                              descending=descending)
        if df is None:
            self.clearCards("results")
            self.labelSearchResult.setText("Không thể truy xuất dữ liệu phim. Vui lòng kiểm tra kết nối cơ sở dữ liệu.")
            return
        conditions=[]
        if keyword!="":
            conditions.append(f"từ khóa \"{keyword}\"")
        if genre_name is not None:
            conditions.append(f"thể loại {CatalogUtil.genreVi(genre_name)}")
        if (year_from,year_to)!=self.yearRange:
            conditions.append(f"năm {year_from}–{year_to}")
        order=f"{self.comboBoxSort.currentText().lower()} {'giảm dần' if descending else 'tăng dần'}"
        if total==0:
            self.labelSearchResult.setText("Không tìm thấy phim phù hợp. Hãy thử từ khóa khác hoặc bấm \"Xóa bộ lọc\".")
        else:
            self.labelSearchResult.setText(f"Tìm thấy {ChartUtil.vn(total)} phim"
                                           + (f" theo {', '.join(conditions)}" if conditions else "")
                                           + f" · sắp xếp theo {order}")
        self.fillCards("results",df,"community")
        self.labelPage.setText(f"Trang {self.page+1}/{pages}")
        self.pushButtonPrev.setEnabled(self.page>0)
        self.pushButtonNext.setEnabled(self.page<pages-1)
    # ======================= CHI TIẾT PHIM (FR-10, FR-11) =======================
    def openMovieDetail(self,movie_id):
        if movie_id is None:
            return
        from ui.MovieDetailDialogEx import MovieDetailDialogEx
        from PyQt6.QtWidgets import QDialog
        self.detailUI=MovieDetailDialogEx()
        dialog=QDialog(self.MainWindow)
        self.detailUI.setupUi(dialog)
        if not self.detailUI.showMovie(self.loginUser.customer_id,int(movie_id)):
            self.showMessage("Không tìm thấy thông tin phim.")
            return
        dialog.exec()
        if self.detailUI.changed:
            self.ratingsChanged()
    def ratingsChanged(self):
        # Sau khi đánh giá thay đổi: cập nhật lịch sử và gợi ý (người mới được cá nhân hóa ngay nhờ fold-in)
        self.loadHistory()
        self.loadRecommendations()
        if self.stackedWidgetHome.currentWidget()==self.pageResults:
            self.loadMovies()
    # ======================= LỊCH SỬ ĐÁNH GIÁ CỦA TÔI (FR-11, FR-12) =======================
    def loadHistory(self):
        self.df_history=ratingDAO.getRatingsByCustomer(self.loginUser.customer_id)
        self.showHistory()
    def clearHistoryFilter(self):
        widgets=(self.lineEditHistorySearch,self.comboBoxHistoryGenre,self.comboBoxHistorySort,
                 self.radioButtonHistoryDesc,self.radioButtonHistoryAsc)
        for widget in widgets:
            widget.blockSignals(True)
        self.lineEditHistorySearch.clear()
        self.comboBoxHistoryGenre.setCurrentIndex(0)
        self.comboBoxHistorySort.setCurrentIndex(0)
        self.radioButtonHistoryDesc.setChecked(True)
        for widget in widgets:
            widget.blockSignals(False)
        self.showHistory()
    def showHistory(self):
        df=self.df_history
        if df is None:
            self.labelHistoryInfo.setText("Không thể truy xuất lịch sử đánh giá.")
            return
        view=df.copy()
        keyword=self.lineEditHistorySearch.text().strip().lower()
        if keyword!="":
            view=view[view["title"].str.lower().str.contains(keyword,regex=False)]
        genre=self.comboBoxHistoryGenre.currentData()
        if genre is not None:
            view=view[view["genres"].fillna("").apply(lambda g: genre in str(g).split("|"))]
        # FR-12: mặc định mới nhất trước
        column="rating_time" if self.comboBoxHistorySort.currentIndex()==0 else "rating_score"
        ascending=self.radioButtonHistoryAsc.isChecked()
        view=view.sort_values([column,"rating_time"],ascending=[ascending,False],kind="stable").reset_index(drop=True)
        self.df_history_view=view
        df_show=pd.DataFrame({"Mã phim":view["movie_id"],
                              "Tên phim":[PosterUtil.shortTitle(t) for t in view["title"]],
                              "Thể loại":[PosterUtil.genresVi(g) for g in view["genres"]],
                              "Năm":view["release_year"],
                              "Thời lượng":[f"{int(d)} phút" if d is not None and d==d else "—" for d in view["duration_minutes"]],
                              "Điểm của bạn":[f"{int(r)} ★" for r in view["rating_score"]],
                              "Bình luận của bạn":[c if isinstance(c,str) and c.strip()!="" else "—" for c in view["comment_text"]],
                              "Ngày đánh giá":[str(d)[:16] for d in view["rating_time"]]})
        TableUtil.showDataIntoTableWidget(self.tableWidgetHistory,df_show,stretch_column=(1,2,6),center_columns=(0,3,4,5,7))
        for row in range(self.tableWidgetHistory.rowCount()):
            for col in (1,2,6):
                item=self.tableWidgetHistory.item(row,col)
                if item is not None:
                    item.setToolTip(item.text())
        if len(df)==0:
            self.labelHistoryInfo.setText("Bạn chưa đánh giá phim nào. Hãy vào \"Trang chủ & Khám phá phim\", nhấp vào "
                                          "một phim để chấm sao.")
        else:
            avg=df["rating_score"].astype(float).mean()
            shown="" if len(view)==len(df) else f" · đang hiển thị {len(view)} đánh giá theo bộ lọc"
            self.labelHistoryInfo.setText(f"Bạn đang có {len(df)} đánh giá, điểm trung bình bạn chấm {ChartUtil.vn(avg,2)} ★"
                                          f"{shown} · chọn một dòng để sửa hoặc xóa đánh giá.")
        # Giữ dòng đang chọn sau khi lọc/cập nhật (nếu phim vẫn còn trong danh sách)
        if self.historyMovieId is not None and self.historyMovieId in set(int(x) for x in view["movie_id"]):
            row=int(view.index[view["movie_id"]==self.historyMovieId][0])
            self.tableWidgetHistory.selectRow(row)
        else:
            self.historyMovieId=None
            self.setHistoryEditEnabled(False)
    def setHistoryEditEnabled(self,enabled):
        for widget in (self.comboBoxEditRating,self.lineEditEditComment,self.pushButtonUpdateRating,
                       self.pushButtonDeleteHistory,self.pushButtonOpenDetail):
            widget.setEnabled(enabled)
        if not enabled:
            self.labelEditMovie.setText("Chọn một dòng trong bảng để sửa số sao, bình luận hoặc xóa đánh giá.")
            self.lineEditEditComment.clear()
    def selectHistoryRow(self):
        row=self.tableWidgetHistory.currentRow()
        if row<0 or self.df_history_view is None or row>=len(self.df_history_view):
            return
        item=self.df_history_view.iloc[row]
        self.historyMovieId=int(item["movie_id"])
        self.setHistoryEditEnabled(True)
        title=f"{PosterUtil.shortTitle(item['title'])} ({item['release_year']})"
        self.labelEditMovie.setText(self.elide(title,self.labelEditMovie.font(),max(200,self.labelEditMovie.width())))
        self.labelEditMovie.setToolTip(title)
        self.comboBoxEditRating.setCurrentIndex(5-int(item["rating_score"]))
        comment=item["comment_text"]
        self.lineEditEditComment.setText(comment if isinstance(comment,str) else "")
        self.lineEditEditComment.setCursorPosition(0)
    def process_updateRating(self):
        if self.historyMovieId is None:
            return
        score=5-self.comboBoxEditRating.currentIndex()
        if ratingDAO.saveRating(self.loginUser.customer_id,self.historyMovieId,score,self.lineEditEditComment.text()):
            self.ratingsChanged()
            self.showMessage("Đã cập nhật đánh giá.",QMessageBox.Icon.Information,"Lịch sử đánh giá")
        else:
            self.showMessage("Lưu đánh giá thất bại, vui lòng thử lại.",QMessageBox.Icon.Critical,"Lịch sử đánh giá")
    def process_deleteHistory(self):
        if self.historyMovieId is None:
            return
        ret=QMessageBox.question(self.MainWindow,"Xóa đánh giá","Bạn có chắc muốn xóa đánh giá của mình cho phim này?",
                                 QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if ret!=QMessageBox.StandardButton.Yes:
            return
        if ratingDAO.deleteRating(self.loginUser.customer_id,self.historyMovieId):
            self.historyMovieId=None
            self.ratingsChanged()
        else:
            self.showMessage("Xóa đánh giá thất bại, vui lòng thử lại.",QMessageBox.Icon.Critical,"Lịch sử đánh giá")
    # ======================= HỒ SƠ CÁ NHÂN (FR-05) =======================
    def favoriteGenreNames(self):
        ids=set(customerDAO.getFavoriteGenreIds(self.loginUser.customer_id))
        df=movieDAO.getGenres()
        if df is None:
            return []
        return [g for (g,i) in zip(df["genre_name"],df["genre_id"]) if int(i) in ids]
    def loadProfile(self):
        cus=customerDAO.getById(self.loginUser.customer_id)
        if cus is None:
            return
        self.loginUser=cus
        self.lineEditProfileUserName.setText(cus.username)
        self.lineEditProfileEmail.setText(cus.email)
        self.lineEditProfileFullName.setText(cus.full_name or "")
        FormUtil.selectData(self.comboBoxProfileGender,cus.gender)
        FormUtil.selectData(self.comboBoxProfileAge,cus.age)
        FormUtil.selectData(self.comboBoxProfileOccupation,cus.occupation)
        self.showFavoriteGenres()
    def showFavoriteGenres(self):
        names=self.favoriteGenreNames()
        if len(names)==0:
            self.labelFavoriteGenres.setText("<span style='color:#6B7280'>Bạn chưa chọn thể loại yêu thích.</span>")
            return
        chips="".join(f"<span style='background-color:#DBEAFE; color:#1E3A8A;'>&nbsp;{CatalogUtil.genreVi(g)}&nbsp;</span>&nbsp; "
                      for g in names)
        self.labelFavoriteGenres.setText(chips)
    def favoriteGenresChanged(self):
        self.showFavoriteGenres()
    def showGenrePreferenceUI(self):
        from ui.GenrePreferenceMainWindowEx import GenrePreferenceMainWindowEx
        self.genreUI=GenrePreferenceMainWindowEx()
        self.genreUI.setupUi(QMainWindow())
        self.genreUI.setLoginUser(self.loginUser,fromProfile=True,parentUI=self)
        self.genreUI.showWindow()
    def process_saveProfile(self):
        full_name=self.lineEditProfileFullName.text().strip()
        if full_name=="":
            self.showMessage("Họ và tên là thông tin bắt buộc.",title="Hồ sơ cá nhân")
            self.lineEditProfileFullName.setFocus()
            return
        cus=self.loginUser
        cus.full_name=full_name
        cus.gender=self.comboBoxProfileGender.currentData()
        cus.age=self.comboBoxProfileAge.currentData()
        cus.occupation=self.comboBoxProfileOccupation.currentData()
        if customerDAO.updateProfile(cus):
            self.labelWelcome.setText(f"Xin chào, {full_name}")
            self.showMessage("Đã cập nhật hồ sơ cá nhân.",QMessageBox.Icon.Information,"Hồ sơ cá nhân")
        else:
            self.showMessage("Không lưu được hồ sơ, vui lòng thử lại.",QMessageBox.Icon.Critical,"Hồ sơ cá nhân")
    def process_changePassword(self):
        from app.utils.SecurityUtil import SecurityUtil

        current=self.lineEditCurrentPassword.text()
        new=self.lineEditNewPassword.text()
        confirm=self.lineEditConfirmPassword.text()
        if current=="" or new=="" or confirm=="":
            self.showMessage("Vui lòng nhập đủ mật khẩu hiện tại, mật khẩu mới và nhập lại mật khẩu mới.",
                             title="Đổi mật khẩu")
            return
        if not customerDAO.checkPassword(self.loginUser.customer_id,current):
            self.showMessage("Mật khẩu hiện tại không đúng.",title="Đổi mật khẩu")
            self.lineEditCurrentPassword.setFocus()
            return
        if not SecurityUtil.isStrongPassword(new):
            self.showMessage("Mật khẩu mới tối thiểu 8 ký tự và phải có cả chữ lẫn số.",title="Đổi mật khẩu")
            return
        if new!=confirm:
            self.showMessage("Mật khẩu nhập lại không khớp.",title="Đổi mật khẩu")
            return
        if customerDAO.setPassword(self.loginUser.customer_id,new):
            for edit in (self.lineEditCurrentPassword,self.lineEditNewPassword,self.lineEditConfirmPassword):
                edit.clear()
            self.showMessage("Đổi mật khẩu thành công.",QMessageBox.Icon.Information,"Đổi mật khẩu")
        else:
            self.showMessage("Không đổi được mật khẩu, vui lòng thử lại.",QMessageBox.Icon.Critical,"Đổi mật khẩu")
    # ======================= ĐĂNG XUẤT =======================
    def openLogin(self):
        if self.session is not None:
            self.session.stop()
        from ui.LoginMainWindowEx import LoginMainWindowEx
        self.myui=LoginMainWindowEx()
        self.myui.setupUi(QMainWindow())
        self.myui.showWindow()
        self.MainWindow.close()
    def forceLogout(self,message):
        self.openLogin()
        self.myui.showMessage(message)
    def process_logout(self):
        ret=QMessageBox.question(self.MainWindow,"Đăng xuất","Bạn có chắc muốn đăng xuất?",
                                 QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)
        if ret!=QMessageBox.StandardButton.Yes:
            return
        self.openLogin()
