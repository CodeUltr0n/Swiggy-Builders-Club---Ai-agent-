import re

css_path = "/Users/chokkaraketankumar/Desktop/Swiggy_mcp_orchestrator/frontend-v2/src/index.css"

with open(css_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update :root variables
root_old = """  /* Authentic High-End Frosted Glass Surfaces */
  --panel-bg: rgba(255, 255, 255, 0.13);
  --surface-bg: rgba(255, 255, 255, 0.10);
  --border-color: rgba(255, 255, 255, 0.38);
  --border-subtle: rgba(255, 255, 255, 0.20);"""

root_new = """  /* Authentic High-End Clean Crystal Glass Surfaces (No milky frozen frost) */
  --panel-bg: rgba(4, 24, 15, 0.42);
  --surface-bg: rgba(4, 24, 15, 0.32);
  --border-color: rgba(255, 255, 255, 0.18);
  --border-subtle: rgba(255, 255, 255, 0.10);"""

content = content.replace(root_old, root_new)

# Inset and shadow in :root
inset_old = """  /* Frosted Glass Specifics (like reference image) */
  --glass-shadow: 0 30px 60px -12px rgba(0, 0, 0, 0.45);
  --glass-inset: inset 0 1.5px 2px 0 rgba(255, 255, 255, 0.6), inset 0 -1px 2px 0 rgba(255, 255, 255, 0.15);"""

inset_new = """  /* Clean Crystal Glass Inset Specular Highlights & Shadows */
  --glass-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
  --glass-inset: inset 0 1px 0 rgba(255, 255, 255, 0.32);"""

content = content.replace(inset_old, inset_new)

# 2. Location pill & MCP Badge: Clean glass
loc_old = """  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.35);
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.35), 0 4px 12px rgba(0,0,0,0.2);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);"""

loc_new = """  background: rgba(4, 24, 15, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.22);
  padding: 6px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-primary);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.35), 0 4px 12px rgba(0,0,0,0.3);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;"""

content = content.replace(loc_old, loc_new)

badge_old = """  background: rgba(255, 255, 255, 0.18);
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: 16px;
  padding: 5px 10px;
  cursor: pointer;
  color: var(--text-primary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  transition: all 0.2s ease;
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.35), 0 4px 12px rgba(0,0,0,0.2);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);"""

badge_new = """  background: rgba(4, 24, 15, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 16px;
  padding: 5px 10px;
  cursor: pointer;
  color: var(--text-primary);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.5px;
  transition: all 0.2s ease;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.35), 0 4px 12px rgba(0,0,0,0.3);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;"""

content = content.replace(badge_old, badge_new)

# 3. User bubble
user_bub_old = """.user-bubble {
  max-width: 65%;
  padding: 8px 16px;
  background: rgba(16, 185, 129, 0.16);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1.5px solid rgba(52, 211, 153, 0.4);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.2);"""

user_bub_new = """.user-bubble {
  max-width: 65%;
  padding: 8px 16px;
  background: rgba(16, 185, 129, 0.22);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  border: 1px solid rgba(52, 211, 153, 0.45);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.25);"""

content = content.replace(user_bub_old, user_bub_new)

# 4. Agent text content & Control plane card
agent_text_old = """  background: var(--panel-bg);
  backdrop-filter: blur(10px) saturate(120%) brightness(1.04);
  -webkit-backdrop-filter: blur(10px) saturate(120%) brightness(1.04);
  border: 1.5px solid var(--border-color);
  border-radius: 24px;
  box-shadow: var(--glass-shadow), var(--glass-inset);"""

agent_text_new = """  background: var(--panel-bg);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  border: 1px solid var(--border-color);
  border-radius: 24px;
  box-shadow: var(--glass-shadow), var(--glass-inset);"""

content = content.replace(agent_text_old, agent_text_new)

control_plane_old = """  background: var(--surface-bg);
  border: 1.5px solid var(--border-color);
  border-radius: 28px;
  padding: 24px;
  margin-bottom: 20px;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 14px;
  backdrop-filter: blur(10px) saturate(120%) brightness(1.04);
  -webkit-backdrop-filter: blur(10px) saturate(120%) brightness(1.04);
  box-shadow: var(--glass-shadow), var(--glass-inset);"""

control_plane_new = """  background: var(--surface-bg);
  border: 1px solid var(--border-color);
  border-radius: 28px;
  padding: 24px;
  margin-bottom: 20px;
  font-family: system-ui, -apple-system, sans-serif;
  font-size: 14px;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  box-shadow: var(--glass-shadow), var(--glass-inset);"""

content = content.replace(control_plane_old, control_plane_new)

# 5. Input container & Input box
input_cont_old = """  background: rgba(3, 18, 11, 0.55);
  border-top: 1.5px solid rgba(255, 255, 255, 0.16);
  backdrop-filter: blur(28px) saturate(110%);
  -webkit-backdrop-filter: blur(28px) saturate(110%);"""

input_cont_new = """  background: rgba(3, 18, 11, 0.55);
  border-top: 1px solid rgba(255, 255, 255, 0.16);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;"""

content = content.replace(input_cont_old, input_cont_new)

input_box_old = """  background: rgba(255, 255, 255, 0.12);
  border: 1.5px solid rgba(255, 255, 255, 0.28);
  border-radius: 30px;
  padding: 5px 12px;
  align-items: center;
  box-shadow: inset 0 1px 2px rgba(255, 255, 255, 0.30), 0 8px 24px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);"""

input_box_new = """  background: rgba(4, 24, 15, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.22);
  border-radius: 30px;
  padding: 5px 12px;
  align-items: center;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.30), 0 8px 24px rgba(0, 0, 0, 0.3);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;"""

content = content.replace(input_box_old, input_box_new)

# 6. Bottom nav bar
bot_nav_old = """  background: rgba(3, 18, 11, 0.65);
  backdrop-filter: blur(28px) saturate(110%);
  -webkit-backdrop-filter: blur(28px) saturate(110%);
  border-top: 1.5px solid rgba(255, 255, 255, 0.15);"""

bot_nav_new = """  background: rgba(3, 18, 11, 0.65);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  border-top: 1px solid rgba(255, 255, 255, 0.16);"""

content = content.replace(bot_nav_old, bot_nav_new)

# 7. Entity Card
entity_card_old = """.entity-card {
  flex: 0 0 280px;
  background: rgba(255, 255, 255, 0.12);
  border: 1.5px solid rgba(255, 255, 255, 0.28);
  border-radius: 24px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  backdrop-filter: blur(40px);
  -webkit-backdrop-filter: blur(40px);
  box-shadow: var(--glass-shadow), var(--glass-inset);
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.entity-card:hover {
  transform: translateY(-6px);
  background: rgba(255, 255, 255, 0.18);
  border-color: rgba(255, 255, 255, 0.5);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.35), var(--glass-inset);
}"""

entity_card_new = """.entity-card {
  flex: 0 0 280px;
  background: rgba(4, 24, 15, 0.42);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 24px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.32);
  transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.entity-card:hover {
  transform: translateY(-6px);
  background: rgba(8, 38, 25, 0.55);
  border-color: rgba(255, 255, 255, 0.40);
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.50);
}"""

content = content.replace(entity_card_old, entity_card_new)

# 8. Deck tabs pills & Filter chips
tabs_pills_old = """  background: rgba(255, 255, 255, 0.08);
  border: 1.5px solid rgba(255, 255, 255, 0.16);
  border-radius: 9999px;
  padding: 4px;
  gap: 4px;
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);"""

tabs_pills_new = """  background: rgba(4, 24, 15, 0.45);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 9999px;
  padding: 4px;
  gap: 4px;
  backdrop-filter: none;
  -webkit-backdrop-filter: none;"""

content = content.replace(tabs_pills_old, tabs_pills_new)

filter_chip_old = """.filter-chip {
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.16);
  color: rgba(255, 255, 255, 0.82);
  font-size: 11px;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 9999px;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  backdrop-filter: blur(8px);
}"""

filter_chip_new = """.filter-chip {
  background: rgba(4, 24, 15, 0.40);
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: rgba(255, 255, 255, 0.82);
  font-size: 11px;
  font-weight: 600;
  padding: 5px 12px;
  border-radius: 9999px;
  white-space: nowrap;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}"""

content = content.replace(filter_chip_old, filter_chip_new)

# 9. Dish Card
dish_card_old = """.dish-card {
  flex: 0 0 210px;
  background: rgba(255, 255, 255, 0.12);
  border: 1.5px solid rgba(255, 255, 255, 0.28);
  border-radius: 18px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: var(--glass-shadow), var(--glass-inset);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
}

.dish-card:hover {
  transform: translateY(-4px);
  background: rgba(255, 255, 255, 0.18);
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.3), var(--glass-inset);
  border-color: rgba(255, 255, 255, 0.5);
}"""

dish_card_new = """.dish-card {
  flex: 0 0 210px;
  background: rgba(4, 24, 15, 0.42);
  border: 1px solid rgba(255, 255, 255, 0.18);
  border-radius: 18px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255, 255, 255, 0.32);
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
}

.dish-card:hover {
  transform: translateY(-4px);
  background: rgba(8, 38, 25, 0.55);
  box-shadow: 0 16px 36px rgba(0, 0, 0, 0.50), inset 0 1px 0 rgba(255, 255, 255, 0.50);
  border-color: rgba(255, 255, 255, 0.40);
}"""

content = content.replace(dish_card_old, dish_card_new)

# 10. Floating cart bar
cart_bar_old = """  backdrop-filter: blur(44px);
  -webkit-backdrop-filter: blur(44px);"""

cart_bar_new = """  backdrop-filter: none;
  -webkit-backdrop-filter: none;"""

content = content.replace(cart_bar_old, cart_bar_new)

# 11. Cart drawer, orders drawer, modal container, location modal
drawers_old = """  background: rgba(6, 43, 26, 0.80);
  backdrop-filter: blur(36px) saturate(140%) brightness(1.08);
  -webkit-backdrop-filter: blur(36px) saturate(140%) brightness(1.08);
  border-top: 2px solid rgba(255, 255, 255, 0.45);
  border-left: 1.5px solid rgba(255, 255, 255, 0.25);
  border-right: 1.5px solid rgba(255, 255, 255, 0.25);"""

drawers_new = """  background: rgba(4, 24, 15, 0.90);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  border-top: 1.5px solid rgba(255, 255, 255, 0.35);
  border-left: 1px solid rgba(255, 255, 255, 0.18);
  border-right: 1px solid rgba(255, 255, 255, 0.18);"""

content = content.replace(drawers_old, drawers_new)

loc_card_old = """  background: rgba(6, 28, 18, 0.92);
  backdrop-filter: blur(36px);
  -webkit-backdrop-filter: blur(36px);
  border: 1.5px solid rgba(255, 255, 255, 0.22);"""

loc_card_new = """  background: rgba(4, 24, 15, 0.92);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  border: 1px solid rgba(255, 255, 255, 0.22);"""

content = content.replace(loc_card_old, loc_card_new)

modal_cont_old = """  background: rgba(28, 27, 36, 0.95);
  backdrop-filter: blur(30px);
  -webkit-backdrop-filter: blur(30px);
  border: 1px solid rgba(28, 27, 36, 0.8);"""

modal_cont_new = """  background: rgba(4, 24, 15, 0.95);
  backdrop-filter: none;
  -webkit-backdrop-filter: none;
  border: 1px solid rgba(255, 255, 255, 0.25);"""

content = content.replace(modal_cont_old, modal_cont_new)

# Any remaining backdrop-filter: blur in saved-address-card or search results
content = re.sub(r'backdrop-filter:\s*blur\([^)]+\)[^;]*;', 'backdrop-filter: none;', content)
content = re.sub(r'-webkit-backdrop-filter:\s*blur\([^)]+\)[^;]*;', '-webkit-backdrop-filter: none;', content)

with open(css_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Clean Glass transformation completed successfully!")
