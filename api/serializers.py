from rest_framework import serializers

from orders.cart import price_items
from orders.models import Order, OrderItem
from orders.services import create_order
from products.models import Category, Product, ProductImage

# --- Catalog -----------------------------------------------------------------

class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'description', 'image', 'product_count')


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ('image', 'order')


class ProductListSerializer(serializers.ModelSerializer):
    category = serializers.SlugRelatedField(slug_field='slug', read_only=True)
    size_options = serializers.ListField(child=serializers.CharField(), read_only=True)
    in_stock = serializers.SerializerMethodField()
    is_new = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = (
            'id', 'name', 'article', 'category', 'price', 'wholesale_price',
            'wholesale_min_qty', 'size_options', 'color', 'image', 'in_stock',
            'is_new', 'is_featured',
        )

    def get_in_stock(self, obj) -> bool:
        return obj.stock > 0


class ProductDetailSerializer(ProductListSerializer):
    images = ProductImageSerializer(source='extra_images', many=True, read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = (*ProductListSerializer.Meta.fields, 'description', 'stock', 'video_url', 'images')


# --- Orders ------------------------------------------------------------------

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            'product', 'product_name', 'article', 'size', 'quantity', 'unit_price', 'line_total',
        )


class OrderItemInputSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True, category__is_active=True)
    )
    size = serializers.CharField(required=False, allow_blank=True, default='')
    quantity = serializers.IntegerField(min_value=1, max_value=9999)

    def validate(self, attrs):
        product, size = attrs['product'], attrs['size'].strip()
        options = product.size_options
        if options and size not in options:
            raise serializers.ValidationError(
                {'size': f'Выберите размер из: {", ".join(options)}'}
            )
        attrs['size'] = size if options else ''
        return attrs


class OrderCreateSerializer(serializers.ModelSerializer):
    """What a client (mobile app, another site) sends to place an order."""

    items = OrderItemInputSerializer(many=True, write_only=True)

    class Meta:
        model = Order
        fields = (
            'customer_name', 'phone', 'extra_phone', 'region', 'locality',
            'address', 'comment', 'items',
        )
        extra_kwargs = {'customer_name': {'required': True, 'allow_blank': False}}

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError('Добавьте хотя бы один товар')
        return items

    def validate(self, attrs):
        if attrs.get('region', Order.Region.PICKUP) != Order.Region.PICKUP and not attrs.get(
            'locality'
        ):
            raise serializers.ValidationError(
                {'locality': 'Укажите район, город или село для доставки'}
            )
        return attrs

    def create(self, validated_data):
        lines = [
            (item['product'], item['size'], item['quantity'])
            for item in validated_data.pop('items')
        ]
        items, _ = price_items(lines)
        return create_order(items=items, **validated_data)

    def to_representation(self, instance):
        return OrderPublicSerializer(instance, context=self.context).data


class OrderPublicSerializer(serializers.ModelSerializer):
    """Order status for the customer. No phone or address: anyone with the id can read it."""

    number = serializers.CharField(read_only=True)
    amount_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            'public_id', 'number', 'status', 'status_display', 'total', 'deposit',
            'amount_due', 'items', 'created_at',
        )


class OrderManagerSerializer(serializers.ModelSerializer):
    """Full order for managers (staff users only)."""

    number = serializers.CharField(read_only=True)
    amount_due = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    full_address = serializers.CharField(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = (
            'id', 'public_id', 'number', 'source', 'status', 'customer_name', 'phone',
            'extra_phone', 'region', 'locality', 'address', 'full_address', 'comment',
            'total', 'deposit', 'amount_due', 'items', 'created_at', 'updated_at',
        )
        read_only_fields = fields


class OrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)

    def validate_status(self, status):
        order = self.context['order']
        if not order.can_change_to(status):
            raise serializers.ValidationError(
                f'Нельзя перевести заказ из «{order.get_status_display()}» '
                f'в «{Order.Status(status).label}»'
            )
        return status
