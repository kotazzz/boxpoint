from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView
from django.contrib import messages
from django.urls import reverse_lazy
from django.db.models import Sum, Count, Q
from faker import Faker
import random
from datetime import timedelta

from .models import (
    Customer,
    StorageCell,
    Order,
    ReturnReason,
    OrderReturn,
    PickupSession
)


class HomeView(ListView):
    model = PickupSession
    template_name = 'core/home.html'
    context_object_name = 'active_sessions'

    def get_queryset(self):
        return PickupSession.objects.filter(is_active=True).order_by('-started_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_pending_orders'] = Order.objects.filter(reception_status='pending').count()
        return context


class CustomerSearchView(TemplateView):
    template_name = 'core/customer_search.html'


class PickupProcessView(DetailView):
    model = Customer
    template_name = 'core/pickup_process.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.get_object()
        
        # Get or create a pickup session for this customer
        session, created = PickupSession.objects.get_or_create(
            customer=customer,
            is_active=True,
            defaults={'started_at': timezone.now()}
        )
        
        # Get pending orders for this customer
        pending_orders = Order.objects.filter(
            customer=customer,
            reception_status='pending'
        ).select_related('storage_cell')
        
        # Add session to the context
        context['session'] = session
        context['pending_orders'] = pending_orders
        
        return context


class OrderInspectionView(UpdateView):
    model = Order
    template_name = 'core/order_inspection.html'
    fields = ['is_under_inspection']
    
    def form_valid(self, form):
        order = form.save(commit=False)
        order.is_under_inspection = True
        order.save()
        messages.success(self.request, f'Заказ {order.order_id} поставлен на проверку')
        return redirect('pickup_process', pk=order.customer.pk)


class OrderCancelView(UpdateView):
    model = Order
    template_name = 'core/order_cancel.html'
    fields = []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.get_object()
        
        # Get reasons based on whether the order was inspected or not
        category = 'opened' if order.is_under_inspection else 'unopened'
        context['reasons'] = ReturnReason.objects.filter(category=category)
        
        return context
    
    def post(self, request, *args, **kwargs):
        order = self.get_object()
        reason_id = request.POST.get('reason')
        notes = request.POST.get('notes', '')
        
        if reason_id:
            reason = get_object_or_404(ReturnReason, id=reason_id)
            
            # Update order status
            order.status = 'returned'
            order.save()
            
            # Create return record
            OrderReturn.objects.create(
                order=order,
                reason=reason,
                notes=notes
            )
            
            # Free up storage cell if this was the last order for this customer
            if not Order.objects.filter(customer=order.customer, status='pending').exists():
                cell = order.storage_cell
                if cell:
                    cell.is_occupied = False
                    cell.current_customer = None
                    cell.save()
            
            messages.success(request, f'Заказ {order.order_id} успешно возвращен')
            return redirect('pickup_process', pk=order.customer.pk)
        else:
            messages.error(request, 'Необходимо указать причину возврата')
            return self.get(request, *args, **kwargs)


class PickupConfirmationView(UpdateView):
    model = PickupSession
    template_name = 'core/pickup_confirmation.html'
    fields = ['include_package']
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.get_object()
        
        # Get all pending orders for this session's customer
        pending_orders = Order.objects.filter(
            customer=session.customer,
            status='pending'
        )
        
        # Calculate summary
        delivered_orders = pending_orders.filter(status='delivered')
        returned_orders = pending_orders.filter(status='returned')
        
        prepaid_total = pending_orders.filter(payment_status='prepaid', status='pending').aggregate(total=Sum('price'))['total'] or 0
        postpaid_total = pending_orders.filter(payment_status='postpaid', status='pending').aggregate(total=Sum('price'))['total'] or 0
        refund_total = returned_orders.filter(payment_status='prepaid').aggregate(total=Sum('price'))['total'] or 0
        
        context.update({
            'pending_orders': pending_orders,
            'delivered_count': delivered_orders.count(),
            'returned_count': returned_orders.count(),
            'pending_count': pending_orders.filter(status='pending').count(),
            'prepaid_total': prepaid_total,
            'postpaid_total': postpaid_total,
            'refund_total': refund_total
        })
        
        return context
    
    def form_valid(self, form):
        session = form.save(commit=False)
        
        # Mark selected orders as delivered
        order_ids = self.request.POST.getlist('deliver_orders')
        if order_ids:
            now = timezone.now()
            Order.objects.filter(id__in=order_ids).update(
                status='delivered',
                delivered_at=now
            )
        
        # Mark the session as completed
        session.is_active = False
        session.completed_at = timezone.now()
        session.save()
        
        # Free up storage cell if all orders processed
        if not Order.objects.filter(customer=session.customer, status='pending').exists():
            cells = StorageCell.objects.filter(current_customer=session.customer)
            for cell in cells:
                cell.is_occupied = False
                cell.current_customer = None
                cell.save()
        
        messages.success(self.request, 'Выдача заказов успешно завершена')
        return redirect('home')


class OrderSearchView(TemplateView):
    template_name = 'core/order_search.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        
        if order_id:
            try:
                order = Order.objects.get(order_id=order_id)
                context['order'] = order
            except Order.DoesNotExist:
                context['not_found'] = True
                
        return context


class OrderReceivingView(TemplateView):
    template_name = 'core/order_receiving.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all available cells
        available_cells = StorageCell.objects.filter(is_occupied=False)
        context['available_cells'] = available_cells
        context['available_cell_count'] = available_cells.count()
        
        # Get recent received orders
        context['recent_orders'] = Order.objects.filter(
            received_at__isnull=False
        ).order_by('-received_at')[:10]
        
        # Get pending orders that haven't been received yet
        context['pending_orders'] = Order.objects.filter(
            received_at__isnull=True,
            status='pending'
        ).select_related('customer').order_by('created_at')
        
        return context
    
    def post(self, request, *args, **kwargs):
        order_id = request.POST.get('order_id')
        customer_id = request.POST.get('customer_id')
        
        if order_id:
            try:
                order = Order.objects.get(order_id=order_id)
                
                # Check if this customer already has a cell assigned
                customer_cell = StorageCell.objects.filter(
                    current_customer=order.customer,
                    is_occupied=True
                ).first()
                
                if not customer_cell:
                    # Find first available cell
                    available_cell = StorageCell.objects.filter(is_occupied=False).first()
                    
                    if available_cell:
                        available_cell.is_occupied = True
                        available_cell.current_customer = order.customer
                        available_cell.save()
                        customer_cell = available_cell
                    else:
                        messages.error(request, 'Нет свободных ячеек')
                        return redirect('order_receiving')
                
                # Assign order to cell
                order.storage_cell = customer_cell
                order.received_at = timezone.now()
                order.save()
                
                messages.success(request, f'Заказ {order.order_id} принят в ячейку {customer_cell.number}')
            except Order.DoesNotExist:
                messages.error(request, f'Заказ с ID {order_id} не найден')
        
        return redirect('order_receiving')


class PickupCancelView(UpdateView):
    model = PickupSession
    template_name = 'core/pickup_cancel.html'
    fields = []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.get_object()
        
        # Get all orders associated with this session
        context['orders'] = Order.objects.filter(
            customer=session.customer,
            status='pending'
        )
        
        # Count orders that have been inspected
        context['inspected_count'] = context['orders'].filter(is_under_inspection=True).count()
        
        return context
    
    def post(self, request, *args, **kwargs):
        session = self.get_object()
        reason = request.POST.get('cancel_reason', '')
        
        # Reset inspection status for all orders
        Order.objects.filter(
            customer=session.customer,
            is_under_inspection=True,
            status='pending'
        ).update(is_under_inspection=False)
        
        # Mark session as inactive
        session.is_active = False
        session.completed_at = timezone.now()
        session.save()
        
        messages.success(request, f'Выдача для клиента {session.customer.name} отменена. Причина: {reason}')
        return redirect('home')


class SystemView(TemplateView):
    template_name = 'core/system.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['customer_count'] = Customer.objects.count()
        context['order_count'] = Order.objects.count()
        context['cell_count'] = StorageCell.objects.count()
        return context
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        
        if action == 'generate_customers':
            count = int(request.POST.get('count', 10))
            self._generate_customers(count)
            messages.success(request, f'Создано {count} клиентов')
            
        elif action == 'generate_orders':
            count = int(request.POST.get('count', 20))
            self._generate_orders(count)
            messages.success(request, f'Создано {count} заказов')
            
        elif action == 'generate_cells':
            count = int(request.POST.get('count', 10))
            self._generate_cells(count)
            messages.success(request, f'Создано {count} ячеек хранения')
            
        elif action == 'clear_data':
            Order.objects.all().delete()
            Customer.objects.all().delete()
            StorageCell.objects.all().delete()
            messages.success(request, 'Все данные очищены')
            
        elif action == 'seed_reasons':
            self._seed_return_reasons()
            messages.success(request, 'Причины возврата добавлены')
        
        return redirect('system')
    
    def _generate_customers(self, count):
        faker = Faker('ru_RU')
        for _ in range(count):
            Customer.objects.create(
                name=faker.name(),
                phone=faker.phone_number(),
                email=faker.email(),
            )
    
    def _generate_orders(self, count):
        if Customer.objects.count() == 0:
            self._generate_customers(5)
            
        faker = Faker('ru_RU')
        customers = list(Customer.objects.all())
        cells = list(StorageCell.objects.filter(is_occupied=False))
        
        # Generate some predefined product data
        products = [
            {'name': 'Смартфон Samsung Galaxy S23', 'sizes': ['128GB', '256GB'], 'colors': ['Черный', 'Белый', 'Синий']},
            {'name': 'Ноутбук HP Pavilion', 'sizes': ['14"', '15.6"'], 'colors': ['Серебристый', 'Черный']},
            {'name': 'Кроссовки Nike Air Max', 'sizes': ['39', '40', '41', '42', '43'], 'colors': ['Черные', 'Белые', 'Красные']},
            {'name': 'Платье летнее', 'sizes': ['XS', 'S', 'M', 'L', 'XL'], 'colors': ['Синее', 'Черное', 'Красное', 'Зеленое']},
            {'name': 'Наушники JBL Tune', 'sizes': ['One size'], 'colors': ['Черные', 'Белые', 'Красные']},
            {'name': 'Книга "Мастер и Маргарита"', 'sizes': ['Твердый переплет'], 'colors': ['Стандарт']},
            {'name': 'Часы Casio', 'sizes': ['40 мм', '44 мм'], 'colors': ['Серебристый', 'Золотой', 'Черный']},
            {'name': 'Утюг Philips', 'sizes': ['Стандарт'], 'colors': ['Голубой', 'Белый']},
            {'name': 'Фен Rowenta', 'sizes': ['1800W', '2100W'], 'colors': ['Черный', 'Розовый']},
            {'name': 'Игрушка мягкая "Медведь"', 'sizes': ['Маленький', 'Средний', 'Большой'], 'colors': ['Коричневый', 'Белый']},
        ]
        
        for _ in range(count):
            customer = random.choice(customers)
            product = random.choice(products)
            
            # Check if customer already has a cell
            customer_cell = StorageCell.objects.filter(current_customer=customer, is_occupied=True).first()
            
            # If no cell assigned and we have available cells, assign one
            if not customer_cell and cells:
                cell = random.choice(cells)
                cell.is_occupied = True
                cell.current_customer = customer
                cell.save()
                cells.remove(cell)
                customer_cell = cell
            
            # Only create order if we have a cell
            if customer_cell:
                # Create order with fields that match the Order model
                Order.objects.create(
                    name=product['name'],
                    customer=customer,
                    description=faker.text(max_nb_chars=100),
                    size=random.choice(product['sizes']),
                    color=random.choice(product['colors']),
                    price=round(random.uniform(500, 15000), 2),
                    payment_status=random.choice(['prepaid', 'postpaid']),
                    status='pending',
                    reception_status='pending',  # Add this field to match the Order model
                    barcode=faker.ean(length=13),  # Add barcode field
                    storage_cell=customer_cell,
                    received_at=timezone.now() - timedelta(days=random.randint(0, 5))
                )
    
    def _generate_cells(self, count):
        for i in range(1, count + 1):
            StorageCell.objects.create(
                number=f"A{i:03d}",
                is_occupied=False
            )
    
    def _seed_return_reasons(self):
        # Remove existing reasons
        ReturnReason.objects.all().delete()
        
        # Create unopened reasons
        ReturnReason.objects.create(name='Поврежденная упаковка', category='unopened')
        ReturnReason.objects.create(name='Отказ до получения', category='unopened')
        
        # Create opened reasons
        ReturnReason.objects.create(name='Поломка товара', category='opened')
        ReturnReason.objects.create(name='Не подошел товар', category='opened')
        ReturnReason.objects.create(name='Не хватает части товара', category='opened')
        ReturnReason.objects.create(name='Изменил решение', category='opened')
        ReturnReason.objects.create(name='Прислали другой товар', category='opened')


def get_customer(request):
    customer_id = request.GET.get('customer_id')
    
    if customer_id:
        try:
            customer = Customer.objects.get(id=customer_id)
            return redirect('pickup_process', pk=customer.id)
        except Customer.DoesNotExist:
            messages.error(request, f'Клиент с ID {customer_id} не найден')
            return redirect('customer_search')
    
    return redirect('customer_search')


def pickup_cancel(request):
    """
    View for cancelling an ongoing pickup session
    """
    if request.method == 'POST':
        session_id = request.POST.get('session_id')
        cancel_reason = request.POST.get('cancel_reason', '')
        
        try:
            pickup_session = PickupSession.objects.get(id=session_id, is_active=True)
            
            # Execute the cancel method which handles all the cleanup
            pickup_session.cancel(reason=cancel_reason)
            
            messages.success(request, f"Выдача для {pickup_session.customer.name} была успешно отменена.")
            return redirect('home')
            
        except PickupSession.DoesNotExist:
            messages.error(request, "Выбранная сессия выдачи не найдена или уже завершена.")
            return redirect('home')
    
    # Get the active pickup session
    try:
        active_session = PickupSession.objects.get(is_active=True)
        context = {
            'pickup_session': active_session,
        }
        return render(request, 'core/pickup_cancel.html', context)
    except PickupSession.DoesNotExist:
        messages.error(request, "Нет активной сессии выдачи для отмены.")
        return redirect('home')
