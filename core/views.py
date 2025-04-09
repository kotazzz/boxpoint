from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView, ListView, DetailView, UpdateView
from django.contrib import messages
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
        # Оптимизируем запрос, чтобы сразу получить связанные заказы
        return PickupSession.objects.filter(is_active=True).prefetch_related(
            models.Prefetch('orders', queryset=Order.objects.filter(status='pending', reception_status='received'))
        ).order_by('-started_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_pending_orders'] = Order.objects.filter(reception_status='pending').count()
        
        # Добавляем информацию о наличии постоплаты для каждой сессии
        active_sessions_with_postpaid_info = []
        for session in context['active_sessions']:
            session.has_postpaid = any(order.payment_status == 'postpaid' for order in session.orders.all())
            active_sessions_with_postpaid_info.append(session)
        
        context['active_sessions'] = active_sessions_with_postpaid_info
        return context


class CustomerSearchView(ListView):
    model = Customer
    template_name = 'core/customer_search.html'
    context_object_name = 'customers'
    paginate_by = 10

    def get_queryset(self):
        query = self.request.GET.get('q', '')
        if query:
            return Customer.objects.filter(
                Q(name__icontains=query) | Q(phone__icontains=query)
            ).order_by('name')
        return Customer.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '')
        context['search_query'] = query if query else ''
        return context


class PickupProcessView(DetailView):
    model = Customer
    template_name = 'core/pickup_process.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.get_object()
        
        # Check if the customer has any pending orders
        has_pending_orders = Order.objects.filter(
            customer=customer,
            status='pending',
            reception_status='received'
        ).exists()
        
        if not has_pending_orders:
            context['no_pending_orders'] = True
            messages.warning(self.request, f'У клиента {customer.name} нет заказов, ожидающих выдачи.')
            return context
        
        # Get or create a pickup session for this customer
        session, created = PickupSession.objects.get_or_create(
            customer=customer,
            is_active=True,
            defaults={'started_at': timezone.now()}
        )
        
        # Get pending orders for this customer
        pending_orders = Order.objects.filter(
            customer=customer,
            status='pending',
            reception_status='received'
        ).select_related('storage_cell')
        
        # Count prepaid and postpaid orders
        prepaid_count = pending_orders.filter(payment_status='prepaid').count()
        postpaid_count = pending_orders.filter(payment_status='postpaid').count()
        marked_for_return_count = pending_orders.filter(marked_for_return=True).count()
        
        # Add session to the context
        context['session'] = session
        context['pending_orders'] = pending_orders
        context['prepaid_count'] = prepaid_count
        context['postpaid_count'] = postpaid_count
        context['marked_for_return_count'] = marked_for_return_count
        
        return context
    
    def post(self, request, *args, **kwargs):
        customer = self.get_object()
        
        # Get session for this customer
        session = get_object_or_404(
            PickupSession,
            customer=customer,
            is_active=True
        )
        
        # Get selected orders
        order_ids = request.POST.getlist('deliver_orders')
        
        # Redirect to confirmation page with selected orders
        if order_ids:
            # Store selected orders in session
            request.session['selected_order_ids'] = order_ids
            return redirect('pickup_confirmation', pk=session.id)
        else:
            messages.warning(request, 'Не выбрано ни одного заказа для выдачи.')
            return redirect('pickup_process', pk=customer.id)


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
            
            # Instead of immediately setting status to 'returned',
            # mark it for return by storing the reason and notes
            # The actual return will happen during pickup confirmation
            order.marked_for_return = True
            order.return_reason_id = reason.id
            order.return_notes = notes
            order.save()
            
            messages.success(request, f'Заказ {order.order_id} отмечен для возврата. Завершите выдачу, чтобы увидеть финансовый итог.')
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
        
        # Get all orders for this session's customer
        orders = Order.objects.filter(
            customer=session.customer
        ).select_related('storage_cell')
        
        # Get selected order IDs from the form submission or URL parameters
        selected_order_ids = []
        if self.request.method == 'POST':
            selected_order_ids = self.request.POST.getlist('deliver_orders')
        elif 'order_ids' in self.request.GET:
            selected_order_ids = self.request.GET.get('order_ids').split(',')
        else:
            # Default to all pending orders if none selected
            selected_order_ids = [str(order.id) for order in orders.filter(
                status='pending',
                reception_status='received',
                marked_for_return=False  # Don't include orders marked for return
            )]
            
        # Filter out orders that are already delivered
        valid_order_ids = []
        for order_id in selected_order_ids:
            try:
                order = orders.get(id=order_id)
                if order.status == 'pending' and order.reception_status == 'received':
                    valid_order_ids.append(order_id)
            except Order.DoesNotExist:
                continue
        
        # Count orders marked for return
        marked_for_return = orders.filter(
            status='pending',
            reception_status='received', 
            marked_for_return=True
        ).count()
        
        # Calculate summaries for confirmed orders
        delivered_count = len(valid_order_ids)
        returned_count = orders.filter(status='returned').count()
        
        # Only count actually received pending orders that aren't being delivered or marked for return
        actual_pending_count = orders.filter(
            status='pending',
            reception_status='received'
        ).exclude(
            id__in=valid_order_ids
        ).exclude(
            marked_for_return=True
        ).count()
        
        pending_count = actual_pending_count
        
        # Calculate financial totals
        prepaid_total = sum(order.price for order in orders.filter(
            id__in=valid_order_ids, 
            payment_status='prepaid'
        ))
        
        postpaid_total = sum(order.price for order in orders.filter(
            id__in=valid_order_ids,
            payment_status='postpaid'
        ))
        
        refund_total = sum(order.price for order in orders.filter(
            marked_for_return=True,
            payment_status='prepaid'
        ))
        
        context.update({
            'orders': orders,
            'selected_orders': valid_order_ids,
            'delivered_count': delivered_count,
            'returned_count': returned_count + marked_for_return,  # Include marked for return in the count
            'pending_count': pending_count,
            'prepaid_total': prepaid_total,
            'postpaid_total': postpaid_total,
            'refund_total': refund_total,
            'marked_for_return': marked_for_return
        })
        
        return context
    
    def form_valid(self, form):
        session = form.save(commit=False)

        # Get all orders for this session's customer
        orders = Order.objects.filter(customer=session.customer)

        # Get selected order IDs from the form submission
        order_ids = self.request.POST.getlist('deliver_orders')

        # Mark orders as delivered or keep them pending based on selection
        now = timezone.now()
        for order in orders:
            if str(order.id) in order_ids and not order.marked_for_return:
                order.status = 'delivered'
                order.delivered_at = now
            else:
                # If the order is not selected or marked for return, keep it pending
                order.status = 'pending'
                order.delivered_at = None

            order.save()

        # Process orders marked for return
        orders_to_return = Order.objects.filter(
            customer=session.customer,
            status='pending',
            marked_for_return=True
        )

        # Create return records and update status
        for order in orders_to_return:
            order.status = 'returned'
            order.save()

            # Create return record if we have a reason
            if order.return_reason_id:
                reason = ReturnReason.objects.get(id=order.return_reason_id)
                OrderReturn.objects.create(
                    order=order,
                    reason=reason,
                    notes=order.return_notes or ''
                )

        # Mark the session as completed
        session.is_active = False
        session.completed_at = now
        session.save()

        # Free up storage cell if all orders processed
        if not Order.objects.filter(customer=session.customer, status='pending').exists():
            cells = StorageCell.objects.filter(current_customer=session.customer)
            for cell in cells:
                cell.is_occupied = False
                cell.current_customer = None
                cell.save()

        messages.success(self.request, 'Выдача заказов успешно завершена')
        return redirect('delivery_summary', order_id=session.customer.id)


class OrderSearchView(TemplateView):
    template_name = 'core/order_search.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order_id = self.request.GET.get('order_id')
        
        if (order_id):
            # Validate that the order_id is valid before trying to query
            try:
                order = Order.objects.get(order_id=order_id)
                context['order'] = order
            except Order.DoesNotExist:
                context['not_found'] = True
                messages.error(self.request, f'Заказ с ID {order_id} не найден')
                
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
        ).order_by('-received_at')[:50]
        
        # Get pending orders that haven't been received yet
        context['pending_orders'] = Order.objects.filter(
            reception_status='pending',
            status='pending'
        ).select_related('customer').order_by('created_at')
        
        return context
    
    def post(self, request, *args, **kwargs):
        order_id = request.POST.get('order_id')
        customer_id = request.POST.get('customer_id')
        
        if order_id:
            # Validate order_id format if needed
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
                
                # Assign order to cell and update reception status
                order.storage_cell = customer_cell
                order.reception_status = 'received'  # Set the reception status explicitly
                order.received_at = timezone.now()
                order.save()
                
                messages.success(request, f'Заказ {order.order_id} принят в ячейку {customer_cell.number}')
            except Order.DoesNotExist:
                messages.error(request, f'Заказ с ID {order_id} не найден')
        elif customer_id:
            # Add validation for customer_id
            if not customer_id.isdigit():
                messages.error(request, 'ID клиента должен быть числом')
                return redirect('order_receiving')
                
            try:
                customer = Customer.objects.get(id=customer_id)
                # Process customer-related operations
            except Customer.DoesNotExist:
                messages.error(request, f'Клиент с ID {customer_id} не найден')
        
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
                # Randomly decide if the order is already received or still pending for reception
                is_received = random.choice([True, False])
                received_timestamp = timezone.now() - timedelta(days=random.randint(0, 5)) if is_received else None
                
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
                    reception_status='received' if is_received else 'pending',
                    barcode=faker.ean(length=13),
                    storage_cell=customer_cell,
                    received_at=received_timestamp
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
        # Validate that customer_id is numeric before attempting to retrieve the customer
        if (customer_id.isdigit()):
            try:
                customer = Customer.objects.get(id=customer_id)
                return redirect('pickup_process', pk=customer.id)
            except Customer.DoesNotExist:
                messages.error(request, f'Клиент с ID {customer_id} не найден')
                return redirect('customer_search')
        else:
            # Search by name if input is not numeric
            customers = Customer.objects.filter(name__icontains=customer_id)
            if customers.count() == 1:
                # If exactly one match, go directly to that customer
                customer = customers.first()
                return redirect('pickup_process', pk=customer.id)
            elif customers.count() > 1:
                # If multiple matches, pass them to the template for selection
                messages.info(request, f'Найдено {customers.count()} клиента с этим именем. Пожалуйста, выберите нужного клиента.')
                return render(request, 'core/customer_search.html', {'customers': customers})
            else:
                messages.error(request, f'Клиент с именем "{customer_id}" не найден')
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


class PickupCloseView(UpdateView):
    model = PickupSession
    template_name = 'core/pickup_close.html'
    fields = []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        session = self.get_object()
        
        # Get all orders associated with this session
        context['orders'] = Order.objects.filter(
            customer=session.customer,
            status='pending'
        )
        
        return context
    
    def post(self, request, *args, **kwargs):
        session = self.get_object()
        cancel_reason = request.POST.get('cancel_reason', '')
        
        # Mark session as inactive
        session.is_active = False
        session.completed_at = timezone.now()
        
        # Store the cancel reason if provided
        if cancel_reason:
            session.notes = f"Closed with reason: {cancel_reason}"
        
        session.save()
        
        messages.success(request, f'Выдача для клиента {session.customer.name} закрыта.')
        return redirect('home')


def delivery_summary(request, order_id):
    """
    Подробный итог выдачи заказа с финансовой информацией и статистикой по товарам
    """
    # Вместо поиска заказа, получаем клиента для отображения статистики
    customer = get_object_or_404(Customer, id=order_id)
    
    # Получаем заказы этого клиента
    orders = Order.objects.filter(customer=customer)
    
    # Счетчики для товаров
    total_delivered = orders.filter(status='delivered').count()
    total_returned = orders.filter(status='returned').count()
    total_retained = orders.filter(status='pending').count()
    
    # Финансовые расчеты
    delivered_total = sum(order.price for order in orders.filter(status='delivered'))
    returned_total = sum(order.price for order in orders.filter(status='returned'))
    retained_total = sum(order.price for order in orders.filter(status='pending'))
    
    # Суммы по предоплаченным товарам
    prepaid_total = sum(order.price for order in orders.filter(status='delivered', payment_status='prepaid'))
    returned_prepaid_total = sum(order.price for order in orders.filter(status='returned', payment_status='prepaid'))
    retained_prepaid_total = sum(order.price for order in orders.filter(status='pending', payment_status='prepaid'))
    
    # Расчет сумм к оплате/возврату
    to_pay_total = delivered_total - prepaid_total
    refund_total = returned_prepaid_total
    
    # Итоговый расчет
    total_due = to_pay_total - refund_total
    
    context = {
        'customer': customer,
        'orders': orders,
        'total_delivered': total_delivered,
        'total_returned': total_returned,
        'total_retained': total_retained,
        'delivered_total': delivered_total,
        'returned_total': returned_total,
        'retained_total': retained_total,
        'prepaid_total': prepaid_total,
        'returned_prepaid_total': returned_prepaid_total,
        'retained_prepaid_total': retained_prepaid_total,
        'to_pay_total': to_pay_total,
        'refund_total': refund_total,
        'total_due': total_due,
    }
    
    return render(request, 'core/delivery_summary.html', context)


class OrderReturnCancelView(UpdateView):
    model = Order
    template_name = 'core/order_return_cancel.html'
    fields = []
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.get_object()
        return context
    
    def post(self, request, *args, **kwargs):
        order = self.get_object()
        
        # Снимаем пометку возврата
        order.marked_for_return = False
        order.return_reason_id = None
        order.return_notes = None
        order.save()
        
        messages.success(request, f'Возврат заказа {order.order_id} отменен')
        return redirect('pickup_process', pk=order.customer.pk)
        
    def get(self, request, *args, **kwargs):
        order = self.get_object()
        
        # Если товар не отмечен для возврата, перенаправляем обратно
        if not order.marked_for_return:
            messages.warning(request, f'Заказ {order.order_id} не отмечен для возврата')
            return redirect('pickup_process', pk=order.customer.pk)
            
        return super().get(request, *args, **kwargs)


class StorageVisualizationView(TemplateView):
    template_name = 'core/storage/visualization.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Поиск по номеру ячейки
        search_query = self.request.GET.get('search', '')
        if search_query:
            cells = StorageCell.objects.filter(number__icontains=search_query).order_by('number')
        else:
            cells = StorageCell.objects.all().order_by('number')
            
        # Добавляем метрики
        context['cells'] = cells
        context['total_cells_count'] = cells.count()
        context['occupied_cells_count'] = cells.filter(is_occupied=True).count()
        context['free_cells_count'] = cells.filter(is_occupied=False).count()
        context['search_query'] = search_query
        
        # Предзагружаем связанные заказы для снижения количества запросов к БД
        # Фильтруем только заказы со статусом 'pending' и reception_status='received'
        cells = cells.prefetch_related(
            models.Prefetch('orders', queryset=Order.objects.filter(
                status='pending', 
                reception_status='received'
            ))
        )
        
        return context


class CustomerDetailView(DetailView):
    model = Customer
    template_name = 'core/customers/customer_detail.html'
    context_object_name = 'customer'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.get_object()
        
        # Получаем заказы клиента по разным статусам
        orders = Order.objects.filter(customer=customer)
        
        # Доступные к выдаче заказы (получены на склад)
        context['available_orders'] = orders.filter(
            status='pending',
            reception_status='received'
        ).select_related('storage_cell').order_by('-received_at')
        
        # Заказы в пути (еще не получены на склад)
        context['in_transit_orders'] = orders.filter(
            status='pending',
            reception_status='pending'
        ).order_by('-created_at')
        
        # История выданных заказов
        context['delivered_orders'] = orders.filter(
            status='delivered'
        ).order_by('-delivered_at')
        
        # Возвращенные заказы
        context['returned_orders'] = orders.filter(
            status='returned'
        ).order_by('-updated_at')
        
        # Статистика по заказам
        context['total_orders'] = orders.count()
        context['available_count'] = context['available_orders'].count()
        context['in_transit_count'] = context['in_transit_orders'].count()
        context['delivered_count'] = context['delivered_orders'].count()
        context['returned_count'] = context['returned_orders'].count()
        
        # Финансовая статистика
        context['total_pending_amount'] = sum(order.price for order in context['available_orders'])
        context['total_in_transit_amount'] = sum(order.price for order in context['in_transit_orders'])
        
        # Сессии выдачи для этого клиента
        context['pickup_sessions'] = PickupSession.objects.filter(
            customer=customer
        ).order_by('-started_at')[:10]  # Показываем только последние 10
        
        return context
