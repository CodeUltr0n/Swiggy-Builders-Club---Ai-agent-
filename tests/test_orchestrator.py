import os
import pytest
import shutil
import tempfile
import asyncio
from orchestrator.memory import MemoryManager
from orchestrator.client import SwiggyMCPClient
from orchestrator.prioritizer import ContextPrioritizer
from orchestrator.router import OrchestratorRouter
from orchestrator.init_orchestrator import register_plugins

# Setup a temporary database for test separation
@pytest.fixture
def temp_db():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_orchestrator.db")
    memory = MemoryManager(db_path)
    memory.save_address("addr_home_001", "Home", "Flat 101, Test Lane", 16.5062, 80.6480)
    yield memory
    shutil.rmtree(temp_dir)

@pytest.fixture
def client(temp_db):
    c = SwiggyMCPClient(temp_db)
    c.env_mode = "simulation"
    return c

@pytest.fixture
def prioritizer(temp_db):
    return ContextPrioritizer(memory_manager=temp_db)

@pytest.fixture
def router(client, prioritizer):
    r = OrchestratorRouter(client, prioritizer)
    register_plugins(r, client)
    return r

# Test 1: Prioritizer Context Scoring
@pytest.mark.asyncio
async def test_prioritizer_scoring(prioritizer):
    # Evening 8 PM context + hunger high -> should score food high
    context = {"time_of_day": "20:00", "hunger_level": "high", "address_label": "Home"}
    scores = await prioritizer.score_tasks("I'm hungry, let's eat", context)

    server_ranks = [s[0] for s in scores]
    assert server_ranks[0] == "food"

    # Morning 8 AM context + "milk" query -> should score instamart high
    context = {"time_of_day": "08:00", "hunger_level": "low", "address_label": "Home"}
    scores = await prioritizer.score_tasks("need milk and tomatoes", context)
    server_ranks = [s[0] for s in scores]
    assert server_ranks[0] == "instamart"

    # Evening 7:30 PM context + "book table" query -> should score dineout high
    context = {"time_of_day": "19:30", "hunger_level": "low", "address_label": "Home"}
    scores = await prioritizer.score_tasks("reserve a table for dinner", context)
    server_ranks = [s[0] for s in scores]
    assert server_ranks[0] == "dineout"

# Test 2: Closed restaurant filtering (Food Server developer rule)
@pytest.mark.asyncio
async def test_closed_restaurant_filtering(client):
    # Search for rest_004 (Corner House Ice Creams) which is CLOSED in seed data
    results = await client.call_tool("food", "search_restaurants", {"query": "Corner House"})
    assert results["success"] is True
    # Should not recommend closed restaurant
    restaurants = results["data"]["restaurants"]
    names = [r["name"] for r in restaurants]
    assert "Corner House Ice Creams" not in names

# Test 3: Food Cart Cap limit of Rs 1000
@pytest.mark.asyncio
async def test_cart_limit_validation(router):
    context = {"address_id": "addr_home_001", "time_of_day": "19:30"}

    # Add 4 Mutton Biryanis (380 * 4 = 1520), should fail due to ₹1000 limit
    res = await router.process_query("add 4 Mutton Biryanis from Meghana Foods to cart", context)
    assert "exceeds" in res["response_text"]
    assert "1000" in res["response_text"]

# Test 4: COD Payment & Coupon Eligibility Validation
@pytest.mark.asyncio
async def test_cod_coupon_validation(client):
    # Coupon GPAY150 requires online payment (requiresOnlinePayment: True)
    with pytest.raises(ValueError, match="V1 supports COD only"):
        await client.plugins["food"].sim_apply_food_coupon({"code": "GPAY150"})

    # Coupon WELCOME50 is COD eligible
    res = await client.plugins["food"].sim_apply_food_coupon({"code": "WELCOME50"})
    assert res["success"] is True
    assert res["data"]["applied_coupon"] == "WELCOME50"

# Test 5: Dineout booking v1 constraint (FREE bookings only)
@pytest.mark.asyncio
async def test_dineout_free_booking(client):
    with pytest.raises(ValueError, match="only supports FREE reservations"):
        await client.plugins["dineout"].sim_create_cart({
            "restaurantId": "dine_001",
            "dealId": "deal_002",
            "billToPay": 99.0,
            "skipPayment": False
        })

    # Free booking (deal_001) should succeed
    res = await client.plugins["dineout"].sim_create_cart({
        "restaurantId": "dine_001",
        "dealId": "deal_001",
        "billToPay": 0.0,
        "skipPayment": True
    })
    assert res["success"] is True

# Test 6: Non-idempotent order retry safeguard
@pytest.mark.asyncio
async def test_order_idempotency_handling(router, client):
    context = {"address_id": "addr_home_001", "time_of_day": "19:30"}

    # Add 1 Biryani
    await router.process_query("add 1 Special Chicken Biryani from Meghana Foods to cart", context)

    # Configure food plugin to throw a 500 error on place order (simulating flaky network/crash)
    food_plugin = client.plugins["food"]
    food_plugin.simulate_flaky_error = True
    food_plugin.has_flaked = False

    # Place order confirmation -> this will invoke placing order
    res = await router.process_query("yes", context)

    assert "Success" in res["response_text"]
    assert "Verified using get_food_orders" in res["response_text"]
    assert food_plugin.has_flaked is True
