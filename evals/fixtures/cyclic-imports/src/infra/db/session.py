from src.domain.models.user import User


def get_session():
    return {}


def audit(user: User):
    return user.id
