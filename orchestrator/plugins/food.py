import random
from typing import Dict, Any, List
from orchestrator.plugins import BasePlugin

class FoodPlugin(BasePlugin):
    def __init__(self, memory_manager):
        super().__init__("food", memory_manager)
        # Mock restaurants database
        self.restaurants = [
            {"id": "rest_001", "name": "Meghana Foods", "cuisine": "Biryani, Andhra", "rating": 4.5, "distance_km": 1.2, "availabilityStatus": "OPEN", "avg_cost": 400},
            {"id": "rest_002", "name": "Imperial Restaurant", "cuisine": "North Indian, Mughlai", "rating": 4.2, "distance_km": 2.5, "availabilityStatus": "OPEN", "avg_cost": 350},
            {"id": "rest_003", "name": "Truffles", "cuisine": "Burgers, American, Cafe", "rating": 4.6, "distance_km": 3.8, "availabilityStatus": "OPEN", "avg_cost": 500},
            {"id": "rest_004", "name": "Corner House Ice Creams", "cuisine": "Desserts", "rating": 4.7, "distance_km": 0.8, "availabilityStatus": "CLOSED", "avg_cost": 200},
            {"id": "rest_005", "name": "Leon Grill", "cuisine": "Fast Food, Burgers", "rating": 4.1, "distance_km": 4.5, "availabilityStatus": "OPEN", "avg_cost": 300}
        ]
        # Mock menus database
        self.menus = {
            "rest_001": [
                {"id": "item_101", "name": "Special Chicken Biryani", "price": 320.0, "category": "Biryani"},
                {"id": "item_102", "name": "Mutton Biryani", "price": 380.0, "category": "Biryani"},
                {"id": "item_103", "name": "Paneer Biryani", "price": 280.0, "category": "Biryani"},
                {"id": "item_104", "name": "Chicken Boneless Kabab", "price": 260.0, "category": "Starters"},
                {"id": "item_105", "name": "Garlic Naan", "price": 60.0, "category": "Breads"},
                {"id": "item_106", "name": "Tandoori Roti", "price": 30.0, "category": "Breads"}
            ],

            "rest_002": [
                {"id": "item_201", "name": "Butter Chicken", "price": 340.0, "category": "Curries"},
                {"id": "item_202", "name": "Kadhai Paneer", "price": 290.0, "category": "Curries"},
                {"id": "item_203", "name": "Garlic Naan", "price": 60.0, "category": "Breads"},
                {"id": "item_204", "name": "Tandoori Roti", "price": 30.0, "category": "Breads"}
            ],
            "rest_003": [
                {"id": "item_301", "name": "All American Cheese Burger", "price": 250.0, "category": "Burgers"},
                {"id": "item_302", "name": "Crunchy Chicken Burger", "price": 280.0, "category": "Burgers"},
                {"id": "item_303", "name": "Peri Peri French Fries", "price": 140.0, "category": "Sides"},
                {"id": "item_304", "name": "Cold Coffee", "price": 180.0, "category": "Beverages"}
            ],
            "rest_005": [
                {"id": "item_501", "name": "Doner Wrap", "price": 210.0, "category": "Wraps"},
                {"id": "item_502", "name": "Jumbo Crispy Fried Chicken (2pc)", "price": 299.0, "category": "Fried Chicken"}
            ]
        }
        # Mock coupons
        self.coupons = [
            {"code": "WELCOME50", "discount_percentage": 50, "max_discount": 100.0, "requiresOnlinePayment": False, "description": "50% off up to Rs 100 (COD eligible)"},
            {"code": "GPAY150", "discount_percentage": 30, "max_discount": 150.0, "requiresOnlinePayment": True, "description": "30% off up to Rs 150 (GPay Only)"},
            {"code": "SWIGGYIT", "discount_percentage": 20, "max_discount": 200.0, "requiresOnlinePayment": False, "description": "20% off up to Rs 200 (COD eligible)"}
        ]
        
        # Helper state to simulate flaky first-time ordering
        self.simulate_flaky_error = False
        self.has_flaked = False

    # Tool simulation handlers
    async def sim_get_addresses(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        addresses = self.memory.get_addresses()
        return {"success": True, "data": addresses}

    async def sim_search_restaurants(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        query = arguments.get("query", "").lower()
        # Filter: only OPEN restaurants are recommended according to developer guidelines
        results = []
        for rest in self.restaurants:
            # Let's filter by query if specified
            if query and query not in rest["name"].lower() and query not in rest["cuisine"].lower():
                continue
            # Note: Developer quickstart says "Only recommend restaurants with availabilityStatus: 'OPEN'"
            if rest["availabilityStatus"] == "OPEN":
                results.append(rest)
        
        return {"success": True, "data": {"restaurants": results}}

    async def sim_get_restaurant_menu(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        rest_id = arguments.get("restaurantId")
        if not rest_id:
            raise ValueError("restaurantId is required")
        if rest_id not in self.menus:
            raise ValueError(f"Restaurant with ID {rest_id} not found or has no menu")
        
        return {
            "success": True,
            "data": {
                "restaurantId": rest_id,
                "items": self.menus[rest_id]
            }
        }

    async def sim_search_menu(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        query = arguments.get("query", "").lower()
        results = []
        for rest_id, items in self.menus.items():
            # Check if restaurant is OPEN
            rest_info = next((r for r in self.restaurants if r["id"] == rest_id), None)
            if not rest_info or rest_info["availabilityStatus"] != "OPEN":
                continue
                
            for item in items:
                if query in item["name"].lower() or query in item["category"].lower():
                    results.append({
                        **item,
                        "restaurantId": rest_id,
                        "restaurantName": rest_info["name"]
                    })
        return {"success": True, "data": {"items": results}}

    async def sim_get_food_cart(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True, "data": self.simulated_cart}

    async def sim_update_food_cart(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        rest_id = arguments.get("restaurantId")
        items = arguments.get("items", [])
        
        if not rest_id:
            raise ValueError("restaurantId is required")
            
        # Check if restaurant is OPEN
        rest_info = next((r for r in self.restaurants if r["id"] == rest_id), None)
        if not rest_info or rest_info["availabilityStatus"] != "OPEN":
            raise ValueError("Cannot add items from a closed restaurant")

        # Cart can only contain items from a single restaurant. Changing restaurant flushes the cart.
        if self.simulated_cart["restaurant_id"] and self.simulated_cart["restaurant_id"] != rest_id:
            self.simulated_cart = self._initial_cart_state()

        self.simulated_cart["restaurant_id"] = rest_id
        
        menu_items = {item["id"]: item for item in self.menus.get(rest_id, [])}
        
        cart_items = []
        subtotal = 0.0
        
        for cart_item in items:
            item_id = cart_item["itemId"]
            quantity = cart_item["quantity"]
            if item_id not in menu_items:
                raise ValueError(f"Item ID {item_id} not found in this restaurant's menu")
            
            menu_item = menu_items[item_id]
            total_item_price = menu_item["price"] * quantity
            subtotal += total_item_price
            cart_items.append({
                "itemId": item_id,
                "name": menu_item["name"],
                "price": menu_item["price"],
                "quantity": quantity,
                "total_price": total_item_price
            })

        self.simulated_cart["items"] = cart_items
        self.simulated_cart["subtotal"] = subtotal
        
        # Apply discount if coupon code exists
        discount = 0.0
        applied = self.simulated_cart["applied_coupon"]
        if applied:
            coupon = next((c for c in self.coupons if c["code"] == applied), None)
            if coupon:
                discount = min((subtotal * coupon["discount_percentage"] / 100.0), coupon["max_discount"])
        
        self.simulated_cart["discount"] = discount
        self.simulated_cart["total"] = subtotal - discount
        
        return {"success": True, "data": self.simulated_cart}

    async def sim_flush_food_cart(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        self.simulated_cart = self._initial_cart_state()
        return {"success": True, "message": "Cart flushed successfully"}

    async def sim_fetch_food_coupons(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        # Return all coupons. (The caller/router must filter those requiring online payment)
        return {"success": True, "data": self.coupons}

    async def sim_apply_food_coupon(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        code = arguments.get("code")
        coupon = next((c for c in self.coupons if c["code"] == code), None)
        if not coupon:
            raise ValueError(f"Invalid coupon code: {code}")
            
        # Developer guideline: "Only COD is supported in v1; filter coupons to those not requiring online payment."
        if coupon["requiresOnlinePayment"]:
            raise ValueError("Coupon requires online payment. V1 supports COD only.")

        self.simulated_cart["applied_coupon"] = code
        # Recalculate cart
        if self.simulated_cart["restaurant_id"]:
            # Re-update to trigger recalculation
            items_args = [{"itemId": item["itemId"], "quantity": item["quantity"]} for item in self.simulated_cart["items"]]
            await self.sim_update_food_cart({
                "restaurantId": self.simulated_cart["restaurant_id"],
                "items": items_args
            })
            
        return {"success": True, "data": self.simulated_cart}

    async def sim_place_food_order(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        payment_method = arguments.get("paymentMethod")
        
        # Validate payment method is COD
        if payment_method != "COD":
            raise ValueError("V1 only supports Cash on Delivery (COD)")

        if not self.simulated_cart["restaurant_id"] or not self.simulated_cart["items"]:
            raise ValueError("Cart is empty")

        # Validate ₹1000 cap
        if self.simulated_cart["total"] > 1000.0:
            raise ValueError(f"Cart total exceeds the ₹1000 cap for Swiggy Builders Club v1. Current total: {self.simulated_cart['total']}")

        # Simulate flaky 500 error once if enabled, to verify non-idempotent handling
        if self.simulate_flaky_error and not self.has_flaked:
            self.has_flaked = True
            # Create the order in backend but throw 500 error to simulate a server crash *after* saving
            order_id = f"ord_food_{random.randint(100000, 999999)}"
            rest_info = next((r for r in self.restaurants if r["id"] == self.simulated_cart["restaurant_id"]), None)
            merchant_name = rest_info["name"] if rest_info else "Unknown Restaurant"
            
            # Save it secretly in memory
            self.memory.save_order(
                order_id=order_id,
                server="food",
                merchant_name=merchant_name,
                items=self.simulated_cart["items"],
                total_amount=self.simulated_cart["total"],
                status="PLACED"
            )
            self.simulated_cart = self._initial_cart_state()
            raise Exception("500 Internal Server Error: Connection timed out during payment confirmation")

        # Regular successful placement
        order_id = f"ord_food_{random.randint(100000, 999999)}"
        rest_info = next((r for r in self.restaurants if r["id"] == self.simulated_cart["restaurant_id"]), None)
        merchant_name = rest_info["name"] if rest_info else "Unknown Restaurant"
        
        # Save to memory DB
        self.memory.save_order(
            order_id=order_id,
            server="food",
            merchant_name=merchant_name,
            items=self.simulated_cart["items"],
            total_amount=self.simulated_cart["total"],
            status="PLACED"
        )
        
        # Flush cart
        self.simulated_cart = self._initial_cart_state()
        
        return {
            "success": True,
            "data": {
                "orderId": order_id,
                "status": "PLACED",
                "paymentMethod": "COD",
                "estimatedDeliveryMinutes": 35
            }
        }

    async def sim_get_food_orders(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        orders = self.memory.get_past_orders()
        food_orders = [ord for ord in orders if ord["server"] == "food"]
        return {"success": True, "data": food_orders}

    async def sim_get_food_order_details(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        order_id = arguments.get("orderId")
        if not order_id:
            raise ValueError("orderId is required")
        orders = self.memory.get_past_orders()
        order = next((o for o in orders if o["id"] == order_id), None)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        return {"success": True, "data": order}

    async def sim_track_food_order(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        order_id = arguments.get("orderId")
        if not order_id:
            raise ValueError("orderId is required")
            
        orders = self.memory.get_past_orders()
        order = next((o for o in orders if o["id"] == order_id), None)
        if not order:
            raise ValueError(f"Order {order_id} not found")
            
        # Mock status updates based on random choice
        statuses = ["Preparing", "Partner Assigned", "Out for Delivery", "Delivered"]
        status = random.choice(statuses[:-1])  # default prepare/out
        
        return {
            "success": True,
            "data": {
                "orderId": order_id,
                "status": status,
                "deliveryPartnerName": "Ramesh Kumar",
                "deliveryPartnerPhone": "+91 98765 43210",
                "etaMinutes": 15
            }
        }

    async def sim_report_error(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        error_summary = arguments.get("summary", "Unknown error")
        mailto = f"mailto:builders@swiggy.in?subject=Developer%20MCP%20Error&body=Error%20Details:%20{error_summary}"
        return {
            "success": True,
            "data": {
                "mailto": mailto,
                "message": "Mail template generated. Please contact support via mailto link."
            }
        }
