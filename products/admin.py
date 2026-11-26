from django.contrib import admin

from .models import Category, Product, ProductImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'slug', 'description')
    prepopulated_fields = {'slug': ('name',)}
    list_per_page = 50


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline]
    list_display = (
        'name',
        'article',
        'category',
        'price',
        'wholesale_price',
        'stock',
        'is_active',
        'is_featured',
        'created_at',
    )

    list_filter = (
        'category',
        'is_active',
        'is_featured',
    )

    search_fields = (
        'name',
        'article',
        'description',
    )

    list_editable = (
        'price',
        'wholesale_price',
        'stock',
        'is_active',
        'is_featured',
    )

    list_select_related = ('category',)
    date_hierarchy = 'created_at'
    list_per_page = 50
