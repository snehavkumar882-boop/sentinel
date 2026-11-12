"""Unit tests for FeatureAttributionExplainer."""

import pandas as pd
from src.ml.explainer import FeatureAttributionExplainer


def test_feature_attribution_ranking() -> None:
    """Verify explainer identifies the primary driver of an anomaly."""
    baseline_stats = {
        "m_normal": {"mean": 10.0, "std": 2.0},
        "m_slight": {"mean": 100.0, "std": 10.0},
        "m_extreme": {"mean": 5.0, "std": 1.0},
    }

    explainer = FeatureAttributionExplainer(baseline_stats)

    # Observation where m_extreme is 50.0 (45 sigma above mean!)
    # m_normal is 11.0 (0.5 sigma)
    # m_slight is 120.0 (2.0 sigma)
    observation = pd.Series({"m_normal": 11.0, "m_slight": 120.0, "m_extreme": 50.0})

    contributions = explainer.explain_observation(observation)

    assert len(contributions) == 3
    # Top contributor must be m_extreme
    top = contributions[0]
    assert top.feature_name == "m_extreme"
    assert top.deviation_sigma == 45.0
    assert top.direction == "above"
    assert top.contribution_weight > 0.85

    # Check weights sum to 1.0
    total_weight = sum(c.contribution_weight for c in contributions)
    assert 0.99 <= total_weight <= 1.01


def test_window_aggregation() -> None:
    """Verify window aggregation identifies persistent anomalous features."""
    baseline_stats = {
        "latency": {"mean": 100.0, "std": 10.0},
        "cpu": {"mean": 30.0, "std": 5.0},
    }
    explainer = FeatureAttributionExplainer(baseline_stats)

    # 10 observations with high latency (3000ms = 290 sigma) and normal cpu (32% = 0.4 sigma)
    window_df = pd.DataFrame(
        {
            "latency": [3000.0] * 10,
            "cpu": [32.0] * 10,
        }
    )

    agg_contributions = explainer.aggregate_window_attributions(window_df)
    assert len(agg_contributions) == 2
    assert agg_contributions[0].feature_name == "latency"
    assert agg_contributions[0].contribution_weight > 0.95
