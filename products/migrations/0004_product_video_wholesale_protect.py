from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_alter_product_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='video_url',
            field=models.URLField(blank=True, help_text='Ссылка на Reels или видео товара', max_length=300),
        ),
        migrations.AddField(
            model_name='product',
            name='wholesale_min_qty',
            field=models.PositiveIntegerField(blank=True, help_text='Минимальное количество для оптовой цены (шт.)', null=True),
        ),
        migrations.AlterField(
            model_name='product',
            name='category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='products', to='products.category'),
        ),
        migrations.AlterField(
            model_name='product',
            name='description',
            field=models.TextField(blank=True),
        ),
    ]
