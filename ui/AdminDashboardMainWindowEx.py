import numpy as np
import pandas as pd
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from ui.AdminDashboardMainWindow import Ui_MainWindow
from ui.AdminNavigation import AdminNavigation
from ui.TimeFilter import TimeFilter
from matplotlib import pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.ticker import FuncFormatter, MaxNLocator

from app.dal.statisticDAO import statisticDAO
from app.utils.CatalogUtil import CatalogUtil
from app.utils.ChartUtil import ChartUtil
from app.utils.ConfigUtil import ConfigUtil
from app.utils.PosterUtil import PosterUtil


class AdminDashboardMainWindowEx(Ui_MainWindow, AdminNavigation, TimeFilter):
    # FR-17, FR-18: báo cáo kinh doanh. Mỗi biểu đồ kèm 1 câu nhận xét để Admin nắm insight ngay
    CHARTS = ["Rating", "Trend", "Age", "Gender", "Occupation", "UserActivity", "Genre", "Featured", "MovieActivity"]

    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)
        self.MainWindow=MainWindow
        self.setupNavigation()
        self.setupPlots()
        self.data=None
        self.drawnTabs=set()
        self.setupSignalAndSlot()
    def showWindow(self):
        self.MainWindow.showMaximized()

    def setupSignalAndSlot(self):
        self.pushButtonApplyFilter.clicked.connect(self.loadData)
        self.tabWidgetDashboard.currentChanged.connect(self.drawCurrentTab)
    def setupPlots(self):
        ChartUtil.setupStyle()
        self.figures={}
        self.canvases={}
        for key in self.CHARTS:
            figure=plt.figure(figsize=(5,3))
            figure.set_layout_engine("tight")
            canvas=FigureCanvas(figure)
            canvas.setMinimumHeight(250 if key in ("Rating","Trend","MovieActivity") else 270)
            getattr(self,f"verticalLayoutPlot{key}").addWidget(canvas)
            self.figures[key]=figure
            self.canvases[key]=canvas
    def loadData(self):
        if not hasattr(self,"firstDate"):
            (first,last)=statisticDAO.getRatingTimeRange()
            self.setupTimeFilter(first,last)
        (date_from,date_to)=self.getPeriod()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        data={"monthly":statisticDAO.getMonthlyScores(date_from,date_to),
              "customers":statisticDAO.getCustomerAggregates(date_from,date_to),
              "movies":statisticDAO.getMovieAggregates(date_from,date_to)}
        if any(v is None for v in data.values()):
            QApplication.restoreOverrideCursor()
            self.showMessage("Không thể truy xuất dữ liệu thống kê. Vui lòng kiểm tra kết nối cơ sở dữ liệu.")
            return
        if not hasattr(self,"movieGenres"):
            self.movieGenres=statisticDAO.getMovieGenres()
            self.totals=statisticDAO.query("select (select count(*) from customers) as customers, "
                                           "(select count(*) from movies where is_hidden=0) as movies").iloc[0]
        for key in ("customers","movies"):
            data[key]["total"]=data[key]["total"].astype(int)
            data[key]["score_sum"]=data[key]["score_sum"].astype(float)
        monthly=data["monthly"]
        monthly["total"]=monthly["total"].astype(int)
        data["dist"]=monthly.groupby("rating",as_index=False)["total"].sum()
        monthly["score_sum"]=monthly["total"]*monthly["rating"].astype(int)
        trend=monthly.groupby("ym",as_index=False)[["total","score_sum"]].sum().sort_values("ym")
        trend["avg_rating"]=trend["score_sum"]/trend["total"]
        data["trend"]=trend.reset_index(drop=True)
        self.data=data
        self.filtered=date_from is not None
        self.labelFilterInfo.setText(self.periodText())
        self.showKPI()
        self.drawnTabs=set()
        self.drawCurrentTab()
        QApplication.restoreOverrideCursor()
    # ======================= KPI (FR-17) =======================
    def showKPI(self):
        cus=self.data["customers"]
        mv=self.data["movies"]
        ratings=int(cus["total"].sum())
        avg=cus["score_sum"].sum()/ratings if ratings>0 else 0
        cells=len(cus)*len(mv)
        sparsity=1-ratings/cells if cells>0 else 0
        self.labelKpiUsers.setText(ChartUtil.vn(len(cus) if self.filtered else self.totals["customers"]))
        self.labelKpiUsersCaption.setText("KHÁCH HOẠT ĐỘNG" if self.filtered else "KHÁCH HÀNG")
        self.labelKpiMovies.setText(ChartUtil.vn(self.totals["movies"]))
        self.labelKpiRatings.setText(ChartUtil.vn(ratings))
        self.labelKpiAvg.setText(f"{ChartUtil.vn(avg,2)} / 5")
        self.labelKpiSparsity.setText(f"{ChartUtil.vn(sparsity*100,2)}%")
        self.frameKpiUsers.setToolTip("Khi lọc theo thời gian: số khách hàng có ít nhất 1 đánh giá trong khoảng đó.")
        self.frameKpiRatings.setToolTip("Chỉ tính đánh giá hợp lệ (không tính đánh giá bị Admin đánh dấu không hợp lệ).")
        self.frameKpiSparsity.setToolTip("Tỉ lệ cặp (khách hàng, phim) chưa có đánh giá: dữ liệu càng thưa, "
                                         "việc gợi ý càng khó.")
    def drawCurrentTab(self):
        if self.data is None:
            return
        index=self.tabWidgetDashboard.currentIndex()
        if index in self.drawnTabs:
            return
        self.drawnTabs.add(index)
        if int(self.data["customers"]["total"].sum())==0:
            for key in self.CHARTS:
                self.figures[key].clear()
                self.canvases[key].draw()
                getattr(self,f"labelInsight{key}").setText("Không có đánh giá hợp lệ trong khoảng thời gian này.")
            self.labelHighlights.setText("Không có dữ liệu trong khoảng thời gian đã chọn.")
            return
        if index==0:
            self.drawRating()
            self.drawTrend()
            self.showHighlights()
        elif index==1:
            self.drawAge()
            self.drawGender()
            self.drawOccupation()
            self.drawUserActivity()
        else:
            self.drawGenre()
            self.drawFeatured()
            self.drawMovieActivity()
    # ======================= HỖ TRỢ VẼ =======================
    def newAxes(self,key):
        figure=self.figures[key]
        figure.clear()
        ax=figure.add_subplot(111)
        return ax
    def finish(self,key,ax,grid_axis="y"):
        ChartUtil.styleAxes(ax,grid_axis)
        self.canvases[key].draw()
    def setInsight(self,key,html):
        getattr(self,f"labelInsight{key}").setText(html)
    @staticmethod
    def pct(part,total):
        return ChartUtil.vn(100*part/total,1)+"%" if total>0 else "0%"
    @staticmethod
    def b(text):
        return f"<b style='color:#1D4ED8'>{text}</b>"
    def groupCustomers(self,column,labels=None):
        cus=self.data["customers"].copy()
        cus["attr"]=cus[column].where(cus[column].notna(),None)
        df=cus.groupby(cus["attr"].fillna("__none__"),sort=False).agg(total=("total","sum"),score_sum=("score_sum","sum"),
                                                                       customers=("total","size")).reset_index()
        df["avg"]=df["score_sum"]/df["total"]
        df["label"]=[("Chưa cung cấp" if a=="__none__" else (labels(a) if labels else str(a))) for a in df["attr"]]
        return df
    # ======================= TAB TỔNG QUAN =======================
    def drawRating(self):
        df=self.data["dist"]
        counts=pd.Series(0,index=[1,2,3,4,5])
        for r in df.itertuples():
            counts[int(r.rating)]=int(r.total)
        total=counts.sum()
        ax=self.newAxes("Rating")
        colors=["#CBD5E1","#CBD5E1","#94A3B8",ChartUtil.PRIMARY,ChartUtil.PRIMARY]
        bars=ax.bar([f"{k} ★" for k in counts.index],counts.values,color=colors,width=0.6)
        for (bar,value) in zip(bars,counts.values):
            ax.annotate(self.pct(value,total),(bar.get_x()+bar.get_width()/2,value),xytext=(0,3),
                        textcoords="offset points",ha="center",fontsize=9,fontweight="bold",color=ChartUtil.TEXT)
        ax.set_ylim(0,counts.max()*1.18)
        ax.yaxis.set_major_formatter(FuncFormatter(ChartUtil.thousands))
        ax.set_ylabel("Lượt đánh giá")
        self.finish("Rating",ax)
        top=int(counts.idxmax())
        self.setInsight("Rating",f"{self.b(self.pct(counts[4]+counts[5],total))} lượt đánh giá là 4–5 sao: khách hàng "
                                 f"nhìn chung hài lòng. Mức được chọn nhiều nhất là {self.b(str(top)+' ★')} "
                                 f"({self.pct(counts[top],total)}); chỉ {self.pct(counts[1]+counts[2],total)} là 1–2 sao.")
    def drawTrend(self):
        df=self.data["trend"].copy()
        df["label"]=[f"{int(ym)%100:02d}/{int(ym)//100}" for ym in df["ym"]]
        df["avg_rating"]=df["avg_rating"].astype(float)
        ax=self.newAxes("Trend")
        x=np.arange(len(df))
        ax.bar(x,df["total"],color=ChartUtil.PRIMARY,alpha=0.85,width=0.7,label="Lượt đánh giá")
        ax.yaxis.set_major_formatter(FuncFormatter(ChartUtil.thousands))
        ax.set_ylabel("Lượt đánh giá")
        step=max(1,int(np.ceil(len(df)/9)))
        ax.set_xticks(x[::step])
        ax.set_xticklabels(df["label"].iloc[::step],fontsize=8.5)
        ax2=ax.twinx()
        # Tháng quá ít lượt đánh giá cho điểm TB dao động mạnh -> không vẽ điểm TB của các tháng đó
        enough=df["total"]>=30
        avg=df["avg_rating"].where(enough)
        ax2.plot(x,avg,color=ChartUtil.ACCENT,marker="o",markersize=3.5,linewidth=2,label="Điểm TB")
        shown=avg.dropna() if avg.notna().any() else df["avg_rating"]
        ax2.set_ylim(max(1,shown.min()-0.4),min(5,shown.max()+0.3))
        ax2.set_ylabel("Điểm trung bình",color=ChartUtil.ACCENT)
        ax2.tick_params(axis="y",colors=ChartUtil.ACCENT)
        ax2.spines["top"].set_visible(False)
        ax2.yaxis.set_major_formatter(FuncFormatter(lambda v,p: ChartUtil.vn(v,1)))
        lines=ax.get_legend_handles_labels()
        lines2=ax2.get_legend_handles_labels()
        ax.legend(lines[0]+lines2[0],lines[1]+lines2[1],frameon=False,loc="lower right",bbox_to_anchor=(1.0,1.0),
                  ncol=2,fontsize=8.5,borderaxespad=0.2)
        self.finish("Trend",ax)
        peak=df.loc[df["total"].idxmax()]
        total=df["total"].sum()
        top3=df.nlargest(3,"total")["total"].sum()
        # Bỏ qua các tháng quá ít đánh giá khi nêu biên độ điểm TB (tránh nhiễu do vài lượt lẻ)
        stable=df[df["total"]>=max(30,0.01*df["total"].max())]
        stable=stable if len(stable)>0 else df
        self.setInsight("Trend",f"Cao điểm vào tháng {self.b(peak['label'])} với {ChartUtil.vn(peak['total'])} lượt "
                                f"({self.pct(peak['total'],total)}). 3 tháng sôi động nhất chiếm {self.b(self.pct(top3,total))} "
                                f"tổng lượt; điểm trung bình theo tháng dao động từ {ChartUtil.vn(stable['avg_rating'].min(),2)} "
                                f"đến {ChartUtil.vn(stable['avg_rating'].max(),2)}.")
    def showHighlights(self):
        # Tổng hợp những phát hiện quan trọng nhất của mọi tab vào một thẻ
        age=self.groupCustomers("age",CatalogUtil.ageLabel)
        gender=self.groupCustomers("gender",CatalogUtil.genderLabel)
        genres=self.genreStats()
        featured=self.featuredMovies()
        cus=self.data["customers"]
        total=cus["total"].sum()
        top_age=age.loc[age["total"].idxmax()]
        top_gender=gender.loc[gender["total"].idxmax()]
        top_genre=genres.iloc[0]
        best_genre=genres[genres["total"]>=genres["total"].max()*0.05].sort_values("avg",ascending=False).iloc[0]
        top20=cus["total"].nlargest(max(1,int(len(cus)*0.2))).sum()
        items=[f"Nhóm <b>{self.ageText(top_age['label'])}</b> đóng góp {self.b(self.pct(top_age['total'],total))} lượt đánh giá.",
               f"Khách hàng <b>{top_gender['label'].lower()}</b> chiếm {self.b(self.pct(top_gender['total'],total))} lượt đánh giá.",
               f"<b>{CatalogUtil.genreVi(top_genre['genre'])}</b> là thể loại được đánh giá nhiều nhất "
               f"({ChartUtil.vn(top_genre['total'])} lượt); <b>{CatalogUtil.genreVi(best_genre['genre'])}</b> được chấm cao nhất "
               f"(★ {ChartUtil.vn(best_genre['avg'],2)}).",
               f"20% khách hàng tích cực nhất tạo ra {self.b(self.pct(top20,total))} lượt đánh giá.",
               ]
        if len(featured)>0:
            items.append(f"Phim nổi bật nhất: <b>{PosterUtil.shortTitle(featured.iloc[0]['title'])}</b> "
                         f"(★ {ChartUtil.vn(featured.iloc[0]['avg'],2)}, {ChartUtil.vn(featured.iloc[0]['total'])} lượt).")
        self.labelHighlights.setText("<table cellspacing='0' cellpadding='5'>"+"".join(
            f"<tr><td valign='top' style='color:#2563EB; font-size:13pt'>•</td><td>{text}</td></tr>" for text in items)
                                     +"</table>")
    # ======================= TAB KHÁCH HÀNG =======================
    def drawGroupBars(self,key,df,horizontal=False,color=ChartUtil.PRIMARY):
        ax=self.newAxes(key)
        if horizontal:
            bars=ax.barh(df["label"],df["total"],color=color,height=0.62)
            ax.invert_yaxis()
            ax.xaxis.set_major_formatter(FuncFormatter(ChartUtil.thousands))
            ax.xaxis.set_major_locator(MaxNLocator(4))
            for (bar,avg) in zip(bars,df["avg"]):
                ax.annotate(f"★ {ChartUtil.vn(avg,2)}",(bar.get_width(),bar.get_y()+bar.get_height()/2),xytext=(4,0),
                            textcoords="offset points",va="center",fontsize=8.5,color="#B45309")
            ax.set_xlim(0,df["total"].max()*1.22)
            ax.tick_params(axis="y",labelsize=8.5)
            self.finish(key,ax,"x")
        else:
            bars=ax.bar(df["label"],df["total"],color=color,width=0.6)
            ax.yaxis.set_major_formatter(FuncFormatter(ChartUtil.thousands))
            for (bar,avg) in zip(bars,df["avg"]):
                ax.annotate(f"★ {ChartUtil.vn(avg,2)}",(bar.get_x()+bar.get_width()/2,bar.get_height()),xytext=(0,3),
                            textcoords="offset points",ha="center",fontsize=8.5,color="#B45309")
            ax.set_ylim(0,df["total"].max()*1.18)
            ax.set_ylabel("Lượt đánh giá")
            ax.tick_params(axis="x",labelsize=8.5)
            self.finish(key,ax)
    def drawAge(self):
        df=self.groupCustomers("age",CatalogUtil.ageLabel)
        order={label:k for (k,label) in enumerate(list(CatalogUtil.AGE_GROUPS.values())+["Chưa cung cấp"])}
        df=df.sort_values("label",key=lambda s: s.map(order))
        self.drawGroupBars("Age",df)
        total=df["total"].sum()
        top=df.loc[df["total"].idxmax()]
        known=df[df["label"]!="Chưa cung cấp"]
        best=known.loc[known["avg"].idxmax()]
        worst=known.loc[known["avg"].idxmin()]
        self.setInsight("Age",f"Nhóm {self.b(self.ageText(top['label']))} đánh giá nhiều nhất ({self.pct(top['total'],total)}). "
                              f"Nhóm {self.ageText(best['label'])} chấm điểm cao nhất (★ {ChartUtil.vn(best['avg'],2)}), "
                              f"nhóm {self.ageText(worst['label'])} khắt khe nhất (★ {ChartUtil.vn(worst['avg'],2)}).")
    @staticmethod
    def ageText(label):
        # "Dưới 18" -> "dưới 18 tuổi", "Từ 56" -> "từ 56 tuổi", "25–34" -> "25–34 tuổi"
        return (label[0].lower()+label[1:] if label[:1].isalpha() else label)+" tuổi"
    def drawGender(self):
        df=self.groupCustomers("gender",CatalogUtil.genderLabel).sort_values("total",ascending=False)
        ax=self.newAxes("Gender")
        colors=[ChartUtil.PRIMARY,"#EC4899","#94A3B8","#CBD5E1"][:len(df)]
        wedges,texts=ax.pie(df["total"],colors=colors,startangle=90,counterclock=False,
                            wedgeprops={"width":0.34,"edgecolor":"white"})
        total=df["total"].sum()
        ax.text(0,0.1,ChartUtil.vn(total),ha="center",va="center",fontsize=10.5,fontweight="bold",color=ChartUtil.TEXT)
        ax.text(0,-0.14,"lượt đánh giá",ha="center",va="center",fontsize=8,color=ChartUtil.MUTED)
        labels=[f"{r.label}: {self.pct(r.total,total)} lượt · ★ {ChartUtil.vn(r.avg,2)} · {ChartUtil.vn(r.customers)} khách"
                for r in df.itertuples()]
        ax.legend(wedges,labels,loc="upper center",bbox_to_anchor=(0.5,0.02),frameon=False,fontsize=8.5,ncol=1)
        ax.set_aspect("equal")
        self.canvases["Gender"].draw()
        top=df.iloc[0]
        per_customer=df.assign(per=df["total"]/df["customers"])
        self.setInsight("Gender",f"Khách hàng {self.b(top['label'].lower())} chiếm {self.b(self.pct(top['total'],total))} lượt "
                                 f"đánh giá. Trung bình mỗi khách: " +
                        ", ".join(f"{r.label.lower()} {ChartUtil.vn(r.per)} lượt" for r in per_customer.itertuples()) + ".")
    def drawOccupation(self):
        df=self.groupCustomers("occupation",CatalogUtil.occupationLabel).sort_values("total",ascending=False)
        df=df[df["label"]!="Chưa cung cấp"].head(8)
        self.drawGroupBars("Occupation",df,horizontal=True,color="#0891B2")
        total=self.data["customers"]["total"].sum()
        self.setInsight("Occupation",f"{self.b(df.iloc[0]['label'])} là nhóm nghề tích cực nhất "
                                     f"({self.pct(df.iloc[0]['total'],total)}); top 3 nghề chiếm "
                                     f"{self.b(self.pct(df.head(3)['total'].sum(),total))} tổng lượt đánh giá.")
    def drawActivity(self,key,counts,bins,labels,unit,color):
        groups=pd.cut(counts,bins=bins,labels=labels,right=False)
        hist=groups.value_counts().reindex(labels).fillna(0)
        ax=self.newAxes(key)
        bars=ax.bar(labels,hist.values,color=color,width=0.65)
        total=hist.sum()
        for (bar,value) in zip(bars,hist.values):
            ax.annotate(self.pct(value,total),(bar.get_x()+bar.get_width()/2,value),xytext=(0,3),
                        textcoords="offset points",ha="center",fontsize=8.5,color=ChartUtil.TEXT)
        ax.set_ylim(0,hist.max()*1.2)
        ax.set_ylabel(f"Số {unit}")
        ax.set_xlabel("Số lượt đánh giá")
        ax.tick_params(axis="x",labelsize=8.5)
        self.finish(key,ax)
    def drawUserActivity(self):
        counts=self.data["customers"]["total"]
        bins=[1,20,50,100,200,500,10**9]
        labels=["1–19","20–49","50–99","100–199","200–499","Từ 500"]
        self.drawActivity("UserActivity",counts,bins,labels,"khách hàng",ChartUtil.PURPLE)
        top10=counts.nlargest(max(1,len(counts)//10)).sum()
        self.setInsight("UserActivity",f"Trung vị {self.b(ChartUtil.vn(counts.median()))} lượt/khách (TB "
                                       f"{ChartUtil.vn(counts.mean())}, ít nhất {ChartUtil.vn(counts.min())}, nhiều nhất "
                                       f"{ChartUtil.vn(counts.max())}). 10% khách tích cực nhất tạo ra "
                                       f"{self.b(self.pct(top10,counts.sum()))} lượt đánh giá.")
    # ======================= TAB PHIM VÀ THỂ LOẠI =======================
    def genreStats(self):
        mv=self.data["movies"].merge(self.movieGenres,on="movie_id")
        df=mv.groupby("genre_name").agg(total=("total","sum"),score_sum=("score_sum","sum")).reset_index()
        df["avg"]=df["score_sum"]/df["total"]
        df=df.rename(columns={"genre_name":"genre"})
        return df.sort_values(["total","avg","genre"],ascending=[False,False,True]).reset_index(drop=True)
    def featuredMovies(self,n=10):
        threshold=ConfigUtil.featuredMinRatings()
        mv=self.data["movies"]
        df=mv[(mv["is_hidden"]==0)&(mv["total"]>=threshold)].copy()
        df["avg"]=df["score_sum"]/df["total"]
        return df.sort_values(["avg","total","title"],ascending=[False,False,True]).head(n).reset_index(drop=True)
    def drawGenre(self):
        df=self.genreStats().head(8)
        df["label"]=[CatalogUtil.genreVi(g) for g in df["genre"]]
        self.drawGroupBars("Genre",df,horizontal=True,color=ChartUtil.PRIMARY)
        total=self.data["movies"]["total"].sum()
        self.setInsight("Genre",f"{self.b(df.iloc[0]['label'])} và {self.b(df.iloc[1]['label'])} dẫn đầu về lượt đánh giá. "
                                f"Một phim có thể thuộc nhiều thể loại nên tổng các cột lớn hơn tổng lượt đánh giá "
                                f"({ChartUtil.vn(total)}).")
    def drawFeatured(self):
        threshold=ConfigUtil.featuredMinRatings()
        df=self.featuredMovies(8)
        if len(df)==0:
            self.figures["Featured"].clear()
            self.canvases["Featured"].draw()
            self.setInsight("Featured",f"Chưa đủ dữ liệu để xếp hạng: không có phim nào đạt {threshold} lượt đánh giá.")
            return
        df["label"]=[self.shorten(PosterUtil.shortTitle(t),30) for t in df["title"]]
        ax=self.newAxes("Featured")
        bars=ax.barh(df["label"],df["avg"],color=ChartUtil.ACCENT,height=0.62)
        ax.invert_yaxis()
        for (bar,total) in zip(bars,df["total"]):
            ax.annotate(f"{ChartUtil.vn(bar.get_width(),2)} · {ChartUtil.vn(total)} lượt",
                        (bar.get_width(),bar.get_y()+bar.get_height()/2),xytext=(4,0),textcoords="offset points",
                        va="center",fontsize=8.5,color=ChartUtil.TEXT)
        low=max(0,np.floor((df["avg"].min()-0.5)*2)/2)
        ax.set_xlim(low,5.55)
        ax.set_xticks(np.arange(low,5.01,0.5))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p: ChartUtil.vn(v,1)))
        ax.tick_params(axis="y",labelsize=8.5)
        self.finish("Featured",ax,"x")
        self.setInsight("Featured",f"Xếp theo điểm trung bình, chỉ xét phim đang hiển thị có từ {self.b(threshold)} lượt "
                                   f"đánh giá trở lên. "
                                   f"Dẫn đầu: {self.b(PosterUtil.shortTitle(df.iloc[0]['title']))}.")
    def drawMovieActivity(self):
        counts=self.data["movies"]["total"]
        bins=[1,5,20,100,500,1000,10**9]
        labels=["1–4","5–19","20–99","100–499","500–999","Từ 1.000"]
        self.drawActivity("MovieActivity",counts,bins,labels,"phim","#0891B2")
        top10=counts.nlargest(max(1,len(counts)//10)).sum()
        few=(counts<20).sum()
        self.setInsight("MovieActivity",f"10% phim được quan tâm nhất chiếm {self.b(self.pct(top10,counts.sum()))} lượt "
                                        f"đánh giá, trong khi {self.b(self.pct(few,len(counts)))} số phim có dưới 20 lượt: "
                                        f"phần lớn kho phim ít được khai thác (trung vị {ChartUtil.vn(counts.median())} "
                                        f"lượt/phim).")
    @staticmethod
    def shorten(text,n):
        return text if len(text)<=n else text[:n-1]+"…"
