import numpy as np
import pandas as pd

D2_FOR_2 = 1.128

def compute_xmr(values: pd.Series) -> dict:
    values = values.astype(float)
    n = len(values)
    if n < 2:
        raise ValueError("Need at least 2 data points.")

    mr = values.diff().abs()
    mr.iloc[0] = np.nan

    mean_x = values.mean()
    mean_mr = mr[1:].mean()

    sigma = mean_mr / D2_FOR_2 if mean_mr > 0 else np.nan

    ucl_x = mean_x + 3 * sigma
    lcl_x = mean_x - 3 * sigma

    ucl_mr = mean_mr * 3.267
    lcl_mr = 0.0

    out_x = values[(values > ucl_x) | (values < lcl_x)].index.tolist()
    out_mr = mr[mr > ucl_mr].index.tolist()

    # simple long-run rule (8 on one side of mean)
    side = np.where(values > mean_x, 1, np.where(values < mean_x, -1, 0))
    long_runs = []
    streak = 0
    last = 0
    for i, s in enumerate(side):
        if s == 0:
            streak = 0
            last = 0
            continue
        if s == last:
            streak += 1
        else:
            streak = 1
            last = s
        if streak >= 8:
            long_runs.append(i)

    return {
        "values": values,
        "mr": mr,
        "mean_x": mean_x,
        "mean_mr": mean_mr,
        "sigma": sigma,
        "ucl_x": ucl_x,
        "lcl_x": lcl_x,
        "ucl_mr": ucl_mr,
        "lcl_mr": lcl_mr,
        "out_of_control_x": out_x,
        "out_of_control_mr": out_mr,
        "long_runs_idx": long_runs,
    }
