import csv
from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from products.models import Category, Product


def to_decimal(value):
    value = (value or '').replace(' ', '').replace(',', '.')
    try:
        return Decimal(value) if value else None
    except InvalidOperation:
        return None


class CsvRow:
    """CSV row where every value is a stripped string ('' for missing columns)."""

    def __init__(self, raw_row):
        self._row = raw_row

    def get(self, key):
        return (self._row.get(key) or '').strip()


def to_int(value, default=None):
    try:
        return max(0, int(str(value).strip()))
    except (TypeError, ValueError):
        return default


class Command(BaseCommand):
    help = 'Импорт товаров из CSV: py manage.py import_products products_template.csv'

    def add_arguments(self, parser):
        parser.add_argument('path')

    def handle(self, *args, **options):
        try:
            f = open(options['path'], encoding='utf-8-sig', newline='')
        except OSError as exc:
            raise CommandError(str(exc)) from exc
        created = updated = skipped = 0
        with f:
            head = f.readline()
            f.seek(0)
            reader = csv.DictReader(f, delimiter=';' if ';' in head else ',')
            for raw_row in reader:
                row = CsvRow(raw_row)
                get = row.get
                article, name, cat_name = get('article'), get('name'), get('category')
                if not (article and name and cat_name):
                    skipped += 1
                    continue
                category = Category.objects.filter(name=cat_name).first()
                if category is None:
                    slug = slugify(cat_name, allow_unicode=True) or 'category'
                    if Category.objects.filter(slug=slug).exists():
                        slug = f'{slug}-{Category.objects.count() + 1}'
                    category = Category.objects.create(name=cat_name, slug=slug)
                _, is_created = Product.objects.update_or_create(
                    article=article,
                    defaults={
                        'category': category,
                        'name': name,
                        'description': get('description'),
                        'price': to_decimal(get('price')),
                        'wholesale_price': to_decimal(get('wholesale_price')),
                        'wholesale_min_qty': to_int(get('wholesale_min_qty')),
                        'stock': to_int(get('stock'), 0),
                        'sizes': get('sizes'),
                        'color': get('color'),
                        'video_url': get('video_url'),
                    },
                )
                created += is_created
                updated += not is_created
        self.stdout.write(self.style.SUCCESS(
            f'Добавлено: {created}, обновлено: {updated}, пропущено: {skipped}'
        ))
