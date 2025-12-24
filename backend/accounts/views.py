from decimal import Decimal

from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q, Sum
from django.utils.timezone import now

from accounts.models import UserProfile, Wallet, Transaction


# Maximum amount a user can transfer per day
DAILY_TRANSFER_LIMIT = 100000  # ₹1,00,000


def get_today_transfer_total(user):
    """
    Returns the total amount successfully transferred by a user today.
    Used to enforce daily transaction limits.
    """
    today = now().date()

    total = Transaction.objects.filter(
        sender=user,
        transaction_type="TRANSFER",
        status="SUCCESS",
        created_at__date=today
    ).aggregate(total=Sum("amount"))["total"]

    return total or 0


def auth_view(request):
    """
    Handles both user login and registration.
    """

    if request.method == "POST" and "login" in request.POST:
        user = authenticate(
            request,
            username=request.POST.get("username"),
            password=request.POST.get("password"),
        )

        if user:
            login(request, user)
            return redirect("/dashboard/")

        return render(request, "accounts/auth.html", {
            "error": "Invalid username or password"
        })

    if request.method == "POST" and "register" in request.POST:
        username = request.POST.get("username")
        password = request.POST.get("password")
        mobile = request.POST.get("mobile")

        if not mobile:
            return render(request, "accounts/auth.html", {
                "error": "Mobile number is required"
            })

        if User.objects.filter(username=username).exists():
            return render(request, "accounts/auth.html", {
                "error": "Username already exists"
            })

        if UserProfile.objects.filter(mobile_number=mobile).exists():
            return render(request, "accounts/auth.html", {
                "error": "Mobile number already registered"
            })

        # Store mobile number in email field for simplicity
        user = User.objects.create_user(
            username=username,
            password=password,
            email=mobile
        )

        # Create associated profile and wallet
        UserProfile.objects.create(user=user, mobile_number=mobile)
        Wallet.objects.get_or_create(user=user)

        return render(request, "accounts/auth.html", {
            "success": "Account created successfully. Please login."
        })

    return render(request, "accounts/auth.html")


@login_required
def dashboard_view(request):
    """
    Displays wallet balance and daily transfer usage.
    """
    return render(request, "accounts/dashboard.html", {
        "wallet": request.user.wallet,
        "daily_limit": DAILY_TRANSFER_LIMIT,
        "spent_today": get_today_transfer_total(request.user)
    })


def logout_view(request):
    """
    Logs the user out and redirects to authentication page.
    """
    logout(request)
    return redirect("/")


@login_required
def add_money_view(request):
    """
    Allows users to add funds to their wallet.
    """
    wallet = request.user.wallet

    if request.method == "POST":
        try:
            amount = Decimal(request.POST.get("amount"))
        except:
            return render(request, "accounts/add_money.html", {
                "error": "Invalid amount"
            })

        if amount <= 0:
            return render(request, "accounts/add_money.html", {
                "error": "Amount must be greater than 0"
            })

        wallet.balance += amount
        wallet.save()

        # Record wallet top-up as a transaction
        Transaction.objects.create(
            sender=request.user,
            amount=amount,
            transaction_type="ADD_MONEY",
            status="SUCCESS"
        )

        return redirect("/transactions/")

    return render(request, "accounts/add_money.html")


@login_required
def transfer_money_view(request):
    """
    Transfers money to another user using user ID.
    Ensures atomic debit and credit.
    """
    sender = request.user
    sender_wallet = sender.wallet

    if request.method == "POST":
        try:
            receiver = User.objects.get(id=request.POST.get("receiver_id"))
            amount = Decimal(request.POST.get("amount"))
        except:
            return render(request, "accounts/transfer_money.html", {
                "error": "Invalid input"
            })

        if amount <= 0:
            return render(request, "accounts/transfer_money.html", {
                "error": "Amount must be greater than zero"
            })

        # Enforce daily transaction limit
        if get_today_transfer_total(sender) + amount > DAILY_TRANSFER_LIMIT:
            return render(request, "accounts/transfer_money.html", {
                "error": "Daily transfer limit exceeded"
            })

        if sender_wallet.balance < amount:
            return render(request, "accounts/transfer_money.html", {
                "error": "Insufficient balance"
            })

        # Ensure debit and credit happen atomically
        with transaction.atomic():
            sender_wallet.balance -= amount
            receiver.wallet.balance += amount

            sender_wallet.save()
            receiver.wallet.save()

            Transaction.objects.create(
                sender=sender,
                receiver=receiver,
                amount=amount,
                transaction_type="TRANSFER",
                status="SUCCESS"
            )

        return redirect("/transactions/")

    return render(request, "accounts/transfer_money.html")


@login_required
def pay_mobile_view(request):
    """
    Transfers money to a user identified by registered mobile number.
    """
    sender = request.user
    sender_wallet = sender.wallet

    if request.method == "POST":
        mobile = request.POST.get("mobile_number")

        try:
            amount = Decimal(request.POST.get("amount"))
        except:
            return render(request, "accounts/pay_mobile.html", {
                "error": "Invalid amount"
            })

        if amount <= 0:
            return render(request, "accounts/pay_mobile.html", {
                "error": "Amount must be greater than zero"
            })

        try:
            receiver = UserProfile.objects.get(
                mobile_number=mobile
            ).user
        except UserProfile.DoesNotExist:
            return render(request, "accounts/pay_mobile.html", {
                "error": "Mobile number not registered"
            })

        if sender == receiver:
            return render(request, "accounts/pay_mobile.html", {
                "error": "Cannot send money to yourself"
            })

        # Enforce daily transaction limit
        if get_today_transfer_total(sender) + amount > DAILY_TRANSFER_LIMIT:
            return render(request, "accounts/pay_mobile.html", {
                "error": "Daily transfer limit exceeded"
            })

        if sender_wallet.balance < amount:
            return render(request, "accounts/pay_mobile.html", {
                "error": "Insufficient balance"
            })

        # Atomic fund transfer
        with transaction.atomic():
            sender_wallet.balance -= amount
            receiver.wallet.balance += amount

            sender_wallet.save()
            receiver.wallet.save()

            Transaction.objects.create(
                sender=sender,
                receiver=receiver,
                amount=amount,
                transaction_type="TRANSFER",
                status="SUCCESS"
            )

        return redirect("/transactions/")

    return render(request, "accounts/pay_mobile.html")


@login_required
def transaction_history_view(request):
    """
    Displays all transactions where the user is sender or receiver.
    Acts as an immutable audit log.
    """
    transactions = Transaction.objects.filter(
        Q(sender=request.user) | Q(receiver=request.user)
    ).order_by("-created_at")

    return render(request, "accounts/transaction_history.html", {
        "transactions": transactions,
        "current_user": request.user
    })
