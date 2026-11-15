import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from ui.ModelTestMainWindow import Ui_MainWindow
from ui.AdminNavigation import AdminNavigation
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from app.dal.customerDAO import customerDAO
from app.dal.ratingDAO import ratingDAO
from app.ml.MovieRecommender import MovieRecommender
from app.utils.CatalogUtil import CatalogUtil
from app.utils.ChartUtil import ChartUtil
from app.utils.TableUtil import TableUtil


class ModelTestMainWindowEx(Ui_MainWindow, AdminNavigation):
    # FR-26: Admin nhập UserID bất kỳ, xem Top-N mà mô hình đang dùng gợi ý (kèm % phù hợp, giống phía người dùng)
    # và đối chiếu với các phim khách hàng đó đã đánh giá cao để đánh giá mô hình hiện tại.
    # Chỉ để kiểm tra: không lưu vào lịch sử gợi ý (recommendTopN save=False) nên không ảnh hưởng thống kê FR-19.
    LIKED_SCORE = 4          # phim "đánh giá cao" = từ 4 sao (cùng ngưỡng với dữ liệu huấn luyện NeuMF)
    TOP_GENRES = 3           # số thể loại khách hàng chấm cao nhiều nhất dùng để đo mức trùng khớp
    MIN_RANDOM_RATINGS = 20  # chọn ngẫu nhiên khách hàng có ít nhất 20 đánh giá hợp lệ

    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)
        self.MainWindow=MainWindow
        self.setupNavigation()
        self.setupPlot()
        self.setupSignalAndSlot()
        self.clearResult()
    def showWindow(self):
        self.MainWindow.showMaximized()
    def setupSignalAndSlot(self):
        self.pushButtonRunTest.clicked.connect(self.process_runTest)
        self.lineEditUserId.returnPressed.connect(self.process_runTest)
        self.pushButtonRandomUser.clicked.connect(self.process_randomUser)
        self.radioButtonTop5.toggled.connect(self.topNChanged)
    def setupPlot(self):
        ChartUtil.setupStyle()
        self.figure=plt.figure(figsize=(4,3))
        self.figure.set_layout_engine("tight")
        self.canvas=FigureCanvas(self.figure)
        self.canvas.setMinimumHeight(260)
        self.verticalLayoutPlotCompare.addWidget(self.canvas)
    def loadData(self):
        # Gọi sau khi đăng nhập (AdminNavigation.setLoginUser): nạp mô hình nếu chưa nạp
        if not MovieRecommender.isReady():
            MovieRecommender.loadModel()
        if not MovieRecommender.isReady():
            self.labelUserDetail.setText("<span style='color:#DC2626'>Chưa nạp được mô hình gợi ý. "
                                         "Kiểm tra màn hình Hiệu quả gợi ý → Bộ máy gợi ý.</span>")
            self.pushButtonRunTest.setEnabled(False)
            self.pushButtonRandomUser.setEnabled(False)
    def getTopN(self):
        return 5 if self.radioButtonTop5.isChecked() else 10
    def topNChanged(self,checked=None):
        # Đổi Top 5 / Top 10 thì chạy lại ngay nếu đã có khách hàng đang thử nghiệm
        if self.lineEditUserId.text().strip()!="" and self.tableWidgetTopN.rowCount()>0:
            self.process_runTest()
    # ======================= XỬ LÝ =======================
    def process_randomUser(self):
        customer_id=ratingDAO.getRandomCustomerId(self.MIN_RANDOM_RATINGS)
        if customer_id is None:
            self.showMessage("Chưa có khách hàng nào đủ đánh giá để thử nghiệm.")
            return
        self.lineEditUserId.setText(str(customer_id))
        self.process_runTest()
    def process_runTest(self):
        text=self.lineEditUserId.text().strip()
        if not text.isdigit() or int(text)<=0:
            self.showMessage("UserID phải là số nguyên dương, ví dụ: 1.")
            self.lineEditUserId.setFocus()
            return
        customer_id=int(text)
        cus=customerDAO.getById(customer_id)
        if cus is None:
            self.clearResult()
            self.showMessage(f"Không tìm thấy khách hàng có UserID = {customer_id}.")
            return
        if not MovieRecommender.isReady() and not MovieRecommender.loadModel():
            self.showMessage("Chưa nạp được mô hình gợi ý.")
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            df_ratings=ratingDAO.getRatingsByCustomer(customer_id)
            df_valid=df_ratings[df_ratings["is_valid"]==1] if df_ratings is not None else pd.DataFrame()
            df_liked=df_valid[df_valid["rating_score"]>=self.LIKED_SCORE] if len(df_valid)>0 else df_valid
            df_top=MovieRecommender.recommendTopN(customer_id,self.getTopN(),save=False)
            self.showUser(cus,df_valid,df_liked)
            self.showTopN(df_top)
            self.showLiked(df_liked,len(df_valid))
            self.showCompare(df_top,df_liked)
        finally:
            QApplication.restoreOverrideCursor()
    # ======================= HIỂN THỊ =======================
    def userState(self,customer_id,n_liked):
        # Cách mô hình nhận diện khách hàng (giống luồng gợi ý ở mục 3.6.2)
        if MovieRecommender.isKnownUser(customer_id):
            return "Khách hàng có trong dữ liệu huấn luyện – dùng vector đã học"
        if n_liked>0:
            return "Khách hàng mới – cá nhân hóa ngay bằng fold-in từ các phim đã chấm từ 4 sao"
        return "Chưa đủ dữ liệu – khách hàng chưa chấm phim nào từ 4 sao nên chưa có gợi ý cá nhân hóa"
    def showUser(self,cus,df_valid,df_liked):
        name=cus.full_name if cus.full_name else f"Khách hàng {cus.customer_id}"
        self.labelUserTitle.setText(f"{name}  ·  UserID {cus.customer_id}  ·  @{cus.username}")
        info=[CatalogUtil.genderLabel(cus.gender),CatalogUtil.ageLabel(cus.age),
              CatalogUtil.occupationLabel(cus.occupation)]
        self.labelUserDetail.setText(" · ".join(info)+f"<br>{ChartUtil.vn(len(df_valid))} đánh giá hợp lệ, trong đó "
                                     f"<b>{ChartUtil.vn(len(df_liked))}</b> phim từ 4 sao<br>"
                                     f"<i>{self.userState(cus.customer_id,len(df_liked))}</i>")
    def showTopN(self,df_top):
        if df_top is None or len(df_top)==0:
            self.tableWidgetTopN.setRowCount(0)
            self.labelTopNTitle.setText("Top-N phim mô hình gợi ý")
            self.labelTopNSub.setText("Mô hình chưa đưa ra được gợi ý cá nhân hóa cho khách hàng này.")
            return
        self.labelTopNTitle.setText(f"Top {len(df_top)} phim mô hình gợi ý")
        self.labelTopNSub.setText("Đã loại các phim khách hàng đã đánh giá và phim đang bị ẩn · "
                                  "% phù hợp là độ tương thích dự báo giữa khách hàng và phim")
        df_show=pd.DataFrame({"Hạng":[f"#{r}" for r in df_top["rank_no"]],
                              "Phim":df_top["title"],
                              "Năm":[CatalogUtil.textOrDash(y) for y in df_top["release_year"]],
                              "Thể loại":[self.genresVi(g) for g in df_top["genres"]],
                              "Độ phù hợp":[f"{ChartUtil.vn(c,1)}%" for c in df_top["compatibility"]]})
        TableUtil.showDataIntoTableWidget(self.tableWidgetTopN,df_show,stretch_column=(1,3),center_columns=(0,2,4))
    def showLiked(self,df_liked,n_valid):
        if len(df_liked)==0:
            self.tableWidgetLiked.setRowCount(0)
            self.labelLikedSub.setText("Khách hàng chưa đánh giá phim nào từ 4 sao.")
            return
        df=df_liked.sort_values(["rating_score","rating_time"],ascending=[False,False])
        self.labelLikedSub.setText(f"{ChartUtil.vn(len(df))} / {ChartUtil.vn(n_valid)} đánh giá hợp lệ · "
                                   f"sắp xếp theo số sao, mới nhất trước")
        df_show=pd.DataFrame({"Phim":df["title"],
                              "Năm":[CatalogUtil.textOrDash(y) for y in df["release_year"]],
                              "Thể loại":[self.genresVi(g) for g in df["genres"]],
                              "Số sao":["★"*int(s) for s in df["rating_score"]],
                              "Ngày đánh giá":[t.strftime("%d/%m/%Y") if hasattr(t,"strftime") else str(t)
                                               for t in df["rating_time"]]})
        TableUtil.showDataIntoTableWidget(self.tableWidgetLiked,df_show,stretch_column=(0,2),center_columns=(1,3,4))
    def showCompare(self,df_top,df_liked):
        # Đối chiếu thể loại: tỉ lệ phim thuộc từng thể loại trong Top-N so với trong các phim khách hàng chấm cao.
        # Mức trùng khớp = % phim gợi ý thuộc ít nhất một trong 3 thể loại khách hàng chấm cao nhiều nhất.
        self.figure.clear()
        if df_top is None or len(df_top)==0 or len(df_liked)==0:
            self.canvas.draw()
            self.labelMatchValue.setText("—")
            self.labelCompareInsight.setText("Cần có danh sách gợi ý và phim đánh giá cao để đối chiếu.")
            return
        liked_share=self.genreShare(df_liked["genres"])
        top_share=self.genreShare(df_top["genres"])
        top_genres=list(liked_share.index[:self.TOP_GENRES])
        matched=sum(1 for g in df_top["genres"] if set(self.splitGenres(g))&set(top_genres))
        match=100.0*matched/len(df_top)
        self.labelMatchValue.setText(f"{ChartUtil.vn(match)}%")
        self.labelMatchValue.setStyleSheet(f"color: {self.matchColor(match)};")
        names=", ".join(f"<b>{CatalogUtil.genreVi(g)}</b>" for g in top_genres)
        self.labelCompareInsight.setText(f"Khách hàng chấm cao nhiều nhất các thể loại {names}. "
                                         f"<b>{matched}/{len(df_top)}</b> phim gợi ý thuộc ít nhất một thể loại này "
                                         f"→ {self.matchVerdict(match)}")
        genres=list(dict.fromkeys(list(liked_share.index[:6])+list(top_share.index[:3])))[:7]
        ax=self.figure.add_subplot(111)
        y=range(len(genres))
        h=0.38
        ax.barh([i-h/2 for i in y],[liked_share.get(g,0) for g in genres],height=h,color=ChartUtil.PALETTE[1],
                label="Phim đã chấm từ 4 sao")
        ax.barh([i+h/2 for i in y],[top_share.get(g,0) for g in genres],height=h,color=ChartUtil.PALETTE[0],
                label="Phim được gợi ý")
        ax.set_yticks(list(y))
        ax.set_yticklabels([CatalogUtil.genreVi(g) for g in genres],fontsize=8.5)
        ax.invert_yaxis()
        ax.set_xlim(0,100)
        ax.set_xlabel("% số phim thuộc thể loại",fontsize=8.5)
        ax.legend(fontsize=8,loc="lower right",frameon=False)
        ChartUtil.styleAxes(ax,"x")
        self.canvas.draw()
    def clearResult(self):
        self.labelUserTitle.setText("Chưa chọn khách hàng")
        self.labelUserDetail.setText("Nhập UserID rồi bấm Chạy thử nghiệm, hoặc bấm Chọn ngẫu nhiên.")
        self.labelTopNTitle.setText("Top-N phim mô hình gợi ý")
        self.labelTopNSub.setText("Đã loại các phim khách hàng đã đánh giá và phim đang bị ẩn")
        self.labelLikedSub.setText("")
        self.labelMatchValue.setStyleSheet("")
        self.tableWidgetTopN.setRowCount(0)
        self.tableWidgetLiked.setRowCount(0)
        self.labelMatchValue.setText("—")
        self.labelCompareInsight.setText("Biểu đồ so sánh tỉ lệ thể loại giữa phim được gợi ý và phim khách hàng "
                                         "đã chấm từ 4 sao.")
        self.figure.clear()
        self.canvas.draw()
    # ======================= HÀM PHỤ =======================
    @staticmethod
    def splitGenres(genres):
        return [] if genres is None or genres!=genres else [g for g in str(genres).split("|") if g!=""]
    @staticmethod
    def genresVi(genres):
        return ", ".join(CatalogUtil.genreVi(g) for g in ModelTestMainWindowEx.splitGenres(genres))
    @staticmethod
    def genreShare(series):
        # % số phim thuộc từng thể loại (một phim có thể thuộc nhiều thể loại), giảm dần
        counts={}
        for genres in series:
            for g in ModelTestMainWindowEx.splitGenres(genres):
                counts[g]=counts.get(g,0)+1
        return (pd.Series(counts,dtype=float)*100.0/max(len(series),1)).sort_values(ascending=False)
    @staticmethod
    def matchColor(match):
        return "#16A34A" if match>=70 else ("#B45309" if match>=40 else "#DC2626")
    @staticmethod
    def matchVerdict(match):
        if match>=70:
            return "gợi ý bám sát sở thích của khách hàng."
        if match>=40:
            return "gợi ý khá phù hợp, có mở rộng sang thể loại khác."
        return "gợi ý đang lệch so với sở thích; nên kiểm tra lại hoặc cập nhật mô hình với dữ liệu mới."
