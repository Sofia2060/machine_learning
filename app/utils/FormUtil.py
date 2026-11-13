from app.utils.CatalogUtil import CatalogUtil


class FormUtil:
    # Đổ danh mục giới tính / nhóm tuổi / nghề nghiệp vào combobox; mục đầu tiên = "chưa chọn" (giá trị None)
    @staticmethod
    def fillProfileCombos(comboGender,comboAge,comboOccupation):
        placeholders=[c.itemText(0) for c in (comboGender,comboAge,comboOccupation)]
        comboGender.clear()
        comboGender.addItem(placeholders[0],None)
        for (code,label) in CatalogUtil.GENDERS.items():
            comboGender.addItem(label,code)
        comboAge.clear()
        comboAge.addItem(placeholders[1],None)
        for (code,label) in CatalogUtil.AGE_GROUPS.items():
            comboAge.addItem(label,code)
        comboOccupation.clear()
        comboOccupation.addItem(placeholders[2],None)
        for (occupation_id,name) in enumerate(CatalogUtil.OCCUPATIONS):
            comboOccupation.addItem(name,occupation_id)
    @staticmethod
    def selectData(combo,value):
        index=combo.findData(value) if value is not None and value==value else 0
        combo.setCurrentIndex(max(index,0))
