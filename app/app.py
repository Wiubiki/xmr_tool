import os
import sys

# --- Make sure the project root is on sys.path so `xmr_core` can be imported ---
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import streamlit as st
import pandas as pd
import numpy as np
from xmr_core.xmr import compute_xmr
import plotly.graph_objects as go

st.set_page_config(page_title="XmR Tool", layout="wide")
st.title("XmR Control Chart Tool")

st.markdown(
    "Paste values below. Dates are optional. If omitted, points will be numbered."
)

col1, col2 = st.columns(2)

with col1:
    raw_values = st.text_area(
        "Values",
        height=200,
        placeholder="356 316 373 302 569 ...",
    )

with col2:
    raw_dates = st.text_area(
        "Dates (optional)",
        height=200,
        placeholder="2025-01-01\n2025-01-02\n...",
    )

series_name = st.text_input("Series name", "Metric")
decimals = st.number_input("Decimal places", 0, 6, 1)

if st.button("Generate XmR"):
    try:
        vals = [float(x) for x in raw_values.replace(",", " ").replace(";", " ").split()]
        values = pd.Series(vals)
    except:
        st.error("Could not parse values.")
        st.stop()

    if raw_dates.strip():
        dates = [d.strip() for d in raw_dates.splitlines() if d.strip()]
        if len(dates) != len(values):
            st.error("Dates and values must have same length.")
            st.stop()
        idx = pd.to_datetime(dates, errors="coerce")
        if idx.isna().any():
            st.error("Some dates could not be parsed.")
            st.stop()
    else:
        idx = pd.RangeIndex(1, len(values) + 1)

    result = compute_xmr(values)

    df = pd.DataFrame({
        "x": result["values"].values,
        "mr": result["mr"].values,
    }, index=idx)

    # Precompute midpoints for both charts BEFORE interpretation or plotting
    mid_upper = (result["mean_x"] + result["ucl_x"]) / 2
    mid_lower = (result["mean_x"] + result["lcl_x"]) / 2

    mr_mid = (result["mean_mr"] + result["ucl_mr"]) / 2


    st.subheader("Stats")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("N", len(values))
    c2.metric("Mean", f"{result['mean_x']:.{decimals}f}")
    c3.metric("Avg MR", f"{result['mean_mr']:.{decimals}f}")
    c4.metric("Sigma", f"{result['sigma']:.{decimals}f}")

    # -----------------------------
    # INTERPRETATION SECTION
    # -----------------------------
    st.subheader("Interpretation")
    col_left, col_right = st.columns(2)

    # ------------------------------------------------------
    # COLUMN LEFT: WHAT THE CHARTS ARE TELLING US
    # ------------------------------------------------------
    with col_left:
        st.markdown("### What the X chart tells us")

        latest_val = df["x"].iloc[-1]
        latest_date = df.index[-1]

        interp_x = []

        # 1. Latest value vs mean
        if latest_val > result["mean_x"]:
            direction = "above"
        elif latest_val < result["mean_x"]:
            direction = "below"
        else:
            direction = "equal to"

        interp_x.append(
            f"- Latest value **({latest_val:.{decimals}f})** on **{latest_date}** is **{direction}** the long-term mean **({result['mean_x']:.{decimals}f})**."
        )

        # 2. Single-point outliers
        if result["out_of_control_x"]:
            interp_x.append(
                f"- **{len(result['out_of_control_x'])} point(s)** beyond X control limits (special-cause spike)."
            )
        else:
            interp_x.append("- No single-point outliers (no special-cause spikes).")

        # 3. Long run (8+)
        if result["long_runs_idx"]:
            interp_x.append(
                "- A **run of 8+ points** on one side of the mean (possible sustained shift)."
            )
        else:
            interp_x.append("- No long runs (no sustained shift).")

        # 4. 3–4 point hugging
        hugging = False
        for i in range(len(df)):
            window = df["x"].iloc[max(0, i-3):i+1]
            if len(window) >= 3 and (
                (window > result["ucl_x"]*0.9).all() or (window < result["lcl_x"]*0.9).all()
            ):
                hugging = True
                break

        if hugging:
            interp_x.append(
                "- **3–4 point limit-hugging** detected (possible change in routine variation)."
            )
        else:
            interp_x.append("- No limit-hugging patterns (variation appears routine).")

        st.markdown("\n".join(interp_x))

        # --------------------------------------------------
        # MR CHART INTERPRETATION
        # --------------------------------------------------
        st.markdown("### What the MR chart tells us")

        if result["out_of_control_mr"]:
            st.markdown(
                f"- **MR outlier detected** → variation is unstable; X-chart limits may not fully reflect real behavior."
            )
        else:
            st.markdown(
                "- No MR outliers → routine variation appears stable and X-chart limits are reliable."
            )

        if (df["mr"].iloc[1:] >= mr_mid).any():
            st.markdown(
                "- Some MR values are high (yellow zone) → variation is increasing, worth monitoring."
            )
        else:
            st.markdown(
                "- MR values follow routine pattern → no sign of increasing noise."
            )


    # ------------------------------------------------------
    # COLUMN RIGHT: HOW TO READ THE X & MR CHARTS
    # ------------------------------------------------------
    with col_right:
        st.markdown("### How to read the X chart")
        st.write(
            """
    The Individuals chart shows *where the process level is going*.  
    You’re looking for signals that the mean or pattern has changed.

    **Key signals:**
    1. **Spikes** — points outside UCL/LCL → special cause.  
    2. **Shifts** — 8+ points on one side of mean → the process level changed.  
    3. **Limit hugging** — 3–4 points near a control limit → variation increasing or system drifting.

    If none of these appear → the process is stable and predictable.
    """
        )

        st.markdown("### How to read the MR chart")
        st.write(
            """
    The MR chart shows *how stable the variation is*.  
    If this chart is unstable, the X chart cannot be trusted.

    **What to look for:**
    1. **MR outliers** → sudden spikes in noise (instability).  
    2. **High MR values** → variation is increasing over time.  
    3. **Low MR values** → system becoming tighter (can indicate improvements or compression).

    Stable MR → reliable control limits.  
    Unstable MR → the system is rattling before it shifts.
    """
        )



    # Individuals chart
    fig_x = go.Figure()

    # --- Compute midpoint boundaries first ---
    mid_upper = (result["mean_x"] + result["ucl_x"]) / 2
    mid_lower = (result["mean_x"] + result["lcl_x"]) / 2

    # --- Shaded danger-zone areas (between midpoint & limits) ---
    fig_x.add_shape(
        type="rect",
        x0=df.index.min(), x1=df.index.max(),
        y0=mid_upper, y1=result["ucl_x"],
        fillcolor="rgba(255, 215, 0, 0.12)",  # transparent golden yellow
        line_width=0,
        layer="below"
    )

    fig_x.add_shape(
        type="rect",
        x0=df.index.min(), x1=df.index.max(),
        y0=result["lcl_x"], y1=mid_lower,
        fillcolor="rgba(255, 215, 0, 0.12)",
        line_width=0,
        layer="below"
    )

    # --- Color-code each point (must be AFTER midpoints exist) ---
    colors = []
    for v in result["values"]:
        if v > result["ucl_x"] or v < result["lcl_x"]:
            colors.append("red")          # outlier
        elif v >= mid_upper or v <= mid_lower:
            colors.append("gold")         # hugging zone
        else:
            colors.append("dodgerblue")   # normal

    # --- Plot the line + colored markers ---
    fig_x.add_trace(go.Scatter(
        x=df.index,
        y=df["x"],
        mode="lines+markers",
        name=series_name,
        marker=dict(color=colors, size=8),
        line=dict(color="gray")
    ))

    # --- Main reference lines ---
    fig_x.add_hline(y=result["mean_x"], line_dash="dash", annotation_text="Mean")
    fig_x.add_hline(y=result["ucl_x"], line_dash="dot", annotation_text="UCL")
    fig_x.add_hline(y=result["lcl_x"], line_dash="dot", annotation_text="LCL")

    # --- Midpoint reference lines (faint) ---
    fig_x.add_hline(
        y=mid_upper,
        line_dash="dot",
        line_color="darkgray",
        opacity=0.5,
        annotation_text=None,
    )

    fig_x.add_hline(
        y=mid_lower,
        line_dash="dot",
        line_color="darkgray",
        opacity=0.5,
        annotation_text=None,
    )

    fig_x.update_layout(
        title="Individuals Chart",
        xaxis_title="Observation",
        yaxis_title=series_name,
    )

    st.plotly_chart(fig_x, use_container_width=True)


    # MR chart
    fig_mr = go.Figure()

    # --- MR midpoint (halfway to UCL) ---
    mr_mid = (result["mean_mr"] + result["ucl_mr"]) / 2

    # --- Shaded high-variation danger zone ---
    fig_mr.add_shape(
        type="rect",
        x0=df.index.min(), x1=df.index.max(),
        y0=mr_mid, y1=result["ucl_mr"],
        fillcolor="rgba(255, 215, 0, 0.12)",  # light transparent yellow
        line_width=0,
        layer="below"
    )

    # --- Color-code MR points ---
    mr_colors = []
    for v in result["mr"]:
        if pd.isna(v):
            mr_colors.append("lightgray")   # first MR is always NaN
        elif v > result["ucl_mr"]:
            mr_colors.append("red")         # MR outlier
        elif v >= mr_mid:
            mr_colors.append("gold")        # elevated variation
        else:
            mr_colors.append("dodgerblue")  # normal

    # --- MR line + markers ---
    fig_mr.add_trace(go.Scatter(
        x=df.index,
        y=df["mr"],
        mode="lines+markers",
        name="MR",
        marker=dict(color=mr_colors, size=8),
        line=dict(color="gray")
    ))

    # --- Reference lines ---
    fig_mr.add_hline(y=result["mean_mr"], line_dash="dash", annotation_text="MR Mean")
    fig_mr.add_hline(y=result["ucl_mr"], line_dash="dot", annotation_text="UCL")
    fig_mr.add_hline(y=0, line_dash="dot", annotation_text="LCL")

    # --- Midpoint line (faint) ---
    fig_mr.add_hline(
        y=mr_mid,
        line_dash="dot",
        line_color="darkgray",
        opacity=0.5,
        annotation_text=None,
    )

    fig_mr.update_layout(
        title="Moving Range Chart",
        xaxis_title="Observation",
        yaxis_title="Moving Range",
    )

    st.plotly_chart(fig_mr, use_container_width=True)

