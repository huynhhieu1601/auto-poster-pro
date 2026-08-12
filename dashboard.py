"""
dashboard.py — Module Dashboard chuyên nghiệp cho Auto Poster Pro (Streamlit + Plotly).

Theo dõi toàn bộ hiệu suất hệ thống từ pandas.DataFrame đọc từ Google Sheet
(Trang tính1) với đúng 12 cột:
    STT, Tên Website, Từ khoá chính, Loại nội dung, Prompt, Số từ viết,
    Ngày đăng, Giờ đăng, Trạng thái, Link bài viết, Audit, Internal Link.

Cách dùng (từ app.py):
    import dashboard
    dashboard.render_dashboard(df_sheet, on_refresh=load_sheet_dataframe)
"""
import os
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st

# Backend Node.js để kích hoạt "Chạy Lịch ngay" (mặc định PORT=3003; đổi qua env)
SCHEDULE_API_URL = os.environ.get("SCHEDULE_API_URL", "http://localhost:3003/api/v1/schedule")

_STD_COLS = ["STT", "Tên Website", "Từ khoá chính", "Loại nội dung", "Prompt",
             "Số từ viết", "Ngày đăng", "Giờ đăng", "Trạng thái",
             "Link bài viết", "Audit", "Internal Link"]
_SUCCESS_STATUS = {"success", "published", "đã đăng", "da dang", "xuất bản"}
_PENDING_STATUS = {"pending", "scheduled", "chưa đăng", "chua dang", "processing", "đang xử lý"}

_CSS = """
<style>
/* Lumina SaaS — Pure Light / Glassmorphism (xem DESIGN.md) */
.kpi-row{display:flex;gap:14px;flex-wrap:wrap;margin-bottom:18px}
.kpi-card{flex:1 1 210px;min-width:200px;background:rgba(255,255,255,.8);
  backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px);
  border:1px solid rgba(30,41,59,.05);border-radius:1rem;padding:20px 22px;
  box-shadow:0 8px 30px rgba(0,0,0,.04);position:relative;border-top:4px solid #0d9488;transition:all .2s ease}
.kpi-card:hover{box-shadow:0 14px 40px rgba(0,0,0,.08)}
.kpi-card.c2{border-top-color:#0d9488}.kpi-card.c3{border-top-color:#7c3aed}.kpi-card.c4{border-top-color:#f59e0b}
.kpi-icon{font-size:20px;position:absolute;top:14px;right:16px;opacity:.85}
.kpi-label{font-family:'JetBrains Mono',monospace;font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#64748b;font-weight:600}
.kpi-value{font-size:26px;font-weight:800;color:#1e293b;margin:4px 0 0;line-height:1.1;letter-spacing:-0.01em}
.kpi-sub{font-size:12px;color:#94a3b8;margin-top:6px}
.health-chip{display:inline-flex;align-items:center;gap:8px;font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;
  background:rgba(255,255,255,.8);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
  border:1px solid rgba(30,41,59,.05);border-radius:9999px;padding:8px 16px;margin:4px 8px 4px 0;color:#334155;box-shadow:0 4px 16px rgba(0,0,0,.04)}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.dot-ok{background:#0d9488;box-shadow:0 0 0 3px rgba(13,148,136,.2)}
.dot-warn{background:#f59e0b;box-shadow:0 0 0 3px rgba(245,158,11,.2)}
.dot-bad{background:#ef4444;box-shadow:0 0 0 3px rgba(239,68,68,.2)}
</style>
"""


# ============================================================
# 1) ÉP KIỂU DỮ LIỆU AN TOÀN (không crash khi có cell trống)
# ============================================================
def _safe_numeric(series):
    """Số từ viết → numeric; cell trống/chuỗi lạ → 0."""
    try:
        return pd.to_numeric(series, errors="coerce").fillna(0).astype(float)
    except Exception:
        return pd.Series([0] * len(series), index=series.index)


def _safe_bool(series):
    """Audit → boolean; nhận TRUE/true/1/x/✔/✓ và cả cell trống."""
    def _b(v):
        if v is None:
            return False
        if isinstance(v, bool):
            return v
        s = str(v).strip().lower()
        return s in ("true", "1", "yes", "x", "✔", "✓", "done", "ok", "đạt")
    try:
        return series.map(_b).fillna(False).astype(bool)
    except Exception:
        return pd.Series([False] * len(series), index=series.index)


def clean_df(df):
    """Chuẩn hoá DataFrame: đủ 12 cột, ép kiểu an toàn, thêm cột datetime."""
    if df is None:
        df = pd.DataFrame()
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    for col in _STD_COLS:
        if col not in df.columns:
            df[col] = ""
    if "Số từ viết" in df.columns:
        df["Số từ viết"] = _safe_numeric(df["Số từ viết"])
    if "Audit" in df.columns:
        df["Audit"] = _safe_bool(df["Audit"])
    df["Trạng thái"] = df["Trạng thái"].fillna("").astype(str).str.strip()
    df["Tên Website"] = df["Tên Website"].fillna("").astype(str).str.strip()
    df["Loại nội dung"] = df["Loại nội dung"].fillna("").astype(str).str.strip()
    df["Từ khoá chính"] = df["Từ khoá chính"].fillna("").astype(str).str.strip()
    df["Ngày đăng"] = df["Ngày đăng"].fillna("").astype(str).str.strip()
    if "Ngày đăng" in df.columns:
        df["Ngày đăng_dt"] = pd.to_datetime(df["Ngày đăng"], errors="coerce")
    return df


def _is_dark():
    try:
        return (st.get_option("theme.base") or "light").lower() == "dark"
    except Exception:
        return False


def _template():
    return "plotly_dark" if _is_dark() else "plotly_white"


# ============================================================
# 2) KHỐI 1 — KPI STAT CARDS
# ============================================================
def _render_kpis(df):
    total = len(df)
    st_col = df["Trạng thái"].str.lower()
    success_count = int(st_col.isin(_SUCCESS_STATUS).sum())
    success_rate = (success_count / total * 100) if total else 0.0
    total_words = int(df["Số từ viết"].sum()) if "Số từ viết" in df.columns else 0
    audit_rate = (df["Audit"].mean() * 100) if "Audit" in df.columns and total else 0.0

    cards = [
        ("Tổng bài viết", f"{total:,}", "Total Posts", "📄", "c1"),
        ("Tỷ lệ thành công", f"{success_rate:.1f}%", f"{success_count:,} bài đã đăng", "✅", "c2"),
        ("Tổng số từ đã viết", f"{total_words:,} từ", "Word Count", "✍️", "c3"),
        ("Tỷ lệ Audit SEO", f"{audit_rate:.1f}%", f"{int(df['Audit'].sum())} bài đạt audit", "🛡️", "c4"),
    ]
    cols = st.columns(4)
    for col, (label, value, sub, icon, cls) in zip(cols, cards):
        with col:
            st.markdown(
                f'<div class="kpi-card {cls}"><span class="kpi-icon">{icon}</span>'
                f'<div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>'
                f'<div class="kpi-sub">{sub}</div></div>',
                unsafe_allow_html=True,
            )


# ============================================================
# 3) KHỐI 2 — BIỂU ĐỒ TRỰC QUAN (Plotly, hỗ trợ Dark/Light)
# ============================================================
def _render_charts(df):
    template = _template()

    # Biểu đồ 1: Timeline Trend (số bài theo Ngày đăng, màu theo Trạng thái)
    tl = df.copy()
    tl["Ngày"] = tl["Ngày đăng_dt"].dt.date
    tl = tl.dropna(subset=["Ngày"])
    tl["Trạng thái (norm)"] = tl["Trạng thái"].apply(
        lambda s: "Success" if s.lower() in _SUCCESS_STATUS
        else ("Scheduled/Pending" if s.lower() in _PENDING_STATUS or not s else s)
    )
    grouped = tl.groupby(["Ngày", "Trạng thái (norm)"], as_index=False).size().rename(columns={"size": "Số bài"})

    if grouped.empty:
        fig1 = px.bar(title="📅 Bài viết theo Ngày đăng", template=template)
    else:
        fig1 = px.bar(grouped, x="Ngày", y="Số bài", color="Trạng thái (norm)",
                      barmode="group", title="📅 Bài viết theo Ngày đăng",
                      template=template, color_discrete_sequence=px.colors.qualitative.Bold)
        fig1.update_layout(xaxis_title="Ngày đăng", yaxis_title="Số bài", legend_title="Trạng thái",
                           bargap=0.2, height=360, margin=dict(l=10, r=10, t=50, b=10))

    # Biểu đồ 2: Donut — phân bổ Loại nội dung
    ct = df["Loại nội dung"].replace("", "Khác").str.strip()
    ct_counts = ct.value_counts().reset_index()
    ct_counts.columns = ["Loại nội dung", "Số bài"]
    fig2 = px.pie(ct_counts, names="Loại nội dung", values="Số bài", hole=0.55,
                  title="🍩 Phân bổ Loại nội dung", template=template,
                  color_discrete_sequence=px.colors.qualitative.Set2)
    fig2.update_traces(textinfo="label+percent", textposition="inside", textfont_size=12)
    fig2.update_layout(height=360, margin=dict(l=10, r=10, t=50, b=10), showlegend=True)

    # Biểu đồ 3: Word Count Histogram
    fig3 = px.histogram(df, x="Số từ viết", nbins=20,
                        title="📊 Phân bố độ dài bài viết (Số từ viết)",
                        template=template, color_discrete_sequence=["#7C3AED"])
    fig3.update_layout(xaxis_title="Số từ", yaxis_title="Số bài", height=320,
                       margin=dict(l=10, r=10, t=50, b=10))

    c1, c2 = st.columns([3, 2])
    with c1:
        st.plotly_chart(fig1, use_container_width=True)
    with c2:
        st.plotly_chart(fig2, use_container_width=True)
    st.plotly_chart(fig3, use_container_width=True)


# ============================================================
# 4) KHỐI 3 — BỘ LỌC & BẢNG THEO DÕI CHI TIẾT
# ============================================================
def _render_filters_table(df):
    st.markdown("#### 📋 Danh sách bài viết gần đây")

    f1, f2, f3 = st.columns(3)
    sites = sorted([s for s in df["Tên Website"].unique() if s])
    statuses = sorted([s for s in df["Trạng thái"].unique() if s])
    types_ = sorted([t for t in df["Loại nội dung"].unique() if t])

    with f1:
        sel_site = st.multiselect("🌐 Tên Website", sites, default=sites)
    with f2:
        sel_status = st.multiselect("🚦 Trạng thái", statuses, default=statuses)
    with f3:
        sel_type = st.multiselect("📁 Loại nội dung", types_, default=types_)

    mask = pd.Series(True, index=df.index)
    if sel_site:
        mask &= df["Tên Website"].isin(sel_site)
    if sel_status:
        mask &= df["Trạng thái"].isin(sel_status)
    if sel_type:
        mask &= df["Loại nội dung"].isin(sel_type)
    view = df[mask].copy()

    if "Ngày đăng_dt" in view.columns and view["Ngày đăng_dt"].notna().any():
        view = view.sort_values("Ngày đăng_dt", ascending=False, na_position="last")
    view = view.head(500)

    if view.empty:
        st.info("Không có dữ liệu khớp bộ lọc.")
        return

    show_cols = ["STT", "Tên Website", "Từ khoá chính", "Loại nội dung", "Số từ viết",
                 "Ngày đăng", "Giờ đăng", "Trạng thái", "Link bài viết", "Audit", "Internal Link"]
    show_cols = [c for c in show_cols if c in view.columns]
    table = view[show_cols].copy()

    st.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
        height=420,
        column_config={
            "Link bài viết": st.column_config.LinkColumn("Link bài viết", display_text="🔗 Xem"),
            "Internal Link": st.column_config.LinkColumn("Internal Link", display_text="🔗 Xem"),
            "Từ khoá chính": st.column_config.TextColumn("Từ khoá chính", width="medium"),
            "Trạng thái": st.column_config.TextColumn("Trạng thái", width="small"),
            "Số từ viết": st.column_config.NumberColumn("Số từ viết", format="%d"),
            "Audit": st.column_config.CheckboxColumn("Audit", width="small"),
            "Ngày đăng": st.column_config.TextColumn("Ngày đăng", width="small"),
            "Giờ đăng": st.column_config.TextColumn("Giờ đăng", width="small"),
        },
    )
    st.caption(f"Hiển thị {len(view)}/{len(df)} dòng · 12 cột chuẩn A–L từ Google Sheet (Trang tính1)")


# ============================================================
# 5) KHỐI 4 — TRẠNG THÁI HỆ THỐNG & NÚT THAO TÁC NHANH
# ============================================================
def _health_chip(label, status, dot):
    return f'<span class="health-chip"><span class="dot {dot}"></span>{label}: {status}</span>'


def _trigger_schedule(on_trigger=None):
    """Kích hoạt chạy Lịch ngay: ưu tiên callback on_trigger, fallback gọi Backend Node.js."""
    if on_trigger is not None:
        try:
            st.success(f"✅ {on_trigger()}")
            return
        except Exception as e:
            st.error(f"❌ {e}")
            return
    try:
        payload = {
            "title": "🚀 Dashboard: Kích hoạt chạy lịch",
            "url": "",
            "publishDate": datetime.now().strftime("%Y-%m-%d"),
            "status": "Scheduled",
        }
        r = requests.post(SCHEDULE_API_URL, json=payload, timeout=15)
        try:
            body = r.json()
            msg = body.get("message", f"HTTP {r.status_code}")
        except Exception:
            msg = f"HTTP {r.status_code}"
        if r.ok:
            st.success(f"✅ {msg}")
        else:
            st.warning(f"⚠️ {msg}")
    except Exception as e:
        st.error(f"❌ Không kết nối được Backend tại {SCHEDULE_API_URL}: {e}")


def _render_system_health(df, on_trigger=None):
    st.markdown("#### ⚡ Trạng thái hệ thống & Thao tác nhanh")

    sheets_ok = len(df) > 0
    bright_ok = bool(os.environ.get("BRIGHTDATA_API_KEY"))
    wp_sites = sorted([s for s in df["Tên Website"].unique() if s])

    chips = ""
    chips += _health_chip("Google Sheets API", "Active" if sheets_ok else "No data", "dot-ok" if sheets_ok else "dot-warn")
    chips += _health_chip("Bright Data Grounding", "Ready" if bright_ok else "Chưa cấu hình", "dot-ok" if bright_ok else "dot-warn")
    chips += _health_chip("WordPress REST API", f"Connected · {len(wp_sites)} site" if wp_sites else "Chưa có site", "dot-ok" if wp_sites else "dot-warn")
    st.markdown(f'<div>{chips}</div>', unsafe_allow_html=True)

    st.markdown("---")
    a1, a2 = st.columns(2)
    with a1:
        if st.button("🔄 Làm mới dữ liệu", use_container_width=True, type="secondary"):
            st.session_state["dash_force_refresh"] = True
            st.rerun()
    with a2:
        if st.button("🚀 Kích hoạt chạy Lịch ngay", use_container_width=True, type="primary"):
            _trigger_schedule(on_trigger)


# ============================================================
# 6) HÀM CHÍNH — RENDER DASHBOARD
# ============================================================
def render_dashboard(df_sheet, on_refresh=None, on_trigger=None):
    """Vẽ toàn bộ Dashboard Auto Poster Pro.

    Args:
        df_sheet: pandas.DataFrame 12 cột đọc từ Google Sheet (Trang tính1).
        on_refresh: callable() → DataFrame mới (nút 🔄 Làm mới). None → tắt làm mới.
        on_trigger: callable() → str (nút 🚀 Kích hoạt chạy Lịch ngay; ưu tiên hơn gọi API mặc định).
    """
    st.markdown(_CSS, unsafe_allow_html=True)

    if on_refresh is not None:
        if st.session_state.pop("dash_force_refresh", False):
            try:
                df_sheet = on_refresh()
            except Exception as e:
                st.error(f"Không làm mới được dữ liệu: {e}")
        elif "dash_df" not in st.session_state:
            st.session_state["dash_df"] = df_sheet
        df_sheet = st.session_state.get("dash_df", df_sheet)

    df = clean_df(df_sheet)

    st.markdown(
        """<div class="header-banner"><h1>📊 Dashboard Hiệu Suất</h1>
        <p>Theo dõi toàn bộ hệ thống Auto Poster Pro — lịch xuất bản, chất lượng SEO & trạng thái kết nối</p></div>""",
        unsafe_allow_html=True,
    )

    if df.empty:
        st.warning("⚠️ Chưa có dữ liệu từ Google Sheet. Vui lòng cấu hình Google Sheets trong ⚙️ Global Settings hoặc chạy worker để tạo dữ liệu.")
        _render_system_health(df, on_trigger=on_trigger)
        return

    # Khối 1: KPI
    _render_kpis(df)
    st.markdown("---")
    # Khối 2: Biểu đồ
    _render_charts(df)
    st.markdown("---")
    # Khối 3: Bộ lọc + bảng
    _render_filters_table(df)
    st.markdown("---")
    # Khối 4: Hệ thống & thao tác nhanh
    _render_system_health(df, on_trigger=on_trigger)

