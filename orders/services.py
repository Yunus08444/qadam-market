from django.db import transaction

from .models import Order, OrderItem
from .notifications import notify_new_order


class EmptyCartError(Exception):
    pass


@transaction.atomic
def create_order(*, customer_name, phone, comment, items):
    """Save the order with its items in one transaction.

    `items` is the list returned by `cart.get_items`. Prices are copied into
    the order so later price changes don't affect already placed orders.
    """
    if not items:
        raise EmptyCartError

    order = Order.objects.create(customer_name=customer_name, phone=phone, comment=comment)
    order_items = [
        OrderItem(
            order=order,
            product=item['product'],
            product_name=item['product'].name,
            article=item['product'].article,
            unit_price=item['unit'],
            quantity=item['qty'],
            line_total=item['line'],
        )
        for item in items
    ]
    OrderItem.objects.bulk_create(order_items)

    order.total = sum(item.line_total for item in order_items if item.line_total is not None)
    order.save(update_fields=['total'])

    # Notify only after the transaction is committed: if it rolls back,
    # the manager must not get a message about an order that doesn't exist.
    transaction.on_commit(lambda: notify_new_order(order.pk))
    return order
