from src.domain.models.user import User


class OrderService:
    def create(self, user: User):
        return {"user_id": user.id}
