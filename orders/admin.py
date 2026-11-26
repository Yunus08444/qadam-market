from django.contrib import admin, messages

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ('product_name', 'article', 'unit_price', 'quantity', 'line_total')
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


def _status_action(status):
    """Build an admin action that moves selected orders to `status`."""

    def action(modeladmin, request, queryset):
        changed, skipped = 0, 0
        for order in queryset:
            if order.can_change_to(status):
                order.change_status(status)
                changed += 1
            else:
                skipped += 1
        if changed:
            modeladmin.message_user(request, f'Обновлено заказов: {changed}', messages.SUCCESS)
        if skipped:
            modeladmin.message_user(
                request,
                f'Пропущено: {skipped} — из их текущего статуса так перевести нельзя',
                messages.WARNING,
            )

    label = Order.Status(status).label
    action.__name__ = f'mark_{status}'
    action.short_description = f'Отметить как «{label}»'
    return action


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    inlines = [OrderItemInline]
    list_display = ('__str__', 'customer_name', 'phone', 'status', 'total', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('customer_name', 'phone', 'items__article', 'items__product_name')
    date_hierarchy = 'created_at'
    list_per_page = 50
    # Status changes only through actions, so the allowed transitions are always respected
    readonly_fields = ('status', 'total', 'public_id', 'created_at', 'updated_at')
    fields = (
        ('customer_name', 'phone'),
        'comment',
        ('status', 'total'),
        ('created_at', 'updated_at'),
        'public_id',
    )
    actions = [
        _status_action(Order.Status.CONFIRMED),
        _status_action(Order.Status.SHIPPED),
        _status_action(Order.Status.COMPLETED),
        _status_action(Order.Status.CANCELLED),
    ]

    def has_add_permission(self, request):
        # Orders come from the website, not from the admin
        return False
