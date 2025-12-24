from django.urls import path
from .views import (
    auth_view,
    dashboard_view,
    logout_view,
    add_money_view,
    transfer_money_view,
    pay_mobile_view,
    transaction_history_view,
)

urlpatterns = [
    path("", auth_view, name="auth"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("logout/", logout_view, name="logout"),
    path("add-money/", add_money_view, name="add_money"),
    path("transfer/", transfer_money_view, name="transfer_money"),
    path("pay-mobile/", pay_mobile_view, name="pay_mobile"),
    path("transactions/", transaction_history_view, name="transactions"),
]
