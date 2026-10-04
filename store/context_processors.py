def cart_count(request):
    cart = request.session.get("cart", {})
    count = sum(int(qty) for qty in cart.values())
    return {"cart_count": count}
