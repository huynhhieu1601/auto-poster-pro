import streamlit as st
import sqlite3
import hashlib
import secrets
from openai import OpenAI
import requests
import json
import os
import base64
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import pandas as pd
import time
import threading
import schedule as schedule_lib

# ============================================================
# CONSTANTS
# ============================================================
DB_FILE = "/tmp/autoposter_data.db"

LOCAL_API_BASE = "http://localhost:3003/v1"
LOCAL_API_KEY = "AQ.Ab8RN6IjV-QWSXPxSIydANNNuh8a2bdOh_wkBRWd_diI7s67Tw"
LOCAL_PROJECT_ID = "777992117459"
LOCAL_MODEL = "gemini-3.6-flash"
LOCAL_IMAGE_MODEL = "gemini-3.1-flash-image"

DEFAULT_SERPAPI_KEY = "eb7a6f72642ad4ffd0dc63c39e2a129d577825b86837b56a4bd86ca233eaf6f6"

# ============================================================
# STREAMLIT PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="WP Auto-Poster PRO",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# MODERN UI — TAILWIND CSS + CUSTOM FIXES
# ============================================================
st.markdown("""
<script src="https://cdn.tailwindcss.com"></script>
<style>
    /* --- TAILWIND BASE RESET --- */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="st-"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* --- FIX SIDEBAR WIDTH & TEXT WRAPPING --- */
    [data-testid="stSidebar"] {
        min-width: 280px !important;
        max-width: 340px !important;
        background: linear-gradient(180deg, #1E1B4B 0%, #312E81 100%) !important;
        border-right: 1px solid rgba(255,255,255,0.05) !important;
    }
    [data-testid="stSidebar"] * {
        word-break: normal !important;
        white-space: normal !important;
        overflow-wrap: break-word !important;
    }
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stMarkdown {
        color: #E0E7FF !important;
        white-space: normal !important;
        word-break: normal !important;
    }
    /* Prevent vertical text in radio buttons */
    [data-testid="stSidebar"] .stRadio label,
    [data-testid="stSidebar"] [data-baseweb="radio"] label {
        writing-mode: horizontal-tb !important;
        text-orientation: mixed !important;
        white-space: nowrap !important;
        display: flex !important;
        align-items: center !important;
    }

    /* --- TOP HEADER BANNER --- */
    .header-banner {
        background: linear-gradient(135deg, #6D28D9 0%, #7C3AED 50%, #8B5CF6 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 10px 25px -5px rgba(124, 58, 237, 0.3);
    }
    .header-banner h1 { font-size: 1.75rem; font-weight: 700; color: white !important; }
    .header-banner p { font-size: 0.9rem; opacity: 0.9; color: rgba(255,255,255,0.85) !important; }

    /* --- TAILWIND CARD WRAPPER --- */
    .card-box {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 0.75rem;
        padding: 1.25rem;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
        margin-bottom: 1rem;
    }

    /* --- SIDEBAR COMPONENTS --- */
    .sidebar-brand { font-size: 1.15rem; font-weight: 700; color: #A78BFA !important; }
    .sidebar-user-card {
        background: rgba(255,255,255,0.06);
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
        border: 1px solid rgba(255,255,255,0.08);
    }
    .sidebar-avatar {
        width: 40px; height: 40px; border-radius: 10px;
        background: linear-gradient(135deg, #7C3AED, #A78BFA);
        display: flex; align-items: center; justify-content: center;
        font-size: 1.1rem; font-weight: 700; color: white;
    }
    .sidebar-status {
        display: inline-block; width: 8px; height: 8px;
        border-radius: 50%; background: #10B981; margin-right: 4px;
    }
    .sidebar-info-box {
        background: rgba(124, 58, 237, 0.12);
        border: 1px solid rgba(124, 58, 237, 0.2);
        border-radius: 12px; padding: 0.75rem 1rem;
        font-size: 0.8rem; color: #C7D2FE; margin-top: 1rem;
    }

    /* --- BUTTONS --- */
    .stButton > button {
        width: 100%; border-radius: 0.5rem; font-weight: 600;
        font-size: 0.9rem !important; padding: 0.5rem 1.5rem !important;
        transition: all 0.2s !important; border: none !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #7C3AED, #6D28D9) !important;
        color: white !important; box-shadow: 0 4px 12px rgba(124, 58, 237, 0.3) !important;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(124, 58, 237, 0.4) !important;
        background: linear-gradient(135deg, #8B5CF6, #7C3AED) !important;
    }
    .stButton > button[kind="secondary"] { background: #F3F4F6 !important; color: #374151 !important; }
    .stButton > button[kind="secondary"]:hover { background: #E5E7EB !important; }

    /* --- INPUTS --- */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        border-radius: 10px !important; border: 1.5px solid #E5E7EB !important;
        transition: border-color 0.2s !important; font-size: 0.9rem !important;
    }
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #7C3AED !important; box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.1) !important;
    }

    /* --- BADGES --- */
    .badge-success { display: inline-block; background: #D1FAE5; color: #065F46; padding: 0.15rem 0.65rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
    .badge-purple { display: inline-block; background: #EDE9FE; color: #5B21B6; padding: 0.15rem 0.65rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
    .badge-amber { display: inline-block; background: #FEF3C7; color: #92400E; padding: 0.15rem 0.65rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }

    /* --- SELECT / RADIO --- */
    .stSelectbox > div > div { border-radius: 10px !important; }
    [data-testid="stRadio"] > div { gap: 0.5rem; }

    /* --- DATAFRAME --- */
    [data-testid="stDataFrame"] table { border-collapse: separate; border-spacing: 0; border-radius: 12px; overflow: hidden; }
    [data-testid="stDataFrame"] thead th {
        background: #F8FAFC !important; color: #64748B !important; font-size: 0.7rem !important;
        text-transform: uppercase !important; font-weight: 600 !important; letter-spacing: 0.5px;
        padding: 0.75rem 1rem !important; border-bottom: 2px solid #E2E8F0 !important;
    }
    [data-testid="stDataFrame"] tbody td { border-bottom: 1px solid #F1F5F9 !important; padding: 0.75rem 1rem !important; font-size: 0.85rem !important; }

    /* --- MISC --- */
    [data-testid="stExpander"] { border-radius: 12px !important; border: 1px solid #E5E7EB !important; box-shadow: none !important; }
    .login-card {
        max-width: 420px; margin: 3rem auto; background: white; border-radius: 20px;
        padding: 2.5rem; box-shadow: 0 20px 60px -20px rgba(0,0,0,0.1); border: 1px solid #F3F4F6;
    }
    .login-card h2 {
        background: linear-gradient(135deg, #7C3AED, #6D28D9);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800; font-size: 1.5rem;
    }
    .website-row {
        background: white; border: 1px solid #F3F4F6; border-radius: 12px; padding: 1rem 1.25rem;
        margin-bottom: 0.5rem; display: flex; align-items: center; justify-content: space-between; transition: box-shadow 0.2s;
    }
    .website-row:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.06); }
    .section-divider { height: 1px; background: linear-gradient(90deg, transparent, #E5E7EB, transparent); margin: 1.5rem 0; }
    .block-container { padding-top: 2rem; }
    .stTabs [data-baseweb="tab"] { font-weight: 500 !important; padding: 0.6rem 1.25rem !important; border-radius: 10px 10px 0 0 !important; }
    .stTabs [aria-selected="true"] { color: #7C3AED !important; border-bottom: 3px solid #7C3AED !important; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SQLITE DATABASE SETUP
# ============================================================
def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            UNIQUE(user_id, key),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS websites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            site_name TEXT NOT NULL,
            wp_url TEXT NOT NULL DEFAULT '',
            wp_username TEXT NOT NULL DEFAULT '',
            wp_app_password TEXT NOT NULL DEFAULT '',
            woo_ck TEXT NOT NULL DEFAULT '',
            woo_cs TEXT NOT NULL DEFAULT '',
            brand_voice_prompt TEXT NOT NULL DEFAULT 'You are an expert SEO content writer. Write in a professional, engaging tone with clear explanations.',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            site_name TEXT DEFAULT '',
            keyword TEXT,
            date TEXT,
            status TEXT,
            content_type TEXT DEFAULT 'post',
            link TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    try:
        cursor.execute("ALTER TABLE history ADD COLUMN content_type TEXT DEFAULT 'post'")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE history ADD COLUMN site_name TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN credits REAL DEFAULT 0")
        conn.commit()
    except sqlite3.OperationalError:
        pass
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS credit_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            type TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    cursor.execute("SELECT COUNT(*) as cnt FROM users")
    if cursor.fetchone()["cnt"] == 0:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, credits) VALUES (?, ?, ?, ?)",
            ("admin", hashlib.sha256("admin123".encode()).hexdigest(), "admin", 100000)
        )
        conn.commit()
    conn.close()

init_db()

# ============================================================
# CREDIT SYSTEM HELPERS
# ============================================================
def get_user_credits(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT credits FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row["credits"] is not None:
        return float(row["credits"])
    return 0.0

def add_credits(user_id, amount, description="Nạp điểm"):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = COALESCE(credits, 0) + ? WHERE id = ?", (amount, user_id))
    cursor.execute(
        "INSERT INTO credit_transactions (user_id, amount, type, description) VALUES (?, ?, 'credit', ?)",
        (user_id, amount, description)
    )
    conn.commit()
    conn.close()

def deduct_user_credit(user_id, cost):
    current = get_user_credits(user_id)
    if current < cost:
        return False
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET credits = credits - ? WHERE id = ?", (cost, user_id))
    cursor.execute(
        "INSERT INTO credit_transactions (user_id, amount, type, description) VALUES (?, ?, 'debit', ?)",
        (user_id, cost, f"Thanh toán bài viết: {cost:,.0f} VNĐ")
    )
    conn.commit()
    conn.close()
    return True

def get_cost_per_post():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM user_settings WHERE user_id IN (SELECT id FROM users WHERE role='admin' LIMIT 1) AND key='cost_per_post'")
    row = cursor.fetchone()
    conn.close()
    if row and row["value"]:
        try:
            return float(row["value"])
        except (ValueError, TypeError):
            pass
    return 2000.0

# ============================================================
# SESSION STATE INITIALIZATION
# ============================================================
defaults = {
    "generated_outline": "",
    "logged_in": False,
    "user_id": None,
    "username": "",
    "worker_started": False,
    "nav_view": "🚀 Content Generator",
    "editing_site": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ============================================================
# AUTH HELPERS
# ============================================================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password, role='user'):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                       (username, hash_password(password), role))
        conn.commit()
        return True, "Registration successful!"
    except sqlite3.IntegrityError:
        return False, "Username already exists."
    finally:
        conn.close()

def login_user(username, password):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    if user and user["password_hash"] == hash_password(password):
        role = user["role"] or "user"
        if str(username).lower() == "admin" and role != "admin":
            cursor.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user["id"],))
            conn.commit()
            role = "admin"
        conn.close()
        st.session_state.logged_in = True
        st.session_state.user_id = user["id"]
        st.session_state.username = user["username"]
        st.session_state.user_role = role
        return True, "Login successful!"
    conn.close()
    return False, "Invalid username or password."

def logout_user():
    for key in ["logged_in", "user_id", "username", "user_role", "generated_outline", "editing_site"]:
        if key in st.session_state:
            st.session_state[key] = False if key == "logged_in" else (None if key in ["user_id", "editing_site", "user_role"] else "")
    st.session_state.worker_started = False

# ============================================================
# USER SETTINGS HELPERS
# ============================================================
def save_user_setting(user_id, key, value):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_settings (user_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value
    """, (user_id, key, value))
    conn.commit()
    conn.close()

def get_all_user_settings(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, value FROM user_settings WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

# ============================================================
# WEBSITE CRUD HELPERS
# ============================================================
def get_websites(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM websites WHERE user_id = ? ORDER BY id", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_website_by_id(website_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM websites WHERE id = ?", (website_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_website_by_name(user_id, site_name):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM websites WHERE user_id = ? AND site_name = ?", (user_id, site_name))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def save_website(user_id, site_name, wp_url, wp_username, wp_app_password,
                 woo_ck, woo_cs, brand_voice_prompt, website_id=None):
    conn = get_db()
    cursor = conn.cursor()
    if website_id:
        cursor.execute("""
            UPDATE websites SET site_name=?, wp_url=?, wp_username=?, wp_app_password=?,
            woo_ck=?, woo_cs=?, brand_voice_prompt=?
            WHERE id=? AND user_id=?
        """, (site_name, wp_url, wp_username, wp_app_password,
              woo_ck, woo_cs, brand_voice_prompt, website_id, user_id))
    else:
        cursor.execute("""
            INSERT INTO websites (user_id, site_name, wp_url, wp_username, wp_app_password,
                                 woo_ck, woo_cs, brand_voice_prompt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, site_name, wp_url, wp_username, wp_app_password,
              woo_ck, woo_cs, brand_voice_prompt))
    conn.commit()
    conn.close()

def delete_website(website_id, user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM websites WHERE id = ? AND user_id = ?", (website_id, user_id))
    conn.commit()
    conn.close()

# ============================================================
# HISTORY HELPERS
# ============================================================
def save_history_entry(user_id, site_name, keyword, date, status, content_type, link):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO history (user_id, site_name, keyword, date, status, content_type, link) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, site_name, keyword, date, status, content_type, link)
    )
    conn.commit()
    conn.close()

def load_history(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT site_name, keyword, date, status, content_type, link FROM history WHERE user_id = ? ORDER BY id DESC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ============================================================
# CORE GENERATION HELPERS (Parameterized)
# ============================================================
def generate_text(prompt, system_prompt, api_base, api_key, project_id, model, temperature=0.7):
    client = OpenAI(base_url=api_base, api_key=api_key,
                    default_headers={"x-goog-project-id": project_id})
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
        temperature=temperature)
    return r.choices[0].message.content

def generate_image(prompt, api_base, api_key, project_id, model, n=1, size="1024x1024"):
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json",
               "x-goog-project-id": project_id}
    r = requests.post(f"{api_base.rstrip('/')}/images/generations", json={"model": model, "prompt": prompt, "n": n, "size": size},
                      headers=headers, timeout=120)
    r.raise_for_status()
    return r.json().get("data", [])

# ============================================================
# SERPAPI — MULTI-KEY WITH USAGE TRACKING & ROTATION
# ============================================================
def get_serpapi_keys():
    keys_str = st.session_state.get("serpapi_keys", "")
    if not keys_str:
        return []
    return [k.strip() for k in keys_str.split("\n") if k.strip()]

def check_serpapi_account(api_key):
    try:
        r = requests.get(f"https://serpapi.com/account?api_key={api_key}", timeout=10)
        if r.status_code != 200:
            return {"valid": False, "plan": "N/A", "searches_per_month": 0, 
                    "plan_searches_left": 0, "total_searches": 0, 
                    "error": f"HTTP {r.status_code}"}
        data = r.json()
        return {
            "valid": True,
            "plan": data.get("plan_name", "Unknown"),
            "searches_per_month": data.get("plan_searches_per_month", 0),
            "plan_searches_left": data.get("plan_searches_left", 0),
            "total_searches": data.get("total_searches", 0),
            "error": None
        }
    except Exception as e:
        return {"valid": False, "plan": "N/A", "searches_per_month": 0,
                "plan_searches_left": 0, "total_searches": 0, "error": str(e)}

def get_active_serpapi_key():
    keys = get_serpapi_keys()
    if not keys:
        raise RuntimeError("No SerpApi keys configured. Please add keys in Global Settings.")
    errors = []
    for key in keys:
        info = check_serpapi_account(key)
        if info["valid"] and info["plan_searches_left"] > 0:
            return key, info
        elif info["valid"]:
            errors.append(f"Key {key[:8]}... has 0 searches left")
        else:
            errors.append(f"Key {key[:8]}... is invalid: {info.get('error', 'Unknown')}")
    raise RuntimeError(
        f"All SerpApi keys have exceeded their monthly quota or are invalid.\n" + "\n".join(errors)
    )

def get_google_top10_outlines(keyword, serpapi_key=None):
    url = "https://serpapi.com/search.json"
    if serpapi_key is None:
        try:
            serpapi_key, _ = get_active_serpapi_key()
        except RuntimeError:
            return []
    try:
        r = requests.get(url, params={"q": keyword, "location": "Vietnam", "hl": "vi", "gl": "vn", "api_key": serpapi_key, "num": 10}, timeout=15)
        r.raise_for_status()
        return [{"title": x.get("title", ""), "link": x.get("link", ""), "snippet": x.get("snippet", "")}
                for x in r.json().get("organic_results", [])[:10]]
    except Exception:
        return []

# ============================================================
# WP / WOOCOMMERCE HELPERS (Parameterized)
# ============================================================
def wp_api_request_params(method, endpoint, wp_url, wp_username, wp_password, **kwargs):
    token = base64.b64encode(f"{wp_username}:{wp_password}".encode()).decode('utf-8')
    url = f"{wp_url.rstrip('/')}/wp-json/{endpoint.lstrip('/')}" if not endpoint.startswith("/wp-json/") else f"{wp_url.rstrip('/')}{endpoint}"
    h = kwargs.pop("headers", {})
    h["Authorization"] = f"Basic {token}"
    return requests.request(method, url, headers=h, **kwargs)

def woo_api_request_params(method, endpoint, wp_url, woo_ck, woo_cs, **kwargs):
    url = f"{wp_url.rstrip('/')}/wp-json/wc/v3/{endpoint.lstrip('/')}" if not endpoint.startswith("/wp-json/wc/") else f"{wp_url.rstrip('/')}{endpoint}"
    return requests.request(method, url, auth=(woo_ck, woo_cs), **kwargs)

def upload_image_to_wp(image_url, wp_url, wp_username, wp_password):
    img_r = requests.get(image_url, timeout=60)
    img_r.raise_for_status()
    b = img_r.content
    ct = img_r.headers.get("Content-Type", "image/png")
    fn = os.path.basename(image_url.split("?")[0])
    if not fn or "." not in fn:
        fn = f"image.{ct.split('/')[-1] if '/' in ct else 'png'}"
    token = base64.b64encode(f"{wp_username}:{wp_password}".encode()).decode('utf-8')
    mr = requests.post(f"{wp_url.rstrip('/')}/wp-json/wp/v2/media", data=b,
                       headers={"Authorization": f"Basic {token}", "Content-Type": ct,
                                "Content-Disposition": f'attachment; filename="{fn}"'})
    mr.raise_for_status()
    rj = mr.json()
    return rj.get("id"), rj.get("source_url")

# ============================================================
# FULL GENERATION + POSTING PIPELINE
# ============================================================
def run_full_pipeline(
    keyword, brand_voice_prompt, word_count,
    wp_url, wp_username, wp_password, woo_ck, woo_cs,
    api_base, api_key, project_id, text_model, image_model,
    content_type="post", schedule_dt=None, serpapi_key=None
):
    try:
        wc = int(word_count) if word_count else 1850
        competitor_ctx = ""
        if serpapi_key is None:
            try:
                serpapi_key, _ = get_active_serpapi_key()
            except RuntimeError:
                pass
        if serpapi_key:
            try:
                t10 = get_google_top10_outlines(keyword, serpapi_key)
                if t10:
                    competitor_ctx = "\n".join(f"{i}. Title: {r['title']}\n   Snippet: {r['snippet']}" for i, r in enumerate(t10, 1))
            except Exception: pass

        title = generate_text(
            prompt=f'Generate a catchy, SEO-optimized title for a {"blog post" if content_type == "post" else "product page"} about "{keyword}". Target: {wc} words. Return ONLY the title.',
            system_prompt=f"{brand_voice_prompt}\n\nYou are an expert headline writer. Output only the title.",
            api_base=api_base, api_key=api_key, project_id=project_id, model=text_model
        ).strip().strip('"').strip("'") or keyword

        ctl = "blog post" if content_type == "post" else "WooCommerce product description"
        op = (f'Analyze Top 10 Google results for "{keyword}":\n{competitor_ctx}\nCreate an all-inclusive SEO outline (H2, H3) for a {ctl} that covers all key points and outperforms them. Target: {wc} words. Output H2/H3, no JSON.'
              if competitor_ctx else
              f'Generate a detailed structured outline for a {ctl} about "{keyword}". Target: {wc} words. Output H2/H3, no JSON.')
        outline = generate_text(prompt=op, system_prompt=f"{brand_voice_prompt}\n\nYou are an expert SEO strategist. Output only the outline.",
                                api_base=api_base, api_key=api_key, project_id=project_id, model=text_model).replace("```", "").strip()

        ap = (f'Write a comprehensive, SEO-optimized WooCommerce product description for: "{keyword}".\nFollow this outline: {outline}\nTarget: {wc} words. Output ONLY valid HTML. Include features, benefits, specs, CTA.'
              if content_type == "product" else
              f'Write a comprehensive, SEO-friendly article for: "{keyword}".\nFollow this outline: {outline}\nTarget: {wc} words. Output ONLY valid HTML.')

        html = generate_text(prompt=ap, system_prompt=f"{brand_voice_prompt}\n\nYou are an expert content writer. Output clean HTML without markdown wrappers.",
                              api_base=api_base, api_key=api_key, project_id=project_id, model=text_model).replace("```html", "").replace("```", "").strip()

        soup = BeautifulSoup(html, 'html.parser')
        h2s = soup.find_all('h2')
        fmid = None

        if h2s:
            for idx, h2 in enumerate(h2s):
                try:
                    idsc = generate_text(
                        prompt=f'Write a short image prompt for "{h2.text.strip()}" about "{keyword}". Output ONLY the prompt.',
                        system_prompt="You are an image prompt engineer.", api_base=api_base, api_key=api_key, project_id=project_id, model=text_model).strip()
                    idata = generate_image(prompt=idsc, api_base=api_base, api_key=api_key, project_id=project_id, model=image_model)
                    if idata:
                        info = idata[0]
                        lu = info.get("url") or (f"data:image/png;base64,{info['b64_json']}" if "b64_json" in info else None)
                        if lu and not lu.startswith("data:"):
                            try:
                                mid, su = upload_image_to_wp(lu, wp_url, wp_username, wp_password)
                                if idx == 0 and mid: fmid = mid
                                lu = su
                            except Exception: pass
                        if lu:
                            t = soup.new_tag("img", src=lu, alt=h2.text.strip(), style="max-width:100%; height:auto; border-radius:8px; margin:1.5rem 0;")
                            h2.insert_after(t)
                except Exception: pass
            html = str(soup)
        else:
            try:
                idata = generate_image(prompt=f"Professional featured image for {keyword}", api_base=api_base, api_key=api_key, project_id=project_id, model=image_model)
                if idata:
                    info = idata[0]
                    lu = info.get("url") or (f"data:image/png;base64,{info['b64_json']}" if "b64_json" in info else None)
                    if lu and not lu.startswith("data:"):
                        try: fmid, _ = upload_image_to_wp(lu, wp_url, wp_username, wp_password)
                        except Exception: pass
            except Exception: pass

        if schedule_dt is None: schedule_dt = datetime.now()
        ps = 'future' if schedule_dt > datetime.now() else 'publish'

        if content_type == "product":
            if not woo_ck or not woo_cs: return (title, html, "", fmid, "WooCommerce keys missing.")
            sd = ""; fp = soup.find('p')
            if fp: sd = fp.get_text()[:300]
            payload = {"name": title, "type": "simple", "description": html, "short_description": sd, "status": ps}
            if ps == "future": payload["date_created_gmt"] = schedule_dt.isoformat()
            if fmid: payload["images"] = [{"id": fmid}]
            r = woo_api_request_params("POST", "products", wp_url, woo_ck, woo_cs, json=payload)
            if r.status_code in [200, 201]:
                d = r.json(); return (title, html, d.get("permalink", "#"), fmid, None)
            return (title, html, "", fmid, f"WooCommerce Error {r.status_code}")
        else:
            payload = {"title": title, "content": html, "status": ps, "date": schedule_dt.isoformat()}
            if fmid: payload["featured_media"] = fmid
            r = wp_api_request_params("POST", "wp/v2/posts", wp_url, wp_username, wp_password, json=payload)
            if r.status_code in [200, 201]:
                d = r.json(); return (title, html, d.get("link", "#"), fmid, None)
            return (title, html, "", fmid, f"WP Error {r.status_code}")
    except Exception as e:
        return ("", "", "", None, str(e))

# ============================================================
# THREAD-SAFE GLOBAL LOG BUFFER
# ============================================================
WORKER_LOGS = []

def worker_log(message):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{ts}] {message}"
    WORKER_LOGS.append(log_entry)
    if len(WORKER_LOGS) > 100:
        WORKER_LOGS.pop(0)
    print(log_entry)

# ============================================================
# BACKGROUND WORKER
# ============================================================
def get_gsheet_client(sa_json):
    import gspread
    return gspread.service_account_from_dict(json.loads(sa_json))

def parse_schedule_date(date_str, time_str):
    from datetime import timezone, timedelta as td
    import pytz
    vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
    date_str = str(date_str).strip() if date_str else ""
    time_str = str(time_str).strip() if time_str else ""
    if not date_str and not time_str:
        return None, False
    if time_str:
        try:
            float_val = float(time_str)
            if 0.0 <= float_val < 1.0 and '.' in time_str:
                total_seconds = float_val * 86400
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        except (ValueError, TypeError):
            pass
    combined_str = f"{date_str} {time_str}".strip()
    try:
        import dateutil.parser
        parsed_dt = dateutil.parser.parse(combined_str, dayfirst=True)
        if parsed_dt.tzinfo is None:
            parsed_dt = vn_tz.localize(parsed_dt)
        return parsed_dt, True
    except Exception:
        pass
    dfmts = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y.%m.%d"]
    pd = None
    if date_str:
        for f in dfmts:
            try: pd = datetime.strptime(date_str, f); break
            except ValueError: continue
    tfmts = ["%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p"]
    pt = None
    if time_str:
        for f in tfmts:
            try: pt = datetime.strptime(time_str, f); break
            except ValueError: continue
    if pd and pt:
        combined = pd.replace(hour=pt.hour, minute=pt.minute, second=pt.second, microsecond=0)
        combined = vn_tz.localize(combined)
        return combined, True
    if pd:
        return vn_tz.localize(pd), True
    if pt:
        now = datetime.now(vn_tz)
        combined = now.replace(hour=pt.hour, minute=pt.minute, second=0, microsecond=0)
        return combined, True
    if date_str or time_str:
        return None, True
    return None, False

def process_sheet_for_user(user_id):
    s = get_all_user_settings(user_id)
    saj, surl = s.get("gsheet_sa_json", ""), s.get("gsheet_url", "")
    if not saj or not surl: return 0
    try:
        gc = get_gsheet_client(saj)
        try: sh = gc.open_by_url(surl)
        except Exception: sh = gc.open_by_key(surl)
        ws = sh.sheet1
        av = ws.get_all_values()
        if not av or len(av) < 2: return 0
        hdrs = [h.strip().lower() for h in av[0]]
        def fc(hay, ndls):
            for i, h in enumerate(hay):
                for n in ndls:
                    if n in h: return i
            return -1
        ix_site = fc(hdrs, ["tên website", "website", "site name", "site"])
        ix_kw = fc(hdrs, ["từ khoá", "từ khóa", "keyword"])
        ix_ct = fc(hdrs, ["loại nội dung", "content type"])
        ix_pmpt = fc(hdrs, ["prompt", "brand voice", "brand"])
        ix_wc = fc(hdrs, ["số từ", "word count"])
        ix_date = fc(hdrs, ["ngày đăng", "ngay dang", "date"])
        ix_time = fc(hdrs, ["giờ đăng", "gio dang", "time", "giờ"])
        ix_st = fc(hdrs, ["trạng thái", "status", "trang thai"])
        ix_lnk = fc(hdrs, ["link", "url", "link bài viết"])
        if ix_site == -1: ix_site = 0
        if ix_kw == -1: ix_kw = 1
        if ix_ct == -1: ix_ct = 2
        if ix_pmpt == -1: ix_pmpt = 3
        if ix_wc == -1: ix_wc = 4
        if ix_date == -1: ix_date = 5
        if ix_time == -1: ix_time = 6
        if ix_st == -1: ix_st = 7
        if ix_lnk == -1: ix_lnk = 8
        ab = s.get("local_api_base", LOCAL_API_BASE)
        ak = s.get("local_api_key", LOCAL_API_KEY)
        pid = s.get("local_project_id", LOCAL_PROJECT_ID)
        tm = s.get("local_model", LOCAL_MODEL)
        im = s.get("local_image_model", LOCAL_IMAGE_MODEL)
        proc = 0
        for ri in range(1, len(av)):
            row = av[ri]
            mx = max(ix_st, ix_lnk, ix_kw, ix_site, ix_date, ix_time)
            while len(row) <= mx: row.append("")
            sv = str(row[ix_st]).strip().lower() if ix_st < len(row) else ""
            kv = str(row[ix_kw]).strip() if ix_kw < len(row) else ""
            snv = str(row[ix_site]).strip() if ix_site < len(row) else ""
            if sv and sv not in ["pending", "chưa đăng", "chua dang", "chuadang"]: continue
            if not kv: continue
            site = get_website_by_name(user_id, snv)
            if not site:
                sites = get_websites(user_id)
                if sites: site = sites[0]
                else:
                    worker_log(f"⚠️ No website for user {user_id}, row {ri+1}"); continue
            bp = site.get("brand_voice_prompt", "You are an expert SEO content writer.")
            pv = str(row[ix_pmpt]).strip() if ix_pmpt < len(row) else ""
            if pv: bp = pv
            wv = str(row[ix_wc]).strip() if ix_wc < len(row) else "1500"
            try: wv = int(wv)
            except: wv = 1500
            cv = str(row[ix_ct]).strip().lower() if ix_ct < len(row) else "post"
            if cv not in ["post", "product"]: cv = "post"
            ds = str(row[ix_date]).strip() if ix_date < len(row) else ""
            ts_ = str(row[ix_time]).strip() if ix_time < len(row) else ""
            sdt, hs = parse_schedule_date(ds, ts_)
            if sdt is None and hs:
                worker_log(f"⚠️ Row {ri+1}: Cannot parse '{ds} {ts_}' for '{kv}'. Posting immediately.")
                sdt = datetime.now(); hs = False
            if sdt is None: sdt = datetime.now(); hs = False
            import pytz
            vn_tz = pytz.timezone("Asia/Ho_Chi_Minh")
            now_vn = datetime.now(vn_tz)
            if hs and sdt.tzinfo is None:
                sdt = vn_tz.localize(sdt)
            if hs and sdt > now_vn:
                tr = sdt - now_vn
                worker_log(f"⏳ Skipping '{kv}', scheduled for {sdt.strftime('%Y-%m-%d %H:%M')} ICT, current time is {now_vn.strftime('%Y-%m-%d %H:%M')} ICT ({int(tr.total_seconds()//3600)}h {int((tr.total_seconds()%3600)//60)}m remaining), waiting...")
                continue
            worker_log(f"🔄 Row {ri+1}: '{kv}' → {site['site_name']} ({cv})")
            try: ws.update_cell(ri + 1, ix_st + 1, "Processing...")
            except Exception: pass
            _, _, link, _, err = run_full_pipeline(
                keyword=kv, brand_voice_prompt=bp, word_count=wv, wp_url=site["wp_url"],
                wp_username=site["wp_username"], wp_password=site["wp_app_password"],
                woo_ck=site["woo_ck"], woo_cs=site["woo_cs"], api_base=ab, api_key=ak,
                project_id=pid, text_model=tm, image_model=im, content_type=cv,
                schedule_dt=sdt, serpapi_key=None)
            if err is None and link:
                ws.update_cell(ri + 1, ix_st + 1, "Success"); ws.update_cell(ri + 1, ix_lnk + 1, link)
                save_history_entry(user_id, site["site_name"], kv, sdt.strftime("%Y-%m-%d %H:%M"),
                                   'future' if sdt > datetime.now() else 'publish', cv, link)
                worker_log(f"✅ Posted: '{kv}' → {link}"); proc += 1
            else:
                em = err or "Unknown error"
                ws.update_cell(ri + 1, ix_st + 1, f"Error: {em[:80]}")
                worker_log(f"❌ Failed: '{kv}' → {em[:120]}")
        return proc
    except ImportError: worker_log("⚠️ gspread not installed"); return 0
    except Exception as e: worker_log(f"❌ Sheet error user {user_id}: {e}"); return 0

def scan_all_users_sheets():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id FROM users"); users = c.fetchall(); conn.close()
    t = 0
    for u in users:
        try: t += process_sheet_for_user(u["id"])
        except Exception as e: worker_log(f"❌ Error user {u['id']}: {e}")
    if t > 0: worker_log(f"✅ Processed {t} total rows")
    return t

def background_worker_loop():
    schedule_lib.every(1).minutes.do(scan_all_users_sheets)
    worker_log("🟢 Worker started (every 1 min)")
    while True: schedule_lib.run_pending(); time.sleep(60)

def start_background_worker():
    if not st.session_state.worker_started:
        threading.Thread(target=background_worker_loop, daemon=True).start()
        st.session_state.worker_started = True
        worker_log("🔧 Worker thread initialized")

# ============================================================
# LOGIN / REGISTER UI
# ============================================================
if not st.session_state.logged_in:
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown("## 🔐 WP Auto-Poster PRO")
    st.caption("Your AI-powered content automation platform")
    t1, t2 = st.tabs(["Sign In", "Create Account"])
    with t1:
        with st.form("login"):
            lu = st.text_input("Username")
            lp = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In", use_container_width=True):
                ok, msg = login_user(lu, lp)
                if ok: st.success(msg); st.rerun()
                else: st.error(msg)
    with t2:
        with st.form("register"):
            ru = st.text_input("Choose Username")
            rp = st.text_input("Choose Password", type="password")
            rp2 = st.text_input("Confirm Password", type="password")
            if st.form_submit_button("Create Account", use_container_width=True):
                if rp != rp2: st.error("Passwords do not match.")
                elif len(rp) < 4: st.error("Min 4 characters.")
                else:
                    ok, msg = register_user(ru, rp)
                    st.success(msg) if ok else st.error(msg)
    st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

# ============================================================
# LOGGED IN — START BACKGROUND WORKER
# ============================================================
start_background_worker()

def load_global_settings():
    if st.session_state.user_id:
        s = get_all_user_settings(st.session_state.user_id)
        for k, d in [("local_api_base", LOCAL_API_BASE), ("local_api_key", LOCAL_API_KEY),
                     ("local_project_id", LOCAL_PROJECT_ID), ("local_model", LOCAL_MODEL),
                     ("local_image_model", LOCAL_IMAGE_MODEL), ("serpapi_keys", DEFAULT_SERPAPI_KEY),
                     ("gsheet_url", ""), ("gsheet_sa_json", "")]:
            if k not in st.session_state or not st.session_state.get(k):
                st.session_state[k] = s.get(k, d)

load_global_settings()
uid = st.session_state.user_id

# ============================================================
# SIDEBAR NAVIGATION
# ============================================================
with st.sidebar:
    st.markdown('<p class="sidebar-brand">⚡ WP Auto-Poster <span style="font-weight:400;font-size:0.7rem;background:rgba(124,58,237,0.3);padding:2px 6px;border-radius:4px;">PRO</span></p>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="sidebar-user-card">
        <div style="display:flex;align-items:center;gap:0.75rem;">
            <div class="sidebar-avatar">{st.session_state.username[0].upper()}</div>
            <div>
                <div style="font-weight:600;color:#E0E7FF;">{st.session_state.username}</div>
                <div style="font-size:0.75rem;color:#A5B4FC;"><span class="sidebar-status"></span>Online</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div style="height:0.5rem;"></div>', unsafe_allow_html=True)
    current_username = str(st.session_state.get('username', '')).lower()
    current_role = str(st.session_state.get('user_role', '')).lower()
    is_admin = (current_username == 'admin') or (current_role == 'admin')
    nav_options = ["🚀 Content Generator", "🌐 Website Manager"]
    if is_admin:
        nav_options.append("⚙️ Global Settings")
    if not is_admin and st.session_state.nav_view == "⚙️ Global Settings":
        st.session_state.nav_view = "🚀 Content Generator"
    view = st.radio(
        "", nav_options, index=0,
        format_func=lambda x: f"  {x}",
        key="nav_radio", label_visibility="collapsed"
    )
    st.session_state.nav_view = view
    if is_admin:
        st.markdown(f'<span class="badge-purple" style="font-size:0.7rem;">🛡️ Admin ({current_role})</span>', unsafe_allow_html=True)
    st.markdown("---")
    user_credits = get_user_credits(uid)
    cost_per_post = get_cost_per_post()
    st.sidebar.metric("💳 Số dư tài khoản", f"{user_credits:,.0f} VNĐ")
    st.sidebar.caption(f"Chi phí: {cost_per_post:,.0f} VNĐ / bài viết thành công")
    with st.expander("💳 Nạp điểm / Mua gói bài đăng", expanded=False):
        st.markdown("**📦 Các gói bài đăng:**")
        col_p1, col_p2, col_p3 = st.columns(3)
        with col_p1:
            if st.button("🎯 Gói 25 bài\n50,000 VNĐ", use_container_width=True, key="pkg25"):
                st.info("Vui lòng chuyển khoản theo thông tin bên dưới và liên hệ Admin để xác nhận.")
        with col_p2:
            if st.button("🔥 Gói 50 bài\n100,000 VNĐ", use_container_width=True, key="pkg50"):
                st.info("Vui lòng chuyển khoản theo thông tin bên dưới và liên hệ Admin để xác nhận.")
        with col_p3:
            if st.button("🚀 Gói 100 bài\n200,000 VNĐ", use_container_width=True, key="pkg100"):
                st.info("Vui lòng chuyển khoản theo thông tin bên dưới và liên hệ Admin để xác nhận.")
        st.markdown("---")
        st.markdown("**🏦 Thông tin chuyển khoản:**")
        st.markdown("""
        - **Ngân hàng:** MB Bank (Ngân hàng TMCP Quân Đội)
        - **Số tài khoản:** 0968335777
        - **Chủ tài khoản:** NGUYEN VAN A
        - **Nội dung chuyển khoản:** `NAP <username>` (vd: NAP admin)
        """)
        st.caption("⏳ Sau khi chuyển khoản, vui lòng liên hệ Admin để được cộng điểm trong vòng 5-10 phút.")
    st.markdown("---")
    st.markdown("""
    <div class="sidebar-info-box">
        <strong>💡 Tip</strong><br>
        Add your websites in <em>Website Manager</em>, then use <em>Content Generator</em> to create AI-powered posts.
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div style="height:1rem;"></div>', unsafe_allow_html=True)
    if st.button("🚪 Logout", use_container_width=True):
        logout_user(); st.rerun()

# ============================================================
# VIEW 1: 🚀 CONTENT GENERATOR
# ============================================================
if st.session_state.nav_view == "🚀 Content Generator":
    st.markdown("""
    <div class="header-banner">
        <h1>🚀 Content Generator</h1>
        <p>AI-powered content creation & automated publishing for WordPress & WooCommerce</p>
    </div>
    """, unsafe_allow_html=True)
    websites = get_websites(uid)
    if not websites:
        st.warning("⚠️ No websites configured. Go to **🌐 Website Manager** to add your first site.")
    else:
        site_options = {w["site_name"]: w for w in websites}
        selected_site_name = st.selectbox("🎯 Target Website", options=list(site_options.keys()))
        selected_site = site_options[selected_site_name]
        c1, c2 = st.columns([2, 1], gap="large")
        with c2:
            st.markdown("#### ⚙️ Settings")
            word_count = st.slider("Word Count", 500, 3000, 1850, 50)
            content_type = st.radio("Content Type", ["post", "product"],
                                    format_func=lambda x: "📝 Blog Post" if x == "post" else "🛒 Woo Product",
                                    horizontal=True, key="gen_ct")
            st.markdown("##### 📅 Schedule")
            cd, ct = st.columns(2)
            with cd: sched_date = st.date_input("Date", key="gen_date")
            with ct: sched_time = st.time_input("Time", key="gen_time")
        with c1:
            keyword = st.text_input("🔑 Primary Keyword", placeholder="e.g. Best SEO Strategies 2026")
            if st.button("✨ Generate SEO Outline (SerpApi)", use_container_width=True):
                if not keyword:
                    st.warning("Please enter a keyword first.")
                else:
                    with st.spinner("Analyzing Top 10 Google results + generating outline..."):
                        try:
                            competitor_context = ""
                            try:
                                t10 = get_google_top10_outlines(keyword, serpapi_key=None)
                                if t10:
                                    competitor_context = "\n".join(f"{i}. {r['title']} — {r['snippet'][:120]}" for i, r in enumerate(t10, 1))
                                    st.info(f"📊 Analyzed {len(t10)} Top 10 results.")
                            except Exception: pass
                            bp = selected_site.get("brand_voice_prompt", "You are an expert SEO writer.")
                            ctl = "blog post" if content_type == "post" else "WooCommerce product description"
                            op = (f'Analyze Top 10 Google results for "{keyword}":\n{competitor_context}\nCreate an all-inclusive SEO outline (H2, H3) for a {ctl} that covers all key points and outperforms them. Target: {word_count} words. Output H2/H3, no JSON.'
                                  if competitor_context else
                                  f'Generate a detailed SEO outline for a {ctl} about "{keyword}". Target: {word_count} words. Output H2/H3, no JSON.')
                            outline = generate_text(prompt=op,
                                system_prompt=f"{bp}\n\nYou are an expert SEO strategist. Output only the outline.",
                                api_base=st.session_state.get("local_api_base", LOCAL_API_BASE),
                                api_key=st.session_state.get("local_api_key", LOCAL_API_KEY),
                                project_id=st.session_state.get("local_project_id", LOCAL_PROJECT_ID),
                                model=st.session_state.get("local_model", LOCAL_MODEL))
                            st.session_state.generated_outline = outline.replace("```", "").strip()
                            st.success("✅ Outline generated!")
                        except Exception as e: st.error(f"Error: {e}")
            custom_outline = st.text_area("📝 Outline (edit before generation)", value=st.session_state.generated_outline, height=250)
        with c2:
            st.markdown("---")
            if st.button("🚀 Generate & Publish", use_container_width=True, type="primary"):
                if not all([selected_site["wp_url"], selected_site["wp_username"], keyword]):
                    st.error("Missing website credentials or keyword!")
                elif content_type == "product" and not (selected_site["woo_ck"] and selected_site["woo_cs"]):
                    st.error("WooCommerce keys required for product publishing!")
                else:
                    cpp = get_cost_per_post()
                    if not deduct_user_credit(uid, cpp):
                        st.error(f"⚠️ Tài khoản của bạn không đủ số dư (Cần {cpp:,.0f} VNĐ/bài). Vui lòng nạp thêm điểm!")
                    else:
                        with st.spinner(f"Generating {content_type}..."):
                            try:
                                bp = selected_site.get("brand_voice_prompt", "You are an expert SEO writer.")
                                dt = datetime.combine(sched_date, sched_time)
                                _, _, link, _, err = run_full_pipeline(
                                    keyword=keyword, brand_voice_prompt=bp, word_count=word_count,
                                    wp_url=selected_site["wp_url"], wp_username=selected_site["wp_username"],
                                    wp_password=selected_site["wp_app_password"],
                                    woo_ck=selected_site["woo_ck"], woo_cs=selected_site["woo_cs"],
                                    api_base=st.session_state.get("local_api_base", LOCAL_API_BASE),
                                    api_key=st.session_state.get("local_api_key", LOCAL_API_KEY),
                                    project_id=st.session_state.get("local_project_id", LOCAL_PROJECT_ID),
                                    text_model=st.session_state.get("local_model", LOCAL_MODEL),
                                    image_model=st.session_state.get("local_image_model", LOCAL_IMAGE_MODEL),
                                    content_type=content_type, schedule_dt=dt, serpapi_key=None)
                                if err is None and link:
                                    st.success(f"✅ Published to {selected_site_name}!")
                                    st.markdown(f"[View {content_type.capitalize()}]({link})")
                                    save_history_entry(uid, selected_site_name, keyword, dt.strftime("%Y-%m-%d %H:%M"),
                                                       'future' if dt > datetime.now() else 'publish', content_type, link)
                                    st.session_state.generated_outline = ""; st.rerun()
                                else: st.error(f"Failed: {err}")
                            except Exception as e: st.error(f"Error: {e}")
            st.markdown("---")
            st.markdown("##### 📊 Sheet Sync")
            if st.session_state.worker_started:
                st.markdown('<span class="badge-success">🟢 Worker RUNNING</span> <span style="font-size:0.75rem;color:#6B7280;">(every 1 min)</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="badge-amber">🔴 Worker STOPPED</span>', unsafe_allow_html=True)
            if st.button("🔄 Run Sheet Automation Now", use_container_width=True):
                if not st.session_state.get("gsheet_sa_json") or not st.session_state.get("gsheet_url"):
                    st.warning("Configure Google Sheets in ⚙️ Global Settings first.")
                else:
                    with st.spinner("Scanning sheet..."):
                        count = process_sheet_for_user(uid)
                        st.success(f"Processed {count} rows!") if count > 0 else st.info("No pending rows found.")
    st.markdown("---")
    st.markdown("### 📋 Execution History")
    hist = load_history(uid)
    if not hist: st.info("No history yet.")
    else:
        df = pd.DataFrame(hist)
        if "date" in df.columns: df["Date & Time"] = df["date"]
        if "site_name" in df.columns: df["Site"] = df["site_name"]
        if "keyword" in df.columns: df["Keyword"] = df["keyword"]
        if "content_type" in df.columns: df["Type"] = df["content_type"].apply(lambda x: "🛒 Product" if x == "product" else "📝 Post")
        if "status" in df.columns: df["Status"] = df["status"].apply(lambda x: "✅ Published" if x == "publish" else ("🕐 Scheduled" if x == "future" else f"❌ {x}"))
        if "link" in df.columns: df["Link"] = df["link"]
        cols = [c for c in ["Site", "Keyword", "Type", "Date & Time", "Status", "Link"] if c in df.columns]
        if cols:
            st.dataframe(df[cols], column_config={
                "Site": st.column_config.TextColumn("Site", width="small"),
                "Keyword": st.column_config.TextColumn("Keyword", width="medium"),
                "Type": st.column_config.TextColumn("Type", width="small"),
                "Date & Time": st.column_config.TextColumn("Date", width="small"),
                "Status": st.column_config.TextColumn("Status", width="small"),
                "Link": st.column_config.LinkColumn("Link", width="small", display_text="View")
            }, hide_index=True, use_container_width=True)

# ============================================================
# VIEW 2: 🌐 WEBSITE MANAGER
# ============================================================
elif st.session_state.nav_view == "🌐 Website Manager":
    st.markdown("""
    <div class="header-banner">
        <h1>🌐 Website Manager</h1>
        <p>Manage your WordPress & WooCommerce websites — add, edit, or remove sites</p>
    </div>
    """, unsafe_allow_html=True)
    webs = get_websites(uid)
    editing_site = st.session_state.get("editing_site")
    is_editing = editing_site is not None
    st.markdown(f"#### {'✏️ Edit Site' if is_editing else '➕ Add New Site'}")
    with st.container():
        form_mode = "edit" if is_editing else "add"
        site_name = st.text_input("Site Name *",
            value=editing_site["site_name"] if is_editing else "",
            placeholder="e.g. My Health Blog", key=f"wm_name_{form_mode}")
        wp_url = st.text_input("WordPress URL *",
            value=editing_site["wp_url"] if is_editing else "",
            placeholder="https://yoursite.com", key=f"wm_url_{form_mode}")
        wp_user = st.text_input("WP Username *",
            value=editing_site["wp_username"] if is_editing else "", key=f"wm_user_{form_mode}")
        wp_pass = st.text_input("WP App Password *", type="password",
            value=editing_site["wp_app_password"] if is_editing else "", key=f"wm_pass_{form_mode}")
        ck1, ck2 = st.columns(2)
        with ck1:
            woo_ck = st.text_input("WooCommerce Consumer Key", type="password",
                value=editing_site["woo_ck"] if is_editing else "", placeholder="ck_...", key=f"wm_ck_{form_mode}")
        with ck2:
            woo_cs = st.text_input("WooCommerce Consumer Secret", type="password",
                value=editing_site["woo_cs"] if is_editing else "", placeholder="cs_...", key=f"wm_cs_{form_mode}")
        brand_voice = st.text_area("Brand Voice / System Prompt (per-site)",
            value=editing_site["brand_voice_prompt"] if is_editing else "You are an expert SEO content writer. Write in a professional, engaging tone.",
            height=120, key=f"wm_brand_{form_mode}")
        col_s, col_x = st.columns([1, 1])
        with col_s:
            btn_label = "💾 Update Site" if is_editing else "💾 Save Site"
            if st.button(btn_label, use_container_width=True, type="primary"):
                if not site_name or not wp_url or not wp_user:
                    st.error("Site Name, WP URL, and WP Username are required.")
                else:
                    save_website(uid, site_name, wp_url, wp_user, wp_pass, woo_ck, woo_cs, brand_voice,
                                 website_id=editing_site["id"] if is_editing else None)
                    st.session_state.editing_site = None
                    st.success(f"✅ Site '{site_name}' saved!"); st.rerun()
        with col_x:
            if st.button("Cancel", use_container_width=True):
                st.session_state.editing_site = None; st.rerun()
    if webs:
        st.markdown("---")
        st.markdown("### 📋 Your Sites")
        for w in webs:
            with st.container():
                c1, c2, c3, c4 = st.columns([1.5, 1.5, 1, 1])
                with c1: st.markdown(f"**{w['site_name']}**")
                with c2: st.caption(w['wp_url'][:45])
                with c3:
                    has_w = bool(w.get('woo_ck'))
                    st.markdown('<span class="badge-purple">🛒 WooCommerce</span>' if has_w else '<span class="badge-success">📝 Blog</span>', unsafe_allow_html=True)
                with c4:
                    e1, e2 = st.columns(2)
                    with e1:
                        if st.button("✏️", key=f"ed_{w['id']}", help="Edit"):
                            st.session_state.editing_site = get_website_by_id(w['id']); st.rerun()
                    with e2:
                        if st.button("🗑️", key=f"dl_{w['id']}", help="Delete"):
                            delete_website(w['id'], uid)
                            st.success(f"Deleted '{w['site_name']}'"); st.rerun()
                st.markdown("<div style='height:0.25rem;'></div>", unsafe_allow_html=True)
    else:
        st.info("No sites added yet. Use the form above to add your first WordPress/WooCommerce site.")

# ============================================================
# VIEW 3: ⚙️ GLOBAL SETTINGS
# ============================================================
elif st.session_state.nav_view == "⚙️ Global Settings":
    if not is_admin:
        st.warning("⚠️ Bạn không có quyền truy cập trang Cấu hình API Hệ thống. Vui lòng liên hệ Admin.")
        st.stop()
    st.markdown("""
    <div class="header-banner">
        <h1>⚙️ Global Settings</h1>
        <p>Configure your AI engine & integrations — these apply across all websites</p>
    </div>
    """, unsafe_allow_html=True)
    tab_ai, tab_gsheet = st.tabs(["🤖 AI Engine", "📊 Google Sheets"])
    with tab_ai:
        st.markdown("#### Local AI API")
        c1, c2 = st.columns(2)
        with c1:
            lab = st.text_input("API Base URL", value=st.session_state.get("local_api_base", LOCAL_API_BASE))
            lak = st.text_input("API Key", value=st.session_state.get("local_api_key", LOCAL_API_KEY), type="password")
            lpi = st.text_input("Project ID", value=st.session_state.get("local_project_id", LOCAL_PROJECT_ID))
        with c2:
            ltm = st.text_input("Text Model", value=st.session_state.get("local_model", LOCAL_MODEL))
            lim = st.text_input("Image Model", value=st.session_state.get("local_image_model", LOCAL_IMAGE_MODEL))
            st.markdown("##### SerpApi Keys (One per line)")
            sk_ = st.text_area("SerpApi Keys", value=st.session_state.get("serpapi_keys", DEFAULT_SERPAPI_KEY),
                               height=100, placeholder="Enter one API key per line...",
                               help="Add multiple SerpApi keys for automatic load balancing and failover.")
        for k, v in [("local_api_base", lab), ("local_api_key", lak), ("local_project_id", lpi),
                      ("local_model", ltm), ("local_image_model", lim), ("serpapi_keys", sk_)]:
            st.session_state[k] = v; save_user_setting(uid, k, v)
    with tab_gsheet:
        st.markdown("#### Google Sheets Automation")
        gu = st.text_input("Sheet URL or ID", value=st.session_state.get("gsheet_url", ""), placeholder="https://docs.google.com/spreadsheets/d/...")
        st.session_state["gsheet_url"] = gu; save_user_setting(uid, "gsheet_url", gu)
        st.markdown("##### Service Account JSON")
        sf = st.file_uploader("Upload JSON key", type=["json"], key="gs_sa_up")
        if sf is not None:
            try:
                sc = sf.read().decode("utf-8"); json.loads(sc)
                st.session_state["gsheet_sa_json"] = sc; save_user_setting(uid, "gsheet_sa_json", sc)
                st.success("✅ Saved!")
            except Exception as e: st.error(f"Invalid JSON: {e}")
        else:
            if st.session_state.get("gsheet_sa_json"): st.caption("✅ Service Account loaded")
            else: st.caption("No file uploaded")
        st.markdown("---")
        st.markdown("**Expected Sheet Columns (10 cols):**")
        st.code("A: Tên Website | B: Từ khoá chính | C: Loại nội dung | D: Prompt |\nE: Số từ viết | F: Ngày đăng | G: Giờ đăng | H: Trạng thái |\nI: Link bài viết | J: STT")
        st.caption("Worker scans every 1 minute. Future-dated rows wait until scheduled.")
        st.markdown("---")
        st.markdown("#### 📊 SerpApi Usage Dashboard")
        if st.button("🔄 Refresh SerpApi Usage", use_container_width=True):
            st.rerun()
        keys_list = get_serpapi_keys()
        if keys_list:
            rows = []
            for key in keys_list:
                info = check_serpapi_account(key)
                prefix = key[:12] + "..." if len(key) > 12 else key
                if info["valid"]:
                    left = info["plan_searches_left"]
                    total = info["searches_per_month"]
                    used = total - left if total > 0 else 0
                    status_badge = '<span class="badge-success">✅ Active</span>' if left > 0 else '<span class="badge-amber">⚠️ Exhausted</span>'
                    rows.append({"Key": prefix, "Plan": info["plan"], "Limit": f"{total}", "Used": f"{used}", "Left": f"{left}", "Status": status_badge})
                else:
                    rows.append({"Key": prefix, "Plan": "N/A", "Limit": "0", "Used": "0", "Left": "0", "Status": '<span class="badge-amber">❌ Invalid</span>'})
            if rows:
                df_usage = pd.DataFrame(rows)
                st.markdown(df_usage[["Key", "Plan", "Limit", "Used", "Left", "Status"]].to_html(index=False, escape=False), unsafe_allow_html=True)
        else:
            st.info("No SerpApi keys configured. Add keys in the AI Engine tab above.")
    st.markdown("---")
    st.markdown("#### 💰 Quản lý Nạp điểm & Chi phí")
    cost_per_post_val = st.number_input("Chi phí mỗi bài đăng (VNĐ)", value=get_cost_per_post(), min_value=0, step=500)
    save_user_setting(uid, "cost_per_post", str(int(cost_per_post_val)))
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, credits FROM users ORDER BY id")
    all_users = cursor.fetchall()
    conn.close()
    if all_users:
        col_usr, col_amt, col_btn = st.columns([2, 1, 1])
        with col_usr:
            selected_user_idx = st.selectbox("Chọn User", options=range(len(all_users)),
                format_func=lambda i: f"{all_users[i]['username']} (💳 {all_users[i]['credits']:,.0f} VNĐ)")
            selected_user = all_users[selected_user_idx]
        with col_amt:
            credit_amount = st.number_input("Số điểm", value=10000, min_value=1000, step=5000)
        with col_btn:
            st.markdown("<div style='height:1.5rem;'></div>", unsafe_allow_html=True)
            if st.button("➕ Nạp điểm", use_container_width=True, type="primary"):
                add_credits(selected_user["id"], credit_amount, f"Admin nạp {credit_amount:,.0f} VNĐ")
                st.success(f"✅ Đã nạp {credit_amount:,.0f} VNĐ cho {selected_user['username']}!")
                st.rerun()
        st.markdown("---")
        balance_data = [{"Username": u["username"], "Balance (VNĐ)": f"{u['credits']:,.0f}"} for u in all_users]
        st.table(pd.DataFrame(balance_data))
    st.markdown("---")
    if st.button("💾 Save All Settings", use_container_width=True, type="primary"):
        st.success("✅ All settings saved!")

# ============================================================
# WORKER LOGS
# ============================================================
st.markdown("---")
with st.expander("🔧 Background Worker Logs", expanded=False):
    if WORKER_LOGS:
        st.code("\n".join(WORKER_LOGS[-50:]), language="text")
    else:
        st.caption("No worker logs yet.")
