import re
from datetime import timedelta

from django.db import models
from django.utils import timezone

SIZE_RANGE_RE = re.compile(r'^(\d{1,3})\s*[-–—]\s*(\d{1,3})$')


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to='categories/',
        blank=True,
        null=True
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products'
    )

    name = models.CharField(max_length=200)
    article = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )

    wholesale_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    wholesale_min_qty = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Минимальное количество для оптовой цены (шт.)'
    )

    stock = models.PositiveIntegerField(default=0)
    sizes = models.CharField(max_length=100, blank=True)
    color = models.CharField(max_length=50, blank=True)
    video_url = models.URLField(
        max_length=300,
        blank=True,
        help_text='Ссылка на Reels или видео товара'
    )

    image = models.ImageField(
        upload_to='products/',
        blank=True,
        null=True
    )

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    @property
    def is_new(self):
        return timezone.now() - self.created_at < timedelta(days=14)

    def price_for(self, qty):
        """Retail price, or wholesale price when the quantity reaches the minimum."""
        if (
            self.wholesale_price is not None
            and self.wholesale_min_qty
            and qty >= self.wholesale_min_qty
        ):
            return self.wholesale_price
        return self.price

    @property
    def size_options(self):
        """Sizes a customer can pick: '39-44' -> ['39', ..., '44'], 'S, M, L' -> ['S', 'M', 'L']."""
        value = self.sizes.strip()
        match = SIZE_RANGE_RE.match(value)
        if match:
            start, end = int(match[1]), int(match[2])
            if start <= end and end - start <= 30:
                return [str(size) for size in range(start, end + 1)]
        return [size for size in re.split(r'[,;/\s]+', value) if size]


class ProductImage(models.Model):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='extra_images'
    )
    image = models.ImageField(upload_to='products/')
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ('order', 'pk')

    def __str__(self):
        return f'{self.product.name} — фото {self.pk}'
