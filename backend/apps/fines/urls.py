from django.urls import path

from apps.fines.views import FineDetailView, FineListView, PaymentDetailView, PaymentListView

app_name = "fines"

urlpatterns = [
    path("fines/", FineListView.as_view(), name="fine-list"),
    path("fines/<int:fine_id>/", FineDetailView.as_view(), name="fine-detail"),
    path("payments/", PaymentListView.as_view(), name="payment-list"),
    path("payments/<int:payment_id>/", PaymentDetailView.as_view(), name="payment-detail"),
]
