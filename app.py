from datetime import datetime, timedelta
import base64
import hashlib
import json
import os
import secrets
import sqlite3
import time
from bs4 import BeautifulSoup
from openai import OpenAI
import pandas as pd
import requests
import streamlit as st

# ============================================================
# CONSTANTS
# ============================================================
DB_FILE = "/tmp/autoposter_data.db"

LOCAL_API_BASE = "http://localhost:3003/v1"
LOCAL_API_KEY = "AQ.Ab8RN6IjV-QWSXPxSIydANNNuh8a2bdOh_wkBRWd_diI7s67Tw"
LOCAL_PROJECT_ID = "777992117459"
LOCAL_MODEL = "gemini-3.6-flash"
LOCAL_IMAGE_MODEL = "gemini-3.1-flash-image"

DEFAULT_SERPAPI_KEY = (
    "eb7a6f72642ad4ffd0dc63c39e2a129d577825b86837b56a4bd86ca233eaf6f6"
)

# ============================================================
# STREAMLIT PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="WP Auto-Poster PRO",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# MODERN UI — LARKEYWORD WHITE CARD STYLE
# ============================================================
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="st-"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* --- SIDEBAR — LIGHT GRAYISH BACKGROUND --- */
    [data-testid="stSidebar"] {
        background-color: #f8fafc !important;
        min-width: 350px !important;
        max-width: 380px !important;
        border-right: 1px solid #e2e8f0 !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        padding: 1.5rem 1rem !important;
    }
    [data-testid="stSidebar"] * {
        word-break: normal !important;
        white-space: normal !important;
    }

    /* --- FLOATING WHITE NAV CARD --- */
    .larkeyword-card {
        background-color: #ffffff;
        border-radius: 20px;
        padding: 16px;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05);
        border: 1px solid #e2e8f0;
        margin-bottom: 16px;
    }

    /* --- RADIO MENU — LARKEYWORD NAV STYLE --- */
    [data-testid="stSidebar"] div[role="radiogroup"] {
        gap: 8px;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label {
        background-color: transparent !important;
        border-radius: 12px !important;
        padding: 10px 16px !important;
        border: 1px solid transparent !important;
        transition: all 0.2s ease !important;
        font-weight: 500 !important;
        color: #334155 !important;
        cursor: pointer !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label:hover {
        background-color: #f1f5f9 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {
        background-color: #ccfbf1 !important;
        color: #0f766e !important;
        font-weight: 700 !important;
    }
    [data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
        display: none !important;
    }

    /* --- BALANCE & BANK CARDS --- */
    .balance-box {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #ffffff;
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .bank-box {
        background: #ffffff;
        border: 1px dashed #cbd5e1;
        border-radius: 14px;
        padding: 14px;
        font-size: 13px;
        color: #334155;
        box-shadow: 0 4px 12px rgba(0,0,0,0.03);
    }

    /* --- TOP HEADER BANNER --- */
    .header-banner {
        background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        color: white;
        box-shadow: 0 10px 25px -5px rgba(13, 148, 136, 0.3);
    }
    .header-banner h1 { font-size: 1.75rem; font-weight: 700; color: white !important; }
    .header-banner p { font-size: 0.9rem; opacity: 0.9; color: rgba(255,255,255,0.85) !important; }

    /* --- BUTTONS --- */
    .stButton > button {
        width: 100%; border-radius: 0.5rem; font-weight: 600;
        font-size: 0.9rem !important; padding: 0.5rem 1.5rem !important;
        transition: all 0.2s !important; border: none !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0d9488, #0f766e) !important;
        color: white !important; box-shadow: 0 4px 12px rgba(13, 148, 136, 0.3) !important;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 20px rgba(13, 148, 136, 0.4) !important;
    }

    /* --- BADGES --- */
    .badge-success { display: inline-block; background: #D1FAE5; color: #065F46; padding: 0.15rem 0.65rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
    .badge-purple { display: inline-block; background: #EDE9FE; color: #5B21B6; padding: 0.15rem 0.65rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }
    .badge-amber { display: inline-block; background: #FEF3C7; color: #92400E; padding: 0.15rem 0.65rem; border-radius: 20px; font-size: 0.75rem; font-weight: 600; }

    /* --- LOGIN CARD --- */
    .login-card {
        max-width: 420px; margin: 3rem auto; background: white; border-radius: 20px;
        padding: 2.5rem; box-shadow: 0 20px 60px -20px rgba(0,0,0,0.1); border: 1px solid #F3F4F6;
    }
</style>
""",
    unsafe_allow_html=True,
)


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
            credits REAL DEFAULT 2000,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
  try:
    cursor.execute(
        "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
    )
  except sqlite3.OperationalError:
    pass
  try:
    cursor.execute("ALTER TABLE users ADD COLUMN credits REAL DEFAULT 2000")
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
            brand_voice_prompt TEXT NOT NULL DEFAULT 'You are an expert SEO content writer.',
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

  # Ensure default admin exists
  cursor.execute("SELECT COUNT(*) as cnt FROM users WHERE username = 'admin'")
  if cursor.fetchone()["cnt"] == 0:
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, credits) VALUES"
        " (?, ?, ?, ?)",
        (
            "admin",
            hashlib.sha256("admin123".encode()).hexdigest(),
            "admin",
            100000,
        ),
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
  cursor.execute(
      "UPDATE users SET credits = COALESCE(credits, 0) + ? WHERE id = ?",
      (amount, user_id),
  )
  cursor.execute(
      "INSERT INTO credit_transactions (user_id, amount, type, description)"
      " VALUES (?, ?, 'RECHARGE', ?)",
      (user_id, amount, description),
  )
  conn.commit()
  conn.close()


def deduct_user_credit(user_id, cost=2000):
  """Trừ chính xác 2,000 VNĐ khi tạo bài thành công."""
  current = get_user_credits(user_id)
  if current < cost:
    return False
  conn = get_db()
  cursor = conn.cursor()
  cursor.execute(
      "UPDATE users SET credits = credits - ? WHERE id = ?", (cost, user_id)
  )
  cursor.execute(
      "INSERT INTO credit_transactions (user_id, amount, type, description)"
      " VALUES (?, -2000, 'DEDUCT', 'Đăng bài viết thành công')",
      (user_id,),
  )
  conn.commit()
  conn.close()
  return True


def get_cost_per_post():
  return 2000


def get_credit_transactions(user_id, limit=20):
  conn = get_db()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT amount, type, description, created_at FROM credit_transactions"
      " WHERE user_id = ? ORDER BY id DESC LIMIT ?",
      (user_id, limit),
  )
  rows = cursor.fetchall()
  conn.close()
  return [dict(r) for r in rows]


# ============================================================
# SAFE RESPONSE PARSER FOR LOCAL AI
# ============================================================
def parse_ai_response(response):
  if isinstance(response, str):
    try:
      data = json.loads(response)
      if isinstance(data, dict) and "choices" in data:
        return data["choices"][0]["message"]["content"]
      return response
    except (json.JSONDecodeError, ValueError):
      return response
  if isinstance(response, dict):
    if "choices" in response:
      return response["choices"][0]["message"]["content"]
    return str(response)
  if hasattr(response, "choices"):
    return response.choices[0].message.content
  return str(response)


# ============================================================
# AUTH HELPERS
# ============================================================
def hash_password(password):
  return hashlib.sha256(password.encode()).hexdigest()


def register_user(username, password, role="user"):
  conn = get_db()
  cursor = conn.cursor()
  try:
    cursor.execute(
        "INSERT INTO users (username, password_hash, role, credits) VALUES (?,"
        " ?, ?, 2000)",
        (username, hash_password(password), role),
    )
    user_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO credit_transactions (user_id, amount, type, description)"
        " VALUES (?, 2000, 'BONUS', 'Tặng 1 bài viết trải nghiệm')",
        (user_id,),
    )
    conn.commit()
    return (
        True,
        "🎉 Đăng ký thành công! Bạn được tặng 1 bài viết trải nghiệm (2,000"
        " VNĐ).",
    )
  except sqlite3.IntegrityError:
    return False, "Username already exists."
  finally:
    conn.close()


def login_user(username, password):
  conn = get_db()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT id, username, password_hash, role FROM users WHERE username = ?",
      (username,),
  )
  user = cursor.fetchone()
  if user and user["password_hash"] == hash_password(password):
    role = user["role"] or "user"
    if str(username).lower() == "admin" and role != "admin":
      cursor.execute(
          "UPDATE users SET role = 'admin' WHERE id = ?", (user["id"],)
      )
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
  for key in [
      "logged_in",
      "user_id",
      "username",
      "user_role",
      "generated_outline",
      "editing_site",
  ]:
    if key in st.session_state:
      st.session_state[key] = False if key == "logged_in" else ""


# ============================================================
# USER SETTINGS & WEBSITE CRUD
# ============================================================
def save_user_setting(user_id, key, value):
  conn = get_db()
  cursor = conn.cursor()
  cursor.execute(
      """
        INSERT INTO user_settings (user_id, key, value)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value
    """,
      (user_id, key, value),
  )
  conn.commit()
  conn.close()


def get_all_user_settings(user_id):
  conn = get_db()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT key, value FROM user_settings WHERE user_id = ?", (user_id,)
  )
  rows = cursor.fetchall()
  conn.close()
  return {row["key"]: row["value"] for row in rows}


def get_websites(user_id):
  conn = get_db()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT * FROM websites WHERE user_id = ? ORDER BY id", (user_id,)
  )
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


def save_website(
    user_id,
    site_name,
    wp_url,
    wp_username,
    wp_app_password,
    woo_ck,
    woo_cs,
    brand_voice_prompt,
    website_id=None,
):
  conn = get_db()
  cursor = conn.cursor()
  if website_id:
    cursor.execute(
        """
            UPDATE websites SET site_name=?, wp_url=?, wp_username=?, wp_app_password=?,
            woo_ck=?, woo_cs=?, brand_voice_prompt=?
            WHERE id=? AND user_id=?
        """,
        (
            site_name,
            wp_url,
            wp_username,
            wp_app_password,
            woo_ck,
            woo_cs,
            brand_voice_prompt,
            website_id,
            user_id,
        ),
    )
  else:
    cursor.execute(
        """
            INSERT INTO websites (user_id, site_name, wp_url, wp_username, wp_app_password,
                                 woo_ck, woo_cs, brand_voice_prompt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            site_name,
            wp_url,
            wp_username,
            wp_app_password,
            woo_ck,
            woo_cs,
            brand_voice_prompt,
        ),
    )
  conn.commit()
  conn.close()


def delete_website(website_id, user_id):
  conn = get_db()
  cursor = conn.cursor()
  cursor.execute(
      "DELETE FROM websites WHERE id = ? AND user_id = ?", (website_id, user_id)
  )
  conn.commit()
  conn.close()


def save_history_entry(
    user_id, site_name, keyword, date, status, content_type, link
):
  conn = get_db()
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO history (user_id, site_name, keyword, date, status,"
      " content_type, link) VALUES (?, ?, ?, ?, ?, ?, ?)",
      (user_id, site_name, keyword, date, status, content_type, link),
  )
  conn.commit()
  conn.close()


def load_history(user_id):
  conn = get_db()
  cursor = conn.cursor()
  cursor.execute(
      "SELECT site_name, keyword, date, status, content_type, link FROM history"
      " WHERE user_id = ? ORDER BY id DESC",
      (user_id,),
  )
  rows = cursor.fetchall()
  conn.close()
  return [dict(row) for row in rows]


# ============================================================
# CORE GENERATION HELPERS
# ============================================================
def generate_text(
    prompt,
    system_prompt,
    api_base,
    api_key,
    project_id,
    model,
    temperature=0.7,
):
  if "localhost" in api_base or "127.0.0.1" in api_base:
    raise ConnectionError(
        "API Base URL đang là localhost. Vui lòng sử dụng URL Ngrok hoặc API"
        " Đám mây."
    )
  client = OpenAI(
      base_url=api_base,
      api_key=api_key,
      default_headers={"x-goog-project-id": project_id},
  )
  r = client.chat.completions.create(
      model=model,
      messages=[
          {"role": "system", "content": system_prompt},
          {"role": "user", "content": prompt},
      ],
      temperature=temperature,
  )
  return parse_ai_response(r)


def generate_image(
    prompt, api_base, api_key, project_id, model, n=1, size="1024x1024"
):
  headers = {
      "Authorization": f"Bearer {api_key}",
      "Content-Type": "application/json",
      "x-goog-project-id": project_id,
  }
  r = requests.post(
      f"{api_base.rstrip('/')}/images/generations",
      json={"model": model, "prompt": prompt, "n": n, "size": size},
      headers=headers,
      timeout=120,
  )
  r.raise_for_status()
  return r.json().get("data", [])


# ============================================================
# WP / WOOCOMMERCE HELPERS
# ============================================================
def wp_api_request_params(
    method, endpoint, wp_url, wp_username, wp_password, **kwargs
):
  token = base64.b64encode(f"{wp_username}:{wp_password}".encode()).decode(
      "utf-8"
  )
  url = (
      f"{wp_url.rstrip('/')}/wp-json/{endpoint.lstrip('/')}"
      if not endpoint.startswith("/wp-json/")
      else f"{wp_url.rstrip('/')}{endpoint}"
  )
  h = kwargs.pop("headers", {})
  h["Authorization"] = f"Basic {token}"
  return requests.request(method, url, headers=h, **kwargs)


def upload_image_to_wp(image_url, wp_url, wp_username, wp_password):
  img_r = requests.get(image_url, timeout=60)
  img_r.raise_for_status()
  b = img_r.content
  ct = img_r.headers.get("Content-Type", "image/png")
  fn = os.path.basename(image_url.split("?")[0])
  if not fn or "." not in fn:
    fn = f"image.{ct.split('/')[-1] if '/' in ct else 'png'}"
  token = base64.b64encode(f"{wp_username}:{wp_password}".encode()).decode(
      "utf-8"
  )
  mr = requests.post(
      f"{wp_url.rstrip('/')}/wp-json/wp/v2/media",
      data=b,
      headers={
          "Authorization": f"Basic {token}",
          "Content-Type": ct,
          "Content-Disposition": f'attachment; filename="{fn}"',
      },
  )
  mr.raise_for_status()
  rj = mr.json()
  return rj.get("id"), rj.get("source_url")


# ============================================================
# FULL PIPELINE EXECUTION
# ============================================================
def run_full_pipeline(
    keyword,
    brand_voice_prompt,
    word_count,
    wp_url,
    wp_username,
    wp_password,
    woo_ck,
    woo_cs,
    api_base,
    api_key,
    project_id,
    text_model,
    image_model,
    content_type="post",
    schedule_dt=None,
    serpapi_key=None,
):
  try:
    wc = int(word_count) if word_count else 1850
    title = (
        generate_text(
            prompt=(
                'Generate a catchy SEO title for a'
                f' {"blog post" if content_type == "post" else "product page"}'
                f' about "{keyword}". Target: {wc} words. Return ONLY the title.'
            ),
            system_prompt=(
                f"{brand_voice_prompt}\n\nYou are an expert headline writer."
                " Output only title."
            ),
            api_base=api_base,
            api_key=api_key,
            project_id=project_id,
            model=text_model,
        )
        .strip()
        .strip('"')
        .strip("'")
        or keyword
    )

    outline = generate_text(
        prompt=(
            f'Generate a detailed outline for a "{keyword}". Target: {wc}'
            " words. Output H2/H3, no JSON."
        ),
        system_prompt=(
            f"{brand_voice_prompt}\n\nYou are an expert SEO strategist."
        ),
        api_base=api_base,
        api_key=api_key,
        project_id=project_id,
        model=text_model,
    )

    html = (
        generate_text(
            prompt=(
                f'Write article for "{keyword}". Outline: {outline}. Target:'
                f" {wc} words. Output ONLY valid HTML."
            ),
            system_prompt=(
                f"{brand_voice_prompt}\n\nYou are an expert content writer."
            ),
            api_base=api_base,
            api_key=api_key,
            project_id=project_id,
            model=text_model,
        )
        .replace("```html", "")
        .replace("```", "")
        .strip()
    )

    if schedule_dt is None:
      schedule_dt = datetime.now()
    ps = "future" if schedule_dt > datetime.now() else "publish"

    payload = {
        "title": title,
        "content": html,
        "status": ps,
        "date": schedule_dt.isoformat(),
    }
    r = wp_api_request_params(
        "POST",
        "wp/v2/posts",
        wp_url,
        wp_username,
        wp_password,
        json=payload,
        timeout=30,
    )
    if r.status_code in [200, 201]:
      return (title, html, r.json().get("link", "#"), None, None)
    return (
        title,
        html,
        "",
        None,
        f"WP Error {r.status_code}: {r.text[:100]}",
    )
  except Exception as e:
    return ("", "", "", None, str(e))


# ============================================================
# SESSION INITIALIZATION
# ============================================================
defaults = {
    "generated_outline": "",
    "logged_in": False,
    "user_id": None,
    "username": "",
    "nav_view": "🚀 Content Generator",
}
for k, v in defaults.items():
  if k not in st.session_state:
    st.session_state[k] = v

# ============================================================
# LOGIN / REGISTER UI
# ============================================================
if not st.session_state.logged_in:
  st.markdown('<div class="login-card">', unsafe_allow_html=True)
  st.markdown("## 🔐 WP Auto-Poster PRO")
  st.caption("Nền tảng tự động hóa nội dung chuẩn SEO")
  t1, t2 = st.tabs(["Đăng nhập", "Tạo tài khoản mới"])
  with t1:
    with st.form("login"):
      lu = st.text_input("Tên đăng nhập")
      lp = st.text_input("Mật khẩu", type="password")
      if st.form_submit_button("Đăng Nhập", use_container_width=True):
        ok, msg = login_user(lu, lp)
        if ok:
          st.success(msg)
          st.rerun()
        else:
          st.error(msg)
  with t2:
    with st.form("register"):
      ru = st.text_input("Tên tài khoản mới")
      rp = st.text_input("Mật khẩu", type="password")
      rp2 = st.text_input("Nhập lại mật khẩu", type="password")
      if st.form_submit_button("Tạo Tài Khoản", use_container_width=True):
        if rp != rp2:
          st.error("Mật khẩu xác nhận không trùng khớp.")
        elif len(rp) < 4:
          st.error("Mật khẩu phải từ 4 ký tự trở lên.")
        else:
          ok, msg = register_user(ru, rp)
          st.success(msg) if ok else st.error(msg)
  st.markdown("</div>", unsafe_allow_html=True)
  st.stop()

uid = st.session_state.user_id

# ============================================================
# SIDEBAR UI (LARKEYWORD STYLE)
# ============================================================
with st.sidebar:
  st.markdown(
      """
    <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
        <div style="background: #0d9488; color: white; padding: 10px; border-radius: 14px; font-weight: bold;">⚡</div>
        <div>
            <h3 style="margin:0; font-size: 18px; font-weight: 800; color: #0f172a;">AutoPoster <span style="font-size: 11px; background: #ccfbf1; color: #0f766e; padding: 2px 6px; border-radius: 6px;">PRO</span></h3>
            <p style="margin:0; font-size: 12px; color: #64748b;">Công cụ tự động hóa nội dung</p>
        </div>
    </div>
    """,
      unsafe_allow_html=True,
  )

  is_admin = st.session_state.get("user_role") == "admin" or str(
      st.session_state.get("username")
  ).lower() in ["admin"]

  st.markdown('<div class="larkeyword-card">', unsafe_allow_html=True)
  menu_options = ["🚀 Content Generator", "🌐 Website Manager"]
  if is_admin:
    menu_options.append("⚙️ Global Settings")
  view = st.radio("Navigation", menu_options, label_visibility="collapsed")
  st.session_state.nav_view = view
  st.markdown("</div>", unsafe_allow_html=True)

  # Balance Box
  user_credits = get_user_credits(uid)
  st.markdown(
      f"""
    <div class="balance-box">
        <div style="font-size: 11px; color: #94a3b8; text-transform: uppercase; font-weight: 600;">Số dư hiện tại</div>
        <div style="font-size: 22px; font-weight: 800; color: #34d399; margin: 4px 0;">{user_credits:,.0f} VNĐ</div>
        <div style="font-size: 11px; color: #cbd5e1;">Chi phí: 2,000 VNĐ / bài đăng</div>
    </div>
    """,
      unsafe_allow_html=True,
  )

  # Bank Info
  st.markdown(
      f"""
    <div class="bank-box">
        <div style="font-weight: 700; color: #0f172a; margin-bottom: 6px; display: flex; justify-content: space-between;">
            <span>🏦 MB BANK</span>
            <span style="color: #0284c7; font-size: 11px;">Chuyển khoản 24/7</span>
        </div>
        <div>STK: <b style="color: #0284c7; font-size: 15px;">999937799</b></div>
        <div>Chủ TK: <b>LƯƠNG HUỲNH HIẾU</b></div>
        <div style="margin-top: 6px; padding-top: 6px; border-top: 1px solid #e2e8f0; font-size: 12px;">
            Nội dung CK: <b style="color: #059669;">NAP {st.session_state.get('username', 'user')}</b>
        </div>
    </div>
    """,
      unsafe_allow_html=True,
  )

  st.markdown("---")
  if st.button("🚪 Đăng xuất", use_container_width=True):
    logout_user()
    st.rerun()

# ============================================================
# VIEW 1: 🚀 CONTENT GENERATOR
# ============================================================
if st.session_state.nav_view == "🚀 Content Generator":
  st.markdown(
      """
    <div class="header-banner">
        <h1>🚀 Content Generator</h1>
        <p>Tạo nội dung tự động chuẩn SEO & xuất bản lên WordPress</p>
    </div>
    """,
      unsafe_allow_html=True,
  )

  websites = get_websites(uid)
  if not websites:
    st.warning(
        "⚠️ Chưa có Website nào được cấu hình. Vui lòng sang **🌐 Website"
        " Manager** để thêm website!"
    )
  else:
    site_options = {w["site_name"]: w for w in websites}
    selected_site_name = st.selectbox(
        "🎯 เลือก Target Website", options=list(site_options.keys())
    )
    selected_site = site_options[selected_site_name]

    c1, c2 = st.columns([2, 1], gap="large")
    with c2:
      st.markdown("#### ⚙️ Cấu hình Bài viết")
      word_count = st.slider("Số lượng từ", 500, 3000, 1850, 50)
      sched_date = st.date_input("Ngày đăng", key="gen_date")
      sched_time = st.time_input("Giờ đăng", key="gen_time")

    with c1:
      keyword = st.text_input(
          "🔑 Từ khóa chính", placeholder="vd: Khám nam khoa uy tín"
      )
      custom_outline = st.text_area(
          "📝 Dàn ý bài viết (Outline)",
          value=st.session_state.generated_outline,
          height=200,
      )

      if st.button(
          "🚀 Generate & Publish", use_container_width=True, type="primary"
      ):
        if not keyword:
          st.error("Vui lòng nhập từ khóa chính!")
        elif user_credits < 2000:
          st.error(
              "⚠️ Số dư tài khoản không đủ (Cần 2,000 VNĐ/bài). Vui lòng nạp"
              " thêm điểm!"
          )
        else:
          with st.spinner("Đang khởi tạo bài viết từ AI..."):
            dt = datetime.combine(sched_date, sched_time)
            api_base = st.session_state.get("local_api_base", LOCAL_API_BASE)
            api_key = st.session_state.get("local_api_key", LOCAL_API_KEY)

            title, html, link, fmid, err = run_full_pipeline(
                keyword=keyword,
                brand_voice_prompt=selected_site.get("brand_voice_prompt", ""),
                word_count=word_count,
                wp_url=selected_site["wp_url"],
                wp_username=selected_site["wp_username"],
                wp_password=selected_site["wp_app_password"],
                woo_ck="",
                woo_cs="",
                api_base=api_base,
                api_key=api_key,
                project_id=LOCAL_PROJECT_ID,
                text_model=LOCAL_MODEL,
                image_model=LOCAL_IMAGE_MODEL,
                schedule_dt=dt,
            )

            if err is None and link:
              deduct_user_credit(uid, 2000)  # Chỉ trừ tiền khi ĐÃ ĐĂNG THÀNH CÔNG
              st.success(f"✅ Đã đăng bài thành công lên {selected_site_name}!")
              st.markdown(f"[🔗 Xem bài viết tại đây]({link})")
              save_history_entry(
                  uid,
                  selected_site_name,
                  keyword,
                  dt.strftime("%Y-%m-%d %H:%M"),
                  "publish",
                  "post",
                  link,
              )
              st.rerun()
            else:
              st.error(
                  f"❌ Đăng bài thất bại: {err}. (Số dư của bạn không bị trừ)."
              )

  st.markdown("---")
  st.markdown("### 📜 Lịch sử Giao dịch / Nạp tiền")
  txn_data = get_credit_transactions(uid)
  if txn_data:
    txn_rows = []
    for t in txn_data:
      amt = t["amount"]
      badge = (
          f'<span class="badge-success">+{amt:,.0f} VNĐ</span>'
          if amt > 0
          else f'<span class="badge-amber">{amt:,.0f} VNĐ</span>'
      )
      txn_rows.append({
          "Thời gian": t["created_at"],
          "Loại": t["type"],
          "Mô tả": t["description"],
          "Số tiền": badge,
      })
    st.markdown(
        pd.DataFrame(txn_rows).to_html(index=False, escape=False),
        unsafe_allow_html=True,
    )
  else:
    st.info("Chưa có lịch sử giao dịch.")

# ============================================================
# VIEW 2: 🌐 WEBSITE MANAGER
# ============================================================
elif st.session_state.nav_view == "🌐 Website Manager":
  st.markdown(
      """
    <div class="header-banner">
        <h1>🌐 Website Manager</h1>
        <p>Quản lý các trang WordPress kết nối tự động</p>
    </div>
    """,
      unsafe_allow_html=True,
  )
  with st.form("add_site"):
    sn = st.text_input("Tên Website *")
    wu = st.text_input("Đường dẫn (WP URL) *", placeholder="https://site.com")
    usr = st.text_input("Tên đăng nhập WP *")
    pwd = st.text_input("Mật khẩu ứng dụng (App Password) *", type="password")
    if st.form_submit_button("💾 Lưu Website", type="primary"):
      if sn and wu and usr and pwd:
        save_website(uid, sn, wu, usr, pwd, "", "", "Professional voice")
        st.success("✅ Đã thêm website mới thành công!")
        st.rerun()

# ============================================================
# VIEW 3: ⚙️ GLOBAL SETTINGS (ADMIN ONLY)
# ============================================================
elif st.session_state.nav_view == "⚙️ Global Settings":
  st.markdown(
      """
    <div class="header-banner">
        <h1>⚙️ Global Settings & Quản lý Điểm</h1>
    </div>
    """,
      unsafe_allow_html=True,
  )

  st.markdown("#### 🤖 Cấu hình AI API")
  lab = st.text_input(
      "API Base URL",
      value=st.session_state.get("local_api_base", LOCAL_API_BASE),
  )
  lak = st.text_input(
      "API Key",
      value=st.session_state.get("local_api_key", LOCAL_API_KEY),
      type="password",
  )
  if st.button("💾 Lưu cấu hình API"):
    save_user_setting(uid, "local_api_base", lab)
    save_user_setting(uid, "local_api_key", lak)
    st.success("✅ Đã lưu cấu hình API thành công!")

  st.markdown("---")
  st.markdown("#### 💰 Quản lý Nạp tiền cho Khách hàng")
  conn = get_db()
  cursor = conn.cursor()
  cursor.execute("SELECT id, username, credits FROM users ORDER BY id")
  all_users = cursor.fetchall()
  conn.close()

  if all_users:
    c_usr, c_amt, c_btn = st.columns([2, 1, 1])
    with c_usr:
      selected_user_idx = st.selectbox(
          "Chọn Tài khoản Khách hàng",
          options=range(len(all_users)),
          format_func=lambda i: (
              f"{all_users[i]['username']} (Dư:"
              f" {all_users[i]['credits']:,.0f}đ)"
          ),
      )
      selected_user = all_users[selected_user_idx]
    with c_amt:
      credit_amount = st.number_input(
          "Số tiền nạp (VNĐ)", value=50000, min_value=1000, step=10000
      )
    with c_btn:
      st.markdown(
          "<div style='height:1.8rem;'></div>", unsafe_allow_html=True
      )
      if st.button("➕ Cộng tiền", type="primary"):
        add_credits(
            selected_user["id"],
            credit_amount,
            f"Admin nạp {credit_amount:,.0f} VNĐ",
        )
        st.success(
            f"✅ Đã nạp thành công {credit_amount:,.0f} VNĐ cho tài khoản"
            f" {selected_user['username']}!"
        )
        st.rerun()
