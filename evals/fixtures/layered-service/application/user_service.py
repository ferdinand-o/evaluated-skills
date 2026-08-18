from domain.user import User


class UserService:
    def create(self, name):
        return User(name)
