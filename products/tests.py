from decimal import Decimal

from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Category, Product


class CatalogViewsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.category = Category.objects.create(name='Обувь', slug='obuv')
        cls.other_category = Category.objects.create(
            name='Одежда',
            slug='odezhda',
        )
        cls.product = Product.objects.create(
            category=cls.category,
            name='Рабочие ботинки',
            article='BOT-101',
            description='Описание товара',
            price=Decimal('1250.00'),
            wholesale_price=Decimal('1000.00'),
            stock=7,
            sizes='40-45',
            color='Чёрный',
            is_featured=True,
        )
        Product.objects.create(
            category=cls.other_category,
            name='Рабочая куртка',
            article='JKT-202',
            description='',
            price=Decimal('2500.00'),
        )
        Product.objects.create(
            category=cls.category,
            name='Перчатки',
            article='GLOVE-303',
            description='',
            price=None,
        )

    def test_home_shows_active_database_categories_and_featured_products(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Обувь')
        self.assertContains(response, 'Рабочие ботинки')
        self.assertContains(response, 'Популярные товары')

    def test_home_does_not_show_products_from_inactive_categories(self):
        self.category.is_active = False
        self.category.save(update_fields=['is_active'])

        response = self.client.get(reverse('home'))

        self.assertNotContains(response, 'Рабочие ботинки')

    def test_catalog_search_matches_name_and_article(self):
        by_name = self.client.get(reverse('catalog'), {'q': 'ботинки'})
        by_article = self.client.get(reverse('catalog'), {'q': 'glove-303'})

        self.assertContains(by_name, 'Рабочие ботинки')
        self.assertNotContains(by_name, 'Рабочая куртка')
        self.assertContains(by_article, 'Перчатки')

    def test_catalog_filters_category_and_excludes_inactive_records(self):
        self.other_category.is_active = False
        self.other_category.save(update_fields=['is_active'])

        response = self.client.get(
            reverse('catalog'),
            {'category': self.category.slug},
        )

        self.assertContains(response, 'Рабочие ботинки')
        self.assertNotContains(response, 'Рабочая куртка')
        self.assertEqual(response.context['page_obj'].paginator.count, 2)

    def test_catalog_sorts_and_handles_invalid_sort_and_page(self):
        response = self.client.get(reverse('catalog'), {'sort': 'price_asc'})
        names = [product.name for product in response.context['page_obj']]
        self.assertEqual(names, ['Рабочие ботинки', 'Рабочая куртка', 'Перчатки'])

        response = self.client.get(reverse('catalog'), {'sort': 'price_desc'})
        names = [product.name for product in response.context['page_obj']]
        self.assertEqual(names, ['Рабочая куртка', 'Рабочие ботинки', 'Перчатки'])

        fallback = self.client.get(
            reverse('catalog'),
            {'sort': 'invalid', 'page': 'not-a-page'},
        )
        self.assertEqual(fallback.context['sort'], 'newest')
        self.assertEqual(fallback.context['page_obj'].number, 1)

    def test_catalog_paginates_and_preserves_filters(self):
        for number in range(13):
            Product.objects.create(
                category=self.category,
                name=f'Товар {number}',
                article=f'PAGE-{number}',
                description='',
                price=Decimal('100.00'),
            )

        response = self.client.get(
            reverse('catalog'),
            {'category': self.category.slug, 'q': 'PAGE-', 'page': '2'},
        )

        self.assertEqual(response.context['page_obj'].number, 2)
        self.assertContains(response, 'category=obuv')
        self.assertContains(response, 'q=PAGE-')

    def test_product_detail_displays_optional_prices_and_attributes(self):
        response = self.client.get(
            reverse('product_detail', args=[self.product.pk]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1250 сом')
        self.assertContains(response, '1000 сом')
        self.assertContains(response, 'BOT-101')
        self.assertContains(response, '40-45')
        self.assertContains(response, 'Чёрный')

        unpriced = self.client.get(
            reverse('product_detail', args=[
                Product.objects.get(article='GLOVE-303').pk,
            ]),
        )
        self.assertContains(unpriced, 'Уточняйте у продавца')
        self.assertNotContains(unpriced, '0 сом')

    def test_hidden_products_and_unknown_products_return_404(self):
        hidden = Product.objects.create(
            category=self.category,
            name='Скрытый товар',
            article='HIDDEN-1',
            description='',
            is_active=False,
        )

        self.assertEqual(
            self.client.get(
                reverse('product_detail', args=[hidden.pk]),
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse('product_detail', args=[99999])).status_code,
            404,
        )

    @override_settings(DEBUG=False)
    def test_not_found_page_uses_the_catalog_error_template(self):
        response = self.client.get('/this-page-does-not-exist/')

        self.assertEqual(response.status_code, 404)
        self.assertContains(response, 'Страница не найдена', status_code=404)

    @override_settings(SELLER_PHONE='+996 (555) 12-34-56')
    def test_configured_seller_phone_creates_phone_and_whatsapp_links(self):
        response = self.client.get(reverse('product_detail', args=[self.product.pk]))

        self.assertContains(response, 'https://wa.me/996555123456')
        self.assertContains(response, 'tel:+996555123456')

    def test_missing_seller_contact_does_not_create_broken_links(self):
        with override_settings(SELLER_PHONE=''):
            response = self.client.get(reverse('product_detail', args=[self.product.pk]))

        self.assertContains(response, 'Контакт продавца пока не настроен')
        self.assertNotContains(response, 'https://wa.me/')

    def test_catalog_stylesheet_is_discoverable_by_staticfiles(self):
        self.assertTrue(finders.find('css/style.css'))

    @override_settings(SELLER_PHONE='+996 555 12 34 56')
    def test_whatsapp_text_video_and_wholesale_minimum(self):
        self.product.video_url = 'https://www.instagram.com/reel/test/'
        self.product.wholesale_min_qty = 10
        self.product.save()

        response = self.client.get(reverse('product_detail', args=[self.product.pk]))

        self.assertContains(response, 'wa.me/996555123456?text=')
        self.assertContains(response, 'Смотреть видео')
        self.assertContains(response, 'от 10 шт.')

    def test_category_with_products_cannot_be_deleted(self):
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.category.delete()

    def test_order_list_flow_and_wholesale_pricing(self):
        Product.objects.filter(pk=self.product.pk).update(wholesale_min_qty=10)
        self.client.post(reverse('order_add', args=[self.product.pk]), {'qty': '12'})

        response = self.client.get(reverse('order_list'))
        self.assertContains(response, 'Рабочие ботинки')
        self.assertEqual(response.context['total'], Decimal('12000.00'))

        self.client.post(reverse('order_set', args=[self.product.pk]), {'qty': '0'})
        self.assertEqual(self.client.get(reverse('order_list')).context['items'], [])

    def test_info_pages_sitemap_and_robots(self):
        for name in ('about', 'wholesale', 'delivery', 'sitemap', 'robots'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_in_stock_filter_and_new_badge(self):
        response = self.client.get(reverse('catalog'), {'in_stock': '1'})
        self.assertEqual(response.context['page_obj'].paginator.count, 1)
        self.assertTrue(self.product.is_new)


class ImportProductsCommandTests(TestCase):
    def run_import(self, content):
        import tempfile
        from io import StringIO
        from pathlib import Path

        from django.core.management import call_command

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'products.csv'
            path.write_text(content, encoding='utf-8')
            out = StringIO()
            call_command('import_products', str(path), stdout=out)
        return out.getvalue()

    def test_creates_categories_and_products_and_skips_invalid_rows(self):
        output = self.run_import(
            'category;name;article;price;wholesale_price;wholesale_min_qty;stock\n'
            'Керзы;Сапоги;K-1;3 500;2800,50;10;5\n'
            'Керзы;Без артикула;;100;;;\n'
        )

        product = Product.objects.get(article='K-1')
        self.assertEqual(product.category.name, 'Керзы')
        self.assertEqual(product.price, Decimal('3500'))
        self.assertEqual(product.wholesale_price, Decimal('2800.50'))
        self.assertEqual(product.wholesale_min_qty, 10)
        self.assertEqual(product.stock, 5)
        self.assertEqual(product.description, '')
        self.assertIn('Добавлено: 1, обновлено: 0, пропущено: 1', output)

    def test_updates_existing_product_by_article(self):
        self.run_import('category,name,article,price\nОбувь,Старое имя,A-1,100\n')
        output = self.run_import('category,name,article,price\nОбувь,Новое имя,A-1,abc\n')

        product = Product.objects.get(article='A-1')
        self.assertEqual(product.name, 'Новое имя')
        self.assertIsNone(product.price)
        self.assertEqual(Category.objects.count(), 1)
        self.assertIn('обновлено: 1', output)

    def test_missing_file_raises_command_error(self):
        from django.core.management import CommandError, call_command

        with self.assertRaises(CommandError):
            call_command('import_products', 'does-not-exist.csv')
