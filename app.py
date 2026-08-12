# WP Auto-Poster PRO — Streamlit client
# Gọi /v1/chat/completions tới Express proxy (thư mục server/) tại LOCAL_API_BASE.
# Client tự fallback credentials mặc định hệ thống khi user mới / chưa có key.

import streamlit as st
import sqlite3
import hashlib
import secrets
from openai import OpenAI
import requests
import json
import re
import os
import base64
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import pandas as pd
import time
import threading
import schedule as schedule_lib
try:
    import linker  # auto internal-link inserter (linker.py)
except Exception:
    linker=None
import dashboard  # Dashboard hiệu suất (dashboard.py)

DB_FILE = "/tmp/autoposter_data.db"
LOCAL_API_BASE = "http://localhost:3003/v1"
LOCAL_API_KEY = "AQ.Ab8RN6IjV-QWSXPxSIydANNNuh8a2bdOh_wkBRWd_diI7s67Tw"
LOCAL_PROJECT_ID = "777992117459"
LOCAL_MODEL = "gemini-3.6-flash"
LOCAL_IMAGE_MODEL = "gemini-3.1-flash-image"
DEFAULT_SERPAPI_KEY = "eb7a6f72642ad4ffd0dc63c39e2a129d577825b86837b56a4bd86ca233eaf6f6"

st.set_page_config(page_title="WP Auto-Poster PRO", page_icon="✨", layout="wide", initial_sidebar_state="expanded")

# CSS (kept minimal — your existing CSS is preserved in the original file)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="st-"]{font-family:'Inter',-apple-system,BlinkMacSystemFont,sans-serif}
[data-testid="stSidebar"]{background-color:#f8fafc!important;min-width:340px!important;max-width:360px!important;border-right:1px solid #e2e8f0!important}
[data-testid="stSidebar"]>div:first-child{padding:1.5rem 1rem!important}
[data-testid="stSidebar"] *{word-break:normal!important;white-space:normal!important}
.larkeyword-card{background-color:#fff;border-radius:24px;padding:20px 16px;box-shadow:0 10px 30px -5px rgba(0,0,0,0.05);border:1px solid #e2e8f0;margin-bottom:16px}
[data-testid="stSidebar"] div[role="radiogroup"]{gap:8px}
[data-testid="stSidebar"] div[role="radiogroup"] label{background-color:transparent!important;border-radius:12px!important;padding:10px 16px!important;border:1px solid transparent!important;transition:all .2s ease!important;font-weight:500!important;color:#334155!important;cursor:pointer!important}
[data-testid="stSidebar"] div[role="radiogroup"] label:hover{background-color:#f1f5f9!important}
[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"]{background-color:#ccfbf1!important;color:#0f766e!important;font-weight:700!important}
[data-testid="stSidebar"] div[role="radiogroup"] label>div:first-child{display:none!important}
.balance-box{background:linear-gradient(135deg,#0f172a 0%,#1e293b 100%);color:#fff;border-radius:16px;padding:16px;margin-bottom:12px}
.bank-box{background:#f8fafc;border:1px dashed #cbd5e1;border-radius:14px;padding:14px;font-size:13px;color:#334155}
.header-banner{background:linear-gradient(135deg,#6D28D9 0%,#7C3AED 50%,#8B5CF6 100%);padding:1.5rem 2rem;border-radius:16px;margin-bottom:1.5rem;color:white;box-shadow:0 10px 25px -5px rgba(124,58,237,0.3)}
.header-banner h1{font-size:1.75rem;font-weight:700;color:white!important}
.stButton>button{width:100%;border-radius:.5rem;font-weight:600;font-size:.9rem!important;padding:.5rem 1.5rem!important;transition:all .2s!important;border:none!important}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#7C3AED,#6D28D9)!important;color:white!important;box-shadow:0 4px 12px rgba(124,58,237,0.3)!important}
.badge-success{display:inline-block;background:#D1FAE5;color:#065F46;padding:.15rem .65rem;border-radius:20px;font-size:.75rem;font-weight:600}
.badge-purple{display:inline-block;background:#EDE9FE;color:#5B21B6;padding:.15rem .65rem;border-radius:20px;font-size:.75rem;font-weight:600}
.badge-amber{display:inline-block;background:#FEF3C7;color:#92400E;padding:.15rem .65rem;border-radius:20px;font-size:.75rem;font-weight:600}
.login-card{max-width:420px;margin:3rem auto;background:white;border-radius:20px;padding:2.5rem;box-shadow:0 20px 60px -20px rgba(0,0,0,0.1);border:1px solid #F3F4F6}
.stTabs [aria-selected="true"]{color:#0d9488!important;border-bottom:3px solid #0d9488!important}
</style>
""", unsafe_allow_html=True)

# DB
def get_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db(); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY AUTOINCREMENT,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'user',credits REAL DEFAULT 2000.0,session_token TEXT DEFAULT '',created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
    for col,defv in [("role","'user'"),("credits","2000.0"),("session_token","''")]:
        try: c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT NOT NULL DEFAULT {defv}"); conn.commit()
        except: pass
    c.execute("CREATE TABLE IF NOT EXISTS user_settings(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,key TEXT NOT NULL,value TEXT,UNIQUE(user_id,key),FOREIGN KEY(user_id) REFERENCES users(id))")
    c.execute("CREATE TABLE IF NOT EXISTS global_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL DEFAULT '')")
    c.execute("CREATE TABLE IF NOT EXISTS websites(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,site_name TEXT NOT NULL,wp_url TEXT NOT NULL DEFAULT '',wp_username TEXT NOT NULL DEFAULT '',wp_app_password TEXT NOT NULL DEFAULT '',woo_ck TEXT NOT NULL DEFAULT '',woo_cs TEXT NOT NULL DEFAULT '',brand_voice_prompt TEXT NOT NULL DEFAULT 'You are an expert SEO content writer.',created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id) REFERENCES users(id))")
    c.execute("CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,site_name TEXT DEFAULT '',keyword TEXT,date TEXT,status TEXT,content_type TEXT DEFAULT 'post',link TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id) REFERENCES users(id))")
    conn.commit()
    for col,defv in [("content_type","'post'"),("site_name","''")]:
        try: c.execute(f"ALTER TABLE history ADD COLUMN {col} TEXT DEFAULT {defv}"); conn.commit()
        except: pass
    c.execute("CREATE TABLE IF NOT EXISTS credit_transactions(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER NOT NULL,amount REAL NOT NULL,type TEXT NOT NULL,description TEXT,created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id) REFERENCES users(id))")
    conn.commit()
    c.execute("SELECT COUNT(*) as cnt FROM users")
    if c.fetchone()["cnt"]==0:
        c.execute("INSERT INTO users(username,password_hash,role,credits) VALUES(?,?,?,?)",("admin",hashlib.sha256("admin123".encode()).hexdigest(),"admin",100000))
        conn.commit()
    # Migration: nếu chưa có global_settings và admin từng lưu cấu hình AI khác mặc định → copy sang global
    c.execute("SELECT COUNT(*) as cnt FROM global_settings")
    if c.fetchone()["cnt"]==0:
        c.execute("SELECT id FROM users WHERE username='admin' LIMIT 1");ar=c.fetchone()
        if ar:
            defaults={"local_api_base":LOCAL_API_BASE,"local_api_key":LOCAL_API_KEY,"local_project_id":LOCAL_PROJECT_ID,"local_model":LOCAL_MODEL,"local_image_model":LOCAL_IMAGE_MODEL,"serpapi_keys":DEFAULT_SERPAPI_KEY}
            c.execute("SELECT key,value FROM user_settings WHERE user_id=? AND key LIKE 'local_%' OR (user_id=? AND key='serpapi_keys')",(ar["id"],ar["id"]))
            for r in c.fetchall():
                if defaults.get(r["key"])!=r["value"]:
                    c.execute("INSERT OR IGNORE INTO global_settings(key,value) VALUES(?,?)",(r["key"],r["value"]))
            conn.commit()
    conn.close()
init_db()

# CREDIT
def get_user_credits(uid):
    conn=get_db();c=conn.cursor();c.execute("SELECT credits FROM users WHERE id=?",(uid,));r=c.fetchone();conn.close()
    return float(r["credits"]) if r and r["credits"] is not None else 0.0
def add_credits(uid,amt,desc="Nạp điểm"):
    conn=get_db();c=conn.cursor()
    c.execute("UPDATE users SET credits=COALESCE(credits,0)+? WHERE id=?",(amt,uid))
    c.execute("INSERT INTO credit_transactions(user_id,amount,type,description) VALUES(?,?,'RECHARGE',?)",(uid,amt,desc))
    conn.commit();conn.close()
def deduct_user_credit(uid,cost=2000):
    cur=get_user_credits(uid)
    if cur<cost: return False
    conn=get_db();c=conn.cursor()
    c.execute("UPDATE users SET credits=credits-? WHERE id=?",(cost,uid))
    c.execute("INSERT INTO credit_transactions(user_id,amount,type,description) VALUES(?,-2000,'DEDUCT','Đăng bài viết thành công')",(uid,))
    conn.commit();conn.close()
    return True
def get_cost_per_post(): return 2000
def get_credit_transactions(uid,limit=20):
    conn=get_db();c=conn.cursor()
    c.execute("SELECT amount,type,description,created_at FROM credit_transactions WHERE user_id=? ORDER BY id DESC LIMIT ?",(uid,limit))
    rows=c.fetchall();conn.close()
    return [dict(r) for r in rows]

# SESSION
for k,v in {"generated_outline":"","logged_in":False,"user_id":None,"username":"","user_role":None,"session_token":"","worker_started":False,"nav_view":"🚀 Content Generator","editing_site":None}.items():
    if k not in st.session_state: st.session_state[k]=v

# AUTH
def hash_password(pw): return hashlib.sha256(pw.encode()).hexdigest()
def vn_tz():
    try:
        import pytz
        return pytz.timezone("Asia/Ho_Chi_Minh")
    except Exception:
        return None
def vn_now():
    """Giờ Việt Nam hiện tại (UTC+7), dạng naive wall-clock — dùng cho lịch đăng & log."""
    tz=vn_tz()
    if tz is not None:
        try: return datetime.now(tz).replace(tzinfo=None)
        except Exception: pass
    return datetime.now()
def is_future(dt_):
    """True nếu dt_ (naive = giờ VN hoặc aware) nằm trong tương lai so với giờ VN hiện tại."""
    if dt_ is None: return False
    tz=vn_tz()
    try:
        if tz is not None and dt_.tzinfo is None: dt_=tz.localize(dt_)
        now=datetime.now(tz) if tz is not None else datetime.now()
        return dt_>now
    except Exception:
        return False
def api_log(msg):
    try: print(f"[{vn_now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}",flush=True)
    except Exception: print(msg,flush=True)
def new_session_token(): return secrets.token_hex(32)
def get_user_by_session_token(tok):
    if not tok: return None
    conn=get_db();c=conn.cursor()
    c.execute("SELECT id,username,role FROM users WHERE session_token=?",(str(tok),));u=c.fetchone();conn.close()
    return dict(u) if u else None
def restore_session_from_token():
    """Tự đăng nhập lại khi session_state bị reset (VD: refresh trình duyệt / server restart).
    Token lưu trong query param 'kt' — được đặt khi đăng nhập/đăng ký."""
    if st.session_state.get("logged_in"): return
    tok=st.query_params.get("kt") if hasattr(st,"query_params") else None
    if isinstance(tok,list): tok=tok[0] if tok else ""
    tok=tok or ""
    u=get_user_by_session_token(tok)
    if u:
        st.session_state.logged_in=True;st.session_state.user_id=u["id"];st.session_state.username=u["username"];st.session_state.user_role=u["role"] or "user";st.session_state.session_token=tok
        api_log(f"🔓 Tự đăng nhập lại user '{u['username']}' từ session token")
    else:
        try: st.query_params.clear()
        except Exception: pass
def _key_prefix(k):
    if not k: return "EMPTY"
    return f"{k[:8]}..." if len(k)>8 else k
def _is_auth_conn_error(e):
    """True nếu lỗi liên quan xác thực (401/403/missing credentials) hoặc kết nối (connection error/reset)."""
    msg=str(e).lower()
    status=getattr(e,"status_code",None)
    if status is None:
        resp=getattr(e,"response",None);status=getattr(resp,"status_code",None) if resp else None
    if status in (401,403): return True
    return any(s in msg for s in [
        "authentication","unauthorized","missing credentials","api key","invalid api",
        "401","403","forbidden",
        "connection error","connection reset","connection aborted","connected aborted",
        "failed to connect","econnrefused","closed","timeout","network",
    ])
def _port_of(u):
    """Lấy cổng từ base URL, VD http://localhost:3003/v1 -> 3003."""
    try: return u.split("//")[1].split("/")[0].split(":")[1]
    except Exception: return "3003"
def _base_variants(ab):
    """Các biến thể host của cùng API base (localhost ↔ 127.0.0.1) để tránh
    lỗi connection khi server chỉ lắng nghe trên một giao thức IPv4 hoặc IPv6."""
    if not ab: return [ab]
    out=[ab]
    for a,b in (("localhost","127.0.0.1"),("127.0.0.1","localhost")):
        if a in ab:
            alt=ab.replace(a,b)
            if alt not in out: out.append(alt)
    return out
def _friendly_error(e, base):
    """Chuyển lỗi thô (Connection error / 401) thành thông báo hướng dẫn khắc phục."""
    msg=str(e);low=msg.lower()
    if any(s in low for s in ("connection error","connection reset","connected aborted","connection aborted","econnrefused","failed to connect","closed","timeout","network is unreachable")):
        return (f"❌ Không kết nối được AI server tại '{base}'. Hướng dẫn: "
                f"(1) chạy server: cd server && npm install && npm start; "
                f"(2) server/.env đặt PORT={_port_of(LOCAL_API_BASE)} để khớp app ({LOCAL_API_BASE}); "
                f"(3) API Base URL trong Global Settings phải có đuôi /v1. "
                f"Chi tiết: {type(e).__name__}: {e}")
    if any(s in low for s in ("401","403","unauthorized","forbidden","authentication","missing credentials","api key")):
        return (f"❌ AI server từ chối xác thực ({type(e).__name__}). Kiểm tra server/.env: "
                f"PROXY_ALLOW_FALLBACK=true và đã cấu hình ApiKey admin trong DB hoặc GEMINI_API_KEY. | {e}")
    return f"{type(e).__name__}: {e}"
def init_user_default_settings(uid):
    """Tự động khởi tạo đầy đủ dữ liệu mặc định cho tài khoản mới:
    API base/key/project mặc định hệ thống, model, serpapi key (credentials mặc định)."""
    for k,v in [("local_api_base",LOCAL_API_BASE),("local_api_key",LOCAL_API_KEY),
                ("local_project_id",LOCAL_PROJECT_ID),("local_model",LOCAL_MODEL),
                ("local_image_model",LOCAL_IMAGE_MODEL),("serpapi_keys",DEFAULT_SERPAPI_KEY)]:
        try: save_user_setting(uid,k,v)
        except Exception as e: api_log(f"init_user_default_settings: không tạo được {k} cho user {uid}: {e}")
def register_user(un,pw,role='user'):
    conn=get_db();c=conn.cursor()
    try:
        tok=new_session_token()
        c.execute("INSERT INTO users(username,password_hash,role,credits,session_token) VALUES(?,?,?,?,?)",(un,hash_password(pw),role,2000,tok))
        uid=c.lastrowid
        c.execute("INSERT INTO credit_transactions(user_id,amount,type,description) VALUES(?,2000,'BONUS','Tặng 1 bài viết trải nghiệm')",(uid,))
        conn.commit()
        init_user_default_settings(uid)
        api_log(f"✅ Đăng ký '{un}' (id={uid}): credits=2000, API key mặc định + session token đã khởi tạo")
        return True,"Registration successful!"
    except sqlite3.IntegrityError: return False,"Username already exists."
    finally: conn.close()
def login_user(un,pw):
    conn=get_db();c=conn.cursor()
    c.execute("SELECT id,username,password_hash,role FROM users WHERE username=?",(un,));u=c.fetchone()
    if u and u["password_hash"]==hash_password(pw):
        role=u["role"] or "user"
        if str(un).lower()=="admin" and role!="admin": c.execute("UPDATE users SET role='admin' WHERE id=?",(u["id"],));conn.commit();role="admin"
        tok=new_session_token();c.execute("UPDATE users SET session_token=? WHERE id=?",(tok,u["id"]));conn.commit()
        conn.close()
        st.session_state.logged_in=True;st.session_state.user_id=u["id"];st.session_state.username=u["username"];st.session_state.user_role=role;st.session_state.session_token=tok
        try: st.query_params["kt"]=tok  # lưu token vào URL để tự đăng nhập lại khi refresh
        except Exception: pass
        return True,"Login successful!"
    conn.close();return False,"Invalid username or password."
def logout_user():
    for k in ["logged_in","user_id","username","user_role","generated_outline","editing_site","session_token"]:
        if k in st.session_state: st.session_state[k]=False if k=="logged_in" else(None if k in["user_id","editing_site","user_role","session_token"] else "")
    try: st.query_params.clear()  # xoá token tự đăng nhập
    except Exception: pass
    st.session_state.worker_started=False

def save_user_setting(uid,k,v):
    conn=get_db();c=conn.cursor()
    c.execute("INSERT INTO user_settings(user_id,key,value) VALUES(?,?,?) ON CONFLICT(user_id,key) DO UPDATE SET value=excluded.value",(uid,k,v))
    conn.commit();conn.close()
def get_all_user_settings(uid):
    conn=get_db();c=conn.cursor();c.execute("SELECT key,value FROM user_settings WHERE user_id=?",(uid,));rows=c.fetchall();conn.close()
    return {r["key"]:r["value"] for r in rows}

def get_websites(uid):
    conn=get_db();c=conn.cursor();c.execute("SELECT * FROM websites WHERE user_id=? ORDER BY id",(uid,));rows=c.fetchall();conn.close()
    return [dict(r) for r in rows]
def get_website_by_id(wid):
    conn=get_db();c=conn.cursor();c.execute("SELECT * FROM websites WHERE id=?",(wid,));r=c.fetchone();conn.close()
    return dict(r) if r else None
def get_website_by_name(uid,sn):
    conn=get_db();c=conn.cursor();c.execute("SELECT * FROM websites WHERE user_id=? AND site_name=?",(uid,sn));r=c.fetchone();conn.close()
    return dict(r) if r else None
def save_website(uid,sn,wu,wu2,wp,ck,cs,bv,website_id=None):
    conn=get_db();c=conn.cursor()
    if website_id: c.execute("UPDATE websites SET site_name=?,wp_url=?,wp_username=?,wp_app_password=?,woo_ck=?,woo_cs=?,brand_voice_prompt=? WHERE id=? AND user_id=?",(sn,wu,wu2,wp,ck,cs,bv,website_id,uid))
    else: c.execute("INSERT INTO websites(user_id,site_name,wp_url,wp_username,wp_app_password,woo_ck,woo_cs,brand_voice_prompt) VALUES(?,?,?,?,?,?,?,?)",(uid,sn,wu,wu2,wp,ck,cs,bv))
    conn.commit();conn.close()
def delete_website(wid,uid):
    conn=get_db();c=conn.cursor();c.execute("DELETE FROM websites WHERE id=? AND user_id=?",(wid,uid));conn.commit();conn.close()
def save_history_entry(uid,sn,kw,dt,st,ct,link):
    conn=get_db();c=conn.cursor()
    c.execute("INSERT INTO history(user_id,site_name,keyword,date,status,content_type,link) VALUES(?,?,?,?,?,?,?)",(uid,sn,kw,dt,st,ct,link))
    conn.commit();conn.close()
def load_history(uid):
    conn=get_db();c=conn.cursor()
    c.execute("SELECT site_name,keyword,date,status,content_type,link FROM history WHERE user_id=? ORDER BY id DESC",(uid,))
    rows=c.fetchall();conn.close();return [dict(r) for r in rows]

# ★★★ FIX: parse_ai_response BEFORE generate_text ★★★
def _clean_json(raw):
    """Chuẩn hoá nội dung JSON-LD: bỏ code fence, khai báo biến JS (const x = ...),
    bỏ dấu ';' cuối. Trả về chuỗi JSON thuần túy { ... } hoặc None nếu không sửa được."""
    if raw is None: return None
    s=str(raw).strip()
    if not s: return None
    # Bỏ code fence ```json ... ```
    s=re.sub(r'^```(?:json)?\s*','',s).rstrip('`').strip()
    # Bỏ khai báo biến JavaScript: const|let|var name = ... hoặc export default ...
    s=re.sub(r'^(?:export\s+default\s+)?(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*','',s,flags=re.M).strip()
    # Bỏ dấu ';' ở cuối
    s=s.rstrip(';').strip()
    # Thử parse trực tiếp
    try:
        obj=json.loads(s)
        return json.dumps(obj,ensure_ascii=False,indent=2)
    except Exception:
        pass
    # Thử trích đối tượng { ... } đầu tiên (bỏ phần khai báo/thừa)
    try:
        dec=json.JSONDecoder()
        start=s.find('{')
        if start>=0:
            obj,_=dec.raw_decode(s[start:])
            return json.dumps(obj,ensure_ascii=False,indent=2)
    except Exception:
        pass
    return None

def clean_jsonld_schema(html):
    """Dọn mọi khối <script type="application/ld+json"> trong HTML:
    chỉ giữ JSON thuần túy { ... } — KHÔNG biến JS (const ... =), KHÔNG dấu ';' ở cuối.
    Khối nào không sửa được (JSON không hợp lệ) sẽ bị gỡ bỏ để không phá trang."""
    if not html or not isinstance(html,str): return html
    try: soup=BeautifulSoup(html,'html.parser')
    except Exception: return html
    changed=False
    for sc in soup.find_all('script'):
        stype=(sc.get('type') or '').strip().lower()
        if stype not in ('application/ld+json','application/json'): continue
        raw=sc.get_text() if sc.string is None else sc.string
        cleaned=_clean_json(raw)
        if cleaned is not None:
            sc.string=cleaned
            changed=True
        else:
            sc.decompose()  # JSON-LD lỗi -> bỏ khối
            changed=True
    return str(soup) if changed else html

def parse_ai_response(response):
    """Safely extract text content from various AI API response formats.
    Raises ValueError if the response contains Kira Agent Platform web UI HTML
    instead of actual AI-generated text."""
    # Extract the raw text content first
    if isinstance(response, str):
        try:
            data = json.loads(response)
            if isinstance(data, dict) and "choices" in data:
                content = data["choices"][0]["message"]["content"]
            else:
                content = response
        except (json.JSONDecodeError, ValueError):
            content = response
    elif isinstance(response, dict):
        if "choices" in response:
            content = response["choices"][0]["message"]["content"]
        else:
            content = str(response)
    elif hasattr(response, "choices"):
        content = response.choices[0].message.content
    else:
        content = str(response)

    # Guard: detect if the API returned web UI HTML instead of AI text
    content_lower = content.lower() if isinstance(content, str) else ""
    if isinstance(content, str) and (
        "<div class=\"app-container\"" in content_lower
        or "<aside" in content_lower
        or "class=\"sidebar-menu\"" in content_lower
        or "sidebar-menu" in content_lower
        or content.strip().startswith("<!doctype html")
    ):
        raise ValueError(
            "❌ Lỗi API: Endpoint trả về giao diện Web Kira Agent thay vì JSON. "
            "Vui lòng kiểm tra lại API Base URL (thêm /v1) hoặc tắt Auth trên Local Server 3003."
        )

    return content

def generate_text(prompt, sp, ab, ak, pid, model, temp=0.7):
    # Fallback credentials mặc định hệ thống nếu user mới / chưa cấu hình key
    ab=ab or LOCAL_API_BASE;pid=pid or LOCAL_PROJECT_ID;ak=ak or LOCAL_API_KEY;model=model or LOCAL_MODEL
    sys_default=(LOCAL_API_BASE,LOCAL_API_KEY,LOCAL_PROJECT_ID)
    attempts=[];seen=set()
    for (uab,uak,upid) in [(ab,ak,pid)]+([sys_default] if (ab,ak,pid)!=sys_default else []):
        for bv in _base_variants(uab):
            key=(bv,uak,upid)
            if key not in seen: seen.add(key);attempts.append(key)
    last_err=None
    for i,(uab,uak,upid) in enumerate(attempts,1):
        try:
            hdrs={"x-goog-project-id":upid,"ngrok-skip-browser-warning":"true","User-Agent":"WPAutoPosterPRO/1.0"}
            client=OpenAI(base_url=uab,api_key=uak if uak else "dummy_key",default_headers=hdrs)
            r=client.chat.completions.create(model=model,messages=[{"role":"system","content":sp},{"role":"user","content":prompt}],temperature=temp)
            api_log(f"generate_text OK | base={uab} model={model} key={_key_prefix(uak)} attempt={i}/{len(attempts)}")
            return parse_ai_response(r)
        except Exception as e:
            last_err=e
            api_log(f"generate_text LỖI attempt={i}/{len(attempts)} | base={uab} model={model} key={_key_prefix(uak)} | {type(e).__name__}: {e}")
            if i<len(attempts) and _is_auth_conn_error(e): continue
            break
    raise RuntimeError(_friendly_error(last_err, ab))

def generate_image(prompt,ab,ak,pid,model,n=1,size="1024x1024"):
    ab=ab or LOCAL_API_BASE;pid=pid or LOCAL_PROJECT_ID;ak=ak or LOCAL_API_KEY;model=model or LOCAL_IMAGE_MODEL
    sys_default=(LOCAL_API_BASE,LOCAL_API_KEY,LOCAL_PROJECT_ID)
    attempts=[];seen=set()
    for (uab,uak,upid) in [(ab,ak,pid)]+([sys_default] if (ab,ak,pid)!=sys_default else []):
        for bv in _base_variants(uab):
            key=(bv,uak,upid)
            if key not in seen: seen.add(key);attempts.append(key)
    last_err=None
    for i,(uab,uak,upid) in enumerate(attempts,1):
        try:
            h={"Authorization":f"Bearer {uak}","Content-Type":"application/json","x-goog-project-id":upid,"ngrok-skip-browser-warning":"true","User-Agent":"WPAutoPosterPRO/1.0"}
            r=requests.post(f"{uab.rstrip('/')}/images/generations",json={"model":model,"prompt":prompt,"n":n,"size":size},headers=h,timeout=120)
            api_log(f"generate_image HTTP {r.status_code} | base={uab} model={model} key={_key_prefix(uak)} attempt={i}/{len(attempts)}")
            if r.status_code in (401,403):
                if i<len(attempts): continue
                r.raise_for_status()
            r.raise_for_status()
            return r.json().get("data",[])
        except Exception as e:
            last_err=e
            api_log(f"generate_image LỖI attempt={i}/{len(attempts)} | base={uab} model={model} key={_key_prefix(uak)} | {type(e).__name__}: {e}")
            if i<len(attempts) and _is_auth_conn_error(e): continue
            break
    raise RuntimeError(_friendly_error(last_err, ab))

# SERPAPI
def get_serpapi_keys():
    ks=st.session_state.get("serpapi_keys","")
    return [k.strip() for k in ks.split("\n") if k.strip()] if ks else []
def check_serpapi_account(ak):
    try:
        r=requests.get(f"https://serpapi.com/account?api_key={ak}",timeout=10)
        if r.status_code!=200: return {"valid":False,"plan":"N/A","searches_per_month":0,"plan_searches_left":0,"total_searches":0,"error":f"HTTP {r.status_code}"}
        d=r.json()
        return {"valid":True,"plan":d.get("plan_name","Unknown"),"searches_per_month":d.get("plan_searches_per_month",0),"plan_searches_left":d.get("plan_searches_left",0),"total_searches":d.get("total_searches",0),"error":None}
    except Exception as e: return {"valid":False,"plan":"N/A","searches_per_month":0,"plan_searches_left":0,"total_searches":0,"error":str(e)}
def get_active_serpapi_key():
    keys=get_serpapi_keys()
    if not keys: raise RuntimeError("No SerpApi keys configured.")
    errs=[]
    for k in keys:
        info=check_serpapi_account(k)
        if info["valid"] and info["plan_searches_left"]>0: return k,info
        elif info["valid"]: errs.append(f"Key {k[:8]}... has 0 searches left")
        else: errs.append(f"Key {k[:8]}... is invalid: {info.get('error','Unknown')}")
    raise RuntimeError(f"All SerpApi keys have exceeded their monthly quota.\n"+"\n".join(errs))
def get_google_top10_outlines(kw,sk=None):
    if sk is None:
        try: sk,_=get_active_serpapi_key()
        except RuntimeError: return []
    try:
        r=requests.get("https://serpapi.com/search.json",params={"q":kw,"location":"Vietnam","hl":"vi","gl":"vn","api_key":sk,"num":10},timeout=15)
        r.raise_for_status()
        return [{"title":x.get("title",""),"link":x.get("link",""),"snippet":x.get("snippet","")} for x in r.json().get("organic_results",[])[:10]]
    except: return []

# WP/WOO
def wp_api_request_params(method,ep,wu,wu2,wp,**kw):
    tok=base64.b64encode(f"{wu2}:{wp}".encode()).decode()
    url=f"{wu.rstrip('/')}/wp-json/{ep.lstrip('/')}" if not ep.startswith("/wp-json/") else f"{wu.rstrip('/')}{ep}"
    h=kw.pop("headers",{});h["Authorization"]=f"Basic {tok}"
    return requests.request(method,url,headers=h,**kw)
def woo_api_request_params(method,ep,wu,ck,cs,**kw):
    url=f"{wu.rstrip('/')}/wp-json/wc/v3/{ep.lstrip('/')}" if not ep.startswith("/wp-json/wc/") else f"{wu.rstrip('/')}{ep}"
    return requests.request(method,url,auth=(ck,cs),**kw)
def upload_image_to_wp(iu,wu,wu2,wp):
    ir=requests.get(iu,timeout=60);ir.raise_for_status();b=ir.content;ct=ir.headers.get("Content-Type","image/png")
    fn=os.path.basename(iu.split("?")[0])
    if not fn or "." not in fn: fn=f"image.{ct.split('/')[-1] if '/' in ct else 'png'}"
    tok=base64.b64encode(f"{wu2}:{wp}".encode()).decode()
    mr=requests.post(f"{wu.rstrip('/')}/wp-json/wp/v2/media",data=b,headers={"Authorization":f"Basic {tok}","Content-Type":ct,"Content-Disposition":f'attachment; filename="{fn}"'})
    mr.raise_for_status();rj=mr.json();return rj.get("id"),rj.get("source_url")

# PIPELINE
def run_full_pipeline(
    keyword=None, brand_voice_prompt=None, word_count=None,
    wp_url=None, wp_username=None, wp_password=None,
    woo_ck=None, woo_cs=None,
    api_base=None, api_key=None, project_id=None,
    text_model=None, image_model=None,
    content_type="post", schedule_dt=None, serpapi_key=None,
    **kwargs,
):
    kw=keyword; bp=brand_voice_prompt; wc=word_count
    wu=wp_url; wu2=wp_username; wp=wp_password
    ck=woo_ck; cs=woo_cs
    ab=api_base; ak=api_key; pid=project_id
    tm=text_model; im=image_model
    ct=content_type; sdt=schedule_dt; sk=serpapi_key
    try:
        wc=int(wc) if wc else 1850;cc=""
        if sk is None:
            try: sk,_=get_active_serpapi_key()
            except: pass
        if sk:
            try:
                t10=get_google_top10_outlines(kw,sk)
                if t10: cc="\n".join(f"{i}. Title: {r['title']}\n   Snippet: {r['snippet']}" for i,r in enumerate(t10,1))
            except: pass
        title=generate_text(prompt=f'Generate a catchy, SEO-optimized title for a {"blog post" if ct=="post" else "product page"} about "{kw}". Target: {wc} words. Return ONLY the title.',sp=f"{bp}\n\nYou are an expert headline writer. Output only the title.",ab=ab,ak=ak,pid=pid,model=tm).strip().strip('"').strip("'") or kw
        ctl="blog post" if ct=="post" else "WooCommerce product description"
        op=(f'Analyze Top 10 Google results for "{kw}":\n{cc}\nCreate an all-inclusive SEO outline (H2, H3) for a {ctl} that covers all key points and outperforms them. Target: {wc} words. Output H2/H3, no JSON.' if cc else f'Generate a detailed structured outline for a {ctl} about "{kw}". Target: {wc} words. Output H2/H3, no JSON.')
        outline=generate_text(prompt=op,sp=f"{bp}\n\nYou are an expert SEO strategist. Output only the outline.",ab=ab,ak=ak,pid=pid,model=tm).replace("```","").strip()
        ap=(f'Write a comprehensive, SEO-optimized WooCommerce product description for: "{kw}".\nFollow this outline: {outline}\nTarget: {wc} words. Output ONLY valid HTML. Include features, benefits, specs, CTA. When adding SEO JSON-LD schema (<script type="application/ld+json">), output PURE JSON only: start with {{ and end with }}, do NOT use a JavaScript variable (no const x = ...), do NOT add a semicolon at the end.' if ct=="product" else f'Write a comprehensive, SEO-friendly article for: "{kw}".\nFollow this outline: {outline}\nTarget: {wc} words. Output ONLY valid HTML. When adding SEO JSON-LD schema (<script type="application/ld+json">), output PURE JSON only: start with {{ and end with }}, do NOT use a JavaScript variable (no const x = ...), do NOT add a semicolon at the end.')
        html=generate_text(prompt=ap,sp=f"{bp}\n\nYou are an expert content writer. Output clean HTML without markdown wrappers. JSON-LD schema blocks (<script type=\"application/ld+json\">) must contain PURE JSON objects only: start with {{ and end with }}, no const/let/var declaration, no trailing semicolon.",ab=ab,ak=ak,pid=pid,model=tm).replace("```html","").replace("```","").strip()

        # Guard: detect if generated content is actually Kira Agent web UI HTML
        if (
            "app-container" in html
            or "sidebar-menu" in html
            or html.strip().startswith("<!DOCTYPE")
        ):
            return (
                title,
                "",
                "",
                None,
                "❌ Lỗi: API Base URL đang trỏ vào trang Web thay vì API Endpoint."
                " Vui lòng thêm /v1 vào API Base URL trong Global Settings.",
            )

        soup=BeautifulSoup(html,'html.parser');h2s=soup.find_all('h2');fmid=None
        if h2s:
            for idx,h2 in enumerate(h2s):
                try:
                    idsc=generate_text(prompt=f'Write a short image prompt for "{h2.text.strip()}" about "{kw}". Output ONLY the prompt.',sp="You are an image prompt engineer.",ab=ab,ak=ak,pid=pid,model=tm).strip()
                    idata=generate_image(prompt=idsc,ab=ab,ak=ak,pid=pid,model=im)
                    if idata:
                        info=idata[0];lu=info.get("url") or (f"data:image/png;base64,{info['b64_json']}" if "b64_json" in info else None)
                        if lu and not lu.startswith("data:"):
                            try: mid,su=upload_image_to_wp(lu,wu,wu2,wp);lu=su
                            except: pass
                            if idx==0 and mid: fmid=mid
                        if lu:
                            t=soup.new_tag("img",src=lu,alt=h2.text.strip(),style="max-width:100%;height:auto;border-radius:8px;margin:1.5rem 0")
                            h2.insert_after(t)
                except: pass
            html=str(soup)
        else:
            try:
                idata=generate_image(prompt=f"Professional featured image for {kw}",ab=ab,ak=ak,pid=pid,model=im)
                if idata:
                    info=idata[0];lu=info.get("url") or (f"data:image/png;base64,{info['b64_json']}" if "b64_json" in info else None)
                    if lu and not lu.startswith("data:"):
                        try: fmid,_=upload_image_to_wp(lu,wu,wu2,wp)
                        except: pass
            except: pass
        # Chuẩn hoá JSON-LD: chỉ giữ JSON thuần { ... } (bỏ const ... =, dấu ';' cuối)
        html=clean_jsonld_schema(html)
        # Tự động chèn 2-5 internal link chuẩn SEO từ sitemap hieutaphoa.com
        if linker is not None:
            try: html=linker.auto_insert_links(html)
            except Exception as e: api_log(f"auto_insert_links LỖI: {e}")
        if sdt is None: sdt=vn_now()
        ps='future' if is_future(sdt) else 'publish'
        if ct=="product":
            if not ck or not cs: return (title,html,"",fmid,"WooCommerce keys missing.")
            sd="";fp=soup.find('p')
            if fp: sd=fp.get_text()[:300]
            payload={"name":title,"type":"simple","description":html,"short_description":sd,"status":ps}
            if ps=="future": payload["date_created_gmt"]=sdt.isoformat()
            if fmid: payload["images"]=[{"id":fmid}]
            r=woo_api_request_params("POST","products",wu,ck,cs,json=payload)
            if r.status_code in[200,201]: d=r.json();return (title,html,d.get("permalink","#"),fmid,None)
            return (title,html,"",fmid,f"WooCommerce Error {r.status_code}")
        else:
            payload={"title":title,"content":html,"status":ps,"date":sdt.isoformat()}
            if fmid: payload["featured_media"]=fmid
            r=wp_api_request_params("POST","wp/v2/posts",wu,wu2,wp,json=payload)
            if r.status_code in[200,201]: d=r.json();return (title,html,d.get("link","#"),fmid,None)
            return (title,html,"",fmid,f"WP Error {r.status_code}")
    except Exception as e:
        api_log(f"run_full_pipeline LỖI | kw={kw} | {type(e).__name__}: {e}")
        return ("","","",None,str(e))

# WORKER
WORKER_LOGS=[]
def worker_log(msg):
    ts=vn_now().strftime("%Y-%m-%d %H:%M:%S");entry=f"[{ts}] {msg}"
    WORKER_LOGS.append(entry)
    if len(WORKER_LOGS)>100: WORKER_LOGS.pop(0)
    print(entry)
def get_gsheet_client(sa): import gspread; return gspread.service_account_from_dict(json.loads(sa))
def load_sheet_dataframe():
    """Đọc Google Sheet (Trang tính1) → DataFrame 12 cột chuẩn cho Dashboard."""
    saj=st.session_state.get("gsheet_sa_json","");surl=st.session_state.get("gsheet_url","")
    if not saj or not surl: return pd.DataFrame()
    try:
        import gspread
        gc=get_gsheet_client(saj)
        try: sh=gc.open_by_url(surl)
        except: sh=gc.open_by_key(surl)
        ws=None
        try:
            ws=sh.worksheet("Trang tính1")
        except Exception:
            ws=sh.sheet1
        av=ws.get_all_values()
        if not av: return pd.DataFrame()
        std=["STT","Tên Website","Từ khoá chính","Loại nội dung","Prompt","Số từ viết","Ngày đăng","Giờ đăng","Trạng thái","Link bài viết","Audit","Internal Link"]
        hdrs=[str(h).strip().lower() for h in av[0]]
        def fc(nd):
            for i,h in enumerate(hdrs):
                for n in nd:
                    if n in h: return i
            return -1
        cols=[fc([c.lower()]) for c in std]
        rows=[]
        for r in av[1:]:
            if not any(str(x).strip() for x in r): continue  # bỏ dòng trống
            row=[]
            for c in cols:
                row.append(r[c] if 0<=c<len(r) else "")
            rows.append(row)
        return pd.DataFrame(rows,columns=std)
    except Exception as e:
        st.error(f"⚠️ Không đọc được Google Sheet: {e}")
        return pd.DataFrame()
def dashboard_trigger_now(uid):
    """Nút 🚀 Kích hoạt chạy Lịch ngay: gọi Backend Node.js trước, fallback chạy worker local."""
    try:
        import requests as _rq
        base=st.session_state.get("local_api_base",LOCAL_API_BASE).replace("/v1","").rstrip("/")
        rr=_rq.post(f"{base}/api/v1/schedule",json={"title":"🚀 Dashboard trigger","status":"Scheduled","publishDate":vn_now().strftime("%Y-%m-%d")},timeout=5)
        if rr.ok:
            return f"Đã gọi backend {base}/api/v1/schedule thành công"
    except Exception:
        pass
    try:
        count=process_sheet_for_user(uid)
        return f"Đã quét & xử lý {count} dòng lịch ngay lập tức"
    except Exception as e:
        return f"Lỗi khi kích hoạt: {e}"
def parse_schedule_date(ds,ts_):
    import pytz; vtz=pytz.timezone("Asia/Ho_Chi_Minh")
    ds=str(ds).strip() if ds else ""; ts_=str(ts_).strip() if ts_ else ""
    if not ds and not ts_: return None,False
    if ts_:
        try:
            fv=float(ts_)
            if 0.0<=fv<1.0 and '.' in ts_: ts_=f"{int((fv*86400)//3600):02d}:{int(((fv*86400)%3600)//60):02d}:{int((fv*86400)%60):02d}"
        except: pass
    cs=f"{ds} {ts_}".strip()
    try:
        import dateutil.parser; pd=dateutil.parser.parse(cs,dayfirst=True)
        if pd.tzinfo is None: pd=vtz.localize(pd)
        return pd,True
    except: pass
    dfmts=["%Y-%m-%d","%d/%m/%Y","%m/%d/%Y","%Y/%m/%d","%d-%m-%Y","%Y.%m.%d"]
    pd=None
    if ds:
        for f in dfmts:
            try: pd=datetime.strptime(ds,f);break
            except: continue
    tfmts=["%H:%M","%H:%M:%S","%I:%M %p","%I:%M:%S %p"]
    pt=None
    if ts_:
        for f in tfmts:
            try: pt=datetime.strptime(ts_,f);break
            except: continue
    if pd and pt: return vtz.localize(pd.replace(hour=pt.hour,minute=pt.minute,second=pt.second,microsecond=0)),True
    if pd: return vtz.localize(pd),True
    if pt: return datetime.now(vtz).replace(hour=pt.hour,minute=pt.minute,second=0,microsecond=0),True
    if ds or ts_: return None,True
    return None,False
def process_sheet_for_user(uid):
    s=get_all_user_settings(uid);saj=s.get("gsheet_sa_json","");surl=s.get("gsheet_url","")
    if not saj or not surl: return 0
    try:
        gc=get_gsheet_client(saj)
        try: sh=gc.open_by_url(surl)
        except: sh=gc.open_by_key(surl)
        ws=sh.sheet1;av=ws.get_all_values()
        if not av or len(av)<2: return 0
        hdrs=[h.strip().lower() for h in av[0]]
        def fc(hy,nd):
            for i,h in enumerate(hy):
                for n in nd:
                    if n in h: return i
            return -1
        ix_site=fc(hdrs,["tên website","website","site name","site"]);ix_kw=fc(hdrs,["từ khoá","từ khóa","keyword"])
        ix_ct=fc(hdrs,["loại nội dung","content type"]);ix_pmpt=fc(hdrs,["prompt","brand voice","brand"])
        ix_wc=fc(hdrs,["số từ","word count"]);ix_date=fc(hdrs,["ngày đăng","ngay dang","date"])
        ix_time=fc(hdrs,["giờ đăng","gio dang","time","giờ"]);ix_st=fc(hdrs,["trạng thái","status","trang thai"])
        ix_lnk=fc(hdrs,["link","url","link bài viết"])
        if ix_site==-1:ix_site=0; ix_kw==-1 and (ix_kw:=1); ix_ct==-1 and (ix_ct:=2); ix_pmpt==-1 and (ix_pmpt:=3)
        ix_wc==-1 and (ix_wc:=4); ix_date==-1 and (ix_date:=5); ix_time==-1 and (ix_time:=6); ix_st==-1 and (ix_st:=7); ix_lnk==-1 and (ix_lnk:=8)
        gs=get_global_settings();s={**s,**gs}  # global settings (admin) ghi đè settings riêng user
        ab=s.get("local_api_base",LOCAL_API_BASE);ak=s.get("local_api_key",LOCAL_API_KEY);pid=s.get("local_project_id",LOCAL_PROJECT_ID)
        tm=s.get("local_model",LOCAL_MODEL);im=s.get("local_image_model",LOCAL_IMAGE_MODEL)
        proc=0
        for ri in range(1,len(av)):
            row_index=ri+1  # chỉ số dòng trên Google Sheet (dòng 1 = header → dữ liệu bắt đầu từ dòng 2)
            row=av[ri];mx=max(ix_st,ix_lnk,ix_kw,ix_site,ix_date,ix_time)
            while len(row)<=mx: row.append("")
            sv=str(row[ix_st]).strip().lower() if ix_st<len(row) else "";kv=str(row[ix_kw]).strip() if ix_kw<len(row) else "";snv=str(row[ix_site]).strip() if ix_site<len(row) else ""
            # Normalize .strip().lower() — chỉ xử lý pending / scheduled / ô trống (không phân biệt hoa thường, không dính khoảng trắng)
            if sv not in["pending","scheduled","chưa đăng","chua dang","chuadang",""]: continue
            if not kv: continue
            site=get_website_by_name(uid,snv)
            if not site:
                sites=get_websites(uid)
                if sites: site=sites[0]
                else: worker_log(f"⚠️ No website for user {uid}, row {row_index}");continue
            bp=site.get("brand_voice_prompt","You are an expert SEO content writer.")
            pv=str(row[ix_pmpt]).strip() if ix_pmpt<len(row) else ""
            if pv: bp=pv
            wv=str(row[ix_wc]).strip() if ix_wc<len(row) else "1500"
            try:wv=int(wv)
            except:wv=1500
            cv=str(row[ix_ct]).strip().lower() if ix_ct<len(row) else "post"
            if cv not in["post","product"]: cv="post"
            ds=str(row[ix_date]).strip() if ix_date<len(row) else "";ts_=str(row[ix_time]).strip() if ix_time<len(row) else ""
            sdt,hs=parse_schedule_date(ds,ts_)
            if sdt is None and hs: worker_log(f"⚠️ Row {row_index}: Cannot parse '{ds} {ts_}' for '{kv}'. Posting immediately.");sdt=vn_now();hs=False
            if sdt is None: sdt=vn_now();hs=False
            import pytz;vtz=pytz.timezone("Asia/Ho_Chi_Minh");now_vn=datetime.now(vtz)
            if hs and sdt.tzinfo is None: sdt=vtz.localize(sdt)
            if hs and is_future(sdt):
                tr=sdt-now_vn;worker_log(f"⏳ Skipping '{kv}', scheduled for {sdt.strftime('%Y-%m-%d %H:%M')} ICT, current time is {now_vn.strftime('%Y-%m-%d %H:%M')} ICT ({int(tr.total_seconds()//3600)}h {int((tr.total_seconds()%3600)//60)}m remaining), waiting...");continue
            worker_log(f"🔄 Row {row_index}: '{kv}' → {site['site_name']} ({cv})")
            try: ws.update_cell(row_index,ix_st+1,"Processing...")
            except: pass
            _,_,link,_,err=run_full_pipeline(keyword=kv,brand_voice_prompt=bp,word_count=wv,wp_url=site["wp_url"],wp_username=site["wp_username"],wp_password=site["wp_app_password"],woo_ck=site["woo_ck"],woo_cs=site["woo_cs"],api_base=ab,api_key=ak,project_id=pid,text_model=tm,image_model=im,content_type=cv,schedule_dt=sdt,serpapi_key=None)
            if err is None and link:
                ws.update_cell(row_index,ix_st+1,"Success");ws.update_cell(row_index,ix_lnk+1,link)
                save_history_entry(uid,site["site_name"],kv,sdt.strftime("%Y-%m-%d %H:%M"),'future' if is_future(sdt) else 'publish',cv,link)
                worker_log(f"✅ Posted: '{kv}' → {link}");proc+=1
            else:
                em=err or "Unknown error";ws.update_cell(row_index,ix_st+1,f"Error: {em[:80]}");worker_log(f"❌ Failed: '{kv}' → {em[:120]}")
        return proc
    except ImportError: worker_log("⚠️ gspread not installed");return 0
    except Exception as e: worker_log(f"❌ Sheet error user {uid}: {e}");return 0
def scan_all_users_sheets():
    conn=get_db();c=conn.cursor();c.execute("SELECT id FROM users");users=c.fetchall();conn.close();t=0
    for u in users:
        try: t+=process_sheet_for_user(u["id"])
        except Exception as e: worker_log(f"❌ Error user {u['id']}: {e}")
    if t>0: worker_log(f"✅ Processed {t} total rows")
    return t
def background_worker_loop():
    schedule_lib.every(1).minutes.do(scan_all_users_sheets);worker_log("🟢 Worker started (every 1 min)")
    while True: schedule_lib.run_pending();time.sleep(60)
def start_background_worker():
    if not st.session_state.worker_started:
        threading.Thread(target=background_worker_loop,daemon=True).start();st.session_state.worker_started=True;worker_log("🔧 Worker thread initialized")

# LOGIN UI
restore_session_from_token()  # tự đăng nhập lại khi refresh (session_state bị reset)
if not st.session_state.logged_in:
    st.markdown('<div class="login-card">',unsafe_allow_html=True)
    st.markdown("## 🔐 WP Auto-Poster PRO");st.caption("Your AI-powered content automation platform")
    t1,t2=st.tabs(["Sign In","Create Account"])
    with t1:
        with st.form("login"):
            lu=st.text_input("Username");lp=st.text_input("Password",type="password")
            if st.form_submit_button("Sign In",use_container_width=True):
                ok,msg=login_user(lu,lp)
                if ok: st.success(msg);st.rerun()
                else: st.error(msg)
    with t2:
        with st.form("register"):
            ru=st.text_input("Choose Username");rp=st.text_input("Choose Password",type="password");rp2=st.text_input("Confirm Password",type="password")
            if st.form_submit_button("Create Account",use_container_width=True):
                if rp!=rp2: st.error("Passwords do not match.")
                elif len(rp)<4: st.error("Min 4 characters.")
                else:
                    ok,msg=register_user(ru,rp)
                    if ok:
                        login_user(ru,rp)  # tự đăng nhập + kích hoạt session token
                        st.success(f"✅ Đăng ký thành công! Chào mừng {ru}");st.rerun()
                    else: st.error(msg)
    st.markdown('</div>',unsafe_allow_html=True);st.stop()

start_background_worker()
# ============================================================
# GLOBAL SETTINGS — chia sẻ cấu hình AI cho toàn bộ hệ thống
# (Global Settings do admin thiết lập, mọi user đều dùng được,
#  không bị kẹt ở default localhost khi admin đã cấu hình URL public)
# ============================================================
def save_global_setting(k,v):
    conn=get_db();c=conn.cursor()
    c.execute("INSERT INTO global_settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))
    conn.commit();conn.close()
def get_global_settings():
    conn=get_db();c=conn.cursor();c.execute("SELECT key,value FROM global_settings");rows=c.fetchall();conn.close()
    return {r["key"]:r["value"] for r in rows}
def load_global_settings():
    # Thứ tự ưu tiên: Global Settings (admin) > settings riêng user > mặc định hệ thống
    gs=get_global_settings()
    s=get_all_user_settings(st.session_state.user_id) if st.session_state.user_id else {}
    for k,d in[("local_api_base",LOCAL_API_BASE),("local_api_key",LOCAL_API_KEY),("local_project_id",LOCAL_PROJECT_ID),("local_model",LOCAL_MODEL),("local_image_model",LOCAL_IMAGE_MODEL),("serpapi_keys",DEFAULT_SERPAPI_KEY),("gsheet_url",""),("gsheet_sa_json","")]:
        st.session_state[k]=gs.get(k) or s.get(k) or d
load_global_settings();uid=st.session_state.user_id

# SIDEBAR
with st.sidebar:
    st.markdown("""<div style="display:flex;align-items:center;gap:12px;margin-bottom:20px;padding-left:8px"><div style="background:#0d9488;color:white;padding:10px;border-radius:14px;font-weight:bold">⚡</div><div><h3 style="margin:0;font-size:18px;font-weight:800;color:#0f172a">AutoPoster <span style="font-size:11px;background:#ccfbf1;color:#0f766e;padding:2px 6px;border-radius:6px">PRO</span></h3><p style="margin:0;font-size:12px;color:#64748b">Công cụ tự động hóa nội dung</p></div></div>""",unsafe_allow_html=True)
    cu=str(st.session_state.get('username','')).lower();cr=str(st.session_state.get('user_role','')).lower();is_admin=(cu=='admin') or (cr=='admin')
    st.markdown('<div class="larkeyword-card">',unsafe_allow_html=True)
    mo=["🚀 Content Generator","📊 Dashboard","🌐 Website Manager"]
    if is_admin: mo.append("⚙️ Global Settings")
    if not is_admin and st.session_state.nav_view=="⚙️ Global Settings": st.session_state.nav_view="🚀 Content Generator"
    view=st.radio("Navigation",mo,label_visibility="collapsed");st.session_state.nav_view=view
    st.markdown('</div>',unsafe_allow_html=True)
    uc=get_user_credits(uid)
    st.markdown(f"""<div class="balance-box"><div style="font-size:11px;color:#94a3b8;text-transform:uppercase;font-weight:600">Số dư hiện tại</div><div style="font-size:22px;font-weight:800;color:#34d399;margin:4px 0">{uc:,.0f} VNĐ</div><div style="font-size:11px;color:#cbd5e1">Chi phí: 2,000 VNĐ / bài đăng</div></div>""",unsafe_allow_html=True)
    st.markdown(f"""<div class="bank-box"><div style="font-weight:700;color:#0f172a;margin-bottom:6px;display:flex;justify-content:space-between"><span>🏦 MB BANK</span><span style="color:#0284c7;font-size:11px">Chuyển khoản 24/7</span></div><div>STK: <b style="color:#0284c7;font-size:15px">999937799</b></div><div>Chủ TK: <b>LƯƠNG HUỲNH HIẾU</b></div><div style="margin-top:6px;padding-top:6px;border-top:1px solid #e2e8f0;font-size:12px">Nội dung CK: <b style="color:#059669">NAP {st.session_state.get('username','user')}</b></div></div>""",unsafe_allow_html=True)
    with st.expander("💳 Mua lượt / Nạp điểm",expanded=False):
        st.markdown("**📦 Các gói bài đăng:**")
        if st.button("🎯 Gói 25 bài — 50,000 VNĐ",key="p25"): st.info("Vui lòng chuyển khoản và liên hệ Admin.")
        if st.button("🔥 Gói 50 bài — 100,000 VNĐ",key="p50"): st.info("Vui lòng chuyển khoản và liên hệ Admin.")
        if st.button("🚀 Gói 100 bài — 200,000 VNĐ",key="p100"): st.info("Vui lòng chuyển khoản và liên hệ Admin.")
        st.caption("⏳ Admin sẽ cộng điểm trong 5-10 phút.")
    st.markdown("---")
    if st.button("🚪 Đăng xuất",use_container_width=True): logout_user();st.rerun()

# VIEW 1
if st.session_state.nav_view=="🚀 Content Generator":
    st.markdown("""<div class="header-banner"><h1>🚀 Content Generator</h1><p>AI-powered content creation & automated publishing for WordPress & WooCommerce</p></div>""",unsafe_allow_html=True)
    websites=get_websites(uid)
    if not websites: st.warning("⚠️ No websites configured.")
    else:
        so={w["site_name"]:w for w in websites};ssn=st.selectbox("🎯 Target Website",options=list(so.keys()));ss=so[ssn]
        c1,c2=st.columns([2,1],gap="large")
        with c2:
            st.markdown("#### ⚙️ Settings");wc=st.slider("Word Count",500,3000,1850,50)
            ct=st.radio("Content Type",["post","product"],format_func=lambda x:"📝 Blog Post" if x=="post" else "🛒 Woo Product",horizontal=True,key="gen_ct")
            st.markdown("##### 📅 Schedule");cd,ct2=st.columns(2)
            with cd: sd=st.date_input("Date",key="gen_date")
            with ct2: st2=st.time_input("Time",value=vn_now().time(),key="gen_time")
        with c1:
            kw=st.text_input("🔑 Primary Keyword",placeholder="e.g. Best SEO Strategies 2026")
            if st.button("✨ Generate SEO Outline (SerpApi)",use_container_width=True):
                if not kw: st.warning("Please enter a keyword first.")
                else:
                    with st.spinner("Analyzing Top 10 Google results..."):
                        try:
                            cc=""
                            try:
                                t10=get_google_top10_outlines(kw,serpapi_key=None)
                                if t10: cc="\n".join(f"{i}. {r['title']} — {r['snippet'][:120]}" for i,r in enumerate(t10,1));st.info(f"📊 Analyzed {len(t10)} Top 10 results.")
                            except: pass
                            bp=ss.get("brand_voice_prompt","You are an expert SEO writer.")
                            ctl="blog post" if ct=="post" else "WooCommerce product description"
                            op=(f'Analyze Top 10 Google results for "{kw}":\n{cc}\nCreate an all-inclusive SEO outline (H2, H3) for a {ctl} that covers all key points and outperforms them. Target: {wc} words. Output H2/H3, no JSON.' if cc else f'Generate a detailed SEO outline for a {ctl} about "{kw}". Target: {wc} words. Output H2/H3, no JSON.')
                            outline=generate_text(prompt=op,sp=f"{bp}\n\nYou are an expert SEO strategist. Output only the outline.",ab=st.session_state.get("local_api_base",LOCAL_API_BASE),ak=st.session_state.get("local_api_key",LOCAL_API_KEY),pid=st.session_state.get("local_project_id",LOCAL_PROJECT_ID),model=st.session_state.get("local_model",LOCAL_MODEL))
                            st.session_state.generated_outline=outline.replace("```","").strip();st.success("✅ Outline generated!")
                        except Exception as e: st.error(f"Error: {e}")
            custom_outline=st.text_area("📝 Outline (edit before generation)",value=st.session_state.generated_outline,height=250)
        with c2:
            st.markdown("---")
            if st.button("🚀 Generate & Publish",use_container_width=True,type="primary"):
                if not all([ss["wp_url"],ss["wp_username"],kw]): st.error("Missing website credentials or keyword!")
                elif ct=="product" and not(ss["woo_ck"] and ss["woo_cs"]): st.error("WooCommerce keys required!")
                else:
                    cpp=get_cost_per_post()
                    if get_user_credits(uid)<cpp: st.error(f"⚠️ Tài khoản không đủ số dư (Cần {cpp:,.0f} VNĐ/bài). Vui lòng nạp thêm điểm!")
                    else:
                        with st.spinner(f"Generating {ct}..."):
                            try:
                                bp=ss.get("brand_voice_prompt","You are an expert SEO writer.")
                                dt=datetime.combine(sd,st2)
                                _,_,link,_,err=run_full_pipeline(keyword=kw,brand_voice_prompt=bp,word_count=wc,wp_url=ss["wp_url"],wp_username=ss["wp_username"],wp_password=ss["wp_app_password"],woo_ck=ss["woo_ck"],woo_cs=ss["woo_cs"],api_base=st.session_state.get("local_api_base",LOCAL_API_BASE),api_key=st.session_state.get("local_api_key",LOCAL_API_KEY),project_id=st.session_state.get("local_project_id",LOCAL_PROJECT_ID),text_model=st.session_state.get("local_model",LOCAL_MODEL),image_model=st.session_state.get("local_image_model",LOCAL_IMAGE_MODEL),content_type=ct,schedule_dt=dt,serpapi_key=None)
                                if err is None and link:
                                    deduct_user_credit(uid,cpp);st.success(f"✅ Published to {ssn}!")
                                    st.markdown(f"[View {ct.capitalize()}]({link})")
                                    save_history_entry(uid,ssn,kw,dt.strftime("%Y-%m-%d %H:%M"),'future' if is_future(dt) else 'publish',ct,link)
                                    st.session_state.generated_outline="";st.rerun()
                                else: st.error(f"Failed: {err}")
                            except Exception as e: st.error(f"Error: {e}")
            st.markdown("---");st.markdown("##### 📊 Sheet Sync")
            if st.session_state.worker_started: st.markdown('<span class="badge-success">🟢 Worker RUNNING</span> <span style="font-size:.75rem;color:#6B7280">(every 1 min)</span>',unsafe_allow_html=True)
            else: st.markdown('<span class="badge-amber">🔴 Worker STOPPED</span>',unsafe_allow_html=True)
            if st.button("🔄 Run Sheet Automation Now",use_container_width=True):
                if not st.session_state.get("gsheet_sa_json") or not st.session_state.get("gsheet_url"): st.warning("Configure Google Sheets first.")
                else:
                    with st.spinner("Scanning..."):
                        count=process_sheet_for_user(uid)
                        if count>0: st.success(f"Processed {count} rows!")
                        else: st.info("No pending rows.")
    st.markdown("---");st.markdown("### 📜 Lịch sử Giao dịch")
    txn=get_credit_transactions(uid)
    if txn:
        tr=[]
        for t in txn:
            amt=t["amount"];badge=f'<span class="badge-success">+{amt:,.0f} VNĐ</span>' if amt>0 else f'<span class="badge-amber">{amt:,.0f} VNĐ</span>'
            tr.append({"Thời gian":t["created_at"],"Loại":t["type"],"Mô tả":t["description"],"Số tiền":badge})
        st.markdown(pd.DataFrame(tr).to_html(index=False,escape=False),unsafe_allow_html=True)
    else: st.info("Chưa có giao dịch nào.")
    st.markdown("---");st.markdown("### 📋 Execution History")
    hist=load_history(uid)
    if not hist: st.info("No history yet.")
    else:
        df=pd.DataFrame(hist)
        if "date" in df.columns: df["Date & Time"]=df["date"]
        if "site_name" in df.columns: df["Site"]=df["site_name"]
        if "keyword" in df.columns: df["Keyword"]=df["keyword"]
        if "content_type" in df.columns: df["Type"]=df["content_type"].apply(lambda x:"🛒 Product" if x=="product" else "📝 Post")
        if "status" in df.columns: df["Status"]=df["status"].apply(lambda x:"✅ Published" if x=="publish" else("🕐 Scheduled" if x=="future" else f"❌ {x}"))
        if "link" in df.columns: df["Link"]=df["link"]
        cols=[c for c in["Site","Keyword","Type","Date & Time","Status","Link"] if c in df.columns]
        if cols: st.dataframe(df[cols],column_config={"Site":st.column_config.TextColumn("Site",width="small"),"Keyword":st.column_config.TextColumn("Keyword",width="medium"),"Type":st.column_config.TextColumn("Type",width="small"),"Date & Time":st.column_config.TextColumn("Date",width="small"),"Status":st.column_config.TextColumn("Status",width="small"),"Link":st.column_config.LinkColumn("Link",width="small",display_text="View")},hide_index=True,use_container_width=True)

# VIEW 1.5 — DASHBOARD HIỆU SUẤT
elif st.session_state.nav_view=="📊 Dashboard":
    st.markdown("""<div class="header-banner"><h1>📊 Dashboard Hiệu Suất</h1><p>Hệ thống theo dõi hiệu suất Auto Poster Pro từ Google Sheet (Trang tính1)</p></div>""",unsafe_allow_html=True)
    if not st.session_state.get("gsheet_sa_json") or not st.session_state.get("gsheet_url"):
        st.warning("⚠️ Vui lòng cấu hình Google Sheets (Service Account JSON + Sheet URL) trong ⚙️ Global Settings trước.")
    else:
        with st.spinner("Đang tải dữ liệu từ Google Sheet..."):
            try:
                df_dash=load_sheet_dataframe()
            except Exception as e:
                st.error(f"Lỗi đọc Google Sheet: {e}");df_dash=pd.DataFrame()
        dashboard.render_dashboard(df_dash, on_refresh=load_sheet_dataframe, on_trigger=lambda: dashboard_trigger_now(uid))

# VIEW 2
elif st.session_state.nav_view=="🌐 Website Manager":
    st.markdown("""<div class="header-banner"><h1>🌐 Website Manager</h1><p>Manage your WordPress & WooCommerce websites</p></div>""",unsafe_allow_html=True)
    webs=get_websites(uid);es=st.session_state.get("editing_site");ie=es is not None
    st.markdown(f"#### {'✏️ Edit Site' if ie else '➕ Add New Site'}")
    with st.container():
        fm="edit" if ie else "add"
        sn=st.text_input("Site Name *",value=es["site_name"] if ie else "",placeholder="e.g. My Health Blog",key=f"wn_{fm}")
        wu=st.text_input("WordPress URL *",value=es["wp_url"] if ie else "",placeholder="https://yoursite.com",key=f"wu_{fm}")
        wu2=st.text_input("WP Username *",value=es["wp_username"] if ie else "",key=f"wu2_{fm}")
        wp=st.text_input("WP App Password *",type="password",value=es["wp_app_password"] if ie else "",key=f"wp_{fm}")
        ck1,ck2=st.columns(2)
        with ck1: ck=st.text_input("WooCommerce Consumer Key",type="password",value=es["woo_ck"] if ie else "",placeholder="ck_...",key=f"ck_{fm}")
        with ck2: cs=st.text_input("WooCommerce Consumer Secret",type="password",value=es["woo_cs"] if ie else "",placeholder="cs_...",key=f"cs_{fm}")
        bv=st.text_area("Brand Voice / System Prompt",value=es["brand_voice_prompt"] if ie else "You are an expert SEO content writer.",height=120,key=f"bv_{fm}")
        cs1,cs2=st.columns([1,1])
        with cs1:
            if st.button("💾 Save Site",use_container_width=True,type="primary"):
                if not sn or not wu or not wu2: st.error("Required fields missing.")
                else: save_website(uid,sn,wu,wu2,wp,ck,cs,bv,website_id=es["id"] if ie else None);st.session_state.editing_site=None;st.success(f"✅ Site '{sn}' saved!");st.rerun()
        with cs2:
            if st.button("Cancel",use_container_width=True): st.session_state.editing_site=None;st.rerun()
    if webs:
        st.markdown("---");st.markdown("### 📋 Your Sites")
        for w in webs:
            with st.container():
                c1,c2,c3,c4=st.columns([1.5,1.5,1,1])
                with c1: st.markdown(f"**{w['site_name']}**")
                with c2: st.caption(w['wp_url'][:45])
                with c3: st.markdown('<span class="badge-purple">🛒 WooCommerce</span>' if bool(w.get('woo_ck')) else '<span class="badge-success">📝 Blog</span>',unsafe_allow_html=True)
                with c4:
                    e1,e2=st.columns(2)
                    with e1:
                        if st.button("✏️",key=f"ed_{w['id']}",help="Edit"): st.session_state.editing_site=get_website_by_id(w['id']);st.rerun()
                    with e2:
                        if st.button("🗑️",key=f"dl_{w['id']}",help="Delete"): delete_website(w['id'],uid);st.success(f"Deleted '{w['site_name']}'");st.rerun()
                st.markdown("<div style='height:.25rem'></div>",unsafe_allow_html=True)
    else: st.info("No sites added yet.")

# VIEW 3
elif st.session_state.nav_view=="⚙️ Global Settings":
    if not is_admin: st.warning("⚠️ Bạn không có quyền truy cập.");st.stop()
    st.markdown("""<div class="header-banner"><h1>⚙️ Global Settings</h1><p>Configure your AI engine & integrations</p></div>""",unsafe_allow_html=True)
    ta,tg=st.tabs(["🤖 AI Engine","📊 Google Sheets"])
    with ta:
        st.markdown("#### Local AI API");c1,c2=st.columns(2)
        with c1: lab=st.text_input("API Base URL",value=st.session_state.get("local_api_base",LOCAL_API_BASE));lak=st.text_input("API Key",value=st.session_state.get("local_api_key",LOCAL_API_KEY),type="password");lpi=st.text_input("Project ID",value=st.session_state.get("local_project_id",LOCAL_PROJECT_ID))
        with c2: ltm=st.text_input("Text Model",value=st.session_state.get("local_model",LOCAL_MODEL));lim=st.text_input("Image Model",value=st.session_state.get("local_image_model",LOCAL_IMAGE_MODEL));sk_=st.text_area("SerpApi Keys",value=st.session_state.get("serpapi_keys",DEFAULT_SERPAPI_KEY),height=100,placeholder="One key per line")
        for k,v in[("local_api_base",lab),("local_api_key",lak),("local_project_id",lpi),("local_model",ltm),("local_image_model",lim),("serpapi_keys",sk_)]: st.session_state[k]=v;save_global_setting(k,v)
    with tg:
        st.markdown("#### Google Sheets Automation");gu=st.text_input("Sheet URL or ID",value=st.session_state.get("gsheet_url",""),placeholder="https://docs.google.com/spreadsheets/d/...");st.session_state["gsheet_url"]=gu;save_user_setting(uid,"gsheet_url",gu)
        st.markdown("##### Service Account JSON");sf=st.file_uploader("Upload JSON key",type=["json"],key="gs_sa_up")
        if sf is not None:
            try: sc=sf.read().decode("utf-8");json.loads(sc);st.session_state["gsheet_sa_json"]=sc;save_user_setting(uid,"gsheet_sa_json",sc);st.success("✅ Saved!")
            except Exception as e: st.error(f"Invalid JSON: {e}")
        else:
            if st.session_state.get("gsheet_sa_json"): st.caption("✅ Service Account loaded")
            else: st.caption("No file uploaded")
        st.markdown("---");st.markdown("#### 📊 SerpApi Usage Dashboard")
        if st.button("🔄 Refresh",use_container_width=True): st.rerun()
        kl=get_serpapi_keys()
        if kl:
            rows=[]
            for k in kl:
                info=check_serpapi_account(k);pfx=k[:12]+"..." if len(k)>12 else k
                if info["valid"]: rows.append({"Key":pfx,"Plan":info["plan"],"Limit":f"{info['searches_per_month']}","Used":f"{info['searches_per_month']-info['plan_searches_left']}","Left":f"{info['plan_searches_left']}","Status":'<span class="badge-success">✅ Active</span>' if info['plan_searches_left']>0 else '<span class="badge-amber">⚠️ Exhausted</span>'})
                else: rows.append({"Key":pfx,"Plan":"N/A","Limit":"0","Used":"0","Left":"0","Status":'<span class="badge-amber">❌ Invalid</span>'})
            if rows: st.markdown(pd.DataFrame(rows)[["Key","Plan","Limit","Used","Left","Status"]].to_html(index=False,escape=False),unsafe_allow_html=True)
        else: st.info("No SerpApi keys configured.")
    st.markdown("---");st.markdown("#### 💰 Quản lý Nạp điểm & Chi phí")
    cppv=st.number_input("Chi phí mỗi bài đăng (VNĐ)",value=int(get_cost_per_post()),min_value=0,step=500);save_user_setting(uid,"cost_per_post",str(int(cppv)))
    conn=get_db();c=conn.cursor();c.execute("SELECT id,username,credits FROM users ORDER BY id");all_u=c.fetchall();conn.close()
    if all_u:
        cu1,cu2,cu3=st.columns([2,1,1])
        with cu1: sui=st.selectbox("Chọn User",options=range(len(all_u)),format_func=lambda i:f"{all_u[i]['username']} (💳 {all_u[i]['credits']:,.0f} VNĐ)");su=all_u[sui]
        with cu2: ca=st.number_input("Số điểm cần cộng",value=10000,min_value=1000,step=5000)
        with cu3: st.markdown("<div style='height:1.5rem'></div>",unsafe_allow_html=True)
        if st.button("➕ Cộng tiền",use_container_width=True,type="primary"): add_credits(su["id"],ca,f"Admin nạp {ca:,.0f} VNĐ");st.success(f"✅ Đã cộng {ca:,.0f} VNĐ cho {su['username']}!");st.rerun()
        st.markdown("---");bd=[{"Username":u["username"],"Balance (VNĐ)":f"{u['credits']:,.0f}"} for u in all_u];st.table(pd.DataFrame(bd))
    st.markdown("---")
    if st.button("💾 Save All Settings",use_container_width=True,type="primary"): st.success("✅ All settings saved!")

st.markdown("---")
with st.expander("🔧 Background Worker Logs",expanded=False):
    if WORKER_LOGS: st.code("\n".join(WORKER_LOGS[-50:]),language="text")
    else: st.caption("No worker logs yet.")
