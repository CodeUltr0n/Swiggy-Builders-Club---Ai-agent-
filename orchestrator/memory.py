import sqlite3
import json
import os
from typing import List, Dict, Any, Optional

class MemoryManager:
    def __init__(self, db_path: str = "orchestrator.db"):
        self.db_path = db_path
        self.initialize_db()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    def initialize_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create user addresses table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS addresses (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    display_text TEXT NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create past orders table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS orders (
                    id TEXT PRIMARY KEY,
                    server TEXT NOT NULL,
                    merchant_name TEXT NOT NULL,
                    items TEXT NOT NULL, -- JSON string
                    total_amount REAL NOT NULL,
                    status TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create user preferences table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS preferences (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            
            # Seed default addresses if empty
            cursor.execute("SELECT COUNT(*) FROM addresses")
            if cursor.fetchone()[0] == 0:
                self.seed_default_data()

            # Clean up abandoned data periodically (on initialization)
            self.purge_abandoned_orders()

    def seed_default_data(self):
        default_addresses = [
            ("addr_home_001", "Home", "Flat 402, Signature Residency, Indiranagar, Bengaluru", 12.9716, 77.5946),
            ("addr_office_002", "Office", "Embassy TechVillage, Bellandur, Bengaluru", 12.9279, 77.6811),
            ("addr_other_003", "Gym", "Cult Fit, HSR Layout, Bengaluru", 12.9116, 77.6389)
        ]
        default_orders = [
            ("ord_food_001", "food", "Meghana Foods", json.dumps([{"name": "Special Chicken Biryani", "quantity": 1, "price": 320.0}]), 320.0, "DELIVERED"),
            ("ord_im_001", "instamart", "Instamart Store", json.dumps([{"name": "Milk & Eggs", "quantity": 1, "price": 65.0}]), 65.0, "DELIVERED"),
            ("ord_dine_001", "dineout", "Truffles", json.dumps([{"title": "Free Reservation for 2", "guests": 2}]), 0.0, "CONFIRMED"),
        ]
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for addr in default_addresses:
                cursor.execute("""
                    INSERT OR REPLACE INTO addresses (id, label, display_text, latitude, longitude)
                    VALUES (?, ?, ?, ?, ?)
                """, addr)
            for ord_item in default_orders:
                cursor.execute("""
                    INSERT OR REPLACE INTO orders (id, server, merchant_name, items, total_amount, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ord_item)

            default_prefs = [
                ("dietary_preference", "Non-Veg"),
                ("preferred_payment_method", "COD"),
            ]
            for pref_k, pref_v in default_prefs:
                cursor.execute("""
                    INSERT OR REPLACE INTO preferences (key, value)
                    VALUES (?, ?)
                """, (pref_k, json.dumps(pref_v)))

            conn.commit()

    # Address operations
    def save_address(self, id: str, label: str, display_text: str, lat: float, lng: float):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO addresses (id, label, display_text, latitude, longitude, last_used)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (id, label, display_text, lat, lng))
            conn.commit()

    def get_addresses(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, label, display_text, latitude, longitude FROM addresses ORDER BY last_used DESC")
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "label": row[1],
                    "display_text": row[2],
                    "latitude": row[3],
                    "longitude": row[4]
                } for row in rows
            ]

    def get_last_used_address(self) -> Optional[Dict[str, Any]]:
        addresses = self.get_addresses()
        return addresses[0] if addresses else None

    def set_last_used_address(self, address_id: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE addresses SET last_used = CURRENT_TIMESTAMP WHERE id = ?", (address_id,))
            conn.commit()

    # Order operations
    def save_order(self, order_id: str, server: str, merchant_name: str, items: List[Dict[str, Any]], total_amount: float, status: str):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            items_json = json.dumps(items)
            cursor.execute("""
                INSERT OR REPLACE INTO orders (id, server, merchant_name, items, total_amount, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (order_id, server, merchant_name, items_json, total_amount, status))
            conn.commit()

    def get_past_orders(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, server, merchant_name, items, total_amount, status, timestamp FROM orders ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [
                {
                    "id": row[0],
                    "server": row[1],
                    "merchant_name": row[2],
                    "items": json.loads(row[3]),
                    "total_amount": row[4],
                    "status": row[5],
                    "timestamp": row[6]
                } for row in rows
            ]

    def purge_abandoned_orders(self):
        """Purge abandoned or failed orders to comply with Swiggy Integration Agreement Section 3.3(i)(b)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Delete orders that are not DELIVERED or CONFIRMED or PLACED and are older than 2 hours
            cursor.execute("""
                DELETE FROM orders 
                WHERE status NOT IN ('DELIVERED', 'CONFIRMED', 'PLACED') 
                AND timestamp <= datetime('now', '-2 hours')
            """)
            conn.commit()

    # Preference operations

    def set_preference(self, key: str, value: Any):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO preferences (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, json.dumps(value)))
            conn.commit()

    def get_preference(self, key: str, default: Any = None) -> Any:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return default

    def get_all_preferences(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT key, value FROM preferences")
            rows = cursor.fetchall()
            return {row[0]: json.loads(row[1]) for row in rows}

    def get_derived_preferences(self) -> Dict[str, Any]:
        """Derive explicit or learned user preferences from database and order history."""
        prefs = self.get_all_preferences()
        if "preferred_server" not in prefs:
            orders = self.get_past_orders(limit=20)
            if orders:
                counts = {}
                for o in orders:
                    s = o.get("server")
                    counts[s] = counts.get(s, 0) + 1
                most_freq = max(counts.items(), key=lambda x: x[1])[0]
                prefs["preferred_server"] = most_freq
        return prefs

