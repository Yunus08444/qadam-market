import uuid

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

    # Unguessable id for the customer-facing "order accepted" page
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    customer_name = models.CharField('Имя', max_length=100)
    phone = models.CharField('Телефон', max_length=32, validators=[phone_validator])
    comment = models.TextField('Комментарий', blank=True, max_length=1000)

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
        related_name='order_items',
    )
    product_name = models.CharField('Товар', max_length=200)
    article = models.CharField('Артикул', max_length=50)
    unit_price = models.DecimalField(
        'Цена за шт.', max_digits=10, decimal_places=2, null=True, blank=True
    )
    quantity = models.PositiveIntegerField('Количество')
    line_total = models.DecimalField(
        'Сумма', max_digits=12, decimal_places=2, null=True, blank=True
    )

    class Meta:
        verbose_name = 'позиция заказа'
        verbose_name_plural = 'позиции заказа'

    def __str__(self):
        return f'{self.product_name} × {self.quantity}'
