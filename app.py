"""
🥗 Diet Coach WhatsApp Bot
Powered by Claude AI + Twilio
"""

import os
import json
import base64
import requests
from datetime import date
from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import anthropic

app = Flask(__name__)

# ─── Configuration ────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
DATA_FILE = "user_data.json"

# ─── Helpers ─────────────────────────────────────────────────────────────────

def load_data():
    """Load user data from JSON file."""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    """Save user data to JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user(phone):
    """Get or create user profile."""
    data = load_data()
    today = str(date.today())
    if phone not in data:
        data[phone] = {
            "setup_done": False,
            "calories_target": 0,
            "protein_target": 0,
            "carbs_target": 0,
            "fat_target": 0,
            "history": [],
            "conversation": [],
            "days": {}
        }
    # Ensure today's entry exists
    if today not in data[phone]["days"]:
        data[phone]["days"][today] = {
            "calories_consumed": 0,
            "protein_consumed": 0,
            "carbs_consumed": 0,
            "fat_consumed": 0,
            "meals": []
        }
    save_data(data)
    return data[phone], today

def save_user(phone, user_data):
    """Save a specific user's data."""
    data = load_data()
    data[phone] = user_data
    save_data(data)

def ask_claude(messages, system_prompt):
    """Call Claude API with conversation history."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=messages
    )
    return response.content[0].text

def ask_claude_with_image(messages, system_prompt, image_url):
    """Call Claude API with an image."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    # Download image
    img_response = requests.get(image_url, auth=(
        os.environ.get("TWILIO_ACCOUNT_SID", ""),
        os.environ.get("TWILIO_AUTH_TOKEN", "")
    ))
    img_b64 = base64.standard_b64encode(img_response.content).decode("utf-8")
    content_type = img_response.headers.get("Content-Type", "image/jpeg")
    
    # Build messages with image
    image_message = {
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": content_type,
                    "data": img_b64
                }
            },
            {
                "type": "text",
                "text": messages[-1]["content"] if messages else "Analyse cette image d'aliments."
            }
        ]
    }
    
    history = messages[:-1] + [image_message]
    
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=history
    )
    return response.content[0].text

def build_system_prompt(user, today):
    """Build the dynamic system prompt based on user profile."""
    day_data = user["days"].get(today, {})
    cal_consumed = day_data.get("calories_consumed", 0)
    cal_target = user.get("calories_target", 0)
    cal_remaining = cal_target - cal_consumed
    
    prot_consumed = day_data.get("protein_consumed", 0)
    carbs_consumed = day_data.get("carbs_consumed", 0)
    fat_consumed = day_data.get("fat_consumed", 0)
    
    meals_today = day_data.get("meals", [])
    meals_summary = "\n".join([f"- {m['name']}: {m['calories']} kcal" for m in meals_today]) or "Aucun repas encore."

    if not user.get("setup_done"):
        return """Tu es un coach nutritionnel bienveillant et motivant qui communique via WhatsApp en français.
Tu t'appelles Coach Alex.

OBJECTIF IMMÉDIAT : Configurer le profil nutritionnel de l'utilisateur.
Commence par te présenter chaleureusement, puis pose des questions pour définir son objectif calorique.

Si l'utilisateur connaît déjà ses objectifs, demande-lui simplement :
1. Calories journalières cibles
2. Protéines (g)
3. Glucides (g)
4. Lipides (g)

Si l'utilisateur ne connaît pas ses objectifs, guide-le avec ces questions :
1. Son objectif (perdre du poids / maintenir / prendre de la masse)
2. Son poids actuel et sa taille
3. Son niveau d'activité physique
4. Son âge et sexe

Calcule ensuite les besoins et propose un plan. Sois chaleureux, encourageant et utilise des emojis.

IMPORTANT : Quand la configuration est terminée, termine ton message avec exactement ce format JSON sur une nouvelle ligne :
SETUP_COMPLETE:{"calories":XXXX,"protein":XXX,"carbs":XXX,"fat":XX}"""
    else:
        return f"""Tu es Coach Alex, un coach nutritionnel bienveillant sur WhatsApp, qui parle français.

═══ PROFIL DE L'UTILISATEUR ═══
🎯 Objectif journalier : {cal_target} kcal
   • Protéines : {user.get('protein_target', 0)}g
   • Glucides : {user.get('carbs_target', 0)}g
   • Lipides : {user.get('fat_target', 0)}g

📊 AUJOURD'HUI ({today}) :
   • Consommé : {cal_consumed} kcal
   • Restant : {cal_remaining} kcal
   • Protéines consommées : {prot_consumed}g / {user.get('protein_target', 0)}g
   • Glucides consommés : {carbs_consumed}g / {user.get('carbs_target', 0)}g
   • Lipides consommés : {fat_consumed}g / {user.get('fat_target', 0)}g

🍽️ Repas d'aujourd'hui :
{meals_summary}
═══════════════════════════════

TES CAPACITÉS :
1. 📸 Analyser des photos d'aliments → proposer une recette adaptée avec macros
2. 🥗 Suggérer des repas selon ce qu'il reste
3. 📊 Indiquer les calories restantes à tout moment
4. ✅ Enregistrer les repas validés
5. 💪 Motiver et encourager l'utilisateur

QUAND TU REÇOIS UNE PHOTO D'ALIMENTS :
- Identifie les ingrédients visibles
- Demande si c'est pour : Petit-déjeuner / Déjeuner / Collation / Dîner
- Propose une recette simple, gourmande et équilibrée avec les ingrédients disponibles
- Indique les calories et macros estimés de la recette
- Demande si le repas est validé

QUAND UN REPAS EST VALIDÉ (mots comme "validé", "mangé", "oui j'ai mangé", "c'est bon" etc.) :
Propose d'enregistrer le repas. Termine ton message avec ce format JSON sur une nouvelle ligne :
MEAL_LOGGED:{{"name":"Nom du repas","calories":XXX,"protein":XX,"carbs":XX,"fat":XX}}

QUAND L'UTILISATEUR DEMANDE LES CALORIES RESTANTES :
Donne un résumé clair avec emojis de ce qui a été consommé et ce qu'il reste.

QUAND C'EST LA FIN DE JOURNÉE OU QUE L'UTILISATEUR LE DEMANDE :
Propose des idées de repas ou collations pour utiliser les calories restantes.

Sois toujours chaleureux, motivant, et utilise des emojis adaptés ! 🌟"""

def parse_setup(text):
    """Extract setup data if Claude completed setup."""
    if "SETUP_COMPLETE:" in text:
        parts = text.split("SETUP_COMPLETE:")
        try:
            json_str = parts[1].strip().split("\n")[0]
            return json.loads(json_str), parts[0].strip()
        except:
            pass
    return None, text

def parse_meal(text):
    """Extract meal data if Claude logged a meal."""
    if "MEAL_LOGGED:" in text:
        parts = text.split("MEAL_LOGGED:")
        try:
            json_str = parts[1].strip().split("\n")[0]
            return json.loads(json_str), parts[0].strip()
        except:
            pass
    return None, text

# ─── Main Webhook ─────────────────────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    """Receive WhatsApp messages via Twilio."""
    phone = request.form.get("From", "default_user")
    body = request.form.get("Body", "").strip()
    num_media = int(request.form.get("NumMedia", 0))
    
    user, today = get_user(phone)
    
    # Keep conversation history (last 20 messages to save tokens)
    if "conversation" not in user:
        user["conversation"] = []
    
    system_prompt = build_system_prompt(user, today)
    
    # Build user message
    user_message_content = body if body else "Bonjour !"
    
    # Add to conversation
    user["conversation"].append({"role": "user", "content": user_message_content})
    
    # Trim history
    if len(user["conversation"]) > 20:
        user["conversation"] = user["conversation"][-20:]
    
    # Call Claude (with or without image)
    try:
        if num_media > 0:
            media_url = request.form.get("MediaUrl0", "")
            reply = ask_claude_with_image(
                user["conversation"],
                system_prompt,
                media_url
            )
        else:
            reply = ask_claude(user["conversation"], system_prompt)
    except Exception as e:
        reply = f"Désolé, j'ai eu un problème technique 😅 Pouvez-vous réessayer ? (Erreur: {str(e)[:100]})"
    
    # Check if setup was completed
    if not user.get("setup_done"):
        setup_data, clean_reply = parse_setup(reply)
        if setup_data:
            user["setup_done"] = True
            user["calories_target"] = setup_data.get("calories", 2000)
            user["protein_target"] = setup_data.get("protein", 150)
            user["carbs_target"] = setup_data.get("carbs", 200)
            user["fat_target"] = setup_data.get("fat", 70)
            reply = clean_reply
    
    # Check if a meal was logged
    meal_data, clean_reply = parse_meal(reply)
    if meal_data:
        day = user["days"][today]
        day["calories_consumed"] += meal_data.get("calories", 0)
        day["protein_consumed"] += meal_data.get("protein", 0)
        day["carbs_consumed"] += meal_data.get("carbs", 0)
        day["fat_consumed"] += meal_data.get("fat", 0)
        day["meals"].append(meal_data)
        reply = clean_reply
    
    # Save assistant response to conversation
    user["conversation"].append({"role": "assistant", "content": reply})
    
    # Save user data
    save_user(phone, user)
    
    # Send response via Twilio
    resp = MessagingResponse()
    resp.message(reply)
    return str(resp)

@app.route("/", methods=["GET"])
def home():
    return "🥗 Diet Coach Bot is running! Connect via WhatsApp using Twilio."

@app.route("/reset/<phone>", methods=["GET"])
def reset_user(phone):
    """Reset a user's data (for testing)."""
    data = load_data()
    if phone in data:
        del data[phone]
        save_data(data)
        return f"User {phone} reset successfully."
    return f"User {phone} not found."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
