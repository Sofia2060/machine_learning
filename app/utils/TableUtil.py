from PyQt6.QtCore import Qt, QObject, QEvent
from PyQt6.QtWidgets import QTableWidgetItem, QHeaderView


class ColumnFitter(QObject):
    # Chia độ rộng cho các cột chữ dài theo kích thước bảng hiện tại (gọi lại mỗi khi bảng đổi kích thước):
    # - mỗi cột luôn rộng ít nhất bằng tiêu đề cột -> tiêu đề không bao giờ bị cắt;
    # - còn dư thì chia thêm cho các cột chữ dài theo độ dài nội dung;
    # - màn hình quá hẹp thì bảng hiện thanh cuộn ngang thay vì cắt chữ chồng lên nhau.
    def __init__(self,table,columns):
        super().__init__(table)
        self.table=table
        self.columns=list(columns)
    def eventFilter(self,obj,event):
        if event.type()==QEvent.Type.Resize:
            self.fit()
        return False
    def headerWidth(self,c):
        header=self.table.horizontalHeader()
        item=self.table.horizontalHeaderItem(c)
        text=item.text() if item is not None else ""
        return header.fontMetrics().horizontalAdvance(text)+28
    def fit(self):
        table=self.table
        header=table.horizontalHeader()
        n=table.columnCount()
        columns=[c for c in self.columns if c<n]
        if not columns:
            return
        fixed=sum(header.sectionSize(c) for c in range(n) if c not in columns and not table.isColumnHidden(c))
        available=table.viewport().width()-fixed-2
        mins={c:self.headerWidth(c) for c in columns}
        natural={c:max(mins[c],min(table.sizeHintForColumn(c)+16,520)) for c in columns}
        total=sum(natural.values())
        if available>=total:
            extra=(available-total)/len(columns)
            widths={c:natural[c]+extra for c in columns}
        else:
            min_total=sum(mins.values())
            if available<=min_total:
                widths=mins
            else:
                # Thiếu chỗ: giữ tối thiểu bằng tiêu đề, phần còn lại chia theo độ dài nội dung
                spare=available-min_total
                need={c:natural[c]-mins[c] for c in columns}
                need_total=sum(need.values()) or 1
                widths={c:mins[c]+spare*need[c]/need_total for c in columns}
        for c in columns:
            header.resizeSection(c,int(widths[c]))


class TableUtil:
    @staticmethod
    def showDataIntoTableWidget(table,df,headers=None,stretch_column=None,center_columns=()):
        # Đổ DataFrame lên QTableWidget (cùng cách làm với showDataIntoTableWidget của thầy)
        table.setRowCount(0)
        if df is None:
            return
        table.setColumnCount(len(df.columns))
        for i in range(len(df.columns)):
            column_header=df.columns[i] if headers is None else headers[i]
            table.setHorizontalHeaderItem(i, QTableWidgetItem(column_header))
        row=0
        for item in df.iloc:
            arr=item.values.tolist()
            table.insertRow(row)
            j=0
            for data in arr:
                cell=QTableWidgetItem("" if data is None else str(data))
                if j in center_columns:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                table.setItem(row,j,cell)
                j=j+1
            row=row+1
        header=table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setDefaultSectionSize(34)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        if stretch_column is None:
            header.setStretchLastSection(True)
            return
        # Cột chữ dài (tên phim, thể loại, email...) được chia phần rộng còn lại; cột số giữ vừa nội dung
        columns=stretch_column if isinstance(stretch_column,(tuple,list)) else (stretch_column,)
        for c in columns:
            header.setSectionResizeMode(c,QHeaderView.ResizeMode.Interactive)
        fitter=getattr(table,"_columnFitter",None)
        if fitter is None:
            fitter=ColumnFitter(table,columns)
            table._columnFitter=fitter
            table.viewport().installEventFilter(fitter)
        fitter.columns=list(columns)
        table.resizeColumnsToContents()
        fitter.fit()
