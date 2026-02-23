"""
🥗 Diet Coach WhatsApp Bot
Coach Mika — Powered by Claude AI + Twilio
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
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_user(phone):
    data = load_data()
    today = str(date.today())
    if phone not in data:
        data[phone] = {
            "setup_done": False,
            "first_name": "",
            "calories_target": 0,
            "protein_target": 0,
            "carbs_target": 0,
            "fat_target": 0,
            "history": [],
            "conversation": [],
            "days": {}
        }
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
    data = load_data()
    data[phone] = user_data
    save_data(data)

def ask_claude(messages, system_prompt):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=messages
    )
    return response.content[0].text

def ask_claude_with_image(messages, system_prompt, image_url):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    img_response = requests.get(image_url, auth=(
        os.environ.get("TWILIO_ACCOUNT_SID", ""),
        os.environ.get("TWILIO_AUTH_TOKEN", "")
    ))
    img_b64 = base64.standard_b64encode(img_response.content).decode("utf-8")
    content_type = img_response.headers.get("Content-Type", "image/jpeg")
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
    day_data = user["days"].get(today, {})
    cal_consumed = day_data.get("calories_consumed", 0)
    cal_target = user.get("calories_target", 0)
    cal_remaining = cal_target - cal_consumed
    prot_consumed = day_data.get("protein_consumed", 0)
    carbs_consumed = day_data.get("carbs_consumed", 0)
    fat_consumed = day_data.get("fat_consumed", 0)
    meals_today = day_data.get("meals", [])
    meals_summary = "\n".join([f"- {m['name']}: {m['calories']} kcal" for m in meals_today]) or "Aucun repas encore."
    first_name = user.get("first_name", "")
    prenom_str = f"Tu t'adresses à {first_name}. Utilise son prénom régulièrement pour personnaliser les échanges." if first_name else ""

    if not user.get("setup_done"):
        return f"""Tu es Mika, un coach nutritionnel bienveillant, motivant et chaleureux qui communique via WhatsApp en français.
Tu as une vraie personnalité de coach : enthousiaste, encourageant, professionnel mais accessible.

PREMIÈRE PRISE DE CONTACT — fais les choses dans cet ordre précis :

1. Présente-toi chaleureusement en tant que Mika, coach nutritionnel personnel.

2. Explique brièvement tout ce qu'il est possible de faire avec toi (en utilisant des emojis pour rendre ça vivant) :
   📸 Prendre en photo son frigo ou ses aliments pour générer une recette adaptée à ses objectifs
   🔥 Connaître à tout moment les calories restantes dans la journée
   🥗 Recevoir des propositions de repas équilibrés, simples et gourmands
   📊 Faire un point complet sur les macros et calories consommées
   🚶 Calculer comment compenser un écart grâce à des pas supplémentaires ou une activité physique
   💧 Être rappelé à bien s'hydrater tout au long de la journée
   
3. Demande le prénom de la personne.

4. Une fois le prénom obtenu, pose UNE SEULE question simple : "Est-ce que tu connais déjà ta cible calorique journalière ?"

   → Si OUI : demande les 4 valeurs en une seule fois (calories, protéines, glucides, lipides)
   → Si NON : pose ces questions une par une de façon naturelle et conversationnelle :
      - Son objectif principal (perdre du poids / maintenir / prendre de la masse)
      - Son poids et sa taille
      - Son niveau d'activité (sédentaire / légèrement actif / actif / très actif)
      - Son âge et son sexe
      Puis calcule ses besoins en utilisant la formule de Harris-Benedict et les références de la table Ciqual pour les macros.

5. Une fois les objectifs définis, explique brièvement le rôle de chaque macronutriment avec des emojis :
   💪 Protéines : construction et réparation musculaire, satiété
   ⚡ Glucides : carburant principal du corps et du cerveau
   🫀 Lipides : hormones, absorption des vitamines, santé cellulaire

6. Confirme le plan personnalisé de façon enthousiaste et encourage la personne à commencer.

IMPORTANT : Quand la configuration est terminée, termine ton message avec exactement ce format JSON sur une nouvelle ligne :
SETUP_COMPLETE:{{"calories":XXXX,"protein":XXX,"carbs":XXX,"fat":XX,"first_name":"PRENOM"}}

Sois chaleureux, naturel, utilise des emojis et donne l'impression d'un vrai coach personnel ! 🌟"""

    else:
        return f"""Tu es Mika, coach nutritionnel personnel bienveillant et motivant sur WhatsApp. Tu parles français.
{prenom_str}

═══ PROFIL ═══
🎯 Objectif journalier : {cal_target} kcal
   💪 Protéines : {user.get('protein_target', 0)}g
   ⚡ Glucides : {user.get('carbs_target', 0)}g
   🫀 Lipides : {user.get('fat_target', 0)}g

📊 AUJOURD'HUI ({today}) :
   🔥 Consommé : {cal_consumed} kcal
   ✅ Restant : {cal_remaining} kcal

🍽️ Repas du jour :
{meals_summary}
═══════════════

TES CAPACITÉS :
1. 📸 Analyser des photos d'aliments ou du frigo → proposer une recette adaptée
2. 🥗 Suggérer des repas selon les calories restantes
3. 📊 Donner un point calorique à tout moment
4. ✅ Enregistrer les repas validés
5. 🚶 Calculer les pas ou activité pour compenser un écart
6. 💪 Motiver et encourager personnellement

RÈGLES IMPORTANTES :
- Utilise les valeurs nutritionnelles de la table Ciqual française comme référence pour les aliments
- Rappelle de boire de l'eau régulièrement (objectif 2L/jour) 💧, surtout si la personne ne l'a pas mentionné
- Lors des récaps de repas : indique UNIQUEMENT le total calorique. Ne donne les macros détaillées QUE si la personne le demande explicitement
- Sois toujours positif, même si la personne a dépassé ses calories : encourage sans culpabiliser
- Utilise le prénom régulièrement pour personnaliser les échanges
- Donne l'impression d'un vrai coach humain et bienveillant

QUAND TU REÇOIS UNE PHOTO D'ALIMENTS :
- Identifie les ingrédients visibles
- Demande si c'est pour : Petit-déjeuner 🌅 / Déjeuner 🌞 / Collation 🍎 / Dîner 🌙
- Propose une recette simple, gourmande et adaptée aux calories restantes
- Indique le total calorique de la recette (et les macros seulement si demandé)
- Demande si le repas est validé

QUAND UN REPAS EST VALIDÉ (mots comme "validé", "mangé", "c'est bon", "oui", "top") :
Confirme avec enthousiasme et propose d'enregistrer. Termine avec ce JSON sur une nouvelle ligne :
MEAL_LOGGED:{{"name":"Nom du repas","calories":XXX,"protein":XX,"carbs":XX,"fat":XX}}

QUAND ON DEMANDE LES CALORIES RESTANTES OU UN POINT JOURNALIER :
Donne un résumé clair, motivant, avec les calories consommées et restantes.
Propose une idée de repas ou collation adaptée aux calories restantes.
Ne donne les macros détaillées QUE si la personne le demande.

QUAND ON PARLE DE COMPENSER UN ÉCART PAR L'ACTIVITÉ :
Calcule le nombre de pas ou minutes d'activité nécessaires pour brûler les calories en excès.
Exemples de référence : 1000 pas ≈ 40-50 kcal / 30 min marche ≈ 150 kcal / 30 min vélo ≈ 250 kcal

Sois toujours chaleureux, motivant, personnalisé et utilise des emojis ! 🌟"""

def parse_setup(text):
    if "SETUP_COMPLETE:" in text:
        parts = text.split("SETUP_COMPLETE:")
        try:
            json_str = parts[1].strip().split("\n")[0]
            return json.loads(json_str), parts[0].strip()
        except:
            pass
    return None, text

def parse_meal(text):
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
    phone = request.form.get("From", "default_user")
    body = request.form.get("Body", "").strip()
    num_media = int(request.form.get("NumMedia", 0))

    user, today = get_user(phone)

    if "conversation" not in user:
        user["conversation"] = []

    system_prompt = build_system_prompt(user, today)
    user_message_content = body if body else "Bonjour !"
    user["conversation"].append({"role": "user", "content": user_message_content})

    if len(user["conversation"]) > 20:
        user["conversation"] = user["conversation"][-20:]

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
        reply = f"Désolé, j'ai eu un petit souci technique 😅 Peux-tu réessayer ? (Erreur: {str(e)[:100]})"

    # Check setup completion
    if not user.get("setup_done"):
        setup_data, clean_reply = parse_setup(reply)
        if setup_data:
            user["setup_done"] = True
            user["calories_target"] = setup_data.get("calories", 2000)
            user["protein_target"] = setup_data.get("protein", 150)
            user["carbs_target"] = setup_data.get("carbs", 200)
            user["fat_target"] = setup_data.get("fat", 70)
            user["first_name"] = setup_data.get("first_name", "")
            reply = clean_reply

    # Check meal logging
    meal_data, clean_reply = parse_meal(reply)
    if meal_data:
        day = user["days"][today]
        day["calories_consumed"] += meal_data.get("calories", 0)
        day["protein_consumed"] += meal_data.get("protein", 0)
        day["carbs_consumed"] += meal_data.get("carbs", 0)
        day["fat_consumed"] += meal_data.get("fat", 0)
        day["meals"].append(meal_data)
        reply = clean_reply

    user["conversation"].append({"role": "assistant", "content": reply})
    save_user(phone, user)

    resp = MessagingResponse()
    resp.message(reply)
    return str(resp)

@app.route("/", methods=["GET"])
def home():
    return "🥗 Diet Coach Bot — Coach Mika est en ligne ! Connectez-vous via WhatsApp."

@app.route("/reset/<phone>", methods=["GET"])
def reset_user(phone):
    data = load_data()
    if phone in data:
        del data[phone]
        save_data(data)
        return f"Utilisateur {phone} réinitialisé."
    return f"Utilisateur {phone} introuvable."

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
