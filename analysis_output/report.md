# Taiwan Helpers' Needs Survey 2026 - JD-R analysis report (pipeline v3.0)

*Auto-generated. Numbers come from `tables/*.csv`; interpretation is deliberately limited to what the estimators can support. All associations are cross-sectional and from a self-selected, non-probability sample.*

## 1. Samples

- Responses: **318**; organisation-based **269** (of whom **32** hybrid: organisation + personal projects); self-employed **49**.
- JS (optional ProQOL block) observed for **203** organisation and **38** self-employed respondents.
- Support-gap branches: staff **241**, decision-makers (founders/board/HR) **28**.

## 2. Measurement and coding audit

Cronbach's alpha, organisation group (full table with omega and CIs: `reliability.csv`):

| construct | brief_literal | extended | primary |
|---|---|---|---|
| OS | 0.75 | 0.87 | 0.87 |
| RET | 0.03 | 0.73 | 0.73 |
| WL | 0.69 | 0.77 | 0.69 |

Items flagged by the automatic direction audit (`coding_audit.csv`):

| spec | construct | item | column_0based | item_rest_rho |
|---|---|---|---|---|
| brief_literal | OS | d_coworker | 12 | -0.44 |
| brief_literal | RET | consider_leaving | 27 | -0.38 |
| brief_literal | RET | expect_stay | 28 | -0.29 |

`primary` repairs only these direction errors (cols 12, 29, 30, 31). Item membership stays as in the brief. `extended` also moves col 11 into WL and drops col 7; it is a sensitivity analysis.

## 3. Simplified JD-R equations - organisation group (primary specification)

Standardised betas, HC3-robust 95% CI. 'CC' = complete case; 'MI' = multiple imputation pooled by Rubin's rules. q = BH-FDR over the **14 primary slopes** (6 + 6 + 2); controls are outside the family.

### Eq.1 Burnout  (n = 263, R2 = 0.495, adj. R2 = 0.465, max VIF = 2.84, BP p = 0.156, RESET p = 0.611, mission-block p = 0.155)

| Predictor | Std beta (CC) | 95% CI | p | q | Std beta (MI) | p (MI) | q (MI) | Robustness value % | VIF | Family |
|---|---|---|---|---|---|---|---|---|---|---|
| Workload | 0.326 | [0.21, 0.44] | 1.3e-07 | 8.8e-07 | 0.343 | 2.8e-08 | 2.0e-07 | 29.150 | 1.678 | primary |
| Organisational support | -0.281 | [-0.44, -0.12] | 8.2e-04 | 0.002 | -0.274 | 0.001 | 0.003 | 19.358 | 2.787 | primary |
| Job resources | 0.064 | [-0.09, 0.22] | 0.419 | 0.554 | 0.055 | 0.481 | 0.613 | 5.019 | 2.836 | primary |
| Pay (high = less strain) | -0.061 | [-0.18, 0.06] | 0.311 | 0.526 | -0.049 | 0.404 | 0.566 | 6.252 | 1.594 | primary |
| Mission alignment | -0.028 | [-0.17, 0.11] | 0.689 | 0.754 | -0.025 | 0.720 | 0.840 | 2.521 | 1.706 | primary |
| Inner drive (UWES-3 engagement) | -0.279 | [-0.40, -0.16] | 4.6e-06 | 2.2e-05 | -0.259 | 2.7e-05 | 9.3e-05 | 25.692 | 1.514 | primary |
| Organisation size (0-5) | -0.017 | [-0.12, 0.09] | 0.750 |  | -0.014 | 0.793 |  | 2.009 | 1.193 | control |
| Children & youth | -0.194 | [-0.40, 0.01] | 0.064 |  | -0.184 | 0.077 |  | 11.176 | 1.304 | control |
| Disability | 0.040 | [-0.20, 0.28] | 0.738 |  | 0.051 | 0.667 |  | 2.107 | 1.391 | control |
| Elder & long-term care | -0.142 | [-0.37, 0.09] | 0.228 |  | -0.157 | 0.174 |  | 7.405 | 1.271 | control |
| Education | -0.170 | [-0.43, 0.09] | 0.200 |  | -0.133 | 0.315 |  | 7.849 | 1.171 | control |
| Low-income families | 0.019 | [-0.22, 0.26] | 0.874 |  | 0.023 | 0.847 |  | 1.001 | 1.149 | control |
| Mental health | -0.307 | [-0.58, -0.04] | 0.025 |  | -0.260 | 0.069 |  | 13.321 | 1.142 | control |
| Social innovation / advocacy | -0.202 | [-0.44, 0.03] | 0.090 |  | -0.201 | 0.090 |  | 10.263 | 1.131 | control |
| Women & gender | 0.100 | [-0.20, 0.40] | 0.505 |  | 0.125 | 0.396 |  | 4.159 | 1.188 | control |

### Eq.2 Job satisfaction  (n = 199, R2 = 0.506, adj. R2 = 0.465, max VIF = 2.64, BP p = 0.024, RESET p = 0.562, mission-block p = 0.529)

| Predictor | Std beta (CC) | 95% CI | p | q | Std beta (MI) | p (MI) | q (MI) | Robustness value % | VIF | Family |
|---|---|---|---|---|---|---|---|---|---|---|
| Workload | 0.012 | [-0.14, 0.16] | 0.874 | 0.874 | 0.006 | 0.929 | 0.944 | 1.166 | 1.618 | primary |
| Organisational support | -0.195 | [-0.38, -0.01] | 0.035 | 0.077 | -0.203 | 0.020 | 0.047 | 14.514 | 2.628 | primary |
| Job resources | 0.188 | [0.01, 0.37] | 0.038 | 0.077 | 0.200 | 0.026 | 0.053 | 14.272 | 2.638 | primary |
| Pay (high = less strain) | 0.028 | [-0.12, 0.17] | 0.700 | 0.754 | 0.004 | 0.944 | 0.944 | 2.810 | 1.573 | primary |
| Mission alignment | 0.076 | [-0.08, 0.23] | 0.338 | 0.526 | 0.081 | 0.260 | 0.454 | 6.852 | 1.687 | primary |
| Inner drive (UWES-3 engagement) | 0.597 | [0.45, 0.74] | 4.0e-14 | 5.6e-13 | 0.591 | 6.6e-15 | 9.2e-14 | 44.990 | 1.527 | primary |
| Organisation size (0-5) | -0.056 | [-0.18, 0.06] | 0.362 |  | -0.041 | 0.467 |  | 6.526 | 1.186 | control |
| Children & youth | 0.234 | [-0.00, 0.47] | 0.053 |  | 0.203 | 0.077 |  | 13.390 | 1.336 | control |
| Disability | 0.158 | [-0.13, 0.44] | 0.274 |  | 0.156 | 0.245 |  | 7.792 | 1.425 | control |
| Elder & long-term care | 0.198 | [-0.10, 0.49] | 0.189 |  | 0.158 | 0.236 |  | 9.274 | 1.282 | control |
| Education | 0.076 | [-0.29, 0.44] | 0.679 |  | 0.065 | 0.684 |  | 3.022 | 1.193 | control |
| Low-income families | -0.177 | [-0.48, 0.13] | 0.258 |  | -0.139 | 0.334 |  | 8.046 | 1.132 | control |
| Mental health | 0.057 | [-0.26, 0.38] | 0.723 |  | 0.043 | 0.786 |  | 2.587 | 1.191 | control |
| Social innovation / advocacy | 0.086 | [-0.29, 0.46] | 0.652 |  | 0.078 | 0.614 |  | 3.287 | 1.125 | control |
| Women & gender | -0.092 | [-0.36, 0.17] | 0.495 |  | -0.089 | 0.529 |  | 4.929 | 1.261 | control |

### Eq.3 Retention  (n = 203, R2 = 0.143, adj. R2 = 0.094, max VIF = 1.38, BP p = 0.409, RESET p = 0.482, mission-block p = 0.812)

| Predictor | Std beta (CC) | 95% CI | p | q | Std beta (MI) | p (MI) | q (MI) | Robustness value % | VIF | Family |
|---|---|---|---|---|---|---|---|---|---|---|
| Job satisfaction (ProQOL CS) | 0.061 | [-0.09, 0.21] | 0.436 | 0.554 | 0.068 | 0.323 | 0.502 | 5.495 | 1.225 | primary |
| Burnout (CBI) | -0.287 | [-0.44, -0.14] | 2.3e-04 | 8.0e-04 | -0.297 | 8.2e-06 | 3.8e-05 | 23.745 | 1.132 | primary |
| Organisation size (0-5) | -0.074 | [-0.22, 0.07] | 0.320 |  | -0.112 | 0.082 |  | 6.964 | 1.163 | control |
| Children & youth | -0.021 | [-0.35, 0.31] | 0.899 |  | 0.069 | 0.627 |  | 0.918 | 1.335 | control |
| Disability | -0.158 | [-0.52, 0.21] | 0.394 |  | -0.100 | 0.535 |  | 5.995 | 1.380 | control |
| Elder & long-term care | 0.033 | [-0.34, 0.41] | 0.863 |  | 0.023 | 0.891 |  | 1.242 | 1.298 | control |
| Education | -0.027 | [-0.46, 0.41] | 0.902 |  | -0.037 | 0.819 |  | 0.890 | 1.200 | control |
| Low-income families | -0.168 | [-0.57, 0.24] | 0.413 |  | -0.112 | 0.530 |  | 5.763 | 1.132 | control |
| Mental health | -0.214 | [-0.63, 0.20] | 0.307 |  | -0.185 | 0.319 |  | 7.146 | 1.171 | control |
| Social innovation / advocacy | 0.097 | [-0.35, 0.55] | 0.672 |  | 0.010 | 0.951 |  | 3.024 | 1.099 | control |
| Women & gender | -0.306 | [-0.73, 0.12] | 0.159 |  | -0.211 | 0.256 |  | 9.713 | 1.214 | control |

**Eq.3b** (Eq.3 + all six predictors; n = 199, R2 = 0.336) is a *sensitivity* check on direct effects only. Adding correlated predictors beside BO and JS can change signs (suppression); individual Eq.3b coefficients must not be read causally. On the same 199 rows, Eq.3 R2 = 0.135 and Eq.3b R2 = 0.336 (increment = 0.202).

### 3b. Sensitivity of the equations (complete-case, primary specification)

Engagement (ID) and compassion satisfaction (JS) are both affective scales from the same questionnaire, so ID may absorb variance and flip signs (organisational support correlates POSITIVELY with JS on its own but negatively once ID and JR are controlled). The table shows each path with and without ID, and with burnout split into its work-related and personal sub-scales.

| Path (std beta) | Reference | Reference result | Variant | Variant result |
|---|---|---|---|---|
| Burnout <- WL | primary | 0.33 (p=0.000) | without ID | 0.30 (p=0.000) |
| Burnout <- OS | primary | -0.28 (p=0.001) | without ID | -0.30 (p=0.001) |
| Burnout <- JR | primary | 0.06 (p=0.419) | without ID | -0.04 (p=0.624) |
| Job satisfaction <- WL | primary | 0.01 (p=0.874) | without ID | 0.09 (p=0.350) |
| Job satisfaction <- OS | primary | -0.19 (p=0.035) | without ID | -0.17 (p=0.104) |
| Job satisfaction <- JR | primary | 0.19 (p=0.038) | without ID | 0.43 (p=0.000) |
| Burnout <- WL | all 13 items | 0.33 (p=0.000) | work-related only / personal only | 0.29 (p=0.000) / 0.34 (p=0.000) |
| Burnout <- OS | all 13 items | -0.28 (p=0.001) | work-related only / personal only | -0.29 (p=0.000) / -0.26 (p=0.004) |
| Burnout <- ID | all 13 items | -0.28 (p=0.000) | work-related only / personal only | -0.32 (p=0.000) / -0.22 (p=0.001) |
| Retention <- burnout | all 13 items | -0.29 (p=0.000) | work-related / personal | -0.31 (p=0.000) / -0.24 (p=0.002) |

**Robustness value (RV)** in the tables above: the share of residual variance an unmeasured confounder would have to explain in BOTH the predictor and the outcome to reduce that coefficient to zero (Cinelli & Hazlett 2020). Higher = harder to explain away; values near 0 are fragile.

**Exploratory demand x resource buffering** (workload x support, workload x resources; FDR over 4 tests):

| Outcome | Interaction | Std beta | p | q | n |
|---|---|---|---|---|---|
| BO | Workload x Organisational support | 0.026 | 0.534 | 0.810 | 263 |
| BO | Workload x Job resources | -0.015 | 0.746 | 0.810 | 263 |
| JS | Workload x Organisational support | 0.024 | 0.721 | 0.810 | 199 |
| JS | Workload x Job resources | -0.017 | 0.810 | 0.810 | 199 |

## 4. Missing job-satisfaction block

- Logistic model of 'JS skipped': AUC = **0.87**, McFadden R2 = 0.33, LR p = 1.0e-11, events = 63.
- Strongest predictors (odds ratio per SD): frontline OR=0.19; manager OR=0.47; Workload OR=0.55.
- Skipping is therefore **not MCAR** and is mainly explained by observed role (client-facing staff answered far more often; the block asks about traumatised clients, which may not apply to admin/management roles), so JS is partly 'not applicable' rather than withheld. Predictability supports MAR-given-covariates for the imputation, but MAR vs MNAR is untestable; the tipping-point table (`tipping_point.csv`, Figure 06) shifts imputed JS by -15 ... +15 points. Complete-case and MI answer different estimands (respondents who answered vs all organisation staff).
- JS -> Retention pooled beta across the delta grid: min 0.051, max 0.075; p ranges 0.27-0.46.

## 5. Associational mediation  X -> {BO, JS} -> RET

| Predictor | Total indirect (CC, BCa) | Total indirect (MI) |
|---|---|---|
| WL | -0.071 [-0.181, 0.012] | -0.068 [-0.151, 0.015] |
| OS | 0.071 [0.002, 0.179] | 0.071 [-0.011, 0.152] |
| JR | -0.035 [-0.126, 0.021] | -0.035 [-0.100, 0.030] |
| PAY | 0.012 [-0.010, 0.053] | 0.005 [-0.015, 0.025] |
| MA | -0.005 [-0.037, 0.028] | -0.004 [-0.031, 0.024] |
| ID | -0.012 [-0.180, 0.191] | -0.027 [-0.181, 0.127] |

CI methods: complete-case = BCa bootstrap; imputed = Rubin's rules with bootstrap within-imputation variance. The complete-case mediation sample (n = 199: JS observed and every predictor present) is smaller than Eq.3's (n = 203), so b_BO / b_JS can differ slightly from the Eq.3 coefficients.

Unstandardised: points of RET (0-100) per point of X. Specific indirect effects via BO and via JS, direct and total effects: `mediation_*.csv`. Interpret as structural associations; see assumption A15.

## 6. Organisation vs self-employed

| Outcome | n org | Mean org | n self | Mean self | Diff (self-org) | Rank-biserial | p | q |
|---|---|---|---|---|---|---|---|---|
| Burnout (CBI) | 269 | 53.317 | 49 | 42.033 | -11.284 | -0.296 | 9.8e-04 | 0.002 |
| Work-related burnout | 269 | 51.301 | 49 | 40.306 | -10.995 | -0.271 | 0.002 | 0.003 |
| Personal burnout | 269 | 55.669 | 49 | 44.048 | -11.622 | -0.302 | 7.5e-04 | 0.002 |
| Inner drive (UWES-3 engagement) | 269 | 56.857 | 49 | 77.551 | 20.694 | 0.594 | 2.9e-11 | 2.0e-10 |
| Job satisfaction (ProQOL CS) | 203 | 64.286 | 38 | 77.412 | 13.127 | 0.373 | 2.4e-04 | 8.3e-04 |
| ProQOL burnout | 203 | 44.581 | 38 | 37.719 | -6.862 | -0.188 | 0.064 | 0.075 |
| ProQOL secondary traumatic stress | 203 | 33.867 | 38 | 33.991 | 0.124 | 0.029 | 0.773 | 0.773 |

Exploratory family of 7 contrasts. Sensitivity excluding hybrid respondents: `group_comparison_excl_hybrid.csv`.

Part of the JD-R model measurable in **both** groups (ID -> BO, ID -> JS; controls: age band, years in helping work). Interaction rows test whether the slope differs between groups (raw units):

| Group | Model | Term | b (0-100 units) | Std beta | p | n |
|---|---|---|---|---|---|---|
| Organisation | R1_BO~ID | ID | -0.484 | -0.448 | 3.3e-13 | 267 |
| Organisation | R2_JS~ID | ID | 0.705 | 0.666 | 1.4e-21 | 202 |
| Self-employed | R1_BO~ID | ID | -0.315 | -0.279 | 0.077 | 49 |
| Self-employed | R2_JS~ID | ID | 0.807 | 0.743 | 2.0e-06 | 38 |
| pooled (interaction) | R1_BO~ID | ID_x_self | 0.144 | 0.199 | 0.436 | 316 |
| pooled (interaction) | R2_JS~ID | ID_x_self | 0.080 | 0.116 | 0.595 | 240 |

The structural equations Eq.1-3 are **not estimable** for the self-employed (WL, OS, JR, PAY, MA, RET, SIZE, MISSION were not asked; assumption A23). Their own top challenges are in `selfemployed_challenges.csv` / Figure 12.

## 7. Support gap: provided vs wanted vs decision-makers

| Support | Staff: provided % | Decision-makers: provided % | Staff: wanted % | Decision-makers: wanted % | Staff unmet % (want, org lacks) | % of wanters lacking it |
|---|---|---|---|---|---|---|
| Career development | 15.4 | 25.0 | 41.1 | 39.3 | 35.7 | 86.9 |
| Acting-position allowance | 5.4 |  | 35.3 | 17.9 | 34.9 | 98.8 |
| Professional skills training | 49.0 | 39.3 | 29.0 | 28.6 | 21.6 | 74.3 |
| Leadership & management training | 14.9 | 32.1 | 22.4 | 35.7 | 20.3 | 90.7 |
| Individual counselling | 49.0 | 42.9 | 32.4 | 32.1 | 17.4 | 53.8 |
| Group stress relief | 34.0 | 42.9 | 21.2 | 25.0 | 16.2 | 76.5 |
| Internal communication | 37.8 | 60.7 | 21.2 | 17.9 | 15.4 | 72.5 |
| Supervision / coaching | 55.6 | 28.6 | 21.2 | 32.1 | 14.1 | 66.7 |
| Flexible / remote work | 36.9 | 64.3 |  |  |  |  |
| Personal / family financial planning |  |  | 25.7 | 21.4 |  |  |

Sample sizes: staff n = 241, decision-makers n = 28 (independent groups; no matched organisations). Newcombe CIs and Fisher tests: `support_gap.csv`. Caveats: A18-A21.

Exploratory association between the number of supports staff say exist and their JD-R scores:

| Outcome | Spearman rho | n | q |
|---|---|---|---|
| Organisational support | 0.375 | 240 | 4.8e-09 |
| Job resources | 0.415 | 241 | 8.9e-11 |
| Workload | -0.144 | 240 | 0.026 |
| Burnout (CBI) | -0.177 | 241 | 0.007 |
| Retention | 0.194 | 241 | 0.004 |

**Resource levels by seniority** (organisation group; Kruskal-Wallis, exploratory; `role_profile.csv`):

| construct | Frontline helper mean (n) | Admin / project / finance mean (n) | Mid-level manager mean (n) | Founder / decision-maker mean (n) | q_fdr |
|---|---|---|---|---|---|
| Workload | 47.4 (159) | 38.7 (45) | 41.9 (34) | 43.8 (21) | 0.043 |
| Organisational support | 61.0 (159) | 65.1 (45) | 65.4 (34) | 77.1 (22) | 0.013 |
| Job resources | 56.8 (160) | 60.4 (45) | 67.2 (34) | 81.1 (22) | 0 |
| Pay (high = less strain) | 51.1 (158) | 62.8 (45) | 75.0 (34) | 65.9 (22) | 0 |
| Mission alignment | 64.2 (157) | 76.7 (45) | 75.7 (34) | 92.0 (22) | 0 |
| Inner drive (UWES-3 engagement) | 52.8 (160) | 53.8 (45) | 63.7 (34) | 77.3 (23) | 0 |
| Burnout (CBI) | 57.8 (160) | 50.0 (45) | 48.3 (34) | 37.8 (23) | 0 |
| Job satisfaction (ProQOL CS) | 61.6 (146) | 63.7 (14) | 72.7 (25) | 77.8 (15) | 0.006 |
| Retention | 60.8 (160) | 56.4 (45) | 72.6 (34) | 90.0 (23) | 0 |

## 8. Validation against the IQP report

The IQP report does not say whether its stars used classical or robust SEs; betas, n and R2 do not depend on that, but star agreement near p = .05 can.

| pipeline | n_terms | mean_abs_diff | max_abs_diff | sign_agreement | significance_agreement | corr_beta |
|---|---|---|---|---|---|---|
| brief_literal CC | 17 | 0.072 | 0.498 | 0.824 | 0.824 | 0.748 |
| extended CC | 17 | 0.03 | 0.506 | 0.941 | 1 | 0.851 |
| primary CC | 17 | 0.041 | 0.534 | 0.941 | 1 | 0.834 |
| primary MI | 17 | 0.047 | 0.527 | 0.941 | 1 | 0.839 |

Under the `extended` item set the pipeline reproduces **16 of 17** printed standardised betas to three decimals, plus every n and R2. The exception(s): Eq1_BO OS (report +0.253, recomputed -0.253). The magnitude agrees and only the sign differs, i.e. the printed sign looks like a transcription error; the recomputed sign (more organisational support -> less burnout) is the theoretically coherent one.

## 9. Robustness across specification, sample and estimator

County clustering: 20 counties but only 4.5 effective clusters (largest county = 40% of respondents), so county-clustered SEs are indicative only.

| Eq | Term | Primary beta | Same sign (share) | p<.05 (share) | Min beta | Max beta | Beta, brief-literal |
|---|---|---|---|---|---|---|---|
| Eq1_BO | WL | 0.326 | 1.000 | 1.000 | 0.315 | 0.406 | 0.362 |
| Eq1_BO | OS | -0.281 | 1.000 | 1.000 | -0.295 | -0.253 | -0.245 |
| Eq1_BO | JR | 0.064 | 1.000 | 0.000 | 0.003 | 0.070 | 0.060 |
| Eq1_BO | PAY | -0.061 | 1.000 | 0.000 | -0.090 | -0.001 | -0.061 |
| Eq1_BO | MA | -0.028 | 1.000 | 0.000 | -0.042 | -0.010 | -0.053 |
| Eq1_BO | ID | -0.279 | 1.000 | 1.000 | -0.293 | -0.222 | -0.271 |
| Eq2_JS | WL | 0.012 | 0.700 | 0.000 | -0.022 | 0.105 | 0.040 |
| Eq2_JS | OS | -0.195 | 1.000 | 0.900 | -0.245 | -0.184 | -0.140 |
| Eq2_JS | JR | 0.188 | 1.000 | 0.400 | 0.176 | 0.200 | 0.164 |
| Eq2_JS | PAY | 0.028 | 1.000 | 0.000 | 0.004 | 0.075 | 0.032 |
| Eq2_JS | MA | 0.076 | 1.000 | 0.000 | 0.058 | 0.142 | 0.051 |
| Eq2_JS | ID | 0.597 | 1.000 | 1.000 | 0.590 | 0.600 | 0.601 |
| Eq3_RET | JS | 0.061 | 1.000 | 0.000 | 0.004 | 0.068 | 0.100 |
| Eq3_RET | BO | -0.287 | 1.000 | 1.000 | -0.307 | -0.286 | 0.032 |

Variants: 2 non-literal specifications + strict (all-items-required) scoring, x 2 samples x complete-case, plus MI and county-clustered SE for the primary specification (`robustness_all_estimates.csv`). `brief_literal` is shown separately because its retention scale is internally inconsistent (alpha ~ 0).

## 10. Assumptions register

| ID | Assumption | Used in | How it is handled / checked |
|---|---|---|---|
| A1 | Questionnaire layout is stable | all | Every positional column is verified against header text; a mismatch aborts the run (LayoutError). |
| A2 | Direction of every item is correct after reverse-coding | scoring | coding_audit.csv flags negative item-rest correlations. This found cols 12 and 29-31 mis-directed in the brief; 'primary' repairs ONLY these. |
| A3 | 'Not applicable', 'no agreement on hours' and 'irregular hours' are missing, not low/mid values | scoring | Declared in NOT_APPLICABLE; not recoded to a number. Affects cols 7, 8 and the N/A answers on demand/resource items. |
| A4 | Ordinal items are equal-interval after POMP rescaling to 0-100 and averaged | all composites | Not testable from these data. Exploratory associations use Spearman; ordinal CFA (WLSMV) is the recommended confirmation (outside this script). |
| A5 | Items in a composite are essentially unidimensional / tau-equivalent | reliability | Alpha AND omega-total reported on PEARSON correlations of 3-7-point ordinal (and binary) items, which biases loadings and omega DOWNWARD relative to polychoric/tetrachoric estimates. The 13-item burnout composite mixes personal and work-related burnout; Eq.1w/1p/3w/3p re-fit the equations with each sub-scale. |
| A6 | Item non-response inside a composite is MAR given the other items | row_mean | Composite defined if >= 50% of items answered (100% for PAY, MA, ID, JS). Missingness inside composites is tiny (<= 3 respondents per item). |
| A7 | Single-item PAY and MA carry no measurement error | Eq.1-3 | UNTESTABLE with one item; slopes for PAY and MA are probably attenuated toward zero. Treat their null results as inconclusive. |
| A8 | Linear, additive conditional means; no interactions | OLS | Ramsey RESET reported per model. Demand x resource buffering is NOT tested because the brief's equations contain no interaction terms. |
| A9 | Observations are independent | OLS, bootstrap | VIOLATION POSSIBLE: no organisation identifier exists, so clustering by employer cannot be modelled. County-clustered SEs are a weak sensitivity (cluster_summary.csv: ~20 counties but only ~4.5 EFFECTIVE clusters, Taipei/New Taipei dominate; CR1 is anti-conservative). HC3 does NOT correct clustering. |
| A10 | Heteroskedasticity is allowed; mean model is correctly specified | HC3 | Koenker-BP reported; HC3 used (preferred for n < 250). Cook's D counts reported; no observation was deleted. |
| A11 | Collinearity is not severe | OLS | VIF and condition number reported per model (rule of thumb: VIF > 5 would be flagged). |
| A12 | Mission = 8 overlapping multi-select dummies (each vs 'not selected'); SIZE is linear on its 0-5 order | controls | Joint Wald test of the dummy block per equation; the dummies are NOT mutually exclusive categories. Free-text 'other' mission answers are ignored. |
| A13 | Skipping the optional ProQOL block is MAR given observed covariates (incl. role) | multiple imputation | UNTESTABLE (MAR vs MNAR). missingness model shows skipping is strongly predictable (role); tipping-point analysis shows how large an MNAR shift in JS would be needed to change conclusions. Complete-case answers a different estimand (respondents who answered). |
| A14 | The imputation model is adequate | MI | Bayesian-ridge chained equations on composites, m imputations, posterior sampling, bounds enforced, auxiliary variables (incl. org-type, role) included; binary auxiliaries are rounded to 0/1. No predictive-mean matching. Composites, not items, are imputed: because the whole ProQOL block is skipped together, the other ProQOL items carry no extra information for JS, so item-level MI would add little here. MI pools RAW coefficients; standardised betas are derived from pooled raw estimates and averaged SDs. |
| A15 | Mediation: temporal order X -> M -> Y, and no unmeasured X-M, M-Y, X-Y confounding | mediation | CROSS-SECTIONAL: order is assumed, never observed. Results are structural ASSOCIATIONS. Confounding sensitivity: Cinelli-Hazlett robustness values (column RV) for each regression slope; no formal mediation-specific sensitivity (e.g. medsens) is computed. |
| A16 | Rows are exchangeable under the bootstrap | BCa / percentile CI | Same independence caveat as A9. |
| A17 | BH-FDR is valid under independence / positive dependence | multiplicity | Primary family = 14 structural slopes. Everything else is exploratory with its own FDR family and must be reported as such. |
| A18 | Self-reported perceptions of what exists ('as far as you know') approximate what exists | support gap | Staff may be unaware of existing supports. Decision-maker answers are the better record of supply but n = 28. |
| A19 | 'Wanted' = chosen among <= 3 picks; not choosing an item does not mean not wanting it | support gap | 'Wanted' is a LOWER BOUND on need; 'provided but not selected' is not evidence of surplus. |
| A20 | Supply and demand option lists correspond item-for-item | support gap | Not exactly: career (system vs discussion) is approximate; flexible work has no demand option; financial planning has no supply option; allowance is not asked of decision-makers. Gaps are computed only where both sides were asked. |
| A21 | Staff and decision-maker samples can be compared as independent groups | support gap | They are different people in different (unidentified) organisations; no matched-pair analysis is possible. |
| A22 | Hybrid respondents (org + personal projects, n = 32) answered the organisational items about their organisational work | grouping | Pooled with organisation respondents; every model is re-run excluding them (sample = org_excl_hybrid). |
| A23 | Self-employed respondents answered only ID, BO, JS (+ProQOL); WL, OS, JR, PAY, MA, RET, SIZE, MISSION do not exist for them | group split | The three JD-R structural equations are therefore NOT identified for the self-employed; only the reduced model (ID, BO, JS) can be compared. |
| A24 | The sample is non-probability, self-selected (~5% response per the IQP report) and all measures are self-reported | inference | No population inference, no weights. Common-method variance probably inflates correlations. Descriptive levels are NOT prevalence estimates. |

## 11. What this analysis cannot establish

- Causal or temporal claims (cross-sectional design; A15).
- Population prevalence or representativeness (A24).
- Clustering within employers (A9) and formal measurement invariance across groups (ordinal CFA needed; only loading congruence is provided: `loading_congruence.csv`).
- Effects of single-item predictors PAY and MA (A7).
