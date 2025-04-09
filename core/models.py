from django.db import models
import shortuuid


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
    STATUS_CHOICES = [
        ('pending', 'Ожидает получения'),
        ('delivered', 'Выдан'),
        ('returned', 'Возвращен'),
        ('cancelled', 'Аннулирован'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('prepaid', 'Предоплачен'),
        ('postpaid', 'Постоплата'),
    ]
    
    order_id = models.CharField(max_length=20, unique=True, default=generate_order_id, verbose_name="ID заказа")
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders", verbose_name="Клиент")
    name = models.CharField(max_length=200, verbose_name="Наименование товара")
    description = models.TextField(blank=True, verbose_name="Описание")
    size = models.CharField(max_length=50, blank=True, verbose_name="Размер")
    color = models.CharField(max_length=50, blank=True, verbose_name="Цвет")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Стоимость")
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='prepaid', verbose_name="Статус оплаты")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending', verbose_name="Статус заказа")
    storage_cell = models.ForeignKey(StorageCell, on_delete=models.SET_NULL, null=True, related_name="orders", verbose_name="Ячейка хранения")
    is_under_inspection = models.BooleanField(default=False, verbose_name="На проверке")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    received_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата приемки")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Дата выдачи")
    
    def __str__(self):
        return f"Заказ {self.order_id}: {self.name}"
    
    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"


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
    
    def __str__(self):
        status = "Активна" if self.is_active else "Завершена"
        return f"Выдача {self.customer.name} ({status})"
    
    class Meta:
        verbose_name = "Сессия выдачи"
        verbose_name_plural = "Сессии выдачи"
