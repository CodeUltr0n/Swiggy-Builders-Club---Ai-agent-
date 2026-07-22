import random
from typing import Dict, Any, List
from orchestrator.plugins import BasePlugin

class InstamartPlugin(BasePlugin):
    def __init__(self, memory_manager):
        super().__init__("instamart", memory_manager)
        # Mock products database
        self.products = [
            {"id": "prod_001", "name": "Nandini Fresh Pasteurized Toned Milk 1L", "price": 46.0, "category": "Dairy", "in_stock": True, "brand": "Nandini"},
            {"id": "prod_008", "name": "Farm Fresh White Eggs (6 pcs)", "price": 55.0, "category": "Dairy", "in_stock": True, "brand": "Farm Fresh"},
            {"id": "prod_002", "name": "Fresho Onion 1kg", "price": 35.0, "category": "Vegetables", "in_stock": True, "brand": "Fresho"},
            {"id": "prod_003", "name": "Fresho Tomato Hybrid 500g", "price": 22.0, "category": "Vegetables", "in_stock": True, "brand": "Fresho"},
            {"id": "prod_004", "name": "Lays Potato Chips India's Magic Masala 50g", "price": 20.0, "category": "Snacks", "in_stock": True, "brand": "Lays"},
            {"id": "prod_005", "name": "Coca-Cola Original Taste 750ml", "price": 45.0, "category": "Beverages", "in_stock": True, "brand": "Coca-Cola"},
            {"id": "prod_006", "name": "Aashirvaad Svasti Pure Cow Ghee 500ml", "price": 340.0, "category": "Staples", "in_stock": True, "brand": "Aashirvaad"},
            {"id": "prod_007", "name": "Surf Excel Easy Wash Detergent Powder 1kg", "price": 160.0, "category": "Household", "in_stock": False, "brand": "Surf Excel"}
        ]

        
    def _initial_cart_state(self) -> Dict[str, Any]:
        return {"items": [], "total": 0.0, "delivery_charge": 29.0, "grand_total": 29.0}

    async def sim_get_addresses(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        addresses = self.memory.get_addresses()
        return {"success": True, "data": addresses}

    async def sim_create_address(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        label = arguments.get("label", "Other")
        display_text = arguments.get("displayText")
        lat = arguments.get("latitude")
        lng = arguments.get("longitude")
        
        if not display_text:
            raise ValueError("displayText is required")
            
        addr_id = f"addr_{random.randint(1000, 9999)}"
        self.memory.save_address(addr_id, label, display_text, lat, lng)
        return {"success": True, "data": {"id": addr_id, "label": label, "displayText": display_text}}

    async def sim_delete_address(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        address_id = arguments.get("addressId")
        if not address_id:
            raise ValueError("addressId is required")
        # Sim deleting address (we can just run a query)
        with self.memory.get_connection() as conn:
            conn.cursor().execute("DELETE FROM addresses WHERE id = ?", (address_id,))
            conn.commit()
        return {"success": True, "message": "Address deleted"}

    async def sim_search_products(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        query = arguments.get("query", "").lower()
        results = []
        for prod in self.products:
            prod_text = f"{prod['name']} {prod['category']} {prod['brand']}".lower()
            if query in prod_text:
                results.append(prod)

        # Fallback: word token matching (e.g. if query is "Amul Milk", match available milk)
        if not results and query:
            tokens = [t for t in query.split() if len(t) > 2]
            for prod in self.products:
                prod_text = f"{prod['name']} {prod['category']} {prod['brand']}".lower()
                if any(t in prod_text for t in tokens):
                    if prod not in results:
                        results.append(prod)

        return {"success": True, "data": {"products": results}}


    async def sim_your_go_to_items(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        # Return first 3 products as go-to items
        return {"success": True, "data": {"products": self.products[:3]}}

    async def sim_get_cart(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return {"success": True, "data": self.simulated_cart}

    async def sim_update_cart(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        items = arguments.get("items", [])
        
        cart_items = []
        subtotal = 0.0
        
        prod_map = {p["id"]: p for p in self.products}
        
        for item in items:
            prod_id = item["productId"]
            qty = item["quantity"]
            
            if prod_id not in prod_map:
                raise ValueError(f"Product {prod_id} not found")
                
            prod = prod_map[prod_id]
            if not prod["in_stock"]:
                raise ValueError(f"Product {prod['name']} is out of stock")
                
            total_price = prod["price"] * qty
            subtotal += total_price
            
            cart_items.append({
                "productId": prod_id,
                "name": prod["name"],
                "price": prod["price"],
                "quantity": qty,
                "total_price": total_price
            })
            
        self.simulated_cart["items"] = cart_items
        self.simulated_cart["total"] = subtotal
        
        # Calculate delivery fee
        delivery_charge = 0.0 if subtotal > 199.0 else 29.0
        self.simulated_cart["delivery_charge"] = delivery_charge
        self.simulated_cart["grand_total"] = subtotal + delivery_charge
        
        return {"success": True, "data": self.simulated_cart}

    async def sim_clear_cart(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        self.simulated_cart = self._initial_cart_state()
        return {"success": True, "message": "Instamart cart cleared"}

    async def sim_checkout(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if not self.simulated_cart["items"]:
            raise ValueError("Instamart cart is empty")
            
        order_id = f"ord_im_{random.randint(100000, 999999)}"
        self.memory.save_order(
            order_id=order_id,
            server="instamart",
            merchant_name="Swiggy Instamart Pod",
            items=self.simulated_cart["items"],
            total_amount=self.simulated_cart["grand_total"],
            status="PLACED"
        )
        
        # Flush cart
        self.simulated_cart = self._initial_cart_state()
        return {
            "success": True,
            "data": {
                "orderId": order_id,
                "status": "PLACED",
                "estimatedDeliveryMinutes": 18
            }
        }

    async def sim_get_orders(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        orders = self.memory.get_past_orders()
        im_orders = [ord for ord in orders if ord["server"] == "instamart"]
        return {"success": True, "data": im_orders}

    async def sim_get_order_details(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        order_id = arguments.get("orderId")
        if not order_id:
            raise ValueError("orderId is required")
        orders = self.memory.get_past_orders()
        order = next((o for o in orders if o["id"] == order_id), None)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        return {"success": True, "data": order}

    async def sim_track_order(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        order_id = arguments.get("orderId")
        if not order_id:
            raise ValueError("orderId is required")
        return {
            "success": True,
            "data": {
                "orderId": order_id,
                "status": "Out for Delivery",
                "etaMinutes": 8
            }
        }

    async def sim_report_error(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        error_summary = arguments.get("summary", "Unknown error")
        mailto = f"mailto:builders@swiggy.in?subject=Developer%20MCP%20Instamart%20Error&body=Error%20Details:%20{error_summary}"
        return {
            "success": True,
            "data": {
                "mailto": mailto,
                "message": "Mail template generated."
            }
        }
