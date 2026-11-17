# 2026 Taiwan Helpers' Needs Survey -- automated analysis summary

- Responses analysed: **318** (269 organisation-affiliated incl. hybrid, 49 freelancers/independents). **Equations 1-3 use organisation respondents only** (freelancers were not asked the workload / support / resource / retention items).
- Sample is self-selected (not probability-based): percentages describe respondents, not all Taiwanese helpers.

## Column map and what the revision changed

Column numbers are **0-based** (pandas `iloc`). The script verified every number in the brief against the question text (all match: True).

| construct | brief_items(0-based cols) | revised_items(0-based cols) | why |
|---|---|---|---|
| WL | 9, 10, 14, 7, 8 | 9, 10, 11, 14, 8 | Added col 11 (skills exceed training; r=.44-.59 with the other workload items, unassigned in the brief). Dropped col 7 (agreed hours): a contract term rather than load, item-rest r~.1, and 'no agreement' (n=32) is missing. |
| OS | 12, 13r, 20, 21, 22, 23, 24 | 12r, 13r, 20, 21, 22, 23, 24 | Col 12 (difficulty with colleagues) must be reversed like col 13: both are 'difficulty' items on a distress scale, and col 12 correlates NEGATIVELY (-.29 to -.41) with the other support items. |
| RET | 27r, 28, 29, 30, 31 | 27r, 28, 29r, 30r, 31r | Cols 29-31 (searched / updated CV / applied) are coded 1 = yes = leaving, so they must be reversed like col 27. As briefed, alpha = 0.03 (no internal consistency); reversed, alpha = 0.73. |
| ID | 32, 33, 34 | 32, 33, 34 | Cols 32-34 are the UWES-3 work-engagement items (energy, passion, absorption), not 'personal values'. Renamed Inner Drive (ID); the notation key's 'PV = Personal Values' should be renamed. |
| MA | 17r | 17r | Col 17 literally asks about personal-values vs organisation-direction mismatch, so it is the best Mission/Value-alignment item. Single item. |
| PAY | 16r | 16r | Single item (col 16, reversed so high = less pay strain). No reliability can be computed. |
| JR | 15r, 18, 19, 25, 26 | 15r, 18, 19, 25, 26 | Unchanged. Note JR and OS correlate strongly (see construct heatmap) -> watch VIF. |
| JS | 51, 53, 57 | 51, 53, 57 | Cols 51/53/57 are ProQOL compassion-satisfaction items (enjoy helping / work satisfies me / glad I chose this job). The block was optional, so n drops to ~203. |
| BO | 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47r | 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47r | Unchanged: 13 CBI items, col 47 reversed (correct). |

### Reliability (Cronbach's alpha): as briefed vs revised

| construct | version | n_items | cronbach_alpha | n_complete |
|---|---|---|---|---|
| WL | brief | 5 | 0.686 | 202 |
| WL | revised | 5 | 0.77 | 222 |
| OS | brief | 7 | 0.755 | 257 |
| OS | revised | 7 | 0.873 | 257 |
| JR | brief | 5 | 0.771 | 256 |
| JR | revised | 5 | 0.771 | 256 |
| PAY | brief | 1 |  | 266 |
| PAY | revised | 1 |  | 266 |
| MA | brief | 1 |  | 265 |
| MA | revised | 1 |  | 265 |
| ID | brief | 3 | 0.934 | 318 |
| ID | revised | 3 | 0.934 | 318 |
| BO | brief | 13 | 0.946 | 318 |
| BO | revised | 13 | 0.946 | 318 |
| JS | brief | 3 | 0.819 | 241 |
| JS | revised | 3 | 0.819 | 241 |
| RET | brief | 5 | 0.028 | 269 |
| RET | revised | 5 | 0.731 | 269 |

## Correlations among the equation constructs (org respondents; Spearman, BH-FDR)

42 of 45 construct pairs are significant at q<.05.

| Variable 1 | Variable 2 | rho | q | n |
|---|---|---|---|---|
| Organizational support (0-100) | Job resources (0-100) | 0.76 | <0.001 | 267 |
| Inner drive / engagement (0-100) | Job satisfaction (0-100) | 0.68 | <0.001 | 203 |
| Organizational support (0-100) | Mission alignment (0-100) | 0.61 | <0.001 | 265 |
| Job resources (0-100) | Mission alignment (0-100) | 0.58 | <0.001 | 265 |
| Workload (0-100) | Burnout (0-100) | 0.56 | <0.001 | 267 |
| Organizational support (0-100) | Burnout (0-100) | -0.53 | <0.001 | 267 |
| Workload (0-100) | Organizational support (0-100) | -0.53 | <0.001 | 267 |
| Workload (0-100) | Pay (0-100, high = less strain) | -0.53 | <0.001 | 266 |
| Job resources (0-100) | Retention (0-100) | 0.53 | <0.001 | 268 |
| Job resources (0-100) | Inner drive / engagement (0-100) | 0.52 | <0.001 | 268 |
| Organizational support (0-100) | Retention (0-100) | 0.47 | <0.001 | 267 |
| Job resources (0-100) | Burnout (0-100) | -0.45 | <0.001 | 268 |
| Job resources (0-100) | Job satisfaction (0-100) | 0.45 | <0.001 | 202 |
| Organizational support (0-100) | Inner drive / engagement (0-100) | 0.43 | <0.001 | 267 |
| Inner drive / engagement (0-100) | Burnout (0-100) | -0.43 | <0.001 | 269 |
| Mission alignment (0-100) | Retention (0-100) | 0.43 | <0.001 | 265 |
| Mission alignment (0-100) | Burnout (0-100) | -0.42 | <0.001 | 265 |
| Job resources (0-100) | Pay (0-100, high = less strain) | 0.42 | <0.001 | 266 |
| Mission alignment (0-100) | Inner drive / engagement (0-100) | 0.41 | <0.001 | 265 |
| Workload (0-100) | Mission alignment (0-100) | -0.40 | <0.001 | 265 |
| Organizational support (0-100) | Pay (0-100, high = less strain) | 0.39 | <0.001 | 266 |
| Workload (0-100) | Job resources (0-100) | -0.39 | <0.001 | 267 |
| Pay (0-100, high = less strain) | Burnout (0-100) | -0.37 | <0.001 | 266 |
| Pay (0-100, high = less strain) | Retention (0-100) | 0.34 | <0.001 | 266 |
| Pay (0-100, high = less strain) | Mission alignment (0-100) | 0.34 | <0.001 | 264 |
| Inner drive / engagement (0-100) | Retention (0-100) | 0.33 | <0.001 | 269 |
| Burnout (0-100) | Retention (0-100) | -0.33 | <0.001 | 269 |
| Burnout (0-100) | Job satisfaction (0-100) | -0.32 | <0.001 | 203 |
| Mission alignment (0-100) | Job satisfaction (0-100) | 0.29 | <0.001 | 200 |
| Organizational support (0-100) | Job satisfaction (0-100) | 0.28 | <0.001 | 202 |
| Inner drive / engagement (0-100) | Org size (ordinal 0-5) | -0.28 | <0.001 | 269 |
| Pay (0-100, high = less strain) | Inner drive / engagement (0-100) | 0.23 | <0.001 | 266 |
| Job satisfaction (0-100) | Org size (ordinal 0-5) | -0.23 | 0.001 | 203 |
| Retention (0-100) | Org size (ordinal 0-5) | -0.22 | <0.001 | 269 |
| Workload (0-100) | Retention (0-100) | -0.22 | <0.001 | 267 |
| Job satisfaction (0-100) | Retention (0-100) | 0.21 | 0.003 | 203 |
| Organizational support (0-100) | Org size (ordinal 0-5) | -0.21 | <0.001 | 267 |
| Pay (0-100, high = less strain) | Job satisfaction (0-100) | 0.20 | 0.004 | 201 |
| Job resources (0-100) | Org size (ordinal 0-5) | -0.19 | 0.002 | 268 |
| Workload (0-100) | Inner drive / engagement (0-100) | -0.17 | 0.005 | 267 |
| Burnout (0-100) | Org size (ordinal 0-5) | 0.15 | 0.014 | 269 |
| Mission alignment (0-100) | Org size (ordinal 0-5) | -0.15 | 0.018 | 265 |

**Partial correlations** (controlling org size + mission area): 35 of 36 construct pairs remain significant at q<.05.

All composite measures together: 145 of 210 pairs significant (q<.05). Full tables are in `tables/`.

## Equation 1: Burnout

Standardised OLS with HC3-robust SEs, n=264, R²=0.504, adj. R²=0.474, F p=5.5e-30; Mission block Wald F p=0.227. All coefficients:

| predictor | std_beta | ci_low | ci_high | p_value | q_value_FDR | VIF |
|---|---|---|---|---|---|---|
| Workload (0-100) | 0.393 | 0.266 | 0.52 | <0.001 | <0.001 | 1.81 |
| Organizational support (0-100) | -0.253 | -0.415 | -0.091 | 0.002 | 0.011 | 2.83 |
| Job resources (0-100) | 0.059 | -0.095 | 0.213 | 0.450 | 0.718 | 2.84 |
| Pay (0-100, high = less strain) | -0.023 | -0.141 | 0.095 | 0.705 | 0.881 | 1.64 |
| Mission alignment (0-100) | -0.01 | -0.146 | 0.126 | 0.887 | 0.950 | 1.73 |
| Inner drive / engagement (0-100) | -0.278 | -0.393 | -0.163 | <0.001 | <0.001 | 1.53 |
| Org size (ordinal 0-5) | -0.016 | -0.121 | 0.089 | 0.765 | 0.882 | 1.2 |
| Children & youth | -0.173 | -0.375 | 0.03 | 0.095 | 0.237 | 1.3 |
| Disability | 0.065 | -0.172 | 0.302 | 0.588 | 0.802 | 1.4 |
| Elder & long-term care | -0.135 | -0.362 | 0.093 | 0.246 | 0.476 | 1.27 |
| Education | -0.152 | -0.414 | 0.11 | 0.254 | 0.476 | 1.18 |
| Low-income families | 0.005 | -0.226 | 0.237 | 0.964 | 0.964 | 1.15 |
| Mental health | -0.267 | -0.539 | 0.004 | 0.054 | 0.188 | 1.13 |
| Social innovation / advocacy | -0.221 | -0.454 | 0.012 | 0.063 | 0.188 | 1.13 |
| Women & gender | 0.106 | -0.188 | 0.4 | 0.479 | 0.718 | 1.19 |

## Equation 2: Job satisfaction

Standardised OLS with HC3-robust SEs, n=199, R²=0.506, adj. R²=0.466, F p=4.6e-21; Mission block Wald F p=0.52. All coefficients:

| predictor | std_beta | ci_low | ci_high | p_value | q_value_FDR | VIF |
|---|---|---|---|---|---|---|
| Workload (0-100) | 0.026 | -0.13 | 0.183 | 0.740 | 0.740 | 1.75 |
| Organizational support (0-100) | -0.189 | -0.372 | -0.006 | 0.043 | 0.196 | 2.65 |
| Job resources (0-100) | 0.186 | 0.009 | 0.363 | 0.040 | 0.196 | 2.64 |
| Pay (0-100, high = less strain) | 0.034 | -0.107 | 0.176 | 0.633 | 0.740 | 1.64 |
| Mission alignment (0-100) | 0.078 | -0.077 | 0.233 | 0.324 | 0.602 | 1.7 |
| Inner drive / engagement (0-100) | 0.596 | 0.453 | 0.738 | <0.001 | <0.001 | 1.52 |
| Org size (ordinal 0-5) | -0.056 | -0.175 | 0.064 | 0.361 | 0.602 | 1.19 |
| Children & youth | 0.236 | -0.002 | 0.475 | 0.052 | 0.196 | 1.34 |
| Disability | 0.162 | -0.122 | 0.445 | 0.262 | 0.561 | 1.43 |
| Elder & long-term care | 0.2 | -0.097 | 0.496 | 0.185 | 0.556 | 1.28 |
| Education | 0.077 | -0.287 | 0.441 | 0.676 | 0.740 | 1.19 |
| Low-income families | -0.178 | -0.485 | 0.129 | 0.255 | 0.561 | 1.13 |
| Mental health | 0.06 | -0.261 | 0.381 | 0.712 | 0.740 | 1.19 |
| Social innovation / advocacy | 0.084 | -0.291 | 0.46 | 0.658 | 0.740 | 1.13 |
| Women & gender | -0.092 | -0.359 | 0.175 | 0.497 | 0.740 | 1.26 |

## Equation 3: Retention

Standardised OLS with HC3-robust SEs, n=203, R²=0.143, adj. R²=0.094, F p=0.0015; Mission block Wald F p=0.812. All coefficients:

| predictor | std_beta | ci_low | ci_high | p_value | q_value_FDR | VIF |
|---|---|---|---|---|---|---|
| Job satisfaction (0-100) | 0.061 | -0.093 | 0.214 | 0.436 | 0.685 | 1.23 |
| Burnout (0-100) | -0.287 | -0.438 | -0.136 | <0.001 | 0.003 | 1.13 |
| Org size (ordinal 0-5) | -0.074 | -0.221 | 0.072 | 0.320 | 0.685 | 1.16 |
| Children & youth | -0.021 | -0.353 | 0.31 | 0.899 | 0.902 | 1.33 |
| Disability | -0.158 | -0.523 | 0.207 | 0.394 | 0.685 | 1.38 |
| Elder & long-term care | 0.033 | -0.343 | 0.409 | 0.863 | 0.902 | 1.3 |
| Education | -0.027 | -0.466 | 0.411 | 0.902 | 0.902 | 1.2 |
| Low-income families | -0.169 | -0.574 | 0.237 | 0.413 | 0.685 | 1.13 |
| Mental health | -0.215 | -0.628 | 0.199 | 0.307 | 0.685 | 1.17 |
| Social innovation / advocacy | 0.097 | -0.353 | 0.547 | 0.672 | 0.902 | 1.1 |
| Women & gender | -0.307 | -0.735 | 0.122 | 0.159 | 0.685 | 1.21 |

## Equation 3b (sensitivity): Retention with all predictors as direct paths

Standardised OLS with HC3-robust SEs, n=199, R²=0.330, adj. R²=0.267, F p=2.5e-09; Mission block Wald F p=0.734. All coefficients:

| predictor | std_beta | ci_low | ci_high | p_value | q_value_FDR | VIF |
|---|---|---|---|---|---|---|
| Job satisfaction (0-100) | -0.088 | -0.284 | 0.108 | 0.379 | 0.723 | 2.03 |
| Burnout (0-100) | -0.144 | -0.332 | 0.044 | 0.132 | 0.448 | 1.96 |
| Workload (0-100) | 0.211 | 0.021 | 0.401 | 0.030 | 0.167 | 2.04 |
| Organizational support (0-100) | 0.127 | -0.09 | 0.343 | 0.250 | 0.606 | 2.87 |
| Job resources (0-100) | 0.282 | 0.086 | 0.477 | 0.005 | 0.086 | 2.72 |
| Pay (0-100, high = less strain) | 0.11 | -0.057 | 0.277 | 0.196 | 0.556 | 1.65 |
| Mission alignment (0-100) | 0.218 | 0.032 | 0.404 | 0.022 | 0.167 | 1.71 |
| Inner drive / engagement (0-100) | -0.028 | -0.209 | 0.152 | 0.757 | 0.891 | 2.39 |
| Org size (ordinal 0-5) | -0.047 | -0.182 | 0.089 | 0.496 | 0.844 | 1.19 |
| Children & youth | 0.096 | -0.222 | 0.413 | 0.553 | 0.847 | 1.37 |
| Disability | -0.005 | -0.355 | 0.344 | 0.976 | 0.976 | 1.44 |
| Elder & long-term care | 0.05 | -0.313 | 0.413 | 0.786 | 0.891 | 1.3 |
| Education | -0.055 | -0.443 | 0.333 | 0.780 | 0.891 | 1.2 |
| Low-income families | -0.178 | -0.579 | 0.223 | 0.383 | 0.723 | 1.14 |
| Mental health | -0.091 | -0.429 | 0.248 | 0.598 | 0.847 | 1.22 |
| Social innovation / advocacy | -0.017 | -0.447 | 0.412 | 0.937 | 0.976 | 1.13 |
| Women & gender | -0.335 | -0.724 | 0.054 | 0.091 | 0.389 | 1.26 |

## Mediation: predictor -> {Burnout, Job satisfaction} -> Retention

Parallel mediation, n=199 complete cases, 2,000 bootstrap resamples (percentile 95% CI). Uses Eq.3 **plus the predictors as direct paths** (a mediation model needs them; Eq.3 as written omits them).

| predictor | indirect_via_burnout | indirect_via_job_sat | total_indirect | total_ind_ci_low | total_ind_ci_high | direct_effect | total_effect | indirect_significant |
|---|---|---|---|---|---|---|---|---|
| Workload (0-100) | -0.055 | -0.002 | -0.057 | -0.132 | 0.016 | 0.211 | 0.154 | False |
| Organizational support (0-100) | 0.038 | 0.017 | 0.055 | -0.004 | 0.134 | 0.127 | 0.182 | False |
| Job resources (0-100) | -0.009 | -0.016 | -0.026 | -0.09 | 0.02 | 0.282 | 0.256 | False |
| Pay (0-100, high = less strain) | 0.011 | -0.003 | 0.008 | -0.024 | 0.045 | 0.11 | 0.118 | False |
| Mission alignment (0-100) | -0.001 | -0.007 | -0.008 | -0.048 | 0.024 | 0.218 | 0.21 | False |
| Inner drive / engagement (0-100) | 0.042 | -0.052 | -0.01 | -0.143 | 0.118 | -0.028 | -0.038 | False |

## Burnout headline numbers

- Personal burnout: mean 53.9 (SD 22.0, n=318); 37% moderate (50-74), 22% high (>=75)
- Work-related burnout: mean 49.6 (SD 20.8, n=318); 35% moderate (50-74), 14% high (>=75)
- >= monthly thoughts of leaving (org respondents): 40%; actively searched for jobs: 57%.

## Items most associated with Burnout (Spearman)

| Variable | rho | q | n |
|---|---|---|---|
| Workload (0-100) | 0.56 | 7.81e-22 | 267 |
| Organizational support (0-100) | -0.53 | 7.68e-20 | 267 |
| Excess workload / uneven division | 0.52 | 5.3e-19 | 266 |
| Org supports work-life balance | -0.51 | 2.69e-18 | 267 |
| Free to voice concerns | -0.48 | 4.83e-16 | 267 |
| Difficulty w/ supervisor | 0.45 | 4.54e-14 | 261 |
| Recognition | -0.45 | 4.35e-14 | 269 |
| Job resources (0-100) | -0.45 | 5.61e-14 | 268 |
| Job demands exceed training | 0.44 | 8.57e-14 | 267 |
| Inner drive / engagement (0-100) | -0.44 | 1.51e-15 | 318 |

## Significant group differences (FDR q<.05)

| Segment | Outcome | Test | p | q | effect | n | Group means |
|---|---|---|---|---|---|---|---|
| Actual weekly hours | Workload (0-100) | Kruskal-Wallis H | 1.12e-13 | 1.6e-11 | 0.278 | 241 | 21-40=32.63; 41-50=40.32; 51-60=57.99; 61+=62.22; <=20=19.92 |
| Respondent type | Inner drive / engagement (0-100) | Kruskal-Wallis H | 9.93e-11 | 7.1e-09 | 0.145 | 318 | Freelancer / independent=77.55; Org + personal projects=60.94; Org-affiliated=56.31 |
| Role | Retention (0-100) | Kruskal-Wallis H | 2.99e-07 | 1.43e-05 | 0.135 | 267 | Admin / project / finance=56.44; Founder / decision-maker=90.0; Frontline helper=60.75; HR / training=69.0; Mid-level manager=72.65 |
| Role | Inner drive / engagement (0-100) | Kruskal-Wallis H | 8.49e-07 | 3.01e-05 | 0.127 | 267 | Admin / project / finance=53.83; Founder / decision-maker=77.29; Frontline helper=52.81; HR / training=66.67; Mid-level manager=63.73 |
| Role | Job resources (0-100) | Kruskal-Wallis H | 1.2e-06 | 3.01e-05 | 0.124 | 266 | Admin / project / finance=60.44; Founder / decision-maker=81.14; Frontline helper=56.76; HR / training=76.75; Mid-level manager=67.21 |
| Role | Frequency considering leaving (0-4) | Kruskal-Wallis H | 1.26e-06 | 3.01e-05 | 0.124 | 267 | Admin / project / finance=1.47; Founder / decision-maker=0.43; Frontline helper=1.72; HR / training=1.2; Mid-level manager=1.12 |
| Role | Work-related burnout (0-100) | Kruskal-Wallis H | 1.62e-06 | 3.3e-05 | 0.122 | 267 | Admin / project / finance=48.1; Founder / decision-maker=33.07; Frontline helper=56.34; HR / training=47.86; Mid-level manager=46.01 |
| Role | Burnout (0-100) | Kruskal-Wallis H | 4.92e-05 | 0.000879 | 0.094 | 267 | Admin / project / finance=50.0; Founder / decision-maker=37.79; Frontline helper=57.85; HR / training=53.08; Mid-level manager=48.3 |
| Role | Mission alignment (0-100) | Kruskal-Wallis H | 6.27e-05 | 0.000996 | 0.094 | 263 | Admin / project / finance=76.67; Founder / decision-maker=92.05; Frontline helper=64.17; HR / training=80.0; Mid-level manager=75.74 |
| Org type | Inner drive / engagement (0-100) | Kruskal-Wallis H | 9.3e-05 | 0.00129 | 0.105 | 269 | Association / society=62.81; Community / regional team=68.89; Foundation=54.62; Government / commissioned=48.55; Other=61.11; Social enterprise=66.08; Social welfare agency=61.84 |
| Actual weekly hours | Personal burnout (0-100) | Kruskal-Wallis H | 9.89e-05 | 0.00129 | 0.098 | 242 | 21-40=47.64; 41-50=53.66; 51-60=66.41; 61+=65.74; <=20=51.82 |
| Age | Job satisfaction (0-100) | Kruskal-Wallis H | 0.000219 | 0.00261 | 0.1 | 240 | 18-24=59.65; 25-29=58.84; 30-34=71.1; 35-39=63.31; 40-49=73.29; 50+=76.04 |
| Org size | Frequency considering leaving (0-4) | Kruskal-Wallis H | 0.000448 | 0.0049 | 0.083 | 269 | 1-4=1.61; 11-15=1.37; 16-30=1.13; 31-50=1.2; 5-10=0.98; 51+=1.79 |
| Actual weekly hours | Burnout (0-100) | Kruskal-Wallis H | 0.00048 | 0.0049 | 0.083 | 242 | 21-40=46.85; 41-50=51.03; 51-60=63.69; 61+=61.43; <=20=49.28 |
| Role | Pay (0-100, high = less strain) | Kruskal-Wallis H | 0.000544 | 0.00519 | 0.075 | 264 | Admin / project / finance=62.78; Founder / decision-maker=65.91; Frontline helper=51.11; HR / training=55.0; Mid-level manager=75.0 |

## Method notes

- Every construct is the mean of its items after rescaling each item to 0-100 (percent of maximum possible) and aligning direction (reverse-scored items flipped), so a higher score always means MORE of the named construct (Pay: less pay strain; Retention: more likely to stay).
- Correlations are Spearman (rank-based, suitable for ordinal items); p-values are corrected with Benjamini-Hochberg FDR. Thresholds were NOT loosened to produce more significant results.
- Regressions: z-scored outcome and continuous predictors (standardised betas), 0/1 mission dummies, HC3 robust standard errors. Mission = 8 service-area dummies (areas with >=10% prevalence; rarer areas are the reference) tested jointly as one block.
- Job satisfaction (ProQOL block) was optional, so Eq.2 / Eq.3 / mediation have smaller n than Eq.1.
- Cross-sectional, self-selected data: all results are associations, not causal effects.
