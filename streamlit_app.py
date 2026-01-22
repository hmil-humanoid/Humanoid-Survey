import streamlit as st
import pandas as pd
import numpy as np
import random
import time
import uuid
import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import statsmodels.api as sm
import matplotlib.pyplot as plt

# ==========================================
# 1. SETUP: FILES & CONNECTIONS
# ==========================================
# RENAMED to avoid conflict with your practice file
CONFIG_FILE = 'cloud_config.json'
SHEET_NAME = "Robot_Conjoint_Data"  # <--- Ensure this matches your Google Sheet Name exactly
ADMIN_PASSWORD = "robot123"


# --- GOOGLE SHEETS CONNECTION ---
def get_google_sheet():
    # We use st.cache_resource so we don't reconnect every single reload (speedup)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open(SHEET_NAME).sheet1
    return sheet


# --- LOCAL CONFIG MANAGEMENT (Renamed file) ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    # Default: All attributes except Price
    return [k for k in details.keys() if k != "Price"]


def save_config(features):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(features, f)


# --- ASSETS ---
icons = {
    "Tidy & Fetch": "🧺", "Deep Clean": "🧽", "Full Home Chef": "👨‍🍳",
    "Flat-Surface Glider": "🛼", "Adaptive Rover": "🚜", "Full Bipedal Walker": "🏃",
    "Light Duty (5kg)": "📕", "Medium Duty (15kg)": "🛍️", "Heavy Duty (40kg)": "🏋️",
    "Compact (1.2m)": "🤏", "Standard (1.5m)": "🙋", "Tall (1.75m)": "🦒",
    "Tech Minimalist": "📟", "Friendly Avatar": "🤖", "Realistic Human": "👤",
    "Indoor Only": "🏠", "Patio & Driveway": "🚲", "All-Terrain Garden": "🌲",
    "2 Hours": "🪫", "4 Hours": "🔋", "8 Hours": "⚡",
    "$8,000": "💲", "$20,000": "💲💲", "$65,000": "💲💲💲"
}

details = {
    "Autonomy": {
        "Tidy & Fetch": "Basic floor clearing, sorting, laundry, dishwashing. NO chemicals.",
        "Deep Clean": "Includes Tidy, Fetch, Laundry + Scrubbing toilets, mopping, chemicals.",
        "Full Home Chef": "Includes Deep Clean + Full cooking (knives, stoves)."
    },
    "Mobility": {
        "Flat-Surface Glider": "Wheels only. Single floor. No thresholds.",
        "Adaptive Rover": "Tracks/Wheels. Handles door thresholds.",
        "Full Bipedal Walker": "Human-like legs. Climbs full stairs."
    },
    "Payload": {
        "Light Duty (5kg)": "Laundry basket, books, tablet.",
        "Medium Duty (15kg)": "Crate of beer, heavy groceries, vacuum.",
        "Heavy Duty (40kg)": "Lifts furniture & heavy boxes."
    },
    "Reach": {
        "Compact (1.2m)": "Tabletops and door handles.",
        "Standard (1.5m)": "Lower kitchen cupboards/shelves.",
        "Tall (1.75m)": "High storage & top shelves."
    },
    "Face": {
        "Tech Minimalist": "Blank sensor array. Machine look.",
        "Friendly Avatar": "Flat screen with animated eyes.",
        "Realistic Human": "3D synthetic skin, realistic mimicry."
    },
    "Outdoor": {
        "Indoor Only": "Cannot leave the house.",
        "Patio & Driveway": "Paved areas. Light rain safe.",
        "All-Terrain Garden": "Grass, mud, heavy rain. Bin collection."
    },
    "Battery": {
        "2 Hours": "More frequent charging required. Autonomously charges.",
        "4 Hours": "Half-day active assistance. Autonomously charges.",
        "8 Hours": "Full work-day capability. Autonomously charges."
    },
    "Price": {
        "$8,000": "Entry Level",
        "$20,000": "Mid-Range",
        "$65,000": "Luxury"
    }
}

all_attributes = list(details.keys())

# ==========================================
# 2. UI CONFIGURATION
# ==========================================
st.set_page_config(layout="wide", page_title="Robot Conjoint (Cloud)")

if 'session_id' not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())[:8]

if 'user_votes' not in st.session_state:
    st.session_state.user_votes = 0

# Load persistent config
active_features = load_config()

# --- ADMIN SIDEBAR ---
with st.sidebar:
    st.write("🔒 **Admin Access**")
    pwd = st.text_input("Enter Password:", type="password")

    if pwd == ADMIN_PASSWORD:
        st.success("Access Granted")
        st.header("⚙️ Cloud Configuration")

        features_to_show = [a for a in all_attributes if a != "Price"]
        selected = st.multiselect(
            "Active Attributes:",
            options=features_to_show,
            default=active_features
        )

        if selected != active_features:
            save_config(selected)
            st.rerun()

        st.divider()
        if st.button("⚠️ CLEAR GOOGLE SHEET", type="primary"):
            try:
                sheet = get_google_sheet()
                sheet.clear()
                st.success("Google Sheet Cleared!")
                time.sleep(1)
            except Exception as e:
                st.error(f"Error: {e}")
    elif pwd != "":
        st.error("Incorrect Password")


# ==========================================
# 3. LOGIC & GENERATION
# ==========================================
def is_valid_profile(profile):
    if "Mobility" in active_features and "Outdoor" in active_features:
        if profile["Mobility"] == "Flat-Surface Glider" and profile["Outdoor"] == "All-Terrain Garden": return False
    if "Reach" in active_features and "Payload" in active_features:
        if profile["Reach"] == "Compact (1.2m)" and profile["Payload"] == "Heavy Duty (40kg)": return False
    if "Mobility" in active_features and "Autonomy" in active_features:
        if (profile["Mobility"] == "Full Bipedal Walker" and profile["Autonomy"] == "Full Home Chef" and profile[
            "Price"] == "$8,000"): return False
        if (profile["Mobility"] == "Flat-Surface Glider" and profile["Autonomy"] == "Tidy & Fetch" and profile[
            "Price"] == "$65,000"): return False
    return True


def calculate_overlap(p1, p2):
    check_list = active_features + ["Price"]
    return sum(1 for k in check_list if p1[k] == p2[k])


def generate_profile():
    while True:
        profile = {}
        profile["Price"] = random.choice(list(details["Price"].keys()))
        for attr in [a for a in all_attributes if a != "Price"]:
            if attr in active_features:
                profile[attr] = random.choice(list(details[attr].keys()))
            else:
                profile[attr] = list(details[attr].keys())[0]
        if is_valid_profile(profile): return profile


# --- GOOGLE SHEETS SAVING ---
def refresh_profiles():
    max_attempts = 100
    pA = generate_profile()
    for _ in range(max_attempts):
        pB = generate_profile()
        threshold = max(2, len(active_features) - 2)
        if pA != pB and calculate_overlap(pA, pB) < threshold: break
    for _ in range(max_attempts):
        pC = generate_profile()
        if pC != pA and pC != pB and calculate_overlap(pA, pC) < threshold and calculate_overlap(pB,
                                                                                                 pC) < threshold: break

    st.session_state.profile_A = pA
    st.session_state.profile_B = pB
    st.session_state.profile_C = pC


if 'profile_A' not in st.session_state: refresh_profiles()


def save_choice(choice_type, chosen=None, rejected1=None, rejected2=None):
    sess_id = st.session_state.session_id
    rows_to_add = []

    # Define Column Order
    cols = ["Resp_ID", "Choice_Type", "Is_Chosen", "Option_Label", "Price"] + all_attributes

    def format_row(profile, label, is_chosen, c_type):
        row_data = [sess_id, c_type, is_chosen, label, profile["Price"]]
        for attr in all_attributes:
            row_data.append(profile.get(attr, ""))
        return row_data

    if choice_type == "None":
        rows_to_add.append(format_row(st.session_state.profile_A, "A", 0, "None"))
        rows_to_add.append(format_row(st.session_state.profile_B, "B", 0, "None"))
        rows_to_add.append(format_row(st.session_state.profile_C, "C", 0, "None"))
        msg = "🚫 'None' recorded."
    else:
        rows_to_add.append(format_row(chosen, choice_type, 1, "Buy"))
        rows_to_add.append(format_row(rejected1, "Other", 0, "Buy"))
        rows_to_add.append(format_row(rejected2, "Other", 0, "Buy"))
        msg = "✅ Vote Saved!"

    # WRITE TO CLOUD
    try:
        sheet = get_google_sheet()
        # Check if empty (add headers)
        if len(sheet.get_all_values()) == 0:
            sheet.append_row(cols)

        for r in rows_to_add:
            sheet.append_row(r)

        st.session_state.user_votes += 1
        refresh_profiles()
        st.toast(msg)
        time.sleep(0.5)

    except Exception as e:
        st.error(f"Cloud Save Error: {e}")


# ==========================================
# 4. MAIN UI
# ==========================================
st.markdown("""
<style>
    .block-container { padding-top: 1rem; padding-bottom: 3rem; }
    .stButton button { width: 100%; border-radius: 8px; font-weight: bold; background-color: #f0f2f6; }
    .stButton button:hover { background-color: #e0e2e6; border-color: #0066cc; color: #0066cc; }
    .price-tag { 
        font-size: 18px; font-weight: bold; color: #0066cc; 
        background-color: #e6f0ff; padding: 6px 10px; 
        border-radius: 6px; display: inline-block; margin-bottom: 12px;
    }
    .attr-row { margin-bottom: 8px; border-bottom: 1px solid #f0f0f0; padding-bottom: 6px; }
    .attr-label { font-size: 13px; font-weight: 700; color: #555; text-transform: uppercase; letter-spacing: 0.5px; }
    .attr-val { font-size: 15px; font-weight: 600; color: #222; margin-left: 5px; }
    .attr-desc { font-size: 13px; color: #666; display: block; margin-top: 2px; line-height: 1.3; }
    .stToast { background-color: #4CAF50; color: white; }
</style>
""", unsafe_allow_html=True)

st.title("🤖 Robot Feature Survey (Cloud)")

if st.session_state.user_votes < 1:
    st.info("**Welcome!** Select the robot you would **actually buy**. Complete 10 rounds.")
elif st.session_state.user_votes < 10:
    st.progress(st.session_state.user_votes / 10)
    st.caption(f"Progress: {st.session_state.user_votes}/10")
else:
    st.success(f"🎉 **Target Reached!** ({st.session_state.user_votes} votes).")

col1, col2, col3 = st.columns(3)


def display_option(col, profile, label, other1, other2):
    with col:
        with st.container(border=True):
            st.subheader(f"Option {label}")
            st.markdown(f"<div class='price-tag'>{icons[profile['Price']]} {profile['Price']}</div>",
                        unsafe_allow_html=True)
            for attr in active_features:
                val = profile[attr]
                html = f"<div class='attr-row'><span class='attr-label'>{attr}</span> <span class='attr-val'>{icons.get(val, '')} {val}</span><span class='attr-desc'>{details[attr][val]}</span></div>"
                st.markdown(html, unsafe_allow_html=True)
            if st.button(f"Select {label}", key=f"btn_{label}_{st.session_state.user_votes}", use_container_width=True):
                save_choice(label, profile, other1, other2)
                st.rerun()


display_option(col1, st.session_state.profile_A, "A", st.session_state.profile_B, st.session_state.profile_C)
display_option(col2, st.session_state.profile_B, "B", st.session_state.profile_A, st.session_state.profile_C)
display_option(col3, st.session_state.profile_C, "C", st.session_state.profile_A, st.session_state.profile_B)

st.markdown("<br>", unsafe_allow_html=True)
col_none1, col_none2, col_none3 = st.columns([1, 2, 1])
with col_none2:
    if st.button("🚫 I wouldn't choose any of these", use_container_width=True):
        save_choice("None")
        st.rerun()

st.markdown("---")

# ==========================================
# 5. ANALYTICS (CLOUD)
# ==========================================
with st.expander("📊 Analytics Dashboard (Live from Cloud)", expanded=False):
    try:
        sheet = get_google_sheet()
        data = sheet.get_all_records()
        df = pd.DataFrame(data)

        if not df.empty:
            df_buy = df[df['Choice_Type'] == 'Buy']

            total_responses = len(df) // 3
            unique_respondents = df['Resp_ID'].nunique()
            avg_resp = total_responses / unique_respondents if unique_respondents > 0 else 0
            walk_away_rate = ((total_responses - (
                        len(df_buy) // 3)) / total_responses) * 100 if total_responses > 0 else 0

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Votes", total_responses)
            m2.metric("Unique People", unique_respondents)
            m3.metric("Avg Votes/Person", f"{avg_resp:.1f}")
            m4.metric("Walk-Away Rate", f"{walk_away_rate:.1f}%")

            if len(df_buy) // 3 >= 5:
                # Prepare data for regression
                analysis_cols = active_features + ["Price"]

                # Filter to active columns only for X
                X_raw = df_buy[analysis_cols]
                y = df_buy['Is_Chosen']

                # Get dummies
                X = pd.get_dummies(X_raw, drop_first=True).astype(int)
                X = sm.add_constant(X)

                model = sm.OLS(y, X).fit()
                utilities = model.params[1:]


                def get_utility(attr, level):
                    key = f"{attr}_{level}"
                    if key in utilities: return utilities[key]
                    return 0


                st.divider()
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.subheader("Relative Importance")
                    ranges = {}
                    for attr in analysis_cols:
                        scores = [get_utility(attr, l) for l in details[attr]]
                        ranges[attr] = max(scores) - min(scores)
                    tot = sum(ranges.values())
                    imp = {k: (v / tot) * 100 for k, v in ranges.items()}
                    imp_df = pd.DataFrame(list(imp.items()), columns=['Attribute', 'Value']).sort_values('Value')
                    fig1, ax1 = plt.subplots(figsize=(6, 4))
                    ax1.barh(imp_df['Attribute'], imp_df['Value'], color='#4e79a7')
                    plt.tight_layout();
                    st.pyplot(fig1)

                with col_d2:
                    st.subheader("Win Rate (Raw)")
                    win_rates = {}
                    for attr in analysis_cols:
                        for lvl in details[attr]:
                            mask = df_buy[attr] == lvl
                            if mask.sum() > 0:
                                icon_str = icons.get(lvl, '')
                                label_str = f"{icon_str} {lvl}"
                                win_rates[label_str] = df_buy[mask]['Is_Chosen'].mean() * 100
                    sorted_w = sorted(win_rates.items(), key=lambda x: x[1])[-15:]
                    fig3, ax3 = plt.subplots(figsize=(6, 8))
                    ax3.barh([x[0] for x in sorted_w], [x[1] for x in sorted_w], color='orange')
                    plt.tight_layout();
                    st.pyplot(fig3)
            else:
                st.info("Collecting more data...")
        else:
            st.write("Google Sheet is empty.")
    except Exception as e:
        st.write("Connecting to Cloud...")