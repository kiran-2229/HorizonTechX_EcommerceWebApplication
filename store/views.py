from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CheckoutForm, RegisterForm
from .models import Order, OrderItem, Product


def home(request):
    products = Product.objects.all().order_by("-created_at")
    return render(request, "store/home.html", {"products": products})


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, "store/product_detail.html", {"product": product})


def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful!")
            return redirect("home")
    else:
        form = RegisterForm()

    return render(request, "registration/register.html", {"form": form})


def get_cart_products(request):
    cart = request.session.get("cart", {})
    items = []
    total = Decimal("0.00")

    for product_id, quantity in cart.items():
        product = Product.objects.filter(pk=product_id).first()
        if product:
            quantity = int(quantity)
            subtotal = product.price * quantity
            items.append({
                "product": product,
                "quantity": quantity,
                "subtotal": subtotal,
            })
            total += subtotal

    return items, total


def cart(request):
    items, total = get_cart_products(request)
    return render(request, "store/cart.html", {"items": items, "total": total})


def add_to_cart(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if product.stock < 1:
        messages.error(request, "This product is out of stock.")
        return redirect("product_detail", pk=pk)

    cart_data = request.session.get("cart", {})
    key = str(pk)
    current_qty = int(cart_data.get(key, 0))

    if current_qty < product.stock:
        cart_data[key] = current_qty + 1
        request.session["cart"] = cart_data
        messages.success(request, f"{product.name} added to cart.")
    else:
        messages.warning(request, "Maximum available stock already in cart.")

    return redirect("cart")


def remove_from_cart(request, pk):
    cart_data = request.session.get("cart", {})
    cart_data.pop(str(pk), None)
    request.session["cart"] = cart_data
    return redirect("cart")


@login_required
def checkout(request):
    items, total = get_cart_products(request)

    if not items:
        messages.warning(request, "Your cart is empty.")
        return redirect("home")

    if request.method == "POST":
        form = CheckoutForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                for item in items:
                    product = Product.objects.select_for_update().get(pk=item["product"].pk)
                    if item["quantity"] > product.stock:
                        messages.error(
                            request,
                            f"Not enough stock for {product.name}. Please update your cart."
                        )
                        return redirect("cart")

                order = Order.objects.create(
                    user=request.user,
                    full_name=form.cleaned_data["full_name"],
                    email=form.cleaned_data["email"],
                    phone=form.cleaned_data["phone"],
                    address=form.cleaned_data["address"],
                    total_amount=total,
                )

                for item in items:
                    product = Product.objects.select_for_update().get(pk=item["product"].pk)
                    qty = item["quantity"]
                    OrderItem.objects.create(
                        order=order,
                        product=product,
                        product_name=product.name,
                        price=product.price,
                        quantity=qty,
                    )
                    product.stock -= qty
                    product.save(update_fields=["stock"])

            request.session["cart"] = {}
            messages.success(request, f"Order #{order.id} placed successfully!")
            return redirect("order_detail", order_id=order.id)
    else:
        form = CheckoutForm(initial={
            "full_name": request.user.get_full_name() or request.user.username,
            "email": request.user.email,
        })

    return render(
        request,
        "store/checkout.html",
        {"items": items, "total": total, "form": form},
    )


@login_required
def orders(request):
    order_list = Order.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "store/orders.html", {"orders": order_list})


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(Order, pk=order_id, user=request.user)
    return render(request, "store/order_detail.html", {"order": order})
