from src.domain.services.order import OrderService


def create_order_route(user):
    return OrderService().create(user)
