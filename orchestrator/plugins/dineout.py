import random
from datetime import datetime, timedelta
from typing import Dict, Any, List
from orchestrator.plugins import BasePlugin

class DineoutPlugin(BasePlugin):
    def __init__(self, memory_manager):
        super().__init__("dineout", memory_manager)
        # Mock dineout restaurants
        self.restaurants = [
            {"id": "dine_001", "name": "Windmills Craftworks", "cuisine": "Microbrewery, Continental", "rating": 4.7, "avg_cost_for_two": 2500, "address": "Whitefield, Bengaluru", "has_deals": True},
            {"id": "dine_002", "name": "Toit Microbrewery", "cuisine": "Italian, Pizza, Craft Beer", "rating": 4.6, "avg_cost_for_two": 2000, "address": "Indiranagar, Bengaluru", "has_deals": False},
            {"id": "dine_003", "name": "The Biere Club", "cuisine": "Finger Food, European", "rating": 4.3, "avg_cost_for_two": 1800, "address": "Lavelle Road, Bengaluru", "has_deals": True},
            {"id": "dine_004", "name": "Szechwan Court", "cuisine": "Chinese, Asian", "rating": 4.5, "avg_cost_for_two": 3500, "address": "MG Road, Bengaluru", "has_deals": False}
        ]

    async def sim_get_addresses(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        addresses = self.memory.get_addresses()
        return {"success": True, "data": addresses}

    async def sim_get_saved_locations(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        addresses = self.memory.get_addresses()
        return {"success": True, "data": [{"id": addr["id"], "label": addr["label"]} for addr in addresses]}


    async def sim_search_restaurants_dineout(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        query = arguments.get("query", "").lower()
        results = []
        for rest in self.restaurants:
            if not query or query in rest["name"].lower() or query in rest["cuisine"].lower() or query in rest["address"].lower():
                results.append(rest)
        return {"success": True, "data": {"restaurants": results}}

    async def sim_get_restaurant_details(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        rest_id = arguments.get("restaurantId")
        rest = next((r for r in self.restaurants if r["id"] == rest_id), None)
        if not rest:
            raise ValueError(f"Dineout restaurant {rest_id} not found")
        return {
            "success": True,
            "data": {
                **rest,
                "timings": "12:00 PM - 11:30 PM",
                "deals": [
                    {"id": "deal_001", "title": "15% Off Total Bill", "isFree": True, "bookingPrice": 0},
                    {"id": "deal_002", "title": "Buy 1 Get 1 on Craft Beers", "isFree": False, "bookingPrice": 99}
                ]
            }
        }

    async def sim_get_available_slots(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        rest_id = arguments.get("restaurantId")
        date_str = arguments.get("date") # e.g. YYYY-MM-DD
        
        if not rest_id:
            raise ValueError("restaurantId is required")
            
        # Return lunch and dinner slots
        return {
            "success": True,
            "data": {
                "restaurantId": rest_id,
                "date": date_str,
                "slots": [
                    {"time": "12:30 PM", "available": True},
                    {"time": "1:00 PM", "available": True},
                    {"time": "1:30 PM", "available": False},
                    {"time": "7:30 PM", "available": True},
                    {"time": "8:00 PM", "available": True},
                    {"time": "8:30 PM", "available": True},
                    {"time": "9:00 PM", "available": False}
                ]
            }
        }

    async def sim_create_cart(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        rest_id = arguments.get("restaurantId")
        deal_id = arguments.get("dealId")
        guests = arguments.get("guests", 2)
        slot_time = arguments.get("slotTime")
        slot_date = arguments.get("slotDate")
        bill_to_pay = arguments.get("billToPay", 0.0)
        skip_payment = arguments.get("skipPayment", True)
        
        # Developer guideline: "Only supports FREE reservations (isFree=true, bookingPrice=0). Paid deals will be rejected."
        # Validates billToPay = 0 and skipPayment = true
        if bill_to_pay > 0 or not skip_payment:
            raise ValueError("V1 only supports FREE reservations. Paid deals are rejected.")
            
        if deal_id == "deal_002":
            # deal_002 is a paid deal in get_restaurant_details
            raise ValueError("Selected deal is not free. Only free bookings are allowed in Builders Club v1.")

        self.simulated_cart = {
            "restaurant_id": rest_id,
            "deal_id": deal_id,
            "guests": guests,
            "slot_time": slot_time,
            "slot_date": slot_date,
            "total": 0.0,
            "is_free": True
        }
        
        return {"success": True, "data": {"cartId": f"cart_dine_{random.randint(1000, 9999)}", "valid": True}}

    async def sim_book_table(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self.simulated_cart.get("restaurant_id"):
            raise ValueError("No active table booking cart. Create cart first.")
            
        rest = next((r for r in self.restaurants if r["id"] == self.simulated_cart["restaurant_id"]), None)
        rest_name = rest["name"] if rest else "Unknown Dineout Restaurant"
        
        booking_id = f"ord_dine_{random.randint(100000, 999999)}"
        
        # Save table booking to memory orders
        self.memory.save_order(
            order_id=booking_id,
            server="dineout",
            merchant_name=rest_name,
            items=[{
                "type": "TABLE_BOOKING",
                "date": self.simulated_cart["slot_date"],
                "time": self.simulated_cart["slot_time"],
                "guests": self.simulated_cart["guests"],
                "deal_id": self.simulated_cart["deal_id"]
            }],
            total_amount=0.0,
            status="CONFIRMED"
        )
        
        # Clear cart
        self.simulated_cart = self._initial_cart_state()
        
        return {
            "success": True,
            "data": {
                "bookingId": booking_id,
                "status": "CONFIRMED",
                "restaurantName": rest_name,
                "date": arguments.get("slotDate", datetime.now().strftime("%Y-%m-%d")),
                "time": arguments.get("slotTime", "8:00 PM"),
                "guests": arguments.get("guests", 2)
            }
        }

    async def sim_get_booking_status(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        booking_id = arguments.get("bookingId")
        if not booking_id:
            raise ValueError("bookingId is required")
            
        orders = self.memory.get_past_orders()
        order = next((o for o in orders if o["id"] == booking_id), None)
        if not order:
            raise ValueError(f"Booking {booking_id} not found")
            
        details = order["items"][0]
        return {
            "success": True,
            "data": {
                "bookingId": booking_id,
                "restaurantName": order["merchant_name"],
                "date": details.get("date"),
                "time": details.get("time"),
                "guests": details.get("guests"),
                "status": "CONFIRMED"
            }
        }

    async def sim_report_error(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        error_summary = arguments.get("summary", "Unknown error")
        mailto = f"mailto:builders@swiggy.in?subject=Developer%20MCP%20Dineout%20Error&body=Error%20Details:%20{error_summary}"
        return {
            "success": True,
            "data": {
                "mailto": mailto,
                "message": "Mail template generated."
            }
        }
