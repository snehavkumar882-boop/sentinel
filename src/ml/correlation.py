"""Metric correlation and lead-lag cross-correlation analysis."""

from typing import List, Tuple
import numpy as np
import pandas as pd
from scipy import stats

from src.ml.models import CorrelationPair, LaggedRelationship


class MetricCorrelationAnalyzer:
    """Computes pairwise linear (Pearson) and monotonic (Spearman) cross-correlations."""

    @staticmethod
    def compute_pairwise_correlations(
        df: pd.DataFrame,
        feature_cols: List[str],
    ) -> List[CorrelationPair]:
        """Compute pairwise correlations across all feature pairs.

        Handles constant/zero-variance signals gracefully without throwing NaN exceptions.
        """
        pairs: List[CorrelationPair] = []
        n = len(feature_cols)

        for i in range(n):
            for j in range(i + 1, n):
                col_a = feature_cols[i]
                col_b = feature_cols[j]

                series_a = df[col_a].dropna()
                series_b = df[col_b].dropna()

                # Align on common index
                common_idx = series_a.index.intersection(series_b.index)
                if len(common_idx) < 3:
                    continue

                vals_a = series_a.loc[common_idx].to_numpy(dtype=float)
                vals_b = series_b.loc[common_idx].to_numpy(dtype=float)

                std_a = float(np.std(vals_a))
                std_b = float(np.std(vals_b))

                # Handle zero variance / constant signals
                if std_a < 1e-7 or std_b < 1e-7:
                    pearson_r = 0.0
                    p_val = 1.0
                    spearman_rho = 0.0
                else:
                    p_res = stats.pearsonr(vals_a, vals_b)
                    pearson_r = float(p_res.statistic)
                    p_val = float(p_res.pvalue)

                    s_res = stats.spearmanr(vals_a, vals_b)
                    spearman_rho = float(s_res.statistic)

                pairs.append(
                    CorrelationPair(
                        metric_a=col_a,
                        metric_b=col_b,
                        pearson_r=round(pearson_r, 4),
                        spearman_rho=round(spearman_rho, 4),
                        abs_correlation=round(abs(pearson_r), 4),
                        p_value=round(p_val, 6),
                    )
                )

        # Sort by strongest absolute correlation descending
        pairs.sort(key=lambda p: p.abs_correlation, reverse=True)
        return pairs


class LaggedCorrelationAnalyzer:
    """Evaluates temporal lead-lag relationships using time-shifted cross-correlation.

    Identifies which telemetry signal historically leads or follows another signal.
    CRITICAL: Temporal precedence does NOT prove causation.
    """

    @staticmethod
    def analyze_lag(
        series_a: pd.Series,
        series_b: pd.Series,
        name_a: str,
        name_b: str,
        max_lag: int = 15,
    ) -> LaggedRelationship:
        """Calculate cross-correlation across lag window [-max_lag, +max_lag].

        A positive optimal lag (+τ) indicates that changes in series_a precede (lead)
        changes in series_b by τ time units.
        A negative optimal lag (-τ) indicates that series_b leads series_a.
        """
        # Ensure clean aligned series
        common_idx = series_a.dropna().index.intersection(series_b.dropna().index)
        s_a = series_a.loc[common_idx].to_numpy(dtype=float)
        s_b = series_b.loc[common_idx].to_numpy(dtype=float)

        best_lag = 0
        best_r = 0.0

        n = len(s_a)
        if n <= max_lag + 2:
            return LaggedRelationship(
                lead_metric=name_a,
                lag_metric=name_b,
                optimal_lag_minutes=0,
                max_cross_correlation=0.0,
                interpretation="Insufficient observations for reliable cross-correlation lag analysis.",
            )

        # Iterate over lag offsets
        for lag in range(-max_lag, max_lag + 1):
            if lag > 0:
                # series_a leads series_b: compare a[0 : n-lag] with b[lag : n]
                a_slice = s_a[: n - lag]
                b_slice = s_b[lag:]
            elif lag < 0:
                # series_b leads series_a: compare a[-lag : n] with b[0 : n+lag]
                pos_lag = abs(lag)
                a_slice = s_a[pos_lag:]
                b_slice = s_b[: n - pos_lag]
            else:
                a_slice = s_a
                b_slice = s_b

            std_a = float(np.std(a_slice))
            std_b = float(np.std(b_slice))
            if std_a < 1e-7 or std_b < 1e-7:
                curr_r = 0.0
            else:
                curr_r = float(np.corrcoef(a_slice, b_slice)[0, 1])

            if np.isnan(curr_r):
                curr_r = 0.0

            if abs(curr_r) > abs(best_r):
                best_r = curr_r
                best_lag = lag

        # Formulate interpretation
        if best_lag > 0:
            lead = name_a
            lagged = name_b
            interp = (
                f"Empirical shift analysis shows '{lead}' leads '{lagged}' by approximately "
                f"{best_lag} minute(s) with peak cross-correlation r={best_r:.3f}. "
                "Note: Temporal precedence does not confirm causation."
            )
        elif best_lag < 0:
            lead = name_b
            lagged = name_a
            interp = (
                f"Empirical shift analysis shows '{lead}' leads '{lagged}' by approximately "
                f"{abs(best_lag)} minute(s) with peak cross-correlation r={best_r:.3f}. "
                "Note: Temporal precedence does not confirm causation."
            )
        else:
            lead = name_a
            lagged = name_b
            interp = (
                f"Peak cross-correlation (r={best_r:.3f}) occurs concurrently at lag=0 minutes "
                f"between '{name_a}' and '{name_b}'."
            )

        return LaggedRelationship(
            lead_metric=lead,
            lag_metric=lagged,
            optimal_lag_minutes=abs(best_lag),
            max_cross_correlation=round(best_r, 4),
            interpretation=interp,
        )
