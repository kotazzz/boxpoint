#!/usr/bin/env python
"""
Box Point setup script - initializes database and creates necessary data
"""
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management import call_command
from core.models import ReturnReason, StorageCell

def main():
    print("Box Point - Настройка системы")
    print("-" * 50)
    
    # Run migrations
    print("Применение миграций...")
    call_command('makemigrations')
    call_command('migrate')
    
    # Create superuser if needed
    from django.contrib.auth.models import User
    if not User.objects.filter(is_superuser=True).exists():
        print("Создание суперпользователя...")
        User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
        )
        print("Суперпользователь создан: admin / admin123")
    
    # Create return reasons if needed
    if ReturnReason.objects.count() == 0:
        print("Создание причин возврата...")
        # Unopened reasons
        ReturnReason.objects.create(name='Поврежденная упаковка', category='unopened')
        ReturnReason.objects.create(name='Отказ до получения', category='unopened')
        
        # Opened reasons
        ReturnReason.objects.create(name='Поломка товара', category='opened')
        ReturnReason.objects.create(name='Не подошел товар', category='opened')
        ReturnReason.objects.create(name='Не хватает части товара', category='opened')
        ReturnReason.objects.create(name='Изменил решение', category='opened')
        ReturnReason.objects.create(name='Прислали другой товар', category='opened')
        print("Причины возврата созданы")
    
    # Create storage cells if needed
    if StorageCell.objects.count() == 0:
        print("Создание ячеек хранения...")
        for i in range(1, 11):  # Create 10 cells by default
            StorageCell.objects.create(number=f"A{i:03d}")
        print("Ячейки хранения созданы")
    
    print("-" * 50)
    print("Настройка завершена!")
    print("Запустите сервер командой: python manage.py runserver")
    print("Админ-панель: http://127.0.0.1:8000/admin/ (admin / admin123)")
    print("Box Point: http://127.0.0.1:8000/")

if __name__ == "__main__":
    main()