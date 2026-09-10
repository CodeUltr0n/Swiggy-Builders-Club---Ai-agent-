// Direct Groq LLM Conversational Client for Swiggy AI
// Allows Swiggy AI to talk to users, introduce itself, and answer questions
// without inappropriately dumping 171 dishes or triggering Food MCP on greetings.

const GROQ_API_KEY = import.meta.env.VITE_GROQ_API_KEY || "";
const GROQ_MODEL = import.meta.env.VITE_GROQ_MODEL || "qwen/qwen3.6-27b";

// Definite action keywords that mean the user wants food, groceries, or table reservations
const ORDER_ACTION_KEYWORDS = new Set([
  'biryani', 'pizza', 'burger', 'sandwich', 'pasta', 'noodles', 'dosa', 'idli', 'vada',
  'thali', 'paneer', 'chicken', 'mutton', 'fish', 'dessert', 'sweet', 'sweets', 'mithai',
  'cake', 'ice cream', 'gulab jamun', 'jalebi', 'rasgulla', 'halwa', 'pastry', 'paratha',
  'curry', 'roti', 'naan', 'chaat', 'samosa', 'fries', 'roll', 'kebab', 'tandoori',
  'milk', 'eggs', 'egg', 'bread', 'butter', 'cheese', 'grocery', 'groceries', 'vegetables',
  'fruits', 'tomato', 'onion', 'potato', 'atta', 'rice', 'dal', 'oil', 'sugar', 'salt',
  'table', 'reserve', 'reservation', 'dineout', 'booking', 'restaurant near me',
  'food', 'order', 'buy', 'hungry', 'crave', 'craving', 'menu', 'restaurant', 'find', 'show', 'get', 'want', 'eat',
  'cart', 'cary', 'basket', 'checkout'
]);

/**
 * Determine if a user's query is conversational, a greeting, or a general question
 * rather than an immediate food or grocery search.
 */
export function isConversationalOrQuestion(query) {
  if (!query) return false;
  const qLower = query.trim().toLowerCase();
  const qClean = qLower.replace(/[^\w\s]/g, ' ').trim();
  const words = qClean.split(/\s+/).filter(Boolean);

  // Order confirmations (yes/no/confirm/cancel) must ALWAYS go to the backend state machine
  const CONFIRMATION_KEYWORDS = new Set(['yes', 'no', 'y', 'n', 'confirm', 'cancel', 'ok', 'okay', 'sure', 'proceed', 'place', 'stop', 'nope', 'nah']);
  if (words.length <= 3 && words.some(w => CONFIRMATION_KEYWORDS.has(w))) {
    return false;
  }

  // Cart operations (show cart, view cart, my cart, cary) must ALWAYS go to backend orchestrator
  if (words.some(w => ['cart', 'cary', 'basket'].includes(w))) {
    return false;
  }

  // If user query mentions explicit food or grocery items, treat as order intent
  const hasOrderAction = words.some(w => ORDER_ACTION_KEYWORDS.has(w));
  if (hasOrderAction) {
    return false;
  }

  // Obvious greetings
  const greetings = new Set([
    'hi', 'hello', 'hey', 'hola', 'namaste', 'sup', 'yo', 'howdy',
    'good morning', 'good afternoon', 'good evening', 'good night', 'greetings'
  ]);
  if (greetings.has(qClean) || words.every(w => greetings.has(w))) {
    return true;
  }

  // Obvious identity and capability queries
  const identityPhrases = [
    'who are you', 'what are you', 'what can you do', 'introduce yourself',
    'tell me about yourself', 'what is your name', 'who made you', 'what is swiggy ai',
    'what do you do', 'how can you help', 'how do you work', 'what are your features',
    'what services do you have', 'help', 'help me', 'support', 'how to use',
    'what is this', 'explain', 'commands', 'options'
  ];
  if (identityPhrases.some(ip => qClean.includes(ip))) {
    return true;
  }

  // Pleasantries
  const pleasantries = [
    'thank you', 'thanks', 'thanks a lot', 'thank you so much', 'bye', 'goodbye',
    'see you', 'nice to meet you', 'how are you', 'how are you doing', 'whats up',
    'cool', 'awesome', 'great', 'ok', 'okay'
  ];
  if (pleasantries.some(p => qClean === p || qClean.startsWith(p))) {
    return true;
  }

  // General questions (starts with question word or ends with '?')
  const isQuestion = query.trim().endsWith('?') || /^(what|who|where|how|why|can you|is there|are you|tell me|do you)\b/i.test(qLower);
  if (isQuestion && !hasOrderAction) {
    return true;
  }

  // Fallback: If there are NO order action keywords, and the query is not a track/status request, route to chat.
  // This ensures random questions ("tell me a joke", "who is dhoni") don't trigger food menus.
  const hasTrackAction = words.some(w => ['track', 'status', 'where'].includes(w));
  if (!hasOrderAction && !hasTrackAction) {
    return true;
  }

  return false;
}

/**
 * Call Groq LLM directly from the frontend to converse naturally with the user.
 */
export async function fetchGroqChat(query, activeLocation = null) {
  const systemPrompt = `You are Swiggy AI, the official intelligent conversational AI assistant for Swiggy.
Your role is to talk warmly and naturally with the user, introduce yourself, and guide them across Swiggy's ecosystem.

Your Core Capabilities:
1. 🍔 Food Delivery: Search curated cuisines, find top-rated dishes (Biryani, Pizza, Sweets, etc.), and instant cart additions.
2. 🛒 Instamart: Instant 10-minute grocery delivery for fresh produce, dairy, snacks, and daily essentials.
3. 🍽️ Dineout: Reserve tables at premier restaurants and unlock exclusive dining discounts.
4. 📦 Order Management: Real-time live order tracking and cart management.

Tone & Style Guidelines:
- Greet the user warmly and introduce yourself as Swiggy AI.
- Answer their question clearly and directly.
- Summarize how you can help using friendly bullet points and emojis.
- Invite the user to tell you what they're craving or what they need today.
- Do NOT output any raw restaurant menus, dish catalogs, or pricing until the user specifically asks for food, dishes, or groceries.
- Keep the response engaging, concise, and beautifully formatted in markdown.`;

  let userMsg = query;
  if (activeLocation?.locality || activeLocation?.city) {
    userMsg += `\n(User delivery location: ${activeLocation.locality || activeLocation.city})`;
  }

  // If no Groq API key is configured in env, return the friendly introduction immediately
  if (!GROQ_API_KEY) {
    return getFallbackResponse();
  }

  try {
    const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${GROQ_API_KEY}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        model: GROQ_MODEL,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userMsg }
        ],
        max_tokens: 450,
        temperature: 0.7,
        reasoning_effort: "none"
      })
    });

    if (!response.ok) {
      const errText = await response.text();
      console.warn("Groq API call returned error status:", response.status, errText);
      throw new Error(`Groq HTTP ${response.status}`);
    }

    const data = await response.json();
    let reply = data.choices?.[0]?.message?.content?.trim() || "";

    // Clean any unclosed or leftover think tags if present
    if (reply.includes("<think>")) {
      reply = reply.replace(/<think>[\s\S]*?(?:<\/think>|$)/g, "").trim();
    }

    if (reply) {
      return reply;
    }
  } catch (err) {
    console.warn("Direct Groq API fetch error:", err);
  }

  // Graceful fallback response
  return getFallbackResponse();
}

/**
 * Return warm standard Swiggy AI introduction.
 */
export function getFallbackResponse() {
  return `Hello! 👋 I am **Swiggy AI**, your personal assistant for all things food, groceries, and dining.

Here is what I can help you with:
• 🍔 **Food Delivery**: Craving something delicious? Search dishes and order from top restaurants.
• 🛒 **Instamart**: Need groceries in 10 minutes? Get snacks, essentials, and fresh produce.
• 🍽️ **Dineout**: Reserve dining tables and unlock exclusive restaurant discounts.
• 📦 **Order Tracking**: Check your active deliveries and manage your cart anytime.

What would you like to explore or order today? 😋`;
}

