from datetime import date, datetime

from PyQt6.QtCore import QDate


class TimeFilter:
    # Bộ lọc khoảng thời gian dùng chung cho Dashboard và Hiệu quả gợi ý (chỉ lọc theo thời gian, FR-18)
    def setupTimeFilter(self,first,last):
        self.firstDate=first.date() if isinstance(first,datetime) else (first or date.today())
        self.lastDate=last.date() if isinstance(last,datetime) else (last or date.today())
        self.comboBoxPeriod.blockSignals(True)
        self.comboBoxPeriod.clear()
        self.comboBoxPeriod.addItem("Toàn bộ thời gian","all")
        for year in range(self.lastDate.year,self.firstDate.year-1,-1):
            self.comboBoxPeriod.addItem(f"Năm {year}",year)
        self.comboBoxPeriod.addItem("Tùy chọn theo tháng","custom")
        self.comboBoxPeriod.blockSignals(False)
        for edit in (self.dateEditFrom,self.dateEditTo):
            edit.setDateRange(QDate(self.firstDate.year,self.firstDate.month,1),QDate(self.lastDate.year,self.lastDate.month,1))
        self.dateEditFrom.setDate(QDate(self.firstDate.year,self.firstDate.month,1))
        self.dateEditTo.setDate(QDate(self.lastDate.year,self.lastDate.month,1))
        self.comboBoxPeriod.currentIndexChanged.connect(self.periodChanged)
        self.periodChanged()
    def periodChanged(self):
        custom=self.comboBoxPeriod.currentData()=="custom"
        for widget in (self.dateEditFrom,self.dateEditTo,self.labelFrom,self.labelTo):
            widget.setEnabled(custom)
    def getPeriod(self):
        # Trả về (date_from, date_to) với date_to không bao gồm; (None, None) = toàn bộ thời gian
        data=self.comboBoxPeriod.currentData()
        if data=="all" or data is None:
            return (None,None)
        if data!="custom":
            return (date(data,1,1),date(data+1,1,1))
        d1=self.dateEditFrom.date()
        d2=self.dateEditTo.date()
        if d1>d2:
            (d1,d2)=(d2,d1)
        start=date(d1.year(),d1.month(),1)
        end=date(d2.year()+(1 if d2.month()==12 else 0),1 if d2.month()==12 else d2.month()+1,1)
        return (start,end)
    def periodText(self):
        data=self.comboBoxPeriod.currentData()
        if data=="all" or data is None:
            return f"Dữ liệu từ {self.firstDate.month:02d}/{self.firstDate.year} đến {self.lastDate.month:02d}/{self.lastDate.year}"
        if data!="custom":
            return f"Năm {data}"
        return f"Từ {self.dateEditFrom.date().toString('MM/yyyy')} đến {self.dateEditTo.date().toString('MM/yyyy')}"
