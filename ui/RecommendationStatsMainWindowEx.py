from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from PyQt6.QtCore import QDate, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMessageBox

from ui.RecommendationStatsMainWindow import Ui_MainWindow
from ui.AdminNavigation import AdminNavigation
from ui.TimeFilter import TimeFilter
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.ticker import MaxNLocator

from app.dal.logDAO import logDAO
from app.dal.modelDAO import modelDAO
from app.dal.recommendationDAO import recommendationDAO
from app.ml.MovieRecommender import MovieRecommender
from app.utils.CatalogUtil import CatalogUtil
from app.utils.ChartUtil import ChartUtil
from app.utils.PosterUtil import PosterUtil


class RetrainThread(QThread):
    # FR-27, NFR-24: huấn luyện lại chạy nền để giao diện không bị treo
    progress = pyqtSignal(str)
    done = pyqtSignal(bool, str)

    def __init__(self,employee_id):
        super().__init__()
        self.employee_id=employee_id
    def run(self):
        try:
            path=MovieRecommender.retrainModel(self.progress.emit)
            if not MovieRecommender.registerModel(path,self.employee_id):
                self.done.emit(False,"Huấn luyện xong nhưng không đăng ký được mô hình mới.")
                return
            self.done.emit(True,path)
        except ImportError:
            self.done.emit(False,"Máy này chưa cài thư viện torch nên chưa huấn luyện lại được. "
                                 "Cài bằng: pip install torch (hoặc chạy python main.py export trên máy của nhóm).")
        except Exception as e:
            self.done.emit(False,f"Huấn luyện lại thất bại: {e}")


class RecommendationStatsMainWindowEx(Ui_MainWindow, AdminNavigation, TimeFilter):
    # FR-19: thống kê lịch sử gợi ý theo thời gian và mô hình, nhìn từ góc độ kinh doanh
    CHARTS = ["Daily", "TopMovies", "TopGenres"]
    # Lịch sử gợi ý phát sinh hằng ngày nên lọc theo ngày (Dashboard lọc theo năm/tháng vì dữ liệu đánh giá trải nhiều năm)
    PERIODS = [("Toàn bộ thời gian","all"),("Hôm nay","today"),("7 ngày qua",7),("30 ngày qua",30),
               ("Tháng này","month"),("Tùy chọn ngày","custom")]

    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)
        self.MainWindow=MainWindow
        self.thread=None
        self.setupNavigation()
        self.setupPlots()
        self.progressBarRetrain.setVisible(False)
        self.labelFilterInfo.setVisible(False)
        self.setupSignalAndSlot()
    def showWindow(self):
        self.MainWindow.showMaximized()

    def setupSignalAndSlot(self):
        # Bộ lọc tự cập nhật ngay khi đổi lựa chọn (không cần bấm nút)
        self.comboBoxPeriod.currentIndexChanged.connect(self.periodChanged)
        self.comboBoxModel.currentIndexChanged.connect(self.filterChanged)
        self.dateEditFrom.dateChanged.connect(self.filterChanged)
        self.dateEditTo.dateChanged.connect(self.filterChanged)
        self.pushButtonRetrain.clicked.connect(self.process_retrain)
        self.pushButtonActivateModel.clicked.connect(self.process_activateModel)
        self.comboBoxModelVersion.currentIndexChanged.connect(self.modelVersionChanged)
    # ======================= BỘ LỌC THEO NGÀY =======================
    def setupTimeFilter(self,first,last):
        today=date.today()
        self.firstDate=first.date() if isinstance(first,datetime) else (first or today)
        self.lastDate=max(last.date() if isinstance(last,datetime) else (last or today),today)
        self.loadingFilter=True
        self.comboBoxPeriod.clear()
        for (text,data) in self.PERIODS:
            self.comboBoxPeriod.addItem(text,data)
        for edit in (self.dateEditFrom,self.dateEditTo):
            edit.setDateRange(QDate(self.firstDate.year,self.firstDate.month,self.firstDate.day),
                              QDate(self.lastDate.year,self.lastDate.month,self.lastDate.day))
        self.dateEditFrom.setDate(QDate(self.firstDate.year,self.firstDate.month,self.firstDate.day))
        self.dateEditTo.setDate(QDate(self.lastDate.year,self.lastDate.month,self.lastDate.day))
        self.loadingFilter=False
        self.periodChanged(reload=False)
    def periodChanged(self,index=None,reload=True):
        # Chỉ hiện ô Từ/đến khi chọn "Tùy chọn ngày"; các mục khác hiện khoảng ngày tương ứng ở cuối thanh lọc
        custom=self.comboBoxPeriod.currentData()=="custom"
        for widget in (self.dateEditFrom,self.dateEditTo,self.labelFrom,self.labelTo):
            widget.setVisible(custom)
        self.labelFilterInfo.setVisible(not custom)
        if reload:
            self.filterChanged()
    def filterChanged(self,*args):
        if not getattr(self,"loadingFilter",True):
            self.loadStats()
    def getPeriod(self):
        # (date_from, date_to) với date_to không bao gồm; (None, None) = toàn bộ thời gian
        data=self.comboBoxPeriod.currentData()
        today=date.today()
        tomorrow=today+timedelta(days=1)
        if data=="today":
            return (today,tomorrow)
        if isinstance(data,int):
            return (today-timedelta(days=data-1),tomorrow)
        if data=="month":
            return (today.replace(day=1),tomorrow)
        if data=="custom":
            d1=self.dateEditFrom.date().toPyDate()
            d2=self.dateEditTo.date().toPyDate()
            if d1>d2:
                (d1,d2)=(d2,d1)
            return (d1,d2+timedelta(days=1))
        return (None,None)
    def periodText(self):
        (d1,d2)=self.getPeriod()
        # Khoảng ngày đang xem (tên khoảng thời gian đã hiện ở combobox nên không lặp lại)
        if d1 is None:
            (d1,d2)=(self.firstDate,self.lastDate)
        else:
            d2=d2-timedelta(days=1)
        return f"Ngày {d1:%d/%m/%Y}" if d1==d2 else f"Từ {d1:%d/%m/%Y} đến {d2:%d/%m/%Y}"
    def setupPlots(self):
        ChartUtil.setupStyle()
        self.figures={}
        self.canvases={}
        for key in self.CHARTS:
            figure=plt.figure(figsize=(5,3))
            figure.set_layout_engine("tight")
            canvas=FigureCanvas(figure)
            canvas.setMinimumHeight(240)
            getattr(self,f"verticalLayoutPlot{key}").addWidget(canvas)
            self.figures[key]=figure
            self.canvases[key]=canvas
    def loadData(self):
        self.loadingFilter=True
        self.comboBoxModel.clear()
        self.comboBoxModel.addItem("Tất cả mô hình",None)
        for name in recommendationDAO.getModelNames():
            self.comboBoxModel.addItem(name,name)
        (first,last)=recommendationDAO.getDateRange()
        self.setupTimeFilter(first,last)
        self.loadModelStatus()
        self.loadStats()
    # ======================= TRẠNG THÁI BỘ MÁY GỢI Ý =======================
    def loadModelVersions(self,active_id):
        # FR-25: danh sách phiên bản mô hình đã đăng ký; chọn một phiên bản rồi bấm "Kích hoạt mô hình"
        self.comboBoxModelVersion.blockSignals(True)
        self.comboBoxModelVersion.clear()
        df=modelDAO.getModels()
        if df is not None:
            for row in df.iloc:
                exported=row["exported_at"] if row["exported_at"] is not None else row["registered_at"]
                name=str(row["model_name"]).split("(")[0]
                text=f"#{int(row['model_id'])} · {name} · {pd.Timestamp(exported):%d/%m/%Y %H:%M}"
                if int(row["model_id"])==active_id:
                    text+="  (đang dùng)"
                self.comboBoxModelVersion.addItem(text,int(row["model_id"]))
                self.comboBoxModelVersion.setItemData(self.comboBoxModelVersion.count()-1,
                                                      f"{text}\nTệp: {row['file_name']}\nĐã học từ "
                                                      f"{ChartUtil.vn(row['n_ratings'] or 0)} đánh giá",
                                                      Qt.ItemDataRole.ToolTipRole)
        index=self.comboBoxModelVersion.findData(active_id)
        self.comboBoxModelVersion.setCurrentIndex(max(index,0))
        self.comboBoxModelVersion.blockSignals(False)
        self.modelVersionChanged()
    def modelVersionChanged(self,*args):
        info=modelDAO.getActiveModel()
        active_id=int(info["model_id"]) if info is not None else None
        selected=self.comboBoxModelVersion.currentData()
        self.pushButtonActivateModel.setEnabled(selected is not None and selected!=active_id)
        self.comboBoxModelVersion.setToolTip(self.comboBoxModelVersion.currentText())
    def process_activateModel(self):
        model_id=self.comboBoxModelVersion.currentData()
        if model_id is None:
            return
        text=self.comboBoxModelVersion.currentText()
        if not self.confirm("Kích hoạt mô hình",f"Dùng phiên bản mô hình này cho gợi ý của toàn bộ khách hàng?\n\n{text}"):
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        ok=MovieRecommender.activateModel(model_id)
        QApplication.restoreOverrideCursor()
        # NFR-23: ghi nhật ký cả khi thất bại; thất bại thì giữ nguyên mô hình đang dùng (FR-25)
        logDAO.log(self.loginUser.employee_id,logDAO.CHANGE_MODEL,text.replace("  (đang dùng)",""),
                   "Thành công" if ok else "Thất bại: "+MovieRecommender.last_error)
        if ok:
            self.showMessage("Đã kích hoạt mô hình. Gợi ý mới cho khách hàng sẽ dùng phiên bản này.",QMessageBox.Icon.Information)
        else:
            self.showMessage(f"Không kích hoạt được mô hình, hệ thống giữ nguyên mô hình đang dùng.\n\n"
                             f"{MovieRecommender.last_error}",QMessageBox.Icon.Critical)
        self.loadModelStatus()
    def loadModelStatus(self):
        info=modelDAO.getActiveModel()
        self.loadModelVersions(int(info["model_id"]) if info is not None else None)
        if info is None:
            self.labelModelStatus.setText("<span style='color:#DC2626'>Chưa có mô hình gợi ý nào được đăng ký.</span>")
            self.labelModelNewData.setVisible(False)
            return
        exported=info["exported_at"] if info["exported_at"] is not None else info["registered_at"]
        self.labelModelStatus.setText(
            f"<table cellpadding='3'><tr><td style='color:#6B7280'>Đang dùng</td><td><b>Gợi ý cá nhân hóa "
            f"({str(info['model_name']).split('(')[0]})</b></td></tr>"
            f"<tr><td style='color:#6B7280'>Cập nhật lúc</td><td><b>{str(exported)[:16]}</b></td></tr>"
            f"<tr><td style='color:#6B7280'>Đã học từ</td><td><b>{ChartUtil.vn(info['n_ratings'] or 0)}</b> đánh giá của "
            f"<b>{ChartUtil.vn(info['n_users'] or 0)}</b> khách hàng</td></tr>"
            f"<tr><td style='color:#6B7280'>Kho phim</td><td><b>{ChartUtil.vn(info['n_items'] or 0)}</b> phim có thể gợi ý</td></tr>"
            f"</table>")
        new_ratings=modelDAO.countRatingsAfter(exported)
        self.labelModelNewData.setVisible(True)
        if new_ratings>0:
            self.labelModelNewData.setText(f"Có <b>{ChartUtil.vn(new_ratings)}</b> đánh giá mới phát sinh sau lần cập nhật "
                                           f"gần nhất. Khách hàng mới đã được gợi ý ngay từ các đánh giá của họ; cập nhật "
                                           f"để bộ máy học đầy đủ dữ liệu mới và các phim mới thêm vào kho.")
        else:
            self.labelModelNewData.setText("Bộ máy gợi ý đã cập nhật với toàn bộ đánh giá hiện có.")
    # ======================= THỐNG KÊ GỢI Ý (FR-19) =======================
    def loadStats(self):
        (date_from,date_to)=self.getPeriod()
        model_name=self.comboBoxModel.currentData()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        summary=recommendationDAO.getSummary(date_from,date_to,model_name)
        daily=recommendationDAO.getListsByDay(date_from,date_to,model_name)
        movies=recommendationDAO.getTopMovies(8,date_from,date_to,model_name)
        genres=recommendationDAO.getTopGenres(date_from,date_to,model_name)
        QApplication.restoreOverrideCursor()
        self.labelFilterInfo.setText(self.periodText())
        self.labelFilterInfo.setVisible(self.comboBoxPeriod.currentData()!="custom")
        if summary is None:
            self.showMessage("Không thể truy xuất lịch sử gợi ý. Vui lòng kiểm tra kết nối cơ sở dữ liệu.")
            return
        lists=int(summary["lists"])
        if lists==0:
            for key in self.CHARTS:
                self.figures[key].clear()
                self.canvases[key].draw()
                getattr(self,f"labelInsight{key}").setText("Chưa có danh sách gợi ý nào trong khoảng thời gian này. "
                                                            "Lịch sử được ghi lại mỗi khi khách hàng mở Trang chủ.")
            for label in (self.labelKpiLists,self.labelKpiCustomers,self.labelKpiHit):
                label.setText("0")
            self.labelKpiCoverage.setText("0 phim")
            return
        n_movies=int(MovieRecommender.model_info["n_items"]) if MovieRecommender.loadModel() else int(summary["movies"])
        hits=int(summary["hits"] or 0)
        self.labelKpiLists.setText(ChartUtil.vn(lists))
        self.labelKpiCustomers.setText(ChartUtil.vn(summary["customers"]))
        self.labelKpiCoverage.setText(f"{ChartUtil.vn(summary['movies'])} phim")
        self.frameKpiCoverage.setToolTip(f"Chiếm {ChartUtil.vn(100*int(summary['movies'])/max(n_movies,1),1)}% kho phim có "
                                         f"thể gợi ý: càng cao thì càng nhiều phim trong kho được giới thiệu tới khách.")
        self.labelKpiHit.setText(ChartUtil.vn(hits))
        self.frameKpiHit.setToolTip("Số phim khách hàng đã đánh giá sau khi được hệ thống gợi ý.")
        self.drawDaily(daily,lists)
        self.drawTopMovies(movies,lists)
        self.drawTopGenres(genres)
        hit_text=(f" Khách hàng đã xem và đánh giá <b>{ChartUtil.vn(hits)}</b> phim sau khi được gợi ý, điểm trung bình "
                  f"<b>★ {ChartUtil.vn(summary['hit_score'],2)}</b>." if hits>0 else
                  " Chưa ghi nhận khách hàng đánh giá phim nào sau khi được gợi ý.")
        self.labelInsightDaily.setText(self.labelInsightDaily.text()+hit_text)
    def drawDaily(self,df,lists):
        figure=self.figures["Daily"]
        figure.clear()
        ax=figure.add_subplot(111)
        # Vẽ đủ mọi ngày trong khoảng lọc (ngày không có danh sách = 0) để thấy đúng nhịp sử dụng
        counts={(d.date() if isinstance(d,datetime) else d):int(v) for (d,v) in zip(df["day"],df["lists"])}
        (d1,d2)=self.getPeriod()
        start=d1 if d1 is not None else min(counts)
        end=(d2-timedelta(days=1)) if d2 is not None else max(counts)
        days=[start+timedelta(days=k) for k in range((end-start).days+1)]
        values=[counts.get(d,0) for d in days]
        df=pd.DataFrame({"day":days,"lists":values})
        labels=[d.strftime("%d/%m") for d in days]
        x=np.arange(len(df))
        bars=ax.bar(x,df["lists"],color=ChartUtil.PRIMARY,width=0.6 if len(df)>3 else 0.5)
        if len(df)<=31:
            ChartUtil.labelBars(ax,[b for (b,v) in zip(bars,values) if v>0])
        ax.set_xlim(-0.6,len(df)-0.4) if len(df)>3 else ax.set_xlim(-2,len(df)+1)
        step=max(1,int(np.ceil(len(df)/10)))
        ax.set_xticks(x[::step])
        ax.set_xticklabels(labels[::step],fontsize=8.5)
        ax.yaxis.set_major_locator(MaxNLocator(integer=True,nbins=5))
        ax.set_ylim(0,df["lists"].max()*1.2)
        ax.set_ylabel("Lần tạo danh sách")
        ChartUtil.styleAxes(ax)
        self.canvases["Daily"].draw()
        peak=df.loc[df["lists"].idxmax()]
        active=sum(1 for v in values if v>0)
        self.labelInsightDaily.setText(f"Hệ thống đã tạo <b>{ChartUtil.vn(lists)}</b> danh sách gợi ý trong "
                                       f"{len(df)} ngày ({active} ngày có khách nhận gợi ý); nhiều nhất vào "
                                       f"{peak['day'].strftime('%d/%m/%Y')} ({ChartUtil.vn(peak['lists'])} danh sách).")
    def drawTopMovies(self,df,lists):
        figure=self.figures["TopMovies"]
        figure.clear()
        ax=figure.add_subplot(111)
        labels=[self.shorten(PosterUtil.shortTitle(t),28) for t in df["title"]]
        bars=ax.barh(labels,df["lists"],color=ChartUtil.ACCENT,height=0.62)
        ax.invert_yaxis()
        for (bar,value) in zip(bars,df["lists"]):
            ax.annotate(f"{ChartUtil.vn(value)} ({ChartUtil.vn(100*value/lists,0)}%)",
                        (bar.get_width(),bar.get_y()+bar.get_height()/2),xytext=(4,0),textcoords="offset points",
                        va="center",fontsize=8.5)
        ax.set_xlim(0,df["lists"].max()*1.3)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True,nbins=4))
        ax.tick_params(axis="y",labelsize=8.5)
        ChartUtil.styleAxes(ax,"x")
        self.canvases["TopMovies"].draw()
        top=df.iloc[0]
        self.labelInsightTopMovies.setText(f"<b>{PosterUtil.shortTitle(top['title'])}</b> xuất hiện trong "
                                           f"<b>{ChartUtil.vn(100*int(top['lists'])/lists,0)}%</b> danh sách gợi ý. "
                                           f"Phim xuất hiện quá thường xuyên cho thấy gợi ý đang thiên về phim phổ biến.")
    def drawTopGenres(self,df):
        figure=self.figures["TopGenres"]
        figure.clear()
        ax=figure.add_subplot(111)
        df=df.head(8)
        labels=[CatalogUtil.genreVi(g) for g in df["genre_name"]]
        bars=ax.barh(labels,df["appearances"],color="#0891B2",height=0.62)
        ax.invert_yaxis()
        ChartUtil.labelBars(ax,bars,horizontal=True)
        ax.set_xlim(0,df["appearances"].max()*1.2)
        ax.xaxis.set_major_locator(MaxNLocator(integer=True,nbins=4))
        ax.tick_params(axis="y",labelsize=8.5)
        ChartUtil.styleAxes(ax,"x")
        self.canvases["TopGenres"].draw()
        self.labelInsightTopGenres.setText(f"<b>{labels[0]}</b> và <b>{labels[1] if len(labels)>1 else ''}</b> là hai thể "
                                           f"loại được giới thiệu nhiều nhất (tính theo số lượt phim xuất hiện trong "
                                           f"các danh sách).")
    @staticmethod
    def shorten(text,n):
        return text if len(text)<=n else text[:n-1]+"…"
    # ======================= CẬP NHẬT MÔ HÌNH (FR-27) =======================
    def process_retrain(self):
        if not self.confirm("Cập nhật gợi ý",
                            "Hệ thống sẽ huấn luyện lại bộ máy gợi ý trên toàn bộ đánh giá hợp lệ hiện có "
                            "(khoảng 1–3 phút tùy máy). Trong thời gian này bạn vẫn dùng được các chức năng khác.\n\n"
                            "Tiếp tục?"):
            return
        self.pushButtonRetrain.setEnabled(False)
        self.progressBarRetrain.setVisible(True)
        self.labelRetrainStatus.setText("Đang chuẩn bị dữ liệu...")
        self.thread=RetrainThread(self.loginUser.employee_id)
        self.thread.progress.connect(self.labelRetrainStatus.setText)
        self.thread.done.connect(self.retrainFinished)
        self.thread.start()
    def retrainFinished(self,ok,message):
        self.progressBarRetrain.setVisible(False)
        self.pushButtonRetrain.setEnabled(True)
        if ok:
            MovieRecommender.loadModel(force=True)
            logDAO.log(self.loginUser.employee_id,logDAO.RETRAIN_MODEL,message.replace("\\","/").split("/")[-1],"Thành công")
            self.labelRetrainStatus.setText("Đã cập nhật bộ máy gợi ý với dữ liệu mới.")
            self.loadModelStatus()
            self.showMessage("Đã cập nhật bộ máy gợi ý. Khách hàng sẽ nhận gợi ý mới ở lần mở Trang chủ tiếp theo.",
                             QMessageBox.Icon.Information)
        else:
            logDAO.log(self.loginUser.employee_id,logDAO.RETRAIN_MODEL,"NeuMF","Thất bại: "+message)
            self.labelRetrainStatus.setText(message)
            self.showMessage(message,QMessageBox.Icon.Critical)
