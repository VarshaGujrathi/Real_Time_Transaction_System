from django.db import models
from django.contrib.auth.models import User

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    mobile_number = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return f"{self.user.username} - {self.mobile_number}"


class Wallet(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="wallet"
    )
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} Wallet | ₹{self.balance}"


class Transaction(models.Model):
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="transactions_sent",
        null=True,
        blank=True
    )
    receiver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="transactions_received",
        null=True,
        blank=True
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    transaction_type = models.CharField(
        max_length=20,
        choices=[
            ("ADD_MONEY", "Add Money"),
            ("TRANSFER", "Transfer"),
        ]
    )

    status = models.CharField(
        max_length=10,
        choices=[
            ("SUCCESS", "SUCCESS"),
            ("FAILED", "FAILED"),
        ]
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type} | ₹{self.amount} | {self.status}"
