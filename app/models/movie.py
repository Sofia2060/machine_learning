class Movie:
    def __init__(self,movie_id=None,title=None,release_year=None,duration_minutes=None,
                 genre_ids=None,is_hidden=0,employee_id=None):
        self.movie_id = movie_id
        self.title = title
        self.release_year = release_year
        self.duration_minutes = duration_minutes
        self.genre_ids = genre_ids if genre_ids is not None else []
        self.is_hidden = is_hidden
        self.employee_id = employee_id
