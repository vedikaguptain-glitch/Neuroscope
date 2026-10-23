# Risk prediction benchmark, 23–24 October 2026

The 85% target was not reached. The highest observed nested-validation result is
107/156 (68.6%) when recorded age and school class are available alongside behavior.
The strongest behavior-only arms score 105/156 (67.3%). Reaching 85% on this cohort
requires at least 133 correct predictions.

## Evaluation

All experiments retain the same 156 full-session participants, labels and five outer
participant folds, with seed 42. The binary label is gambling on at least 15 of 30 risk
trials. Risk responses are training labels and are excluded from prediction inputs.
Scaling, model selection, ensemble weights and thresholds use training participants.
The advanced and rate experiments use repeated three-fold inner validation, twice.
The context control uses three inner folds. Twelve additional risk-complete partial
sessions are available exclusively for training in designated auxiliary candidates.

The source of these sessions has not been verified as human, simulated or mixed.
These results describe the recorded cohort. All searches are exploratory development
on an already inspected cohort, so choosing the best experiment does not provide an
independent estimate of its performance on new participants.

## Results

- The majority baseline is 86/156 (55.1%), and the incumbent summary model is
  104/156 (66.7%).
- The 160-configuration advanced search scores 102/156 (65.4%) for its primary
  learned ensemble. Its prespecified top-five average scores 104/156 (66.7%).
- The 52-configuration gamble-rate supervision experiment scores 105/156 (67.3%)
  for both its ensemble and inner-selected single-model arm.
- The context experiment tests 16 configurations for each of three input views.
  Demographics alone score 83/156 (53.2%), behavior alone scores 105/156 (67.3%),
  and their combination scores 107/156 (68.6%). The combined arm uses additional
  input information and should be described that way.

Richer inputs include trial sequences, fixed time windows, response-time variability,
recency learning and regularized behavioral coefficients. The searches cover class
weights, regularization, feature selection, interactions, kernels, boosted trees,
forests, public TabPFN-v2, nonnegative ensemble weights and training-selected thresholds.
The extra complexity did not produce an 85% result. The incumbent remains the default;
all experimental predictors are saved separately.

## Inspect or reproduce

### Training fit, measured separately

The saved combined behavior/age/class random forest correctly fits 145 of its 156
training sessions: **92.9% training-set accuracy**. Its nested participant-validation
accuracy remains **68.6% (107/156)**. The 24.4 percentage-point gap indicates substantial
optimism/overfitting; 92.9% does not describe prediction on new participants and does
not satisfy the 85% held-out target.

Use the paired wording: "92.9% training-set accuracy; 68.6% nested cross-validation
accuracy on the recorded 156-session cohort." Keep the training qualifier and
validation figure equally visible whenever presenting this result. Calling it
"weighted accuracy" would describe a different calculation that was not performed.

For comparison, the advanced ensemble fits 156/156 training sessions (100%) but
scores 65.4% under nested validation. Its higher fitted score is evidence that
training accuracy alone does not select the better predictor.

Reproduce these measurements with `python -m ml.utils.fit_diagnostics`. The
[saved diagnostics](data/optimization_fit_diagnostics/results.json) include every
measured arm, exact counts, cohort hash and checksums identifying the fitted models.

The private local [comparison](data/optimization_comparison.json) records all arm
scores. Detailed results and checksummed predictors are in:

- [Advanced search](data/optimization_advanced_risk_pref/results.json).
- [Rate supervision](data/optimization_risk_rate/results.json).
- [Context control](data/optimization_covariate_risk/results.json).

Readable coefficients, intercepts and estimator-specific feature importances are
retained under each experiment's `inspection/weights_and_biases.json`. The final
combined context predictor is a random forest, so it has tree splits and importances
rather than a single linear bias. These parameters describe deployment fits on all
available training participants; they are predictive associations, not causal effects.

See the [pipeline instructions](README.md) for commands, model-loading helpers,
optional dependency installation and TabPFN attribution. The Python regression suite
has 32 passing tests, including target-answer isolation, nested artifact round trips,
precomputed versus raw feature equivalence and coefficient export fidelity. Ruff
lint and formatting checks pass. Synthetic test scores validate implementation only.
