import stripe

from django.conf import settings


from rest_framework.decorators import api_view
from rest_framework.response import Response

stripe.api_key = settings.STRIPE_API_KEY


@api_view(['POST'])
def webhook_handler(request):
    # You can use webhooks to receive information about asynchronous payment events.
    # For more about our webhook events check out https://stripe.com/docs/webhooks.
    webhook_secret = settings.STRIPE_WEBHOOK_SECRET

    if webhook_secret:
        # Retrieve the event by verifying the signature using the raw body and secret if webhook signing is configured.
        signature = request.headers.get('stripe-signature')
        try:
            event = stripe.Webhook.construct_event(
                payload=request.body,
                sig_header=signature,
                secret=webhook_secret
            )
            data = event['data']
        except Exception as e:
            return Response(str(e) + " * " + webhook_secret)
        # Get the type of webhook event sent - used to check the status of PaymentIntents.
        event_type = event['type']
    else:
        data = request.data['data']
        event_type = request.data['type']

    # data_object = data['object']

    if event_type == 'customer.subscription.created':
        # Used to provision services after the trial has ended.
        # The status of the invoice will show up as paid. Store the status in your
        # database to reference when a user accesses your service to avoid hitting rate
        # limits.
        print(data)

    if event_type == 'invoice.payment_failed':
        # If the payment fails or the customer does not have a valid payment method,
        # an invoice.payment_failed event is sent, the subscription becomes past_due.
        # Use this webhook to notify your user that their payment has
        # failed and to retrieve new card details.
        print(data)

    if event_type == 'customer.subscription.deleted':
        # handle subscription cancelled automatically based
        # upon your subscription settings. Or if the user cancels it.
        print(data)

    return Response({'status': 'success', 'data': data})


@api_view(['POST'])
def create_subscription_view(request):
    data = request.data
    try:
        # Attach the payment method to the customer
        stripe.PaymentMethod.attach(
            data['paymentMethodId'],
            customer=data['customerId'],
        )
        # Set the default payment method on the customer
        stripe.Customer.modify(
            data['customerId'],
            invoice_settings={
                'default_payment_method': data['paymentMethodId'],
            },
        )
        # Create the subscription
        subscription = stripe.Subscription.create(
            customer=data['customerId'],
            items=[
                {
                    'price': data['priceId'],
                }
            ],
            expand=['latest_invoice.payment_intent'],
        )
        return Response(subscription)
    except Exception as e:
        return Response({'error': {'message': str(e)}})