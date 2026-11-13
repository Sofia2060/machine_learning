class Rating:
    def __init__(self,rating_id=None,customer_id=None,movie_id=None,rating_score=None,
                 comment_text=None,rating_time=None,is_valid=1):
        self.rating_id = rating_id
        self.customer_id = customer_id
        self.movie_id = movie_id
        self.rating_score = rating_score
        self.comment_text = comment_text
        self.rating_time = rating_time
        self.is_valid = is_valid
