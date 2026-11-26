import json
import urllib.error
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from products.models import Category, Product

from .models import Order, OrderItem
from .notifications import format_order_message, send_telegram_message

VALID_CUSTOMER = {
    'customer_name': 'Азамат',
    'phone': '+996 555 12 34 56',
    'region': 'pickup',
    'comment': '',
}


class OrderTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        category = Category.objects.create(name='Обувь', slug='obuv')
        cls.boots = Product.objects.create(
            category=category,
            name='Рабочие ботинки',
            article='BOT-101',
            price=Decimal('1250.00'),
            wholesale_price=Decimal('1000.00'),
            wholesale_min_qty=10,
        )
        cls.gloves = Product.objects.create(
            category=category, name='Перчатки', article='GLOVE-1', price=None
        )

    def add_to_cart(self, product, qty):
        self.client.post(reverse('order_add', args=[product.pk]), {'qty': str(qty)})


class CheckoutTests(OrderTestCase):
    def test_checkout_saves_order_with_price_snapshot_and_clears_cart(self):
        self.add_to_cart(self.boots, 12)
        self.add_to_cart(self.gloves, 3)

        with self.captureOnCommitCallbacks(execute=False):
            response = self.client.post(reverse('checkout'), VALID_CUSTOMER)

        order = Order.objects.get()
        self.assertRedirects(response, reverse('order_done', args=[order.public_id]))
        self.assertEqual(order.status, Order.Status.NEW)
        self.assertEqual(order.total, Decimal('12000.00'))

        boots = order.items.get(article='BOT-101')
        self.assertEqual(boots.unit_price, Decimal('1000.00'))
        self.assertEqual(boots.quantity, 12)
        gloves = order.items.get(article='GLOVE-1')
        self.assertIsNone(gloves.unit_price)
        self.assertIsNone(gloves.line_total)

        self.assertEqual(self.client.get(reverse('order_list')).context['items'], [])

    def test_order_keeps_old_price_after_product_changes(self):
        self.add_to_cart(self.boots, 1)
        self.client.post(reverse('checkout'), VALID_CUSTOMER)

        Product.objects.filter(pk=self.boots.pk).update(price=Decimal('9999'), name='Новое имя')

        item = OrderItem.objects.get()
        self.assertEqual(item.unit_price, Decimal('1250.00'))
        self.assertEqual(item.product_name, 'Рабочие ботинки')

    def test_deleting_product_keeps_order_items(self):
        self.add_to_cart(self.gloves, 1)
        self.client.post(reverse('checkout'), VALID_CUSTOMER)

        self.gloves.delete()

        item = OrderItem.objects.get()
        self.assertIsNone(item.product)
        self.assertEqual(item.article, 'GLOVE-1')

    def test_invalid_form_shows_errors_and_keeps_cart(self):
        self.add_to_cart(self.boots, 1)

        response = self.client.post(
            reverse('checkout'), {'customer_name': '', 'phone': 'abc', 'comment': ''}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors['customer_name'])
        self.assertContains(response, 'Введите номер телефона')
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(len(response.context['items']), 1)

    def test_empty_cart_redirects_without_creating_order(self):
        response = self.client.post(reverse('checkout'), VALID_CUSTOMER)

        self.assertRedirects(response, reverse('order_list'))
        self.assertEqual(Order.objects.count(), 0)

    def test_honeypot_filled_by_bot_creates_nothing(self):
        self.add_to_cart(self.boots, 1)

        response = self.client.post(reverse('checkout'), {**VALID_CUSTOMER, 'website': 'spam'})

        self.assertRedirects(response, reverse('catalog'))
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_requires_post(self):
        self.assertEqual(self.client.get(reverse('checkout')).status_code, 405)

    def test_done_page_is_only_visible_to_the_customer_who_ordered(self):
        self.add_to_cart(self.boots, 1)
        self.client.post(reverse('checkout'), VALID_CUSTOMER)
        order = Order.objects.get()
        url = reverse('order_done', args=[order.public_id])

        response = self.client.get(url)
        self.assertContains(response, f'Заказ №{order.number} принят')
        self.assertContains(response, 'Рабочие ботинки')

        self.client.logout()  # new session, as if someone else opened the link
        self.assertEqual(self.client.get(url).status_code, 404)


class OrderStatusTests(OrderTestCase):
    def setUp(self):
        self.order = Order.objects.create(customer_name='Азамат', phone='+996555123456')

    def test_allowed_transitions(self):
        self.order.change_status(Order.Status.CONFIRMED)
        self.order.change_status(Order.Status.SHIPPED)
        self.order.change_status(Order.Status.COMPLETED)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.COMPLETED)

    def test_forbidden_transition_raises_and_keeps_status(self):
        with self.assertRaises(ValueError):
            self.order.change_status(Order.Status.SHIPPED)

        self.order.change_status(Order.Status.CANCELLED)
        with self.assertRaises(ValueError):
            self.order.change_status(Order.Status.CONFIRMED)

        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.CANCELLED)

    def test_order_number_is_zero_padded(self):
        self.assertEqual(self.order.number, f'{self.order.pk:05d}')
        self.assertEqual(Order().number, '—')


class OrderAdminTests(OrderTestCase):
    def setUp(self):
        admin = get_user_model().objects.create_superuser('admin', 'a@example.com', 'pass')
        self.client.force_login(admin)
        self.new = Order.objects.create(customer_name='A', phone='+996555000001')
        self.done = Order.objects.create(
            customer_name='B', phone='+996555000002', status=Order.Status.COMPLETED
        )

    def test_confirm_action_respects_transitions(self):
        response = self.client.post(
            reverse('admin:orders_order_changelist'),
            {'action': 'mark_confirmed', '_selected_action': [self.new.pk, self.done.pk]},
            follow=True,
        )

        self.new.refresh_from_db()
        self.done.refresh_from_db()
        self.assertEqual(self.new.status, Order.Status.CONFIRMED)
        self.assertEqual(self.done.status, Order.Status.COMPLETED)
        self.assertContains(response, 'Обновлено заказов: 1')
        self.assertContains(response, 'Пропущено: 1')

    def test_changelist_and_change_page_open(self):
        self.assertEqual(
            self.client.get(reverse('admin:orders_order_changelist')).status_code, 200
        )
        self.assertEqual(
            self.client.get(
                reverse('admin:orders_order_change', args=[self.new.pk])
            ).status_code,
            200,
        )


class TelegramNotificationTests(OrderTestCase):
    def make_order(self):
        self.add_to_cart(self.boots, 2)
        self.add_to_cart(self.gloves, 1)
        self.client.post(reverse('checkout'), {**VALID_CUSTOMER, 'comment': 'Размер 42'})
        return Order.objects.get()

    def test_message_contains_order_details(self):
        order = self.make_order()

        text = format_order_message(order)

        self.assertIn(f'Новый заказ №{order.number}', text)
        self.assertIn('+996 555 12 34 56', text)
        self.assertIn('Размер 42', text)
        self.assertIn('Рабочие ботинки (арт. BOT-101) × 2 — 2500 сом', text)
        self.assertIn('Перчатки (арт. GLOVE-1) × 1', text)
        self.assertIn('Итого: 2500 сом', text)

    @override_settings(TELEGRAM_BOT_TOKEN='123:abc', TELEGRAM_CHAT_ID='42')
    @mock.patch('orders.notifications.urllib.request.urlopen')
    def test_notification_is_sent_after_commit(self, urlopen):
        urlopen.return_value.__enter__.return_value.status = 200
        self.add_to_cart(self.boots, 1)

        with self.captureOnCommitCallbacks(execute=False) as callbacks:
            self.client.post(reverse('checkout'), VALID_CUSTOMER)
        urlopen.assert_not_called()  # nothing is sent before the commit

        for callback in callbacks:
            callback()

        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.telegram.org/bot123:abc/sendMessage')
        payload = json.loads(request.data)
        self.assertEqual(payload['chat_id'], '42')
        self.assertIn('Рабочие ботинки', payload['text'])

    @override_settings(TELEGRAM_BOT_TOKEN='', TELEGRAM_CHAT_ID='')
    @mock.patch('orders.notifications.urllib.request.urlopen')
    def test_not_configured_telegram_is_skipped(self, urlopen):
        self.assertFalse(send_telegram_message('hello'))
        urlopen.assert_not_called()

    @override_settings(TELEGRAM_BOT_TOKEN='123:abc', TELEGRAM_CHAT_ID='42')
    @mock.patch(
        'orders.notifications.urllib.request.urlopen',
        side_effect=urllib.error.URLError('no network'),
    )
    def test_network_error_does_not_break_checkout(self, urlopen):
        self.add_to_cart(self.boots, 1)

        with self.assertLogs('orders.notifications', level='WARNING'):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.client.post(reverse('checkout'), VALID_CUSTOMER)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Order.objects.count(), 1)
