# Generated by Django 5.2 on 2025-04-10 10:35

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_order_marked_for_return_order_return_notes_and_more'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='storagecell',
            options={'ordering': ['number'], 'verbose_name': 'Ячейка хранения', 'verbose_name_plural': 'Ячейки хранения'},
        ),
    ]
