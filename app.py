import streamlit as st
import base64
import json
import re
from openai import OpenAI

# ---------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------
st.set_page_config(
    page_title="AI Food & Fitness Analyzer",
    page_icon="🍽️",
    layout="wide"
)

st.title("🍽️ AI Food & Fitness Analyzer")
st.caption("Menu analysis + fitness insights + images + chat 🤖")

# ---------------------------------------------------
# SIDEBAR – API KEY + IMAGE TOGGLE
# ---------------------------------------------------
st.sidebar.header("🔐 OpenAI API Key")
api_key = st.sidebar.text_input("Paste your OpenAI API key", type="password")

st.sidebar.divider()
generate_images = st.sidebar.checkbox(
    "🖼️ Generate food images (slower & costs more)",
    value=True
)

if not api_key:
    st.info("Enter your OpenAI API key to start")
    st.stop()

client = OpenAI(api_key=api_key)

# ---------------------------------------------------
# INIT SESSION STATE
# ---------------------------------------------------
if "fitness_filter" not in st.session_state:
    st.session_state.fitness_filter = "ALL"

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ---------------------------------------------------
# HELPERS
# ---------------------------------------------------
def extract_json(text):
    text = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(match.group()) if match else {}

def image_to_base64(file):
    return base64.b64encode(file.read()).decode("utf-8")

# ---------------------------------------------------
# FITNESS CLASSIFICATION LOGIC
# ---------------------------------------------------
def classify_fitness_goals(n):
    goals = []
    if n["calories"] <= 500 and n["fat_g"] <= 20:
        goals.append("Weight Loss 🔥")
    if n["protein_g"] >= 25:
        goals.append("Muscle Gain 💪")
    if 400 <= n["calories"] <= 650 and n["protein_g"] >= 15:
        goals.append("Lean / Maintenance ⚖️")
    if n["carbs_g"] <= 15:
        goals.append("Keto / Low Carb 🥑")
    return goals

# ---------------------------------------------------
# OPENAI CORE FUNCTIONS
# ---------------------------------------------------
def extract_menu(image_b64):
    response = client.responses.create(
        model="gpt-4o",
        input=[{
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": """
Extract the menu exactly as shown in the image.

Return ONLY JSON:
{
  "categories": [
    {
      "category": string,
      "items": [{ "name": string }]
    }
  ]
}
"""
                },
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{image_b64}"
                }
            ]
        }]
    )
    return extract_json(response.output_text)

def analyze_dish(dish):
    response = client.responses.create(
        model="gpt-4o-mini",
        input=f"""
Estimate nutrition for this dish.

Dish: {dish}

Return ONLY JSON:
{{
  "calories": number,
  "protein_g": number,
  "carbs_g": number,
  "fat_g": number
}}
"""
    )
    return extract_json(response.output_text)

def get_ingredients(dish):
    response = client.responses.create(
        model="gpt-4o-mini",
        input=f"""
List typical ingredients for this dish.

Dish: {dish}

Return ONLY JSON:
{{
  "ingredients": [string]
}}
"""
    )
    return extract_json(response.output_text).get("ingredients", [])

def generate_food_image(dish):
    prompt = f"""
Professional food photography of {dish}.
High resolution, realistic textures, restaurant plating, appetizing.
"""
    try:
        img = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1024",
            quality="high"
        )
        return base64.b64decode(img.data[0].b64_json)
    except Exception as e:
        return None

# ---------------------------------------------------
# NEED BOT
# ---------------------------------------------------
def need_bot_answer(question, results):
    context = [
        {
            "dish": r["dish"],
            "category": r["category"],
            "nutrition": r["nutrition"],
            "fitness_goals": r["fitness_goals"],
            "ingredients": r["ingredients"]
        }
        for r in results
    ]

    response = client.responses.create(
        model="gpt-4o-mini",
        input=f"""
You are a helpful food & fitness assistant.

Answer using ONLY this menu data:
{json.dumps(context, indent=2)}

Question:
{question}
"""
    )

    return response.output_text.strip()

# ---------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------
uploaded = st.file_uploader("📋 Upload menu image", type=["png", "jpg", "jpeg"])

if uploaded:
    st.image(uploaded, use_container_width=True)

    if st.button("📋 Analyze Menu"):
        with st.spinner("Extracting menu and analyzing dishes..."):
            image_b64 = image_to_base64(uploaded)
            menu = extract_menu(image_b64)

            results = []
            for cat in menu.get("categories", []):
                for item in cat["items"]:
                    nutrition = analyze_dish(item["name"])
                    ingredients = get_ingredients(item["name"])
                    fitness_goals = classify_fitness_goals(nutrition)

                    image = generate_food_image(item["name"]) if generate_images else None

                    results.append({
                        "category": cat["category"],
                        "dish": item["name"],
                        "nutrition": nutrition,
                        "fitness_goals": fitness_goals,
                        "ingredients": ingredients,
                        "image": image
                    })

            st.session_state.results = results
            st.session_state.fitness_filter = "ALL"
            st.session_state.chat_history = []

# ---------------------------------------------------
# DISPLAY RESULTS
# ---------------------------------------------------
if "results" in st.session_state:
    results = st.session_state.results

    st.header("🍽️ Dish Breakdown")

    for r in results:
        if st.session_state.fitness_filter == "ALL" or \
           st.session_state.fitness_filter in r["fitness_goals"]:

            st.subheader(r["dish"])

            if r["image"]:
                st.image(r["image"], use_container_width=True)
            else:
                st.info("🖼️ Image not available")

            n = r["nutrition"]
            st.write(
                f"Calories: {n['calories']} | "
                f"Protein: {n['protein_g']}g | "
                f"Carbs: {n['carbs_g']}g | "
                f"Fat: {n['fat_g']}g"
            )

            st.caption("🎯 Fits: " + ", ".join(r["fitness_goals"]))
            st.caption("🧾 Ingredients: " + ", ".join(r["ingredients"]))
            st.divider()

    # ---------------------------------------------------
    # NEED BOT
    # ---------------------------------------------------
    st.header("🤖 Need Bot – Ask about this menu")

    for chat in st.session_state.chat_history:
        with st.chat_message(chat["role"]):
            st.write(chat["content"])

    user_q = st.chat_input("Ask: Best dish for muscle gain?")

    if user_q:
        st.session_state.chat_history.append({"role": "user", "content": user_q})

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                ans = need_bot_answer(user_q, results)
                st.write(ans)

        st.session_state.chat_history.append({"role": "assistant", "content": ans})