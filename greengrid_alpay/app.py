"""
GreenGrid — GIS Dashboard (app.py) v6
======================================
Google Earth + Energy AI dashboard hissi.
  - Dark theme + glassmorphism panels
  - Energy mode switch (Solar/Wind/Hydro/All)
  - Glow ring markers for best zones
  - Floating KPI overlay
  - Smart insight cards
  - Circle + polygon + rectangle draw
  - Progressive analysis with live progress
"""

import streamlit as st
import folium
from folium.plugins import Draw, HeatMap
from streamlit_folium import st_folium
import plotly.graph_objects as go
import numpy as np

from data_fetcher import gather_all
from decision_engine import recommend
from maintenance import maintenance_schedule
from grid_analyzer import analyze_grid, circle_to_bounds

# ══════════════════════════════════════════════
# THEME & CONFIG
# ══════════════════════════════════════════════
st.set_page_config(page_title="GreenGrid", page_icon="🌱",
                   layout="wide", initial_sidebar_state="collapsed")

EM = {"Solar": "☀️", "Wind": "💨", "Hydro": "💧", "All": "🌍"}
NM = {"Solar": "Güneş", "Wind": "Rüzgar", "Hydro": "Hidro", "All": "Tümü"}
CM = {"Solar": "#FF8C00", "Wind": "#4A9EFF", "Hydro": "#00C896"}
GRADIENTS = {
    "Solar": {0.3: "#2d1b00", 0.5: "#804000", 0.7: "#cc6600", 0.85: "#ff8c00", 1.0: "#ffc266"},
    "Wind":  {0.3: "#001a33", 0.5: "#003366", 0.7: "#1a75ff", 0.85: "#4a9eff", 1.0: "#99c2ff"},
    "Hydro": {0.3: "#001a13", 0.5: "#004d33", 0.7: "#00804d", 0.85: "#00c896", 1.0: "#66e0b8"},
}

# ──────────────────────────────────────────────
# GLOBAL CSS
# ──────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Inter:wght@300;400;500;600;700&display=swap');

/* Base theme */
.stApp { font-family: 'Inter', sans-serif; }
.block-container { padding-top: 1rem; }

/* Tab styling */
.stTabs [data-baseweb="tab-list"] {
    gap: 0; background: rgba(30,30,40,0.4);
    border-radius: 12px; padding: 4px;
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.06);
}
.stTabs [data-baseweb="tab"] {
    font-family: 'Inter'; font-size: 0.95rem; font-weight: 600;
    padding: 0.6rem 1.5rem; border-radius: 8px;
    color: rgba(255,255,255,0.6);
}
.stTabs [aria-selected="true"] {
    background: rgba(0,200,150,0.15) !important;
    color: #00C896 !important;
}

/* Glassmorphism card */
.glass-card {
    background: rgba(20,20,30,0.6);
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.8rem;
    box-shadow: 0 8px 32px rgba(0,0,0,0.3);
}
.glass-card-accent {
    background: linear-gradient(135deg, rgba(20,20,30,0.7), rgba(30,30,45,0.5));
    backdrop-filter: blur(20px);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.8rem;
}

/* KPI card */
.kpi-card {
    text-align: center;
    padding: 1rem;
    background: rgba(20,20,30,0.5);
    backdrop-filter: blur(15px);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
}
.kpi-value {
    font-family: 'JetBrains Mono';
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.1;
}
.kpi-label {
    font-size: 0.75rem;
    color: rgba(255,255,255,0.5);
    margin-top: 4px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
.kpi-sub {
    font-size: 0.7rem;
    color: rgba(255,255,255,0.35);
    font-family: 'JetBrains Mono';
}

/* Mode button */
.mode-btn {
    display: inline-block;
    padding: 6px 16px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.2s;
    border: 1px solid rgba(255,255,255,0.1);
}
.mode-active {
    background: rgba(0,200,150,0.2);
    border-color: #00C896;
    color: #00C896;
    box-shadow: 0 0 15px rgba(0,200,150,0.15);
}

/* Insight cards */
.insight-card {
    padding: 0.8rem 1rem;
    border-radius: 10px;
    margin-bottom: 0.5rem;
    border-left: 3px solid;
}
.insight-success {
    background: rgba(0,200,150,0.08);
    border-color: #00C896;
}
.insight-warning {
    background: rgba(255,140,0,0.08);
    border-color: #FF8C00;
}
.insight-info {
    background: rgba(74,158,255,0.08);
    border-color: #4A9EFF;
}
.insight-title {
    font-weight: 600;
    font-size: 0.85rem;
    margin-bottom: 4px;
}
.insight-text {
    font-size: 0.82rem;
    color: rgba(255,255,255,0.7);
    line-height: 1.4;
}

/* Maintenance card */
.maint-card {
    padding: 0.6rem 0.9rem;
    border-radius: 8px;
    margin-bottom: 0.3rem;
    font-size: 0.85rem;
}

/* Header */
.header-glow {
    text-align: center;
    padding: 0.8rem 0 0.3rem 0;
}
.header-glow h1 {
    font-family: 'JetBrains Mono';
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(135deg, #00C896, #4A9EFF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
}
.header-glow p {
    color: rgba(255,255,255,0.4);
    font-size: 0.85rem;
    margin-top: 0.2rem;
    letter-spacing: 2px;
    text-transform: uppercase;
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# HEADER
# ──────────────────────────────────────────────
st.markdown("""
<div class="header-glow">
    <h1>🌱 GREENGRID</h1>
    <p>Sürdürülebilir Enerji Karar Sistemi</p>
</div>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def fmt(lat, lon):
    return (f"{abs(lat):.4f}°{'N' if lat >= 0 else 'S'}, "
            f"{abs(lon):.4f}°{'E' if lon >= 0 else 'W'}")


def render_kpi_row(avgs, bests=None):
    """3 KPI card render eder."""
    cols = st.columns(3)
    for col, src in zip(cols, ["Solar", "Wind", "Hydro"]):
        with col:
            avg = avgs.get(src, 0)
            sub = f"en iyi {bests[src]['score']:.0f}" if bests and bests.get(src) else ""
            st.markdown(f"""
            <div class="kpi-card">
                <div style="font-size:1.5rem;">{EM[src]}</div>
                <div class="kpi-value" style="color:{CM[src]};">{avg:.0f}</div>
                <div class="kpi-label">{NM[src]}</div>
                <div class="kpi-sub">{sub}</div>
            </div>""", unsafe_allow_html=True)


def render_insight_cards(insights):
    """Smart insight kartları render eder."""
    for ins in insights:
        itype = ins.get("type", "info")
        css_class = f"insight-{itype}"
        st.markdown(f"""
        <div class="insight-card {css_class}">
            <div class="insight-title">{ins['title']}</div>
            <div class="insight-text">{ins['text']}</div>
        </div>""", unsafe_allow_html=True)


def build_glow_marker(lat, lon, src, score, conf=None):
    """Glow ring marker oluşturur."""
    color = CM[src]
    popup_html = f"""
    <div style="font-family:Inter,sans-serif; min-width:160px;">
        <div style="font-size:1.4rem; text-align:center;">{EM[src]}</div>
        <div style="text-align:center; font-size:1.2rem; font-weight:700;
            color:{color};">{score:.0f}/100</div>
        <div style="text-align:center; font-size:0.8rem; color:#666;">
            {NM[src]} Enerjisi</div>
        {f'<div style="text-align:center; font-size:0.75rem; color:#999;">Güven: %{conf*100:.0f}</div>' if conf else ''}
    </div>"""

    return [
        # Outer glow
        folium.CircleMarker([lat, lon], radius=18,
            color=color, fill=True, fill_color=color,
            fill_opacity=0.08, weight=1, opacity=0.3),
        # Middle ring
        folium.CircleMarker([lat, lon], radius=12,
            color=color, fill=True, fill_color=color,
            fill_opacity=0.15, weight=2, opacity=0.5),
        # Core
        folium.CircleMarker([lat, lon], radius=6,
            color=color, fill=True, fill_color=color,
            fill_opacity=0.9, weight=2, opacity=1.0,
            popup=folium.Popup(popup_html, max_width=200)),
        # Emoji
        folium.Marker([lat, lon],
            icon=folium.DivIcon(html=f"""
                <div style="font-size:16px; text-shadow:0 0 10px {color},
                    0 0 20px {color}40; position:relative; top:-8px; left:-5px;">
                    {EM[src]}</div>"""),
            tooltip=f"{EM[src]} {score:.0f}/100"),
    ]


# ══════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════
tab1, tab2 = st.tabs(["📍  Nokta Analizi", "🗺️  Bölgesel GIS"])


# ══════════════════════════════════════════════
# TAB 1: NOKTA ANALİZİ
# ══════════════════════════════════════════════
with tab1:
    col_map, col_res = st.columns([1, 1], gap="large")

    with col_map:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("#### 📍 Konum Seçimi")
        c1, c2, c3 = st.columns([2, 2, 1])
        with c1:
            mlat = st.number_input("Enlem", value=39.0, min_value=-90.0,
                                   max_value=90.0, step=0.01, format="%.4f", key="pt_lat")
        with c2:
            mlon = st.number_input("Boylam", value=35.0, min_value=-180.0,
                                   max_value=180.0, step=0.01, format="%.4f", key="pt_lon")
        with c3:
            st.write(""); st.write("")
            btn = st.button("🔍 Analiz", use_container_width=True, key="pt_btn")
        st.markdown('</div>', unsafe_allow_html=True)

        m = folium.Map(location=[39.0, 35.0], zoom_start=6,
                       tiles="CartoDB dark_matter")
        if "pt_analysis" in st.session_state:
            p = st.session_state["pt_analysis"]
            for marker in build_glow_marker(p["lat"], p["lon"],
                                            p["result"]["recommendation"],
                                            p["result"]["scores"][p["result"]["recommendation"]],
                                            p["result"].get("confidence")):
                marker.add_to(m)
        md = st_folium(m, height=460, width=None, key="pt_map")

    # Trigger
    nl, no = None, None
    if btn:
        nl, no = mlat, mlon
    elif md and md.get("last_clicked"):
        cl = md["last_clicked"]
        p = st.session_state.get("pt_analysis")
        if p is None or abs(p["lat"] - cl["lat"]) > 0.001 or abs(p["lon"] - cl["lng"]) > 0.001:
            nl, no = cl["lat"], cl["lng"]

    if nl is not None:
        with col_res:
            with st.spinner(f"🛰️ Analiz: {fmt(nl, no)}"):
                try:
                    features = gather_all(nl, no)
                    result = recommend(features)
                    schedule = maintenance_schedule(result["recommendation"], features)
                    st.session_state["pt_analysis"] = {
                        "lat": nl, "lon": no,
                        "features": features, "result": result, "schedule": schedule}
                except Exception as e:
                    st.error(f"❌ {e}")
                    st.stop()

    with col_res:
        if "pt_analysis" in st.session_state:
            a = st.session_state["pt_analysis"]
            f_ = a["features"]; r = a["result"]; sch = a["schedule"]
            w = r["recommendation"]; wc = CM[w]
            conf = r.get("confidence", 0.8)

            # Winner card
            st.markdown(f"""
            <div class="glass-card-accent" style="border-left:4px solid {wc};">
                <div style="display:flex; align-items:center; gap:12px;">
                    <span style="font-size:2.2rem;">{EM[w]}</span>
                    <div>
                        <div style="font-size:1.3rem; font-weight:700;
                            color:{wc};">{NM[w]} Enerjisi</div>
                        <div style="font-size:0.85rem; color:rgba(255,255,255,0.6);">
                            {fmt(a['lat'], a['lon'])}</div>
                    </div>
                    <div style="margin-left:auto; text-align:right;">
                        <div style="font-family:'JetBrains Mono'; font-size:1.6rem;
                            font-weight:700; color:{wc};">
                            {r['scores'][w]:.0f}</div>
                        <div style="font-size:0.7rem; color:rgba(255,255,255,0.4);">/ 100</div>
                    </div>
                </div>
                <div style="margin-top:0.7rem; font-size:0.88rem;
                    color:rgba(255,255,255,0.65);">{r['reason']}</div>
                <div style="margin-top:0.5rem;">
                    <span style="background:rgba(0,200,150,0.15); color:#00C896;
                        padding:3px 12px; border-radius:20px; font-size:0.78rem;
                        font-weight:600;">{r['feasibility']}</span>
                    <span style="background:rgba(74,158,255,0.15); color:#4A9EFF;
                        padding:3px 12px; border-radius:20px; font-size:0.78rem;
                        font-weight:600; margin-left:6px;">Güven %{conf*100:.0f}</span>
                </div>
            </div>""", unsafe_allow_html=True)

            # Score bars
            fig = go.Figure()
            for src in ["Hydro", "Wind", "Solar"]:
                fig.add_trace(go.Bar(
                    y=[f"{EM[src]} {NM[src]}"], x=[r["scores"][src]],
                    orientation="h", marker_color=CM[src],
                    text=f"{r['scores'][src]:.0f}", textposition="inside",
                    textfont=dict(size=14, color="white", family="JetBrains Mono"),
                    showlegend=False))
            fig.update_layout(
                height=140, margin=dict(l=0, r=10, t=5, b=5),
                xaxis=dict(range=[0, 100], showgrid=False, showticklabels=False),
                yaxis=dict(showgrid=False),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="rgba(255,255,255,0.7)"),
                barmode="stack", bargap=0.4)
            st.plotly_chart(fig, use_container_width=True)

            # Expanders
            with st.expander("📈 Aylık Profil"):
                ay = ["Oca","Şub","Mar","Nis","May","Haz",
                      "Tem","Ağu","Eyl","Eki","Kas","Ara"]
                fs = go.Figure()
                fs.add_trace(go.Bar(x=ay, y=f_["monthly_ghi"],
                    name="GHI", marker_color="#FF8C00", opacity=0.7))
                fs.add_trace(go.Scatter(x=ay, y=f_["monthly_wind"],
                    name="Rüzgar", mode="lines+markers",
                    line=dict(color="#4A9EFF", width=2), yaxis="y2"))
                fs.update_layout(height=220, margin=dict(l=0, r=0, t=10, b=10),
                    yaxis=dict(title=dict(text="GHI", font=dict(color="#FF8C00", size=10)),
                               showgrid=False),
                    yaxis2=dict(title=dict(text="m/s", font=dict(color="#4A9EFF", size=10)),
                                overlaying="y", side="right", showgrid=False),
                    legend=dict(orientation="h", y=1.15, font=dict(size=10)),
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="rgba(255,255,255,0.6)"))
                st.plotly_chart(fs, use_container_width=True)

            with st.expander("🧮 Detaylı Skorlar"):
                for src in ["Solar", "Wind", "Hydro"]:
                    adj = r["scores"][src]
                    st.markdown(f"**{EM[src]} {NM[src]}** — `{adj:.1f}`")
                    for k, v in r["breakdown"][src].items():
                        st.caption(f"→ {k}: {v}")
                    st.divider()

            # Maintenance
            st.markdown("#### 🔧 Bakım Takvimi")
            for t in sch:
                d = t["interval_days"]
                iv = f"{d // 365}y" if d >= 365 else f"{d}g" if d < 30 else f"~{d // 30}ay"
                pc = {"Yüksek": ("#DC3545", "15"), "Orta": ("#FF8C00", "12"),
                      "Düşük": ("#00C896", "10")}
                color, op = pc[t["priority"]]
                st.markdown(f"""
                <div class="maint-card" style="background:rgba({int(color[1:3],16)},
                    {int(color[3:5],16)},{int(color[5:7],16)},0.{op});">
                    <strong>{t['task']}</strong>
                    <span style="float:right; font-family:'JetBrains Mono';
                        font-size:0.8rem;">{iv}</span><br/>
                    <span style="font-size:0.78rem; color:rgba(255,255,255,0.5);">
                        {t['reason']}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="glass-card" style="text-align:center; padding:3rem;">
                <div style="font-size:3rem; margin-bottom:1rem;">🛰️</div>
                <div style="font-size:1.1rem; font-weight:600;
                    color:rgba(255,255,255,0.7);">Konum Seçin</div>
                <div style="font-size:0.85rem; color:rgba(255,255,255,0.4);
                    margin-top:0.5rem;">
                    Haritada tıklayın veya koordinat girin</div>
                <div style="margin-top:1.5rem; font-size:0.8rem;
                    color:rgba(255,255,255,0.3);">
                    Konya 37.87, 32.49 · Çanakkale 40.18, 26.40 · Rize 40.95, 40.80
                </div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════
# TAB 2: BÖLGESEL GIS
# ══════════════════════════════════════════════
with tab2:
    col_ctrl, col_dash = st.columns([1, 1], gap="large")

    with col_ctrl:
        # ── Mode Switch ──
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)

        mode_cols = st.columns(4)
        current_mode = st.session_state.get("energy_mode", "All")
        for i, mode in enumerate(["Solar", "Wind", "Hydro", "All"]):
            with mode_cols[i]:
                if st.button(f"{EM[mode]} {NM[mode]}", key=f"mode_{mode}",
                             use_container_width=True,
                             type="primary" if mode == current_mode else "secondary"):
                    st.session_state["energy_mode"] = mode
                    current_mode = mode

        st.markdown('</div>', unsafe_allow_html=True)

        # ── Controls ──
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.markdown("#### 🗺️ Alan Seçimi")
        st.caption("Haritada alan çizin veya yarıçap seçin")

        ctrl1, ctrl2 = st.columns([2, 1])
        with ctrl1:
            resolution = st.select_slider("Grid",
                options=[3, 4, 5, 6, 7], value=4,
                format_func=lambda x: f"{x}×{x}", key="grid_res")
        with ctrl2:
            st.write("")
            analyze_btn = st.button("🚀 Başlat", use_container_width=True,
                                    key="grid_btn", type="primary")

        st.markdown('</div>', unsafe_allow_html=True)

        # ── Map ──
        m2 = folium.Map(location=[39.0, 35.0], zoom_start=6,
                        tiles="CartoDB dark_matter")

        Draw(
            draw_options={
                "rectangle": {"shapeOptions": {"color": "#00C896", "weight": 2,
                                               "fillOpacity": 0.05}},
                "polygon": {"shapeOptions": {"color": "#4A9EFF", "weight": 2,
                                             "fillOpacity": 0.05}},
                "circle": {"shapeOptions": {"color": "#FF8C00", "weight": 2,
                                            "fillOpacity": 0.05}},
                "polyline": False, "marker": False, "circlemarker": False},
            edit_options={"edit": False},
        ).add_to(m2)

        # Previous results overlay
        if "grid_result" in st.session_state:
            gr = st.session_state["grid_result"]

            # Heatmap layers based on mode
            active_sources = (["Solar", "Wind", "Hydro"] if current_mode == "All"
                              else [current_mode])

            for src in active_sources:
                if gr["heatmaps"][src]:
                    gradient = GRADIENTS.get(src, GRADIENTS["Solar"])
                    HeatMap(gr["heatmaps"][src], min_opacity=0.2, radius=28,
                            blur=22, gradient=gradient,
                            name=f"{NM[src]}").add_to(m2)

            # Glow markers for best zones
            best_zones = gr.get("best_zones", {})
            for src in active_sources:
                for pt in best_zones.get(src, [])[:3]:
                    score = pt["result"]["scores"][src]
                    conf = pt["result"].get("confidence", 0.75)
                    for marker in build_glow_marker(pt["lat"], pt["lon"],
                                                    src, score, conf):
                        marker.add_to(m2)

            # Grid dots with tooltips
            for pt in gr["points"]:
                if pt["result"] is None:
                    continue
                scores = pt["result"]["scores"]
                pw = pt["result"]["recommendation"]
                ps = scores[pw]
                if ps > 10:
                    tooltip = (f"☀️ {scores['Solar']:.0f} · "
                               f"💨 {scores['Wind']:.0f} · "
                               f"💧 {scores['Hydro']:.0f}")
                    display_src = pw if current_mode == "All" else current_mode
                    display_score = scores[display_src]
                    opacity = max(0.2, display_score / 100)
                    folium.CircleMarker(
                        [pt["lat"], pt["lon"]], radius=5,
                        color=CM[display_src], fill=True,
                        fill_color=CM[display_src],
                        fill_opacity=opacity, weight=1, opacity=0.6,
                        tooltip=tooltip).add_to(m2)

            # Bounds outline
            bds = gr["bounds"]
            folium.Rectangle(
                [[bds["min_lat"], bds["min_lon"]],
                 [bds["max_lat"], bds["max_lon"]]],
                color="rgba(255,255,255,0.2)", weight=1,
                fill=False, dash_array="8").add_to(m2)

            folium.LayerControl(collapsed=False).add_to(m2)

        md2 = st_folium(m2, height=520, width=None, key="grid_map")

    # ── Bounds extraction ──
    drawn_bounds = None
    if md2 and md2.get("all_drawings"):
        last = md2["all_drawings"][-1]
        geom = last.get("geometry", {})

        if geom.get("type") == "Polygon" and geom.get("coordinates"):
            coords = geom["coordinates"][0]
            lats = [c[1] for c in coords]
            lons = [c[0] for c in coords]
            drawn_bounds = {"min_lat": min(lats), "max_lat": max(lats),
                            "min_lon": min(lons), "max_lon": max(lons)}

        elif geom.get("type") == "Point":
            # Circle: folium Draw returns center in geometry, radius in properties
            props = last.get("properties", {})
            radius_m = props.get("radius", 10000)
            clat, clon = geom["coordinates"][1], geom["coordinates"][0]
            drawn_bounds = circle_to_bounds(clat, clon, radius_m / 1000)

    # ── Analysis trigger ──
    if analyze_btn:
        if drawn_bounds is None:
            with col_dash:
                st.warning("⚠️ Önce haritada bir alan çizin.")
        else:
            with col_dash:
                st.markdown("#### 🛰️ Analiz Ediliyor...")
                prog = st.progress(0, text="Başlatılıyor...")

                def update_progress(pct, text):
                    prog.progress(min(pct, 1.0), text=text)

                try:
                    result = analyze_grid(drawn_bounds, resolution, update_progress)
                    st.session_state["grid_result"] = result
                    prog.empty()
                    st.rerun()
                except Exception as e:
                    prog.empty()
                    st.error(f"❌ {e}")

    # ── Dashboard panel ──
    with col_dash:
        if "grid_result" in st.session_state:
            gr = st.session_state["grid_result"]
            valid_ct = len([p for p in gr["points"] if p["result"] is not None])

            # ── KPI Cards ──
            st.markdown(f"""
            <div class="glass-card" style="padding:0.6rem 1rem;">
                <span style="font-size:0.75rem; color:rgba(255,255,255,0.4);
                    text-transform:uppercase; letter-spacing:1px;">
                    {gr['resolution']}×{gr['resolution']} Grid · {valid_ct} Nokta
                </span>
            </div>""", unsafe_allow_html=True)

            render_kpi_row(gr["averages"], gr["best"])

            # ── Distribution chart ──
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown("##### Skor Dağılımı")

            # Hex → rgba helper
            def hex_to_rgba(hex_color, alpha=0.3):
                r = int(hex_color[1:3], 16)
                g = int(hex_color[3:5], 16)
                b = int(hex_color[5:7], 16)
                return f"rgba({r},{g},{b},{alpha})"

            fig = go.Figure()
            for src in ["Solar", "Wind", "Hydro"]:
                scores = [p["result"]["scores"][src]
                          for p in gr["points"] if p["result"]]
                fig.add_trace(go.Violin(
                    y=scores, name=f"{EM[src]}",
                    marker_color=CM[src], line_color=CM[src],
                    fillcolor=hex_to_rgba(CM[src], 0.25),
                    box_visible=True, meanline_visible=True,
                    opacity=0.8))
            fig.update_layout(
                height=220, margin=dict(l=0, r=0, t=10, b=10),
                yaxis=dict(range=[0, 100], showgrid=True,
                           gridcolor="rgba(255,255,255,0.05)",
                           title=dict(text="Skor", font=dict(size=10))),
                showlegend=False,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="rgba(255,255,255,0.6)", size=11))
            st.plotly_chart(fig, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # ── Best Locations ──
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown("##### 📍 En Uygun Noktalar")
            for src in ["Solar", "Wind", "Hydro"]:
                b = gr["best"].get(src)
                if b and b["score"] > 15:
                    st.markdown(f"""
                    <div style="display:flex; align-items:center; gap:8px;
                        padding:4px 0; border-bottom:1px solid rgba(255,255,255,0.05);">
                        <span style="font-size:1.2rem;">{EM[src]}</span>
                        <span style="font-family:'JetBrains Mono'; font-size:0.85rem;
                            color:rgba(255,255,255,0.5);">
                            {b['lat']:.4f}, {b['lon']:.4f}</span>
                        <span style="margin-left:auto; font-family:'JetBrains Mono';
                            font-weight:700; color:{CM[src]};">
                            {b['score']:.0f}</span>
                    </div>""", unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

            # ── Smart Insights ──
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown("##### 🧠 Akıllı Yorumlar")
            render_insight_cards(gr["insights"])
            st.markdown('</div>', unsafe_allow_html=True)

            # ── Clear ──
            if st.button("🗑️ Temizle", key="clear_grid"):
                del st.session_state["grid_result"]
                st.rerun()

        elif drawn_bounds:
            st.markdown(f"""
            <div class="glass-card" style="text-align:center; padding:2rem;">
                <div style="font-size:2rem;">📐</div>
                <div style="font-size:0.9rem; color:rgba(255,255,255,0.6);
                    margin-top:0.5rem;">Alan seçildi</div>
                <div style="font-family:'JetBrains Mono'; font-size:0.8rem;
                    color:rgba(255,255,255,0.35); margin-top:0.3rem;">
                    {drawn_bounds['min_lat']:.3f}° – {drawn_bounds['max_lat']:.3f}° N
                </div>
                <div style="margin-top:1rem; font-size:0.85rem;
                    color:#00C896;">🚀 Başlat butonuna basın</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="glass-card" style="text-align:center; padding:2.5rem;">
                <div style="font-size:3rem; margin-bottom:0.8rem;">🗺️</div>
                <div style="font-size:1.1rem; font-weight:600;
                    color:rgba(255,255,255,0.6);">Bölge Seçin</div>
                <div style="font-size:0.82rem; color:rgba(255,255,255,0.35);
                    margin-top:0.8rem; line-height:1.6;">
                    🔲 Dikdörtgen · 🔷 Çokgen · ⭕ Yarıçap<br/>
                    araçlarından birini kullanın
                </div>
            </div>""", unsafe_allow_html=True)

            st.markdown("""
            <div class="glass-card">
                <div class="insight-title" style="color:rgba(255,255,255,0.5);">
                    Mod Seçimi</div>
                <div class="insight-text">
                    Üstteki enerji modu butonlarıyla harita katmanını değiştirin.
                    <strong>Tümü</strong> modunda 3 kaynak birlikte gösterilir.
                </div>
            </div>""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────
st.markdown("""
<div style="text-align:center; padding:1rem 0 0.5rem; font-size:0.7rem;
    color:rgba(255,255,255,0.2); letter-spacing:1px;">
    GREENGRID v2.0 · NASA POWER · OpenTopoData · Open-Meteo · OSM
</div>""", unsafe_allow_html=True)