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


def get_items(session):
    """Return (items, total) for the products that are still available."""
    lines = []
    for key, qty in get_cart(session).items():
        product_id, size = parse_key(key)
        if product_id is not None:
            lines.append((key, product_id, size, qty))

    products = Product.objects.filter(
        pk__in={product_id for _, product_id, _, _ in lines},
        is_active=True,
        category__is_active=True,
    ).in_bulk()

    # Wholesale price depends on the total quantity of a product across all sizes
    qty_per_product = defaultdict(int)
    for _, product_id, _, qty in lines:
        qty_per_product[product_id] += qty

    items, total = [], Decimal('0')
    for key, product_id, size, qty in lines:
        product = products.get(product_id)
        if product is None:
            continue
        unit = product.price_for(qty_per_product[product_id])
        line = unit * qty if unit is not None else None
        if line is not None:
            total += line
        items.append({
            'key': key,
            'product': product,
            'size': size,
            'qty': qty,
            'unit': unit,
            'line': line,
        })
    items.sort(key=lambda item: (item['product'].name, item['size']))
    return items, total
