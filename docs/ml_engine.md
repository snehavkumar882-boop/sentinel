# SENTINEL Machine Learning Engine Documentation

## 1. Architectural Philosophy & Objectives
The Sentinel ML Engine provides **explainable, deterministic, and statistically sound** anomaly detection and relationship analysis. Rather than employing opaque, black-box deep learning architectures, Sentinel prioritizes algorithms whose parameters and outputs can be mathematically audited by Site Reliability Engineers (SREs).

### Core Principles
1. **Explainable AI First:** Every flagged anomaly includes an exact mathematical explanation (e.g. standard deviations from expected baseline, feature attribution weight).
2. **Strict Baseline Isolation:** Unsupervised models (Isolation Forest) are trained **only on normal baseline operations**, ensuring the model never learns to view an incident as "normal".
3. **Correlation vs. Causation Guardrails:** Cross-correlation and lead-lag analysis identify temporal relationships and lead indicators without fabricating causal claims.
4. **Negative Control Verification:** Diagnostic pipelines explicitly check negative controls (e.g. verifying CPU and Memory remain normal) to eliminate false diagnostic pathways.

---

## 2. Algorithms & Implementation Details

### 2.1 Statistical Anomaly Detector (`RollingZScoreDetector`)
- **Formula:**
  $$\mu_{t} = \frac{1}{W} \sum_{i=1}^{W} x_{t-i}, \quad \sigma_{t} = \sqrt{\frac{1}{W} \sum_{i=1}^{W} (x_{t-i} - \mu_t)^2}$$
  $$Z_t = \frac{x_t - \mu_t}{\sigma_t + \epsilon}$$
- **Anti-Leakage Design:** Uses a lagged backward window $[t-W, t-1]$ via `shift(1)`. The observation at time $t$ is strictly excluded from its own reference distribution.
- **Dynamic Severity Thresholds:**
  - $|Z| \ge 4.5\sigma \rightarrow \text{CRITICAL}$
  - $3.5\sigma \le |Z| < 4.5\sigma \rightarrow \text{HIGH}$
  - $3.0\sigma \le |Z| < 3.5\sigma \rightarrow \text{MEDIUM}$
  - $|Z| < 3.0\sigma \rightarrow \text{LOW}$

### 2.2 Multivariate Isolation Forest (`IsolationForestDetector`)
- **Algorithm:** Scikit-learn `IsolationForest(n_estimators=100, contamination=0.05, random_state=42)`.
- **Training Strategy:** Fitted exclusively on clean baseline telemetry ($t < 100\,\text{mins}$). The incident window ($t \ge 120\,\text{mins}$) is held out and evaluated only during inference.
- **Normalized Anomaly Scoring:**
  Scikit-learn's `decision_function` returns lower values for anomalies (negative values). Sentinel maps this into an intuitive severity score $S \in [0.0, 1.0]$:
  $$S = \text{clip}\left(\frac{0.20 - \text{raw\_score}}{0.50}, 0.0, 1.0\right)$$
  - Nominal scores: $0.0 - 0.35$
  - Elevated/Anomalous scores: $0.60 - 1.00$

### 2.3 Metric Correlation Analysis (`MetricCorrelationAnalyzer`)
- **Pairwise Metrics:** Pearson correlation coefficient ($r$) for linear relationships and Spearman rank correlation ($\rho$) for non-linear monotonic shifts.
- **Zero-Variance Resilience:** Handles metrics with zero standard deviation (e.g. constant pool caps) by gracefully returning $r = 0.0$ and $p = 1.0$ instead of propagating `NaN` errors.

### 2.4 Lead-Lag Cross-Correlation (`LaggedCorrelationAnalyzer`)
- **Objective:** Quantify temporal precedence between telemetry signals.
- **Cross-Correlation Window:** Lags evaluated across $\tau \in [-L, +L]$ (default $L = 10$ minutes):
  $$r(\tau) = \text{Corr}(X_t, Y_{t+\tau})$$
- **Lead Direction:** A positive optimal lag ($\tau^* > 0$) indicates that signal $X$ moved before signal $Y$.
- **Causation Guardrail:** All outputs explicitly state that empirical temporal precedence does *not* prove causation.

### 2.5 Feature Attribution & Explainability (`FeatureAttributionExplainer`)
- Measures normalized deviation weights across all dimensions for anomalous vectors:
  $$Z_i = \frac{x_i - \mu_{\text{baseline}, i}}{\sigma_{\text{baseline}, i} + \epsilon}, \quad w_i = \frac{|Z_i|}{\sum_{j=1}^D |Z_j|}$$
- Rank-orders the top drivers contributing to an anomaly, detailing the exact sigma deviation and direction ("above" or "below" baseline).

---

## 3. Training & Evaluation Methodology

1. **Partitioning:**
   - **Baseline Split:** Minutes 0 through 99 (100 samples) $\rightarrow$ Used for parameter estimation and Isolation Forest training.
   - **Pre-Incident Transition:** Minutes 100 through 119 $\rightarrow$ Post-deployment drift monitoring.
   - **Incident Ground Truth Window:** Minutes 120 through 154 (35 samples) $\rightarrow$ Used for recall evaluation.
   - **Recovery Window:** Minutes 155 through 239 $\rightarrow$ Used to verify return-to-normal detection.
2. **Metrics Tracked:**
   - **Detection Latency:** Time delay between incident onset ($t=120$) and first anomaly alert.
   - **Incident Recall:** Percentage of incident-period minutes correctly flagged.
   - **Baseline False Positive Rate (FPR):** Percentage of normal baseline minutes erroneously flagged.

---

## 4. Limitations & Interpretative Guidelines
1. **Correlation vs. Causation:** High correlation ($r > 0.90$) indicates strong statistical co-movement, not direct physical causation. Upstream configuration events (such as deployment events) must corroborate findings.
2. **Non-Stationarity:** System baselines drift over time due to organic traffic growth. In production, baselines should be retrained periodically on rolling weekly cycles.
3. **Sampling Resolution:** 1-minute telemetry resolution detects macro-level incidents within 1-2 minutes. Sub-second transient microbursts require sub-minute metric scraping.
