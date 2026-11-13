from matplotlib import pyplot as plt


class ChartUtil:
    # Bảng màu thống nhất cho mọi biểu đồ
    PRIMARY = "#2563EB"
    ACCENT = "#F5A524"
    GREEN = "#16A34A"
    PURPLE = "#7C3AED"
    RED = "#DC2626"
    GRAY = "#94A3B8"
    TEXT = "#1F2937"
    MUTED = "#6B7280"
    PALETTE = ["#2563EB", "#F5A524", "#16A34A", "#7C3AED", "#DC2626", "#0891B2", "#DB2777", "#65A30D"]

    @staticmethod
    def setupStyle():
        plt.rcParams.update({"font.size": 9.5, "axes.titlesize": 11, "axes.labelsize": 9.5,
                             "axes.edgecolor": "#CBD5E1", "axes.labelcolor": ChartUtil.MUTED,
                             "xtick.color": ChartUtil.MUTED, "ytick.color": ChartUtil.MUTED,
                             "axes.titleweight": "bold", "axes.titlecolor": ChartUtil.TEXT,
                             "figure.facecolor": "white", "axes.facecolor": "white"})
    @staticmethod
    def styleAxes(ax,grid_axis="y"):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#CBD5E1")
        ax.spines["bottom"].set_color("#CBD5E1")
        if grid_axis:
            ax.grid(axis=grid_axis, color="#E5E7EB", linewidth=0.8)
            ax.set_axisbelow(True)
    @staticmethod
    def labelBars(ax,bars,digits=0,horizontal=False,color=None):
        for bar in bars:
            if horizontal:
                value = bar.get_width()
                ax.annotate(ChartUtil.vn(value,digits), (value, bar.get_y()+bar.get_height()/2),
                            xytext=(4, 0), textcoords="offset points", va="center", fontsize=8.5,
                            color=color or ChartUtil.TEXT)
            else:
                value = bar.get_height()
                ax.annotate(ChartUtil.vn(value,digits), (bar.get_x()+bar.get_width()/2, value),
                            xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8.5,
                            color=color or ChartUtil.TEXT)
    @staticmethod
    def thousands(x,pos=None):
        return f"{x:,.0f}".replace(",", ".")
    @staticmethod
    def vn(value,digits=0):
        # Định dạng số kiểu Việt Nam: 1.000.209 ; 3,58
        text = f"{float(value):,.{digits}f}"
        return text.replace(",", "#").replace(".", ",").replace("#", ".")
