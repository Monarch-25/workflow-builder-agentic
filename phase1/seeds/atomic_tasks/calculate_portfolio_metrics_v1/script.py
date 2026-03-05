# AUTO-GENERATED ATOMIC TASK SCRIPT
# task_id:       calculate_portfolio_metrics_v1
# input_schema:  {"price_series": "list[float]", "risk_free_rate": "float"}
# output_schema: {"returns": "list[float]", "volatility": "float", "sharpe_ratio": "float"}

import json
import sys

import numpy as np


def execute(inputs: dict) -> dict:
    """Calculate portfolio metrics from a price series."""
    prices = np.array(inputs["price_series"], dtype=np.float64)
    rf = inputs.get("risk_free_rate", 0.0)

    if len(prices) < 2:
        raise ValueError("Need at least 2 prices to compute returns")

    # Daily log returns
    log_returns = np.diff(np.log(prices))
    # Annualised (assume 252 trading days)
    annualised_return = float(np.mean(log_returns) * 252)
    annualised_vol = float(np.std(log_returns, ddof=1) * np.sqrt(252))

    sharpe = (annualised_return - rf) / annualised_vol if annualised_vol > 0 else 0.0

    return {
        "returns": log_returns.tolist(),
        "volatility": round(annualised_vol, 6),
        "sharpe_ratio": round(sharpe, 6),
    }


if __name__ == "__main__":
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    with open(input_path) as f:
        inputs = json.load(f)
    result = execute(inputs)
    with open(output_path, "w") as f:
        json.dump(result, f)
