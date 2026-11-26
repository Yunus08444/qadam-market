import uuid

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

phone_validator = RegexValidator(
    regex=r'^\+?[\d\s()-]{9,20}$',
    message='Введите номер телефона, например +996 555 123 456',
)


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Новый'
        CONFIRMED = 'confirmed', 'Подтверждён'
        SHIPPED = 'shipped', 'Отгружен'
        COMPLETED = 'completed', 'Выполнен'
        CANCELLED = 'cancelled', 'Отменён'

    # Which status an order may move to from its current one
    TRANSITIONS = {
        Status.NEW: {Status.CONFIRMED, Status.CANCELLED},
        Status.CONFIRMED: {Status.SHIPPED, Status.CANCELLED},
        Status.SHIPPED: {Status.COMPLETED},
        Status.COMPLETED: set(),
        Status.CANCELLED: set(),
    }

    class Region(models.TextChoices):
        PICKUP = 'pickup', 'Самовывоз — рынок Дордой'
        BISHKEK = 'bishkek', 'г. Бишкек'
        OSH_CITY = 'osh_city', 'г. Ош'
        CHUY = 'chuy', 'Чуйская обл.'
        OSH = 'osh', 'Ошская обл.'
        JALAL_ABAD = 'jalal_abad', 'Джалал-Абадская обл.'
        BATKEN = 'batken', 'Баткенская обл.'
        NARYN = 'naryn', 'Нарынская обл.'
        ISSYK_KUL = 'issyk_kul', 'Иссык-Кульская обл.'
        TALAS = 'talas', 'Таласская обл.'

    class Source(models.TextChoices):
        SITE = 'site', 'Сайт'
        WHATSAPP = 'whatsapp', 'WhatsApp'
        PHONE = 'phone', 'Звонок'
        INSTAGRAM = 'instagram', 'Instagram'

    # Unguessable id for the customer-facing "order accepted" page
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    source = models.CharField(
        'Откуда заказ', max_length=20, choices=Source.choices, default=Source.SITE
    )

    # Orders copied from WhatsApp often have no name, so it is optional here
    # (the website form still asks for it)
    customer_name = models.CharField('Имя', max_length=100, blank=True)
    phone = models.CharField('Телефон', max_length=32, validators=[phone_validator])
    extra_phone = models.CharField(
        'Доп. телефон', max_length=32, blank=True, validators=[phone_validator]
    )

    region = models.CharField(
        'Область', max_length=20, choices=Region.choices, default=Region.PICKUP
    )
    locality = models.CharField('Район / город / село', max_length=150, blank=True)
    address = models.CharField('Улица, дом', max_length=200, blank=True)

    comment = models.TextField('Комментарий', blank=True, max_length=1000)
    deposit = models.DecimalField(
        'Задаток', max_digits=10, decimal_places=2, default=0,
        help_text='Сколько клиент уже оплатил',
    )

    status = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    total = models.DecimalField('Сумма', max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField('Создан', auto_now_add=True)
    updated_at = models.DateTimeField('Изменён', auto_now=True)

    class Meta:
        ordering = ('-created_at',)
        verbose_name = 'заказ'
        verbose_name_plural = 'заказы'

    def __str__(self):
        return f'Заказ №{self.number}'

    @property
    def number(self):
        return f'{self.pk:05d}' if self.pk else '—'

    @property
    def is_delivery(self):
        return self.region != self.Region.PICKUP

    @property
    def full_address(self):
        if not self.is_delivery:
            return self.get_region_display()
        parts = [self.get_region_display(), self.locality, self.address]
        return ', '.join(part for part in parts if part)

    @property
    def amount_due(self):
        """What the customer still has to pay on delivery."""
        return max(self.total - self.deposit, 0)

    def recalculate_total(self):
        self.total = sum(
            item.line_total for item in self.items.all() if item.line_total is not None
        )
        self.save(update_fields=['total', 'updated_at'])

    def can_change_to(self, status):
        return status in self.TRANSITIONS[self.status]

    def change_status(self, status):
        if not self.can_change_to(status):
            raise ValueError(
                f'Нельзя перевести заказ из «{self.get_status_display()}» '
                f'в «{self.Status(status).label}»'
            )
        self.status = status
        self.save(update_fields=['status', 'updated_at'])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    # The product may be deleted later, so name, article and price are copied
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Товар',
        related_name='order_items',
    )
    # Filled from the product automatically when left empty
    product_name = models.CharField('Название', max_length=200, blank=True)
    article = models.CharField('Артикул', max_length=50, blank=True)
    size = models.CharField('Размер', max_length=20, blank=True)
    unit_price = models.DecimalField(
        'Цена за шт.', max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Пусто — возьмётся цена товара',
    )
    quantity = models.PositiveIntegerField('Количество', default=1)
    line_total = models.DecimalField(
        'Сумма', max_digits=12, decimal_places=2, null=True, blank=True, editable=False
    )

    class Meta:
        verbose_name = 'позиция заказа'
        verbose_name_plural = 'позиции заказа'

    def __str__(self):
        size = f', размер {self.size}' if self.size else ''
        return f'{self.product_name}{size} × {self.quantity}'

    def save(self, *args, **kwargs):
        if self.product_id:
            self.product_name = self.product_name or self.product.name
            self.article = self.article or self.product.article
            if self.unit_price is None:
                self.unit_price = self.product.price_for(self.quantity)
        self.line_total = (
            self.unit_price * self.quantity if self.unit_price is not None else None
        )
        super().save(*args, **kwargs)

    def clean(self):
        if not self.product_id and not self.product_name:
            raise ValidationError('Выберите товар или впишите название')
