"""Order list ("cart") stored in the session.

The session holds {key: quantity}, where key is "<product_id>" or
"<product_id>:<size>" — the same boots in sizes 41 and 43 are two lines.
"""

from collections import defaultdict
from decimal import Decimal

from products.models import Product

SESSION_KEY = 'order_list'
MAX_QTY = 9999


def make_key(product_id, size=''):
    return f'{product_id}:{size}' if size else str(product_id)


def parse_key(key):
    product_id, _, size = key.partition(':')
    return (int(product_id), size) if product_id.isdigit() else (None, '')


def get_cart(session):
    return session.get(SESSION_KEY, {})


def save_cart(session, cart):
    session[SESSION_KEY] = cart


def clear_cart(session):
    session.pop(SESSION_KEY, None)


def count_items(session):
    """Number of pieces in the order list, ignoring products that were removed or hidden."""
    parsed = [(*parse_key(key), qty) for key, qty in get_cart(session).items()]
    if not parsed:
        return 0  # no query for visitors with an empty list
    available = set(
        Product.objects.filter(
            pk__in={product_id for product_id, _, _ in parsed if product_id is not None},
            is_active=True,
            category__is_active=True,
        ).values_list('pk', flat=True)
    )
    return sum(qty for product_id, _, qty in parsed if product_id in available)


def price_items(lines):
    """Turn [(product, size, qty), ...] into priced order items and a total.

    Used by both the website cart and the API, so prices are always
    calculated the same way. The wholesale price depends on the total
    quantity of a product across all its sizes.
    """
    qty_per_product = defaultdict(int)
    for product, _, qty in lines:
        qty_per_product[product.pk] += qty

    items, total = [], Decimal('0')
    for product, size, qty in lines:
        unit = product.price_for(qty_per_product[product.pk])
        line = unit * qty if unit is not None else None
        if line is not None:
            total += line
        items.append({
            'key': make_key(product.pk, size),
            'product': product,
            'size': size,
            'qty': qty,
            'unit': unit,
            'line': line,
        })
    items.sort(key=lambda item: (item['product'].name, item['size']))
    return items, total


def get_items(session):
    """Return (items, total) for the products in the session that are still available."""
    parsed = [(*parse_key(key), qty) for key, qty in get_cart(session).items()]
    products = Product.objects.filter(
        pk__in={product_id for product_id, _, _ in parsed if product_id is not None},
        is_active=True,
        category__is_active=True,
    ).in_bulk()
    lines = [
        (products[product_id], size, qty)
        for product_id, size, qty in parsed
        if product_id in products
    ]
    return price_items(lines)
