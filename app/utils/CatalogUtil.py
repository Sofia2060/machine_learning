class CatalogUtil:
    # Danh mục dùng chung: nhóm tuổi, nghề nghiệp, giới tính, thể loại (theo README của MovieLens 1M)
    AGE_GROUPS = {1: "Dưới 18", 18: "18–24", 25: "25–34", 35: "35–44", 45: "45–49", 50: "50–55", 56: "Từ 56"}
    OCCUPATIONS = ["Khác / không xác định", "Giảng viên / nhà giáo dục", "Nghệ sĩ",
                   "Nhân viên văn phòng / hành chính", "Sinh viên đại học / sau đại học", "Dịch vụ khách hàng",
                   "Bác sĩ / chăm sóc sức khỏe", "Quản lý / điều hành", "Nông dân", "Nội trợ",
                   "Học sinh phổ thông", "Luật sư", "Lập trình viên", "Đã nghỉ hưu", "Bán hàng / tiếp thị",
                   "Nhà khoa học", "Tự kinh doanh", "Kỹ thuật viên / kỹ sư", "Thợ thủ công", "Thất nghiệp",
                   "Nhà văn"]
    GENDERS = {"Male": "Nam", "Female": "Nữ", "Other": "Không muốn nói"}
    GENRES = ["Action", "Adventure", "Animation", "Children's", "Comedy", "Crime", "Documentary", "Drama",
              "Fantasy", "Film-Noir", "Horror", "Musical", "Mystery", "Romance", "Sci-Fi", "Thriller", "War",
              "Western"]
    GENRE_VI = {"Action": "Hành động", "Adventure": "Phiêu lưu", "Animation": "Hoạt hình",
                "Children's": "Thiếu nhi", "Comedy": "Hài", "Crime": "Hình sự", "Documentary": "Tài liệu",
                "Drama": "Chính kịch", "Fantasy": "Giả tưởng", "Film-Noir": "Phim đen", "Horror": "Kinh dị",
                "Musical": "Nhạc kịch", "Mystery": "Bí ẩn", "Romance": "Lãng mạn", "Sci-Fi": "Khoa học viễn tưởng",
                "Thriller": "Giật gân", "War": "Chiến tranh", "Western": "Viễn Tây"}

    @staticmethod
    def ageLabel(age):
        if age is None or age!=age:
            return "Chưa cung cấp"
        return CatalogUtil.AGE_GROUPS.get(int(age), str(age))
    @staticmethod
    def genderLabel(gender):
        if gender is None or gender!=gender or gender=="":
            return "Chưa cung cấp"
        return CatalogUtil.GENDERS.get(gender, gender)
    @staticmethod
    def occupationLabel(occupation_id):
        # CSDL lưu mã nghề nghiệp MovieLens 0–20 (bảng occupations); giao diện hiển thị tên tiếng Việt
        if occupation_id is None or occupation_id!=occupation_id or str(occupation_id).strip()=="":
            return "Chưa cung cấp"
        try:
            return CatalogUtil.OCCUPATIONS[int(occupation_id)]
        except (ValueError,IndexError):
            return str(occupation_id)
    @staticmethod
    def textOrDash(value):
        if value is None or value!=value or str(value).strip()=="":
            return "Chưa cung cấp"
        return str(value)
    @staticmethod
    def genreVi(genre):
        return CatalogUtil.GENRE_VI.get(genre, genre)
