"""Unit tests for metric correlation and lead-lag cross-correlation."""

import numpy as np
import pandas as pd

from src.ml.correlation import LaggedCorrelationAnalyzer, MetricCorrelationAnalyzer


def test_pairwise_correlation_calculation() -> None:
    """Verify Pearson and Spearman calculations for known positive, negative, and zero correlations."""
    n = 100
    x = np.linspace(1.0, 100.0, n)
    y_pos = 2.0 * x + np.random.normal(0, 0.1, n)
    y_neg = -3.0 * x + np.random.normal(0, 0.1, n)
    y_rand = np.random.normal(0, 1.0, n)
    y_const = np.full(n, 5.0)

    df = pd.DataFrame(
        {
            "x": x,
            "y_pos": y_pos,
            "y_neg": y_neg,
            "y_rand": y_rand,
            "y_const": y_const,
        }
    )

    pairs = MetricCorrelationAnalyzer.compute_pairwise_correlations(
        df, ["x", "y_pos", "y_neg", "y_rand", "y_const"]
    )

    lookup = {(p.metric_a, p.metric_b): p for p in pairs}
    # Also index reverse
    for p in pairs:
        lookup[(p.metric_b, p.metric_a)] = p

    # 1. Strong positive correlation
    assert lookup[("x", "y_pos")].pearson_r > 0.99
    assert lookup[("x", "y_pos")].spearman_rho > 0.99
    assert lookup[("x", "y_pos")].p_value < 1e-5

    # 2. Strong negative correlation
    assert lookup[("x", "y_neg")].pearson_r < -0.99
    assert lookup[("x", "y_neg")].abs_correlation > 0.99

    # 3. Low/Random correlation
    assert lookup[("x", "y_rand")].abs_correlation < 0.35

    # 4. Zero variance constant signal (handled without error)
    assert lookup[("x", "y_const")].pearson_r == 0.0
    assert lookup[("x", "y_const")].p_value == 1.0


def test_lagged_cross_correlation_identifies_lead_signal() -> None:
    """Verify lagged cross-correlation correctly discovers known shift of +3 minutes."""
    n = 120
    t = np.arange(n)
    # Signal A is a smooth wave
    sig_a = np.sin(2 * np.pi * t / 30.0)

    # Signal B is Signal A shifted forward by 3 steps: B(t) = A(t - 3)
    sig_b = np.roll(sig_a, 3)

    series_a = pd.Series(sig_a)
    series_b = pd.Series(sig_b)

    lag_rel = LaggedCorrelationAnalyzer.analyze_lag(
        series_a, series_b, name_a="signal_a", name_b="signal_b", max_lag=10
    )

    assert lag_rel.lead_metric == "signal_a"
    assert lag_rel.lag_metric == "signal_b"
    assert lag_rel.optimal_lag_minutes == 3
    assert lag_rel.max_cross_correlation > 0.95
    assert "causation" in lag_rel.causation_disclaimer.lower()


def test_lagged_correlation_insufficient_data() -> None:
    """Verify lag analyzer handles series with too few observations gracefully."""
    s_a = pd.Series([1.0, 2.0, 3.0])
    s_b = pd.Series([1.0, 2.0, 3.0])

    lag_rel = LaggedCorrelationAnalyzer.analyze_lag(s_a, s_b, "a", "b", max_lag=10)
    assert lag_rel.optimal_lag_minutes == 0
    assert "Insufficient observations" in lag_rel.interpretation
