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

    st.subheader("Stats")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("N", len(values))
    c2.metric("Mean", f"{result['mean_x']:.{decimals}f}")
    c3.metric("Avg MR", f"{result['mean_mr']:.{decimals}f}")
    c4.metric("Sigma", f"{result['sigma']:.{decimals}f}")

    st.subheader("Interpretation")
    notes = []
    notes.append(
        "- Points outside Individuals limits: "
        f"{len(result['out_of_control_x']) or 'None'}"
    )
    notes.append(
        "- Points outside MR limits: "
        f"{len(result['out_of_control_mr']) or 'None'}"
    )
    notes.append(
        "- Long runs (8+): "
        f"{len(result['long_runs_idx']) or 'None'}"
    )
    st.markdown("\n".join(notes))

    # Individuals chart
    fig_x = go.Figure()
    fig_x.add_trace(go.Scatter(x=df.index, y=df["x"],
                               mode="lines+markers", name=series_name))
    fig_x.add_hline(y=result["mean_x"], line_dash="dash", annotation_text="Mean")
    fig_x.add_hline(y=result["ucl_x"], line_dash="dot", annotation_text="UCL")
    fig_x.add_hline(y=result["lcl_x"], line_dash="dot", annotation_text="LCL")
    fig_x.update_layout(title="Individuals Chart", xaxis_title="Observation")
    st.plotly_chart(fig_x, use_container_width=True)

    # MR chart
    fig_mr = go.Figure()
    fig_mr.add_trace(go.Scatter(x=df.index, y=df["mr"],
                                mode="lines+markers", name="MR"))
    fig_mr.add_hline(y=result["mean_mr"], line_dash="dash", annotation_text="MR Mean")
    fig_mr.add_hline(y=result["ucl_mr"], line_dash="dot", annotation_text="UCL")
    fig_mr.add_hline(y=0, line_dash="dot", annotation_text="LCL")
    fig_mr.update_layout(title="Moving Range Chart", xaxis_title="Observation")
    st.plotly_chart(fig_mr, use_container_width=True)

    st.subheader("Data")
    st.dataframe(df.style.format(
        {"x": f"{{:.{decimals}f}}", "mr": f"{{:.{decimals}f}}"}
    ))
