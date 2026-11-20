# Sample review, with an audit

This is one review from the [calibration run](REPORT.md), shown unedited, followed
by a check of it against the paper and against the real ICLR 2025 reviews.

> Written in run 1, before the score rescale. Its overall of 4.3 is the raw
> weighted score; on the current scale that is about 5.0 (the human average
> was 5.33).

- **Paper:** *SFESS: Score Function Estimators for k-Subset Sampling*, an ICLR 2025
  submission ([OpenReview q87GUkdQBm](https://openreview.net/forum?id=q87GUkdQBm)),
  accepted as a poster. Human ratings 5, 5, 6 (average 5.33); the area chair
  called it "probably the most borderline paper I recommended for acceptance".
- **Run:** blinded (the reviewer saw only the earliest "Under review" PDF), venue
  ICLR, literature cutoff 2024-10-01. About 10 minutes from start to finish. 11
  related arXiv papers, 3 of them read in full; the paper's own arXiv preprint
  was found and excluded.
- **Plugin score:** 4.3 / 10, about one point below the human average.

## Audit

Checked after the review was written:

| Check | Result |
|---|---|
| Quoted phrases exist in the paper | 9 of 9 found verbatim ("a significant research gap", "we can cache any repeated calls", "All methods use single sample estimates", "non-differentiable downstream models", "not the original discrete distribution", "the the relaxation temperature", O(n log n), ArgTopK, cuFFT) |
| Cited arXiv IDs are real and match their titles | 11 of 11 |
| "Kool et al. [arXiv:2002.06043] is not cited" | Correct: the paper cites Kool et al. 2019a and 2019b, not the 2020 unordered-set estimator |
| Overlap with the human reviews | Reviewer 1's main objection (the score function estimator for this distribution is already in SIMPLE, so novelty is thin) appears here as W4, citing the same paper. Reviewer 1's "not consistently better than SIMPLE" appears under Experiments. Reviewer 2's request to explain `ArgTopK(log θ + g)` is the starting point of W1 |
| Points the humans did not raise | The sampler as written does not draw from the distribution whose score is used (W1). The headline "non-differentiable f" advantage is never tested (W2). SFESS + VR gets 32× the function evaluations of the baselines (W3) |
| Missed | The area chair's point that "tuning-free" is inaccurate, because the number of control-variate samples M is a hyperparameter. The review discusses M but does not challenge the claim |

## The review


> AI-generated review (Agentic Research Paper Reviewer, following the
> paperreview.ai pipeline). May contain errors; use as guidance and apply
> your own judgment. Target venue: ICLR 2025. Literature cutoff: 2024-10-01.
> Date: 2026-11-18.

#### Summary

The paper asks whether score function (REINFORCE) estimators are a viable way to learn through k-subset sampling, which prior work has mostly handled with relaxed sampling (Gumbel-softmax top-k) or approximate pathwise gradients (straight-through, I-MLE, SIMPLE). The k-subset distribution is defined as independent Bernoulli(θ_i) variables conditioned on their sum being k (eq. 2). Its score therefore splits into a sum of Bernoulli scores minus the gradient of the log Poisson-binomial probability p(Σb_i = k) (eq. 3). The authors compute that normalizer with the closed-form DFT expression of Fernandez & Williams (2010), using cuFFT (eq. 6, Listing 1). They reduce variance with a leave-one-out multi-sample baseline over M = 32 samples (eq. 7, Alg. 2). Samples are drawn with Gumbel top-k (Alg. 1).

Table 1 claims the resulting estimator (SFESS / SFESS + VR) is the only method with exact samples, unbiased gradients, support for non-differentiable f, and no tuning. Experiments on MNIST and Fashion-MNIST cover a toy problem with known gradients (n = 10, k = 5), feature selection (n = 784, k ∈ {30, 50}), a discrete VAE with k-subset latents, and stochastic k-NN. Baselines are GS, STGS, I-MLE and SIMPLE. The paper reports that SFESS + VR is "comparable" to these baselines: best on feature selection (Table 2), second best or near-tied on the VAE (Table 3), and within 0.001–0.004 of the best on k-NN (Table 4).

#### Strengths

- **S1.** The experiments show that a plain multi-sample leave-one-out baseline turns an unusable estimator into a competitive one. Vanilla SFESS fails on the VAE (BCE+KL ≈ 205.7 / 384 in Table 3, flat curves in Fig. 5), while SFESS + VR reaches 68.83 / 218.39, close to or better than SIMPLE. Fig. 3 shows gradient error falling steadily from M = 2 to M = 128. This is a useful data point against the view that score function estimators are too noisy for k-subsets.
- **S2.** SFESS + VR posts the best mean on all four feature-selection settings (Table 2: e.g. 0.154 ± 0.003 vs SIMPLE 0.160 ± 0.002 on MNIST k = 30; 0.320 vs 0.327 on Fashion-MNIST k = 30). The convergence curves (Fig. 4, Fig. 9) show a consistent edge in early training on Fashion-MNIST.
- **S3.** The method is simple and cheap. Fig. 7 shows a per-step wall-clock for SFESS + VR on the MNIST VAE that is below SIMPLE's and similar to GS/STGS, despite 32 samples. The normalizer depends only on θ and k, so it can be cached across samples (p. 4, "we can cache any repeated calls").
- **S4.** The presentation is clear and self-contained. Fig. 1 and Table 1 position the three families of estimators; Alg. 2 and Listing 1 make the method easy to reimplement; and the toy problem reuses SIMPLE's setup, so the bias/variance numbers are directly comparable to prior work.

#### Weaknesses

- **W1 (major).** The sampler as specified does not match the distribution whose score is used. Alg. 1 draws z = ArgTopK(log θ + g, k), which gives the Plackett–Luce / without-replacement set probability (Kool et al. [arXiv:2002.06043], eq. 6), not the conditional-Bernoulli p(z) ∝ ∏_{i∈S} θ_i/(1−θ_i) of eq. 2 (the conditional Poisson design, which [arXiv:2109.11034] keeps distinct from Gumbel-top-k). As written, Alg. 1 + eq. 3 is therefore not a valid score function estimator, and Table 1's "Exact samples ✓ / Unbiased ✓" depend on a sampler the paper does not state. Fix: use exact conditional-Poisson sampling (sequential DP, as in SIMPLE [arXiv:2210.01941] Alg. 2) and say which sampler produced every result.
- **W2 (major).** The headline advantage, a non-differentiable f (abstract: "applicable to non-differentiable downstream models, unlike existing methods"; Table 1 column 3), is never tested. Every task in Sec. 4 (toy squared error, BCE reconstruction, ELBO, k-NN loss trained with differentiable encoders) has a differentiable f in which the baselines also work. Add at least one task with a black-box or non-differentiable f, e.g. a discrete reward, a non-differentiable model, or a combinatorial objective.
- **W3 (major).** The comparisons are not compute-matched. The Fig. 2 caption says "All methods use single sample estimates, except SFESS + VR, where control variates are computed using 32 samples," so SFESS + VR evaluates f 32× more often per data point. Fig. 7 gives wall-clock for a single setting (MNIST VAE, tiny MLPs). Baselines given M = 32 averaged samples, or a FLOP/f-evaluation-matched comparison, are needed before "comparable" can be read as a fair verdict.
- **W4 (major).** The novelty claim ("a significant research gap ... where score function estimators are not being considered", p. 2) is overstated. SIMPLE [arXiv:2210.01941] already writes the exact conditional score ∇log p(z | Σz = k), computes the normalizer exactly, and evaluates SFE as a baseline in the same toy problem. Score-function estimators with leave-one-out baselines over without-replacement k-sets exist in Kool et al. [arXiv:2002.06043], which is uncited. The actual delta is narrower: a DFT normalizer plus a standard leave-one-out baseline (Kool 2019a, VIMCO). Reframe the contribution as an empirical re-evaluation and cite and position against these works.
- **W5 (minor).** The baselines are incomplete and possibly undertuned. NCPSS appears in Table 1 but not in Sec. 4. No other unbiased multi-sample estimator is compared (e.g. the unordered set estimator [arXiv:2002.06043], CARMS [arXiv:2110.14002], double control variates [arXiv:2111.05300]). I-MLE's noise temperatures are fixed at 1.0 without tuning (p. 6), although I-MLE is known to be step-size sensitive [arXiv:2209.04862], and the GS τ grid has three values. Learning rate and steps are shared across all methods.
- **W6 (minor).** The empirical scope is narrow: MNIST and Fashion-MNIST with small MLPs, 5 seeds. SIMPLE's headline benchmark (learning-to-explain on BeerAdvocate, [arXiv:2210.01941] Tables 2–3) is absent, and there is no study of how variance scales with n and k beyond the n = 10 toy.
- **W7 (minor).** The complexity claim does not match the implementation. Section 3 claims "O(n log n) time-complexity", but Listing 1 forms an (n+1)×n matrix `theta * c**i` and takes a product over it, which is O(n²) work before the FFT. There is no cost or stability comparison against the O(nk) DP the paper itself cites (Ahmed et al. 2023).

#### Detailed Comments

### Novelty and relation to prior work

The closest retrieved works and the delta over each:

- **SIMPLE [arXiv:2210.01941].** It uses the same distribution (independent Bernoulli conditioned on Σ = k, its eq. 2) and computes log p(Σ = k) exactly, with an O(nk) DP and an O(log k log n) vectorized variant. Its Sec. 2 explicitly writes the score function estimator E[ℓ · ∇log p(z | Σz = k)] and remarks that it "is typically avoided due to its notoriously high variance." It includes SFE in its synthetic bias/variance experiment, the same n = 10, k = 5 toy that SFESS adapts. What SFESS adds over SIMPLE: a variance-reduced SFE (multi-sample leave-one-out) and the empirical finding that it is competitive on downstream tasks. The DFT normalizer is an alternative to SIMPLE's DP, not a new capability. The paper cites SIMPLE for the recursive method (p. 4), but the introduction's framing of a research gap where these estimators are "not being considered" understates that SIMPLE considered SFE and measured it.
- **Kool et al., unordered set estimator [arXiv:2002.06043] (not cited).** It derives an unbiased REINFORCE estimator from k samples drawn without replacement with Gumbel-top-k, computes the probability of the unordered set exactly (its eq. 6 and App. B), and adds a built-in leave-one-out-style baseline. Its target differs: an expectation over single items, not a set-valued f. So it does not pre-empt SFESS, but it is directly relevant prior use of score-function estimation on Gumbel-top-k k-sets with LOO baselines. It is also the natural reference for what distribution Alg. 1 actually samples (see W1). It should be cited and, ideally, adapted as a baseline.
- **Conditional Poisson Stochastic Beam Search [arXiv:2109.11034] (not cited).** It uses the same conditional Poisson design in ML, with an O(NK) normalizer DP, an exact sequential sampler, and inclusion probabilities obtained by differentiating the normalizer. That last quantity is closely related to the −∇log p(Σb = k) term in eq. 3. It also explicitly treats CP sampling as a different design from Kool et al.'s Gumbel-top-k stochastic beam search. It belongs in the related work.
- **Xie & Ermon [arXiv:1901.10517], I-MLE [arXiv:2106.01798], SST [arXiv:2006.08063].** These are correctly positioned as relaxed or perturbation-based alternatives. Yin et al. [arXiv:2006.06448] also uses unbiased gradient estimators for probabilistic subset selection in the Bernoulli/L0 setting and is a relevant omission for the feature-selection framing.

Overall, the technical components (conditional-Bernoulli score, Fernandez–Williams DFT normalizer, leave-one-out baseline) are all individually known. The contribution is their assembly and a positive empirical message. That is legitimate but modest for ICLR, and the paper should claim it as such.

### Method and soundness

- **Sampler vs score mismatch (W1).** Eq. 2 defines p(z) ∝ ∏_{i∈S} θ_i ∏_{i∉S}(1−θ_i) ∝ ∏_{i∈S} θ_i/(1−θ_i). Alg. 1 perturbs log θ (not the log-odds) and takes the top k. Even with log-odds logits, Gumbel-top-k gives the Plackett–Luce set probability, a sum over orderings ([arXiv:2002.06043] eq. 6), which is not of product form. The score function identity in App. A needs samples from the same p_θ whose log-derivative is taken. If the experiments used Alg. 1, the estimator is biased. If they used an exact sampler (e.g. SIMPLE's code, which the toy problem is adapted from per footnote 3), the paper should say so and replace Alg. 1. The near-zero SFESS bias in Fig. 2 hints at the latter, but the text never says. This determines whether Table 1's "exact samples" and "unbiased" entries hold, so it needs an unambiguous answer.
- **Numerical behavior of the DFT normalizer.** Listing 1 computes the PMF in probability space, takes `.real` of the FFT output, and the log is then differentiated by autodiff (p. 4). For n = 784 with many θ_i near 0 or 1, p(Σb = k) can be extremely small. FFT-based PMFs have absolute rather than relative error, so log p may be inaccurate or even undefined if the real part rounds to ≤ 0. (Unverified concern: the paper gives no analysis or log-space variant, and the feature-selection runs evidently trained, so this may not bite at these scales.)
- **Complexity (W7).** As noted above, Listing 1 is O(n²) arithmetic plus an O(n log n) FFT. This is fine at n = 784, but the "O(n log n)" claim should be corrected or the implementation changed.
- **Unbiasedness of eq. 7.** The leave-one-out baseline over M i.i.d. samples keeps the estimator unbiased, given correct sampling. This part is standard and sound.
- **Table 1 entries.** GS is marked "Unbiased ✓". That is true only for the gradient of the relaxed objective, which the text on p. 3 itself says is "not the original discrete distribution". It reads inconsistently next to STGS/SIMPLE marked ✗.

### Experiments and evidence

Diffing against the experiments a rigorous version would contain:

- **Non-differentiable f (missing; W2).** This is the main claimed differentiator in the abstract, Table 1 and the conclusion ("wider applicability"), and no experiment exercises it.
- **Compute-matched baselines (partly missing; W3).** SFESS + VR uses M = 32 f-evaluations per data point. The Fig. 7 wall-clock covers one configuration with very small networks, where the GPU is underutilized. Baselines with M-sample averaging, or plots against f-evaluations, would make "comparable" meaningful.
- **Other unbiased / variance-reduced score-function estimators (missing; W5).** The only SF comparison is the vanilla SFESS ablation. The natural competitors are other unbiased multi-sample estimators adapted to subsets: the unordered set estimator [arXiv:2002.06043], CARMS-style antithetic sampling [arXiv:2110.14002], and double control variates on top of the LOO baseline [arXiv:2111.05300].
- **NCPSS (missing).** It is listed in Table 1 and discussed in Sec. 5 but not run.
- **Tuning fairness.** I-MLE runs with untuned temperatures (p. 6) and performs worst on most tasks, e.g. 0.740 / 0.696 k-NN accuracy in Table 4. Given its documented step-size sensitivity [arXiv:2209.04862], its numbers likely understate it.
- **Results vs claims.** The "comparable results ... across all tasks" claim is broadly supported. Feature-selection gains over SIMPLE are small but consistent (Table 2). On the VAE, SIMPLE is better on MNIST at both sizes (81.90 vs 90.04; 67.96 vs 68.83) and SFESS + VR is marginally better on Fashion-MNIST d = 20 (218.39 vs 218.82). The k-NN results are within noise of GS/STGS/SIMPLE. With 5 seeds and gaps of ~1 std, "best" in Table 2 should be stated cautiously.
- **Scope (W6).** MNIST and Fashion-MNIST only, and no L2X/BeerAdvocate, which is SIMPLE's headline benchmark ([arXiv:2210.01941] Tables 2–3). There is no variance-vs-n or variance-vs-k study beyond the n = 10 toy, although score-function variance is expected to grow with n.
- **Sensitivity to M** is shown only on the toy problem (Fig. 3). A downstream-task curve would show the cost/accuracy trade-off.

### Clarity and presentation

The paper is easy to follow and the method can be reimplemented from Alg. 2 and Listing 1. Notation issues: eq. 6 omits the DFT frequency index in the exponent (it should depend on l; Listing 1's `c**i` supplies it). θ is a probability in [0,1]^n in eq. 2 but is used as logits in Alg. 1 (`log θ + g`). The parameterization actually optimized (raw probabilities, sigmoid of logits?) is not stated. Fig. 3 says "cosine difference" and Fig. 2 says "1 − cosine similarity". There is no limitations section. Nits: "the the relaxation temperature" (p. 6), "τ → inf" (p. 8).

#### Questions for Authors

1. Which sampler produced the samples in each experiment: Alg. 1 (Gumbel top-k on log θ) or an exact conditional-Bernoulli sampler? If Alg. 1, how do you reconcile its Plackett–Luce set distribution with the score of eq. 2/3, and what does Fig. 2's bias look like with an exact sampler?
2. Can you show a task with a genuinely non-differentiable or black-box f, where SFESS + VR succeeds and relaxed/pathwise baselines cannot be applied or degrade?
3. How do GS, STGS and SIMPLE perform when given the same M = 32 samples per data point (averaged), or when compared at an equal number of f-evaluations?
4. How does SFESS + VR compare with other unbiased multi-sample estimators, e.g. the unordered set estimator of [arXiv:2002.06043] adapted to set-valued f, or a leave-one-out baseline with double control variates [arXiv:2111.05300]?
5. Is the DFT normalizer numerically stable for large n with extreme θ (e.g. n = 784, k = 30 late in training)? Did you compare its accuracy and runtime with the O(nk) DP of SIMPLE?
6. How do results change if I-MLE's noise temperature is tuned over a grid comparable to GS's τ?

#### Overall Assessment

| Dimension | Score (1–10) |
|---|---|
| Originality | 4 |
| Importance of research question | 5 |
| Claims supported by evidence | 4 |
| Soundness of experiments | 4 |
| Clarity of writing | 6 |
| Value to the research community | 4 |
| Contextualization vs. prior work | 4 |
| **Overall (weighted)** | **4.3 / 10** |

Overall 4.3 / 10, below the ICLR accept borderline (≈6). Two things drive the score.

- **Claims and soundness.** The two properties that set SFESS apart in Table 1 are not established.
  - Exact samples and unbiasedness depend on a sampler that, as specified (Alg. 1), does not draw from eq. 2's distribution.
  - Applicability to non-differentiable f is never tested.
  - The comparisons give SFESS + VR 32× more f-evaluations than the baselines.
- **Originality.** SIMPLE [arXiv:2210.01941] already formulated and evaluated the exact score function estimator for this distribution. The remaining delta is a known DFT normalizer plus a standard leave-one-out baseline.

The empirical message, that a variance-reduced score function estimator is competitive on these tasks, is useful. Three changes would most improve the paper:

- an exact sampler, clearly specified;
- a non-differentiable-f experiment;
- compute-matched and unbiased-estimator baselines, on a benchmark beyond MNIST.

These scores use calibrated anchors, not a fitted regression, with about ±1.5 points of uncertainty. They are calibrated only for ICLR-style ML venues.

#### Related Work Consulted

- arXiv:2210.01941 — SIMPLE: A Gradient Estimator for k-Subset Sampling (full summary)
- arXiv:2002.06043 — Estimating Gradients for Discrete Random Variables by Sampling without Replacement (full summary)
- arXiv:2109.11034 — Conditional Poisson Stochastic Beam Search (full summary)
- arXiv:1901.10517 — Reparameterizable Subset Sampling via Continuous Relaxations (abstract)
- arXiv:2106.01798 — Implicit MLE: Backpropagating Through Discrete Exponential Family Distributions (abstract)
- arXiv:2209.04862 — Adaptive Perturbation-Based Gradient Estimation for Discrete Latent Variable Models (abstract)
- arXiv:2006.08063 — Gradient Estimation with Stochastic Softmax Tricks (abstract)
- arXiv:2006.06448 — Probabilistic Best Subset Selection via Gradient-Based Optimization (abstract)
- arXiv:2110.14002 — CARMS: Categorical-Antithetic-REINFORCE Multi-Sample Gradient Estimator (abstract)
- arXiv:2111.05300 — Double Control Variates for Gradient Estimation in Discrete Latent Variable Models (abstract)
- arXiv:1901.09346 — Concrete Autoencoders for Differentiable Feature Selection and Reconstruction (abstract)
