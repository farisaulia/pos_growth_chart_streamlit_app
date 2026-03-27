import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

st.set_page_config(page_title="POS Trend Analyzer", layout="wide")

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def classify(slope, r2):
    if slope > 0 and r2 > 0.6:   return "Consistent Growth"
    if slope > 0:                 return "Inconsistent Growth"
    if slope < 0 and r2 > 0.6:   return "Consistent Decline"
    if slope < 0:                 return "Inconsistent Decline"
    return "Flat"


def analyze(df, aging_filter):
    month_cols = sorted(
        [c for c in df.columns if c.startswith("M")],
        key=lambda x: int(x.replace("M", ""))
    )
    df_aging = df[df["Aging"] == aging_filter]
    df_melt = df_aging.melt(
        id_vars=["POS Name"], value_vars=month_cols,
        var_name="Month", value_name="Value"
    )
    df_melt["Month_num"] = df_melt["Month"].str.replace("M", "").astype(int)

    results = []
    for pos in df_melt["POS Name"].unique():
        subset = (
            df_melt[df_melt["POS Name"] == pos]
            .dropna(subset=["Value"])
            .sort_values("Month_num")
        )
        x = subset["Month_num"].values
        y = subset["Value"].values
        if len(x) < 2:
            continue
        slope, intercept = np.polyfit(x, y, 1)
        y_fit = slope * x + intercept
        ss_res = np.sum((y - y_fit) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        r2 = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        total_growth = y[-1] - y[0]
        growth_pct = ((y[-1] - y[0]) / y[0]) * 100 if y[0] != 0 else np.nan
        results.append({
            "POS": pos, "x": x, "y": y, "y_fit": y_fit,
            "slope": slope, "r2": r2,
            "total_growth": int(total_growth),
            "growth_pct": round(growth_pct, 2) if not np.isnan(growth_pct) else None,
            "status": classify(slope, r2),
        })
    return results, sorted(df_melt["Month_num"].unique())


COLORS = [
    "#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A",
    "#19D3F3", "#FF6692", "#B6E880", "#FF97FF", "#FECB52",
    "#1F77B4", "#FF7F0E", "#2CA02C", "#D62728", "#9467BD",
]


def build_figure(results, unique_months, pos_color_map, title, search=""):
    fig = go.Figure()

    # Sort alphabetically so legend appears A-Z
    results = sorted(results, key=lambda r: r["POS"])

    search_term = search.strip().lower()

    for r in results:
        pos = r["POS"]
        color = pos_color_map[pos]
        slope_sign = "(+ve)" if r["slope"] > 0 else "(-ve)"

        # Dim traces that don't match the search term
        matched = (search_term == "") or (search_term in pos.lower())
        line_opacity   = 1.0 if matched else 0.08
        marker_opacity = 0.3 if matched else 0.03
        label_color    = color if matched else "#cccccc"

        hover_text = (
            f"<b>{pos}</b><br>"
            f"Status: {r['status']}<br>"
            f"Slope: {r['slope']:+.3f} {slope_sign}<br>"
            f"R2: {r['r2']:.3f}<br>"
            f"Total Growth: {r['total_growth']:+d}<br>"
            + (f"Growth %: {r['growth_pct']:+.1f}%" if r["growth_pct"] is not None else "")
        )

        # Raw scatter dots
        fig.add_trace(go.Scatter(
            x=r["x"], y=r["y"],
            mode="markers",
            name=pos,
            legendgroup=pos,
            showlegend=False,
            marker=dict(color=color, size=7, opacity=marker_opacity),
            hoverinfo="skip",
        ))

        # Trend line
        fig.add_trace(go.Scatter(
            x=r["x"], y=r["y_fit"],
            mode="lines",
            name=pos,
            legendgroup=pos,
            showlegend=True,
            line=dict(color=color, width=2),
            opacity=line_opacity,
            hovertemplate=hover_text + "<extra></extra>",
        ))

        # (+ve)/(-ve) label — same legendgroup, hides/shows with the line
        fig.add_trace(go.Scatter(
            x=[r["x"][-1] + 0.3],
            y=[r["y_fit"][-1]],
            mode="text",
            text=[slope_sign],
            textfont=dict(color=label_color, size=13),
            legendgroup=pos,
            showlegend=False,
            hoverinfo="skip",
        ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color="#111"), x=0.01),
        xaxis=dict(
            tickvals=unique_months,
            ticktext=[f"M{m}" for m in unique_months],
            title=dict(text="Month", font=dict(color="#111")),
            tickfont=dict(color="#111"),
            gridcolor="#d1d5db",
            linecolor="#888",
            linewidth=1,
            showline=True,
            mirror=True,
        ),
        yaxis=dict(
            title=dict(text="Value", font=dict(color="#111")),
            tickfont=dict(color="#111"),
            gridcolor="#d1d5db",
            linecolor="#888",
            linewidth=1,
            showline=True,
            mirror=True,
        ),
        legend=dict(
            itemclick="toggle",
            itemdoubleclick="toggleothers",
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor="#888",
            borderwidth=1,
            font=dict(color="#111", size=12),
        ),
        hovermode="closest",
        margin=dict(l=60, r=100, t=50, b=50),
        height=500,
        plot_bgcolor="white",
        paper_bgcolor="white",
    )
    return fig


# ──────────────────────────────────────────────
# Load data
# ──────────────────────────────────────────────

# Replace this URL with your own GitHub raw file URL
GITHUB_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/data/your_file.xlsx"

@st.cache_data
def load_from_github(url):
    import requests, io
    response = requests.get(url)
    response.raise_for_status()
    xl = pd.ExcelFile(io.BytesIO(response.content))
    return {s: xl.parse(s) for s in xl.sheet_names}

@st.cache_data
def load_from_upload(file):
    if file.name.endswith(".csv"):
        return {"Sheet1": pd.read_csv(file)}
    xl = pd.ExcelFile(file)
    return {s: xl.parse(s) for s in xl.sheet_names}


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
st.title("POS Trend Analyzer")

uploaded = st.file_uploader("Override with a different file (optional)", type=["xlsx", "xls", "csv"])

if uploaded:
    sheets = load_from_upload(uploaded)
else:
    try:
        sheets = load_from_github(GITHUB_URL)
    except Exception as e:
        st.error(f"Could not load file from GitHub: {e}")
        st.stop()
sheet_name = st.selectbox("Sheet", list(sheets.keys())) if len(sheets) > 1 else list(sheets.keys())[0]
df = sheets[sheet_name]

if not {"POS Name", "Aging"}.issubset(df.columns):
    st.error("Missing required columns: 'POS Name' and/or 'Aging'")
    st.stop()

# Assign one consistent colour per POS (sorted A-Z so colours are stable)
all_pos_names = sorted(df["POS Name"].dropna().unique().tolist())
pos_color_map = {pos: COLORS[i % len(COLORS)] for i, pos in enumerate(all_pos_names)}

# Search box — applies to all charts at once
search = st.text_input("Search POS", placeholder="Type to highlight matching POS, others will dim...")

# One chart per aging bucket
for aging in df["Aging"].dropna().unique():
    results, unique_months = analyze(df, aging)
    if not results:
        continue

    fig = build_figure(results, unique_months, pos_color_map, f"[{sheet_name}] - {aging}", search)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander(f"Summary table - {aging}", expanded=False):
        summary_df = pd.DataFrame([{
            "POS":          r["POS"],
            "Status":       r["status"],
            "Slope":        r["slope"],
            "R2":           r["r2"],
            "Total Growth": r["total_growth"],
            "Growth %":     r["growth_pct"],
        } for r in results]).sort_values("Slope", ascending=False)

        st.dataframe(summary_df, use_container_width=True, hide_index=True)
        st.download_button(
            f"Download CSV - {aging}",
            summary_df.to_csv(index=False),
            f"summary_{aging.replace(' ', '_')}.csv",
            "text/csv",
            key=f"dl_{aging}",
        )