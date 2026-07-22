# Developer Study Guide: Swiggy MCP Orchestrator

This guide walks you through the entire architecture, directory structure, setup workflow, and code logic of the Swiggy MCP Orchestrator. Use this document to understand the codebase and prepare your submission video.

---

## 1. What is the Swiggy MCP Orchestrator?
Traditionally, developers build isolated AI agents for different services: a Food agent, an Instamart agent, and a Dineout agent. This creates siloed context and high token overhead.

The **MCP Orchestrator** flips the model. It sits as a single intelligence layer above multiple Model Context Protocol (MCP) servers. Using active user context (time, location, hunger, and preferences), it determines the single most relevant action to take right now, routing natural language commands to the correct Swiggy server (Food, Instamart, or Dineout) and executing the multi-tool checkout pipelines under strict Swiggy developer rules.

---

## 2. Project Setup & Workspace Initialization

To run the orchestrator, we initialize a sandboxed virtual environment to manage dependencies:

```bash
# 1. Create a local virtual environment (.venv)
uv venv

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Install packages (mcp, pyyaml, httpx, pytest, pytest-asyncio)
uv pip install -r requirements.txt
```

*Note: The `.vscode/settings.json` file in the project forces your IDE (Cursor/VS Code) to use the virtual environment interpreter (`.venv/bin/python`) so that all package auto-completes and syntax highlights function correctly.*

---

## 3. Directory Structure & File Breakdowns

### `config/` (Configurations)
*   **[`servers.yaml`](file:///Users/chokkaraketankumar/Desktop/Swiggy%20-%20mcp-orchestrator/config/servers.yaml)**: Holds the staging and production URLs for the Swiggy MCP servers (`/food`, `/im`, `/dineout`). When credentials are wired, the client queries this file to find where to route JSON-RPC requests.
*   **[`settings.yaml`](file:///Users/chokkaraketankumar/Desktop/Swiggy%20-%20mcp-orchestrator/config/settings.yaml)**: Controls application state. Contains `env_mode` (can be `simulation` or `staging`), the SQLite database path, and default coordinate overrides.

### `orchestrator/` (Core Logic)
#### 1. **[`memory.py`](file:///Users/chokkaraketankumar/Desktop/Swiggy%20-%20mcp-orchestrator/orchestrator/memory.py)** (Persistent Storage)
*   **Purpose**: Manages a local SQLite database (`orchestrator.db`) to store persistent profiles across sessions.
*   **Key Functions**:
    *   `initialize_db()`: Creates the SQL tables: `addresses` (saved user locations), `orders` (placed order details), and `preferences` (habit tracking key-values).
    *   `seed_default_data()`: Seeds default coordinates in Bengaluru (Indiranagar, HSR, and Bellandur) to simulate a user's location habits.
    *   `save_order()` / `get_past_orders()`: Records transactions so the system can recall user habits (e.g. how many times they ordered biryani recently).

#### 2. **[`prioritizer.py`](file:///Users/chokkaraketankumar/Desktop/Swiggy%20-%20mcp-orchestrator/orchestrator/prioritizer.py)** (Context Scoring Engine)
*   **Purpose**: Ranks the target servers (Food vs. Instamart vs. Dineout) based on environmental signals rather than just raw keyword match.
*   **Weight Calculations**:
    *   **Time of day**: Morning hours (7 AM-11 AM) boost Instamart (groceries/milk). Lunch (12 PM-3 PM) and Dinner (7 PM-11 PM) boost Food delivery. Dineout reservation scores peak in the evening.
    *   **Location**: If `address_label` is `"Office"`, Instamart is penalized (users don't cook raw groceries at work), and Food delivery/Dineout is boosted.
    *   **Hunger & Urgency**: High hunger levels boost Food delivery (instant gratification) over Dineout (requires travel).
    *   **History**: A proportional boost is added based on past order frequencies retrieved from SQLite.
    *   **Intent Override**: If queries have strong keywords (e.g., "milk", "table"), the engine applies a temporary override boost to the target domain.

#### 3. **[`plugins/`](file:///Users/chokkaraketankumar/Desktop/Swiggy%20-%20mcp-orchestrator/orchestrator/plugins/)** (Swiggy Tool Simulations)
Since staging access is issued after signing agreements, we built a fully-realized simulation engine that returns mock responses matching Swiggy's v1.0 specifications.
*   **[`__init__.py`](file:///Users/chokkaraketankumar/Desktop/Swiggy%20-%20mcp-orchestrator/orchestrator/plugins/__init__.py)**: Defines `BasePlugin` which routes tool requests to standard simulation methods (prefixed with `sim_`) or forwards them to real servers.
*   **[`food.py`](file:///Users/chokkaraketankumar/Desktop/Swiggy%20-%20mcp-orchestrator/orchestrator/plugins/food.py)**: Implements 14 Food tools.
    *   *Rules Enforced*: Only returns `"OPEN"` restaurants. Carts can only contain items from a single restaurant. Integrates a testable flaky checkout mode to verify idempotency handling.
*   **[`instamart.py`](file:///Users/chokkaraketankumar/Desktop/Swiggy%20-%20mcp-orchestrator/orchestrator/plugins/instamart.py)**: Implements 13 Instamart tools.
    *   *Rules Enforced*: Restricts out-of-stock items, calculates delivery fees (free above ₹199, otherwise ₹29), and simulates standard checkouts.
*   **[`dineout.py`](file:///Users/chokkaraketankumar/Desktop/Swiggy%20-%20mcp-orchestrator/orchestrator/plugins/dineout.py)**: Implements 8 Dineout tools.
    *   *Rules Enforced*: Rejects any reservation containing a paid deal (enforcing the Swiggy v1 rule that only free bookings are supported).

#### 4. **[`client.py`](file:///Users/chokkaraketankumar/Desktop/Swiggy%20-%20mcp-orchestrator/orchestrator/client.py)** (MCP Request Routing)
*   **Purpose**: Manages active sessions.
*   **Logic**: If `env_mode` is `"simulation"`, it resolves immediately to local plugin stubs. If `"staging"` or `"production"`, it constructs JSON-RPC 2.0 requests, attaches OAuth Bearer tokens, and makes async HTTP/SSE requests to Swiggy endpoints. It also contains token lifecycle checks, returning standard 401s if access tokens expire (they live for 5 days).

#### 5. **[`router.py`](file:///Users/chokkaraketankumar/Desktop/Swiggy%20-%20mcp-orchestrator/orchestrator/router.py)** (Command Dispatcher & Developer Rules)
*   **Purpose**: The central coordinator that parses queries, calls the prioritizer, executes multi-tool loops, and checks constraints.
*   **Core Flows & Rules Built-in**:
    1.  **Addressing**: Automatically calls `get_addresses` to resolve locations before recommending items.
    2.  **Order Cap**: Enforces the Swiggy Builders Club ₹1000 limit, clearing the cart and showing a warning if exceeded.
    3.  **COD Coupon Filter**: Intercepts `fetch_food_coupons` and automatically applies eligible Cash-on-Delivery coupons, ignoring online-payment ones.
    4.  **Confirmations**: Prompts the user with a summary before calling the order placement action.
    5.  **Idempotency Recovery**: If order placement fails with a network error, instead of retrying, it queries `get_food_orders` first to check if the transaction succeeded under the hood.

#### 6. **[`__main__.py`](file:///Users/chokkaraketankumar/Desktop/Swiggy%20-%20mcp-orchestrator/orchestrator/__main__.py)** (CLI Interface)
*   **Purpose**: Implements the interactive terminal loop.
*   **Command Knobs**:
    *   `/context`: Displays current settings or dynamically sets mock factors (e.g. `/context time_of_day 08:00` or `/context hunger_level high`) so you can watch priority rankings adjust in real-time.
    *   `/history`: Displays historical data stored inside the local SQLite database.
    *   `/reset`: Clears carts and active states.

---

## 4. Testing & Verification

We wrote unit tests in **[`tests/test_orchestrator.py`](file:///Users/chokkaraketankumar/Desktop/Swiggy%20-%20mcp-orchestrator/tests/test_orchestrator.py)** to automatically verify all core developer requirements:

1.  **Prioritization Scoring Test**: Checks if time, hunger, and location labels yield correct server priority order.
2.  **Closed Restaurant Filtering Test**: Confirms restaurants with status `"CLOSED"` are excluded from food search results.
3.  **Cart Limit Test**: Confirms carts exceeding ₹1000 are rejected and cleared.
4.  **COD Coupon Test**: Asserts that only Cash-on-Delivery coupons apply successfully.
5.  **Dineout Free Booking Test**: Confirms that paid Dineout reservations are blocked, and free deals pass.
6.  **Idempotency Recovery Test**: Simulates a network crash (500) during checkout, verifying that the router queries recent orders to confirm successful placement instead of double-ordering.

*To run tests:* `python -m pytest tests/test_orchestrator.py -v`

---

## 5. Walkthrough Guide for Recording your Demo Video

Use this script plan to make a professional 2-minute recording for your staging application:

### Step 1: Introduction (15 seconds)
*   Show your editor workspace.
*   *Say*: "Hi Swiggy Builders Club Team, this is Ketan. I have built the MCP Orchestrator. It's a pluggable layer that coordinates across Swiggy's Food, Instamart, and Dineout servers using active context signals."

### Step 2: Running Automated Tests (20 seconds)
*   Open the terminal in Cursor/VS Code and execute:
    `python -m pytest tests/test_orchestrator.py -v`
*   *Say*: "First, I'll run the test suite. We are validating all developer rules under simulation: closed restaurant filtering, the ₹1000 limit, COD coupon checks, and the non-idempotent order checkout recovery. All 6 tests are passing green."

### Step 3: Run the Interactive CLI & Show Prioritization (30 seconds)
*   Start the application:
    `python -m orchestrator`
*   *Say*: "Now let's launch the interactive console. It boots up in simulation mode and automatically seeds a mock user database with Indiranagar coordinates."
*   Type: `/context` to show default settings.
*   Type: `/context time_of_day 08:00` then type: `I want to eat something`. Show the logs ranking **Instamart** at the top because it's breakfast time.
*   Type: `/context time_of_day 20:00` then type: `I want to eat something`. Show the logs ranking **Food Delivery** at the top because it's dinner time.

### Step 4: Complete a Food checkout flow (45 seconds)
*   Type: `search for biryani`. Show the open restaurants.
*   Type: `add 1 Special Chicken Biryani from Meghana Foods`. Show that a COD coupon is automatically applied, and it asks for confirmation.
*   Type: `yes`. Show the order placed successfully.
*   Type: `track order`. Show the live tracking updates retrieved from SQLite.
*   Type: `/history` to show the final receipt saved in the database.

### Step 5: Wrap up (10 seconds)
*   *Say*: "Everything is working locally end-to-end. I have completed the integration agreement form and look forward to receiving my staging credentials. Thank you!"
