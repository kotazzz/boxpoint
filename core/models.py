from django.db import models
import shortuuid
from django.utils import timezone


def generate_order_id():
    """Generate a unique order ID with BP prefix"""
    return f"BP-{shortuuid.uuid()[:8].upper()}"


class Customer(models.Model):
    name = models.CharField(max_length=100, verbose_name="Имя клиента")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    email = models.EmailField(blank=True, null=True, verbose_name="Email")
    
    def __str__(self):
        return f"{self.name} ({self.phone})"
    
    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"


class StorageCell(models.Model):
    number = models.CharField(max_length=10, unique=True, verbose_name="Номер ячейки")
    is_occupied = models.BooleanField(default=False, verbose_name="Занята")
    current_customer = models.ForeignKey(
        Customer, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name="storage_cells",
        verbose_name="Текущий клиент"
    )
    
    def __str__(self):
        status = "Занята" if self.is_occupied else "Свободна"
        return f"Ячейка {self.number} ({status})"
    
    class Meta:
        verbose_name = "Ячейка хранения"
        verbose_name_plural = "Ячейки хранения"


class Order(models.Model):
    RECEPTION_STATUS_CHOICES = [
        ('pending', 'В обработке'),
        ('received', 'Принят'),
        ('cancelled', 'Отменен'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'В ожидании'),
        ('delivered', 'Доставлен'),
        ('returned', 'Возвращен'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('prepaid', 'Предоплата'),
        ('postpaid', 'Наложенный платеж'),
    ]
    
    order_id = models.CharField(max_length=50, unique=True, default=generate_order_id, verbose_name="ID заказа")
    barcode = models.CharField(max_length=100, blank=True, null=True, verbose_name="Штрихкод")
    name = models.CharField(max_length=255, verbose_name="Наименование")
    description = models.TextField(blank=True, null=True, verbose_name="Описание")
    size = models.CharField(max_length=20, blank=True, null=True, verbose_name="Размер")
    color = models.CharField(max_length=50, blank=True, null=True, verbose_name="Цвет")
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Цена")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='postpaid', verbose_name="Статус оплаты")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус заказа")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders", verbose_name="Клиент")
    storage_cell = models.ForeignKey("StorageCell", on_delete=models.SET_NULL, null=True, blank=True, related_name="orders", verbose_name="Ячейка хранения")
    is_picked_up = models.BooleanField(default=False, verbose_name="Выдан")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    reception_status = models.CharField(max_length=20, choices=RECEPTION_STATUS_CHOICES, default='pending', verbose_name="Статус приемки")
    reception_date = models.DateTimeField(null=True, blank=True, verbose_name="Дата приемки")
    received_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата получения")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата выдачи")
    is_under_inspection = models.BooleanField(default=False, verbose_name="На проверке")
    notes = models.TextField(blank=True, null=True, verbose_name="Примечания")
    # Новые поля для отложенного возврата
    marked_for_return = models.BooleanField(default=False, verbose_name="Отмечен для возврата")
    return_reason_id = models.IntegerField(blank=True, null=True, verbose_name="ID причины возврата")
    return_notes = models.TextField(blank=True, null=True, verbose_name="Примечания к возврату")

    def __str__(self):
        return f"{self.order_id} - {self.name} ({self.customer.name})"
    
    def is_available_for_pickup(self):
        """Check if this order is available for pickup"""
        return self.reception_status == 'received' and not self.is_picked_up
    
    def save(self, *args, **kwargs):
        if self.reception_status == 'received' and not self.reception_date:
            self.reception_date = timezone.now()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-created_at']


class ReturnReason(models.Model):
    INSPECTION_CATEGORY = [
        ('unopened', 'Невскрытый товар'),
        ('opened', 'Вскрытый товар'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Причина возврата")
    category = models.CharField(max_length=10, choices=INSPECTION_CATEGORY, verbose_name="Категория")
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Причина возврата"
        verbose_name_plural = "Причины возврата"


class OrderReturn(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="return_info", verbose_name="Заказ")
    reason = models.ForeignKey(ReturnReason, on_delete=models.CASCADE, verbose_name="Причина возврата")
    notes = models.TextField(blank=True, verbose_name="Примечания")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата возврата")
    
    def __str__(self):
        return f"Возврат заказа {self.order.order_id}"
    
    class Meta:
        verbose_name = "Возврат заказа"
        verbose_name_plural = "Возвраты заказов"


class PickupSession(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="pickup_sessions", verbose_name="Клиент")
    orders = models.ManyToManyField(Order, related_name="pickup_sessions", verbose_name="Заказы")
    include_package = models.BooleanField(default=False, verbose_name="Добавить пакет")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата начала")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата завершения")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    is_cancelled = models.BooleanField(default=False, verbose_name="Отменена")
    cancel_reason = models.TextField(blank=True, null=True, verbose_name="Причина отмены")
    
    def __str__(self):
        if self.is_cancelled:
            return f"Выдача {self.customer.name} (Отменена)"
        status = "Активна" if self.is_active else "Завершена"
        return f"Выдача {self.customer.name} ({status})"
    
    def has_received_orders(self):
        """Check if there are any received orders in this pickup session"""
        return self.orders.filter(reception_status='received').exists()
    
    def count_received_orders(self):
        """Count the number of received orders in this pickup session"""
        return self.orders.filter(reception_status='received').count()
    
    def cancel(self, reason=None):
        """Cancel the pickup session and reset all associated orders"""
        from django.utils import timezone
        
        self.is_cancelled = True
        self.is_active = False
        self.completed_at = timezone.now()
        
        if reason:
            self.cancel_reason = reason
        
        # Reset all orders that were marked as picked up during this session
        for order in self.orders.all():
            if order.is_picked_up:
                order.is_picked_up = False
                order.save()
        
        self.save()
        return True
    
    class Meta:
        verbose_name = "Сессия выдачи"
        verbose_name_plural = "Сессии выдачи"
