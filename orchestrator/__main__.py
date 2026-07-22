import asyncio
import os
import sys
import yaml
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from orchestrator.memory import MemoryManager
from orchestrator.client import SwiggyMCPClient
from orchestrator.llm import LLMClient
from orchestrator.prioritizer import ContextPrioritizer
from orchestrator.router import OrchestratorRouter
from orchestrator.init_orchestrator import register_plugins

# ANSI Color codes for clean CLI visuals
ORANGE = "\033[38;5;208m"
GREEN = "\033[92m"
BLUE = "\033[94m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_banner():
    banner = f"""
{ORANGE}{BOLD}=============================================================
             SWIGGY MCP ORCHESTRATOR - DEVELOPER CLI
============================================================={RESET}
A context-aware routing & prioritization layer over Swiggy's
Food, Instamart, and Dineout MCP servers (LLM Enabled).
"""
    print(banner)

def print_help():
    help_text = f"""
{BOLD}Commands available:{RESET}
  {CYAN}/context{RESET}                  Show current simulation context (time, hunger, etc.)
  {CYAN}/context <key> <value>{RESET}    Set context value (e.g. '/context hunger_level high')
  {CYAN}/history{RESET}                  List order and booking history from DB
  {CYAN}/reset{RESET}                    Reset conversation state and carts
  {CYAN}/help{RESET}                     Show this help guide
  {CYAN}/exit{RESET}                     Exit the program
"""
    print(help_text)

async def main():
    print_banner()

    # Load settings & weights
    config_path = str(Path(__file__).parent.parent / "config" / "settings.yaml")
    weights_path = str(Path(__file__).parent.parent / "config" / "weights.yaml")

    with open(config_path) as f:
        raw_settings = yaml.safe_load(f)

    llm_config = raw_settings.get("llm", {})
    db_path = raw_settings.get("db_path", "orchestrator.db")

    # Initialize Core
    memory = MemoryManager(db_path)
    client = SwiggyMCPClient(memory)

    llm = None
    if llm_config.get("enabled", True):
        provider = llm_config.get("provider", "groq")
        model = llm_config.get("model")
        api_key = llm_config.get("api_key")
        llm = LLMClient(provider=provider, model=model, api_key=api_key)

    prioritizer = ContextPrioritizer(memory_manager=memory, config_path=weights_path, llm_client=llm)
    router = OrchestratorRouter(client=client, prioritizer=prioritizer, llm=llm)

    # Register handlers
    register_plugins(router, client)

    # Default initial context
    context = {
        "address_id": "addr_home_001",
        "address_label": "Home",
        "lat": 12.9716,
        "lng": 77.5946,
        "time_of_day": datetime.now().strftime("%H:%M"),
        "hunger_level": "medium",
        "urgency": "normal"
    }

    print(f"{GREEN}Initialization successful!{RESET}")
    print(f"Environment Mode: {BOLD}{client.env_mode.upper()}{RESET}")
    print(f"LLM Provider: {BOLD}{llm.provider.upper() if llm else 'NONE'}{RESET}")
    print(f"Memory DB: {BOLD}{db_path}{RESET}")
    print_help()

    # Pre-select Home address as starting point
    addr = memory.get_last_used_address()
    if addr:
        context["address_id"] = addr["id"]
        context["address_label"] = addr["label"]
        print(f"Current Address: {BLUE}{addr['label']}{RESET} - {addr['display_text']}")

    while True:
        try:
            # Show active stage in prompt
            prompt_suffix = ""
            if router.current_state.get("stage") == "awaiting_order_confirm":
                prompt_suffix = f" {RED}[Awaiting Confirm]{RESET}"

            # Read input
            query = input(f"\n{ORANGE}Orchestrator{prompt_suffix} > {RESET}").strip()

            if not query:
                continue

            # Handle commands
            if query.startswith("/"):
                parts = query.split()
                cmd = parts[0].lower()

                if cmd == "/exit":
                    print("Goodbye!")
                    break
                elif cmd == "/help":
                    print_help()
                elif cmd == "/reset":
                    router.reset_state()
                    # Flush carts
                    await client.call_tool("food", "flush_food_cart", {})
                    await client.call_tool("instamart", "clear_cart", {})
                    print(f"{GREEN}State and carts cleared.{RESET}")
                elif cmd == "/context":
                    if len(parts) == 1:
                        print(f"\n{BOLD}Current Context:{RESET}")
                        for k, v in context.items():
                            print(f"  {k}: {BLUE}{v}{RESET}")
                    elif len(parts) >= 3:
                        key = parts[1]
                        val = " ".join(parts[2:])
                        if key in context:
                            if key == "address_id":
                                addr_list = memory.get_addresses()
                                matched = next((a for a in addr_list if a["id"] == val), None)
                                if matched:
                                    context["address_id"] = val
                                    context["address_label"] = matched["label"]
                                    memory.set_last_used_address(val)
                                    print(f"{GREEN}Context updated: address_id = {val} ({matched['label']}){RESET}")
                                else:
                                    print(f"{RED}Address ID not found in database.{RESET}")
                            else:
                                context[key] = val
                                print(f"{GREEN}Context updated: {key} = {val}{RESET}")
                        else:
                            print(f"{RED}Invalid context key. Supported: address_id, time_of_day, hunger_level, urgency{RESET}")
                    else:
                        print(f"{RED}Usage: /context <key> <value>{RESET}")
                elif cmd == "/history":
                    orders = memory.get_past_orders()
                    if not orders:
                        print("No past orders or bookings found.")
                    else:
                        print(f"\n{BOLD}Past Orders & Bookings:{RESET}")
                        for idx, o in enumerate(orders):
                            print(f"  {idx+1}. [{o['server'].upper()}] ID: {o['id']} | Merchant: {o['merchant_name']} | Total: ₹{o['total_amount']} | Status: {o['status']} | Time: {o['timestamp']}")
                else:
                    print(f"{RED}Unknown command. Type /help to see available commands.{RESET}")
                continue

            # Process query
            res = await router.process_query(query, context)

            # Print Priority Rankings if available
            if "rankings" in res or "tool_calls" in res:
                print(f"\n{YELLOW}{BOLD}--- Orchestration Logs ---{RESET}")
                if "rankings" in res:
                    print(f"Prioritization Ranking:")
                    for idx, (srv, score, reason) in enumerate(res.get("rankings", [])):
                        star = "★" if idx == 0 else " "
                        print(f"  {star} {srv:<12} | Score: {score:<4} | Reasoning: {reason}")
                elif router.current_state.get("active_server"):
                    srv = router.current_state["active_server"]
                    print(f"Routing to server: {BLUE}{srv.upper()}{RESET}")

                if res.get("tool_calls"):
                    print(f"Tools Invoked:")
                    for call in res["tool_calls"]:
                        status_color = GREEN if call["result"].get("success", False) else RED
                        print(f"  • {BLUE}{call['tool']}{RESET}({call['args']}) -> {status_color}{'SUCCESS' if call['result'].get('success') else 'FAILED'}{RESET}")
                print(f"{YELLOW}{BOLD}--------------------------{RESET}\n")

            # Print response
            print(f"{BOLD}Agent:{RESET} {res['response_text']}")

        except KeyboardInterrupt:
            print("\nExiting CLI...")
            break
        except Exception as e:
            print(f"\n{RED}An error occurred: {str(e)}{RESET}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
