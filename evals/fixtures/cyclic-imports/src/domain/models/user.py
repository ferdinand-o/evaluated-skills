from src.infra.db.session import get_session


class User:
    def __init__(self, user_id):
        self.id = user_id
        self.session = get_session()
