import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = 'https://api.telegram.org/bot{token}/sendMessage'
TIMEOUT_SECONDS = 5


def send_telegram_message(text):
    """Send a message to the manager chat. Returns True on success.

    A failed notification must never break placing an order, so network
    errors are logged instead of raised.
    """
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if not (token and chat_id):
        logger.info('Telegram is not configured, skipping notification')
        return False

    request = urllib.request.Request(
        TELEGRAM_API_URL.format(token=token),
        data=json.dumps({'chat_id': chat_id, 'text': text}).encode(),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        logger.warning('Failed to send Telegram notification', exc_info=True)
        return False


def format_order_message(order):
    lines = [f'Новый заказ №{order.number} ({order.get_source_display()})']
    if order.customer_name:
        lines.append(f'Имя: {order.customer_name}')
    phones = ', '.join(phone for phone in (order.phone, order.extra_phone) if phone)
    lines.append(f'Телефон: {phones}')
    label = 'Адрес' if order.is_delivery else 'Получение'
    lines.append(f'{label}: {order.full_address}')
    if order.comment:
        lines.append(f'Комментарий: {order.comment}')
    lines.append('')
    for n, item in enumerate(order.items.all(), 1):
        size = f', размер {item.size}' if item.size else ''
        price = f' — {item.line_total:.0f} сом' if item.line_total is not None else ''
        lines.append(
            f'{n}. {item.product_name} (арт. {item.article}){size} × {item.quantity}{price}'
        )
    lines.append('')
    lines.append(f'Итого: {order.total:.0f} сом')
    return '\n'.join(lines)


def notify_new_order(order_id):
    from .models import Order

    order = Order.objects.prefetch_related('items').get(pk=order_id)
    return send_telegram_message(format_order_message(order))
