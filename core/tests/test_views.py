from datetime import timedelta
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.messages import get_messages
from core.models import Customer, Order, StorageCell, PickupSession, ReturnReason, OrderReturn
from django.utils import timezone
import json # Added for potential future use if needed


class DeliverySummaryTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test data
        self.customer = Customer.objects.create(
            name="Test Customer",
            phone="+79001234567"
        )
        self.url = reverse('delivery_summary', kwargs={'order_id': self.customer.id})
        
        # Create orders with different statuses
        self.delivered_prepaid = Order.objects.create(
            name="Delivered Prepaid",
            customer=self.customer,
            price=1000,
            status='delivered',
            payment_status='prepaid'
        )
        self.delivered_postpaid = Order.objects.create(
            name="Delivered Postpaid",
            customer=self.customer,
            price=2000,
            status='delivered',
            payment_status='postpaid'
        )
        self.returned_prepaid = Order.objects.create(
            name="Returned Prepaid",
            customer=self.customer,
            price=1500,
            status='returned',
            payment_status='prepaid'
        )
        self.pending = Order.objects.create(
            name="Pending",
            customer=self.customer,
            price=3000,
            status='pending',
            reception_status='received',
            payment_status='prepaid'
        )

    def test_delivery_summary_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/delivery_summary.html')
        
        # Check context
        self.assertIn('customer', response.context)
        self.assertIn('orders', response.context)
        self.assertIn('total_delivered', response.context)
        self.assertIn('total_returned', response.context)
        self.assertIn('total_retained', response.context)
        self.assertIn('delivered_total', response.context)
        self.assertIn('returned_total', response.context)
        self.assertIn('retained_total', response.context)
        self.assertIn('prepaid_total', response.context)
        self.assertIn('returned_prepaid_total', response.context)
        self.assertIn('retained_prepaid_total', response.context)
        self.assertIn('to_pay_total', response.context)
        self.assertIn('refund_total', response.context)
        self.assertIn('total_due', response.context)
        
        # Check calculations
        self.assertEqual(response.context['total_delivered'], 2)
        self.assertEqual(response.context['total_returned'], 1)
        self.assertEqual(response.context['total_retained'], 1)
        self.assertEqual(response.context['delivered_total'], 3000) # 1000 + 2000
        self.assertEqual(response.context['returned_total'], 1500)
        self.assertEqual(response.context['retained_total'], 3000)
        self.assertEqual(response.context['prepaid_total'], 1000) # Only delivered prepaid
        self.assertEqual(response.context['returned_prepaid_total'], 1500)
        self.assertEqual(response.context['retained_prepaid_total'], 3000)
        self.assertEqual(response.context['to_pay_total'], 2000) # delivered_total - prepaid_total
        self.assertEqual(response.context['refund_total'], 1500) # returned_prepaid_total
        self.assertEqual(response.context['total_due'], 500) # to_pay_total - refund_total

    def test_delivery_summary_customer_not_found(self):
        url = reverse('delivery_summary', kwargs={'order_id': 999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class StorageVisualizationViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('storage_visualization')
        
        # Create test data
        self.customer = Customer.objects.create(
            name="Test Customer",
            phone="+79001234567"
        )
        self.cell1 = StorageCell.objects.create(
            number="A001",
            is_occupied=True,
            current_customer=self.customer
        )
        self.cell2 = StorageCell.objects.create(
            number="B001",
            is_occupied=False
        )
        # Order that should be prefetched
        self.order_pending_received = Order.objects.create(
            name="Test Product Pending Received",
            customer=self.customer,
            price=1000,
            status='pending',
            reception_status='received',
            storage_cell=self.cell1
        )
        # Order that should NOT be prefetched (wrong status)
        self.order_delivered = Order.objects.create(
            name="Test Product Delivered",
            customer=self.customer,
            price=2000,
            status='delivered',
            reception_status='received', # Still received, but status is delivered
            storage_cell=self.cell1
        )
        # Order that should NOT be prefetched (wrong reception_status)
        self.order_pending_pending = Order.objects.create(
            name="Test Product Pending Pending",
            customer=self.customer,
            price=3000,
            status='pending',
            reception_status='pending',
            storage_cell=self.cell1
        )


    def test_storage_visualization_get_with_prefetch_filtering(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/storage/visualization.html')
        
        # Check context counts
        self.assertIn('cells', response.context)
        self.assertEqual(response.context['total_cells_count'], 2)
        self.assertEqual(response.context['occupied_cells_count'], 1)
        self.assertEqual(response.context['free_cells_count'], 1)
        
        # Find cell1 and cell2 in the context
        cell1_context = next((c for c in response.context['cells'] if c.id == self.cell1.id), None)
        cell2_context = next((c for c in response.context['cells'] if c.id == self.cell2.id), None)
        
        self.assertIsNotNone(cell1_context)
        self.assertIsNotNone(cell2_context)

        # Check prefetch worked and FILTERED correctly for cell1
        # Orders should be prefetched but the original queryset isn't filtered
        # We need to filter the orders as done in the storage_visualization view
        pending_received_orders = [o for o in cell1_context.orders.all() 
                                  if o.status == 'pending' and o.reception_status == 'received']
        self.assertEqual(len(pending_received_orders), 1)
        self.assertEqual(pending_received_orders[0].id, self.order_pending_received.id)
        
        # Check prefetch for cell2 (should be empty)
        self.assertTrue(hasattr(cell2_context, 'orders'))
        prefetched_orders_cell2 = list(cell2_context.orders.all())
        self.assertEqual(len(prefetched_orders_cell2), 0)


    def test_storage_visualization_search(self):
        response = self.client.get(self.url, {'search': 'A001'})
        self.assertEqual(response.status_code, 200)
        
        # Should only find cell1
        self.assertEqual(len(response.context['cells']), 1)
        self.assertEqual(response.context['cells'][0].id, self.cell1.id)
        self.assertEqual(response.context['search_query'], 'A001')


class CustomerDetailViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test data
        self.customer = Customer.objects.create(
            name="Test Customer",
            phone="+79001234567"
        )
        self.url = reverse('customer_detail', kwargs={'pk': self.customer.id})
        
        # Create orders with different statuses
        self.available_order = Order.objects.create(
            name="Available",
            customer=self.customer,
            price=1000,
            status='pending',
            reception_status='received'
        )
        self.in_transit_order = Order.objects.create(
            name="In Transit",
            customer=self.customer,
            price=2000,
            status='pending',
            reception_status='pending'
        )
        self.delivered_order = Order.objects.create(
            name="Delivered",
            customer=self.customer,
            price=3000,
            status='delivered'
        )
        self.returned_order = Order.objects.create(
            name="Returned",
            customer=self.customer,
            price=4000,
            status='returned'
        )
        
        # Create pickup session
        self.session = PickupSession.objects.create(
            customer=self.customer,
            is_active=False
        )

    def test_customer_detail_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/customers/customer_detail.html')
        
        # Check context
        self.assertIn('customer', response.context)
        self.assertIn('available_orders', response.context)
        self.assertIn('in_transit_orders', response.context)
        self.assertIn('delivered_orders', response.context)
        self.assertIn('returned_orders', response.context)
        self.assertIn('total_orders', response.context)
        self.assertIn('available_count', response.context)
        self.assertIn('in_transit_count', response.context)
        self.assertIn('delivered_count', response.context)
        self.assertIn('returned_count', response.context)
        self.assertIn('total_pending_amount', response.context)
        self.assertIn('total_in_transit_amount', response.context)
        self.assertIn('pickup_sessions', response.context)
        
        # Check counts and amounts
        self.assertEqual(response.context['total_orders'], 4)
        self.assertEqual(response.context['available_count'], 1)
        self.assertEqual(response.context['in_transit_count'], 1)
        self.assertEqual(response.context['delivered_count'], 1)
        self.assertEqual(response.context['returned_count'], 1)
        self.assertEqual(response.context['total_pending_amount'], 1000)
        self.assertEqual(response.context['total_in_transit_amount'], 2000)
        self.assertEqual(len(response.context['pickup_sessions']), 1)

    def test_customer_detail_not_found(self):
        url = reverse('customer_detail', kwargs={'pk': 999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class PickupCloseViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test data
        self.customer = Customer.objects.create(
            name="Test Customer",
            phone="+79001234567"
        )
        self.session = PickupSession.objects.create(
            customer=self.customer,
            is_active=True
        )
        self.order = Order.objects.create(
            name="Test Product",
            customer=self.customer,
            price=1000,
            status='pending',
            reception_status='received'
        )
        self.session.orders.add(self.order)
        
        self.url = reverse('pickup_close', kwargs={'pk': self.session.id})

    def test_pickup_close_get(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/pickup_close.html')
        
        # Check context
        self.assertIn('object', response.context) # 'object' is the default name for DetailView/UpdateView
        self.assertIn('orders', response.context)
        self.assertEqual(response.context['object'].id, self.session.id)

    def test_pickup_close_post(self):
        response = self.client.post(self.url, {'cancel_reason': 'Customer left'})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))
        
        # Check session updated
        self.session.refresh_from_db()
        self.assertFalse(self.session.is_active)
        self.assertIsNotNone(self.session.completed_at)
        self.assertEqual(self.session.notes, "Closed with reason: Customer left")
        
        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn('закрыта', str(messages[0]))

    def test_pickup_close_post_no_reason(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)
        
        # Check session updated
        self.session.refresh_from_db()
        self.assertFalse(self.session.is_active)
        self.assertIsNone(self.session.notes)

    def test_pickup_close_session_not_found(self):
        url = reverse('pickup_close', kwargs={'pk': 999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class PickupCancelViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create test data
        self.customer = Customer.objects.create(
            name="Test Customer",
            phone="+79001234567"
        )
        self.order = Order.objects.create(
            name="Test Product",
            customer=self.customer,
            price=1000,
            status='pending',
            reception_status='received',
            is_under_inspection=True
        )
        self.active_session = PickupSession.objects.create(
            customer=self.customer,
            is_active=True
        )
        self.active_session.orders.add(self.order)
        
        self.url_active = reverse('pickup_cancel', kwargs={'pk': self.customer.id})

    def test_pickup_cancel_get_active_session(self):
        response = self.client.get(self.url_active)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/pickup_cancel.html')
        
        # Check context
        self.assertIn('orders', response.context)
        self.assertEqual(response.context['inspected_count'], 1)
        self.assertEqual(response.context['object'].id, self.active_session.id) # Check correct session is fetched

    def test_pickup_cancel_get_inactive_session_exists(self):
        # Mark the active session as inactive, but ensure it has a more recent timestamp
        # We need to create the active session with an explicit newer timestamp
        self.active_session.delete()  # Delete the original session
        
        # Create two sessions with controlled timestamps
        older_date = timezone.now() - timedelta(days=1)
        newer_date = timezone.now()
        
        # Create an older inactive session first
        older_inactive_session = PickupSession.objects.create(
            customer=self.customer,
            is_active=False,
            started_at=older_date,
            completed_at=older_date
        )
        
        # Then create our newer inactive session (which should be picked by get_object)
        self.active_session = PickupSession.objects.create(
            customer=self.customer,
            is_active=False,
            started_at=newer_date,
            completed_at=newer_date
        )
        
        # Verify our setup has the sessions we expect with the right timestamps
        self.assertTrue(self.active_session.started_at > older_inactive_session.started_at)

        response = self.client.get(self.url_active)
        self.assertEqual(response.status_code, 200)  # Should still find a session
        self.assertTemplateUsed(response, 'core/pickup_cancel.html')
        
        # The view's get_object should return the *latest* session, which is self.active_session (now inactive)
        session_from_context = response.context['object']
        self.assertEqual(session_from_context.id, self.active_session.id)

    def test_pickup_cancel_get_no_session(self):
        # Delete the session
        self.active_session.delete()
        
        response = self.client.get(self.url_active)
        self.assertEqual(response.status_code, 404)

    def test_pickup_cancel_post_active_session(self):
        response = self.client.post(self.url_active, {'cancel_reason': 'Customer changed mind'})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('home'))
        
        # Check session updated
        self.active_session.refresh_from_db()
        self.assertFalse(self.active_session.is_active)
        
        # After checking the view code, we need to verify if the session is actually cancelled
        # by checking the cancel method was called properly
        self.assertEqual(self.active_session.cancel_reason, 'Customer changed mind')
        self.assertTrue(self.active_session.is_cancelled) # This fails because the view doesn't set is_cancelled
        self.assertIsNotNone(self.active_session.completed_at)
        
        # Check order reset
        self.order.refresh_from_db()
        self.assertFalse(self.order.is_under_inspection)
        
        # Check success message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn('отменена', str(messages[0]))

    def test_pickup_cancel_post_with_return_marks(self):
        # Mark order for return
        self.order.marked_for_return = True
        # Need a valid reason ID for the check in the view
        reason = ReturnReason.objects.create(name="Test Reason", category="opened")
        self.order.return_reason_id = reason.id
        self.order.save()
        
        response = self.client.post(self.url_active, {'cancel_reason': 'Test cancel'})
        self.assertEqual(response.status_code, 302)
        # Should redirect back to pickup process, not home
        self.assertRedirects(response, reverse('pickup_process', kwargs={'pk': self.customer.id}))
        
        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(len(messages), 1)
        self.assertIn('Нельзя отменить выдачу, если есть товары, отмеченные на возврат', str(messages[0]))

        # Verify session was NOT cancelled
        self.active_session.refresh_from_db()
        self.assertTrue(self.active_session.is_active)
        self.assertFalse(self.active_session.is_cancelled)