"""One evidence-led statistics slide for the main DNHacks pitch.

Only committed aggregate figures are embedded; this module never fits a model.
"""
from pptx.util import Inches

from deck_style import AMBER, GREEN, MONO, MUTED, PAPER, ROOT, note, slide, text


def build_training(p, num=5):
    s=slide(p,num,'Training objective / measured GPU work')
    text(s,'Learn structure by reconstructing genes we deliberately hide.',.62,1.02,12.05,.92,32,PAPER,True)
    text(s,'19,000 genes → 512 hidden → 128 latent features',.67,2.10,11.99,.47,24,GREEN,True)
    text(s,'Denoising objective: Vincent et al. · JMLR 2010  /  GSE212041 cohort',.69,2.65,11.97,.19,10,MUTED)
    s.shapes.add_picture(str(ROOT/'assets/revision/plots/training-baseline.png'), Inches(.59), Inches(2.84), width=Inches(6.32), height=Inches(3.48))
    text(s,'THE OBJECTIVE',7.18,2.87,5.03,.30,11,GREEN,True,MONO)
    text(s,'L = mean (x̂ᵢ − xᵢ)²,  i ∈ masked genes',7.18,3.36,5.18,.69,23,PAPER,True)
    text(s,'Hide 15% of inputs; score only their reconstruction.\nThe encoder must use relationships among genes.',7.19,4.23,5.02,1.27,19,MUTED)
    text(s,'149 TRAIN / 74 DEV / 151 EVAL\nL40S · 100 epochs · 3.41s fit',7.20,5.66,5.01,.69,14,GREEN,True,MONO)
    text(s,'TRAIN loss 0.116 vs ≈1 for the mean predictor. Generalization is tested on the next slide.',.69,6.52,11.98,.40,16,PAPER)
    note(s,num,'Learn structure by reconstructing genes we deliberately hide.',
         'We train a representation before collecting evidence. Each gene is standardized using training donors only. We hide fifteen percent of the inputs and minimize squared error on those hidden entries, so simply copying the input cannot solve the task. This is the denoising-autoencoder principle. A predictor that always returns the training mean has expected standardized error around one; the recorded training loss ends at point-one-one-six. This is a fit diagnostic, not proof of generalization. We froze that encoder and evaluated it on fresh donors. The recorded hundred-epoch fit ran on an L40S GPU in three-point-four-one seconds.',40,
         'Implemented loss in expr_encoder.py: (decoder(encoder(damaged))-target)[mask].square().mean(). Each nonconstant gene has TRAIN empirical variance1 after log1p(TPM) standardization. Returning its TRAIN mean corresponds to zero and gives expected uniformly masked MSE approximately1. This analytically defined reference is not a new empirical baseline run, held-out score or random-network measurement. Final recorded TRAIN masked MSE0.1161042408. A changing random mask and minibatch weight updates are part of the logged curve. No per-epoch held-out loss exists. MSE is appropriate to standardized continuous reconstruction; low TRAIN MSE does not establish biological usefulness. Denoising rationale follows Vincent et al.2010; this architecture is our small cohort-specific implementation, not their benchmark replication. GPU metadata: L40S/CUDA12.8/Torch2.10.0, float32, fixed seed20260905,100epochs,Adam.001, batch64. Timing covers the fit call plus CUDA synchronization; excludes file serialization, data loading/download and provisioning; it is not a discovery runtime or CPU speedup. The small float64 bettor device check actually ran faster on CPU than CUDA. No GPU rediscovery run is attributed to these records.',
         'Keep the TRAIN label and analytical-baseline label. Data source: GSE212041 observational D0 cohort,374donors. Fixed149/74/151split; top19000variance genes, means/scales and representation fitted onTRAIN only. Training is distinct from branch-monitor fitting, which remains future work.',
         'AI Technical Sophistication (50); Technical Execution (50); AI Reliability (25)',
         ['denoising','src/dnhacksbio/expr_encoder.py','research/learned-evalue-validation/real-expression/training.json','research/learned-evalue-validation/real-expression/device-benchmark.json','presentation/assets/revision/plots/manifest.json'])
    return s


def build_statistics(p, num=4):
    """Append a 16:9 slide joining actual training, scoring mechanics and results."""
    heading = "Evidence must grow on data the model has never seen."
    s = slide(p, num, "Technical proof / learned biological evidence")
    text(s, heading, .62, 1.02, 12.05, .92, 32, PAPER, True)
    text(s,'Train on the past → bet on a fresh pair → accumulate evidence',.67,2.06,12.0,.5,22,GREEN)
    text(s,'Pandeva et al. · AISTATS 2024  /  DAVT adaptation',.69,2.64,5.87,.20,10,MUTED)
    text(s,'Lbet = −mean log q     q = 1 + tanh(d)',.68,2.98,5.82,.70,23,PAPER,True)
    text(s,'d = clip(g(x) − g(y), −4, 4)\nEₜ = Eₜ₋₁ × qₜ',.70,3.91,5.55,.89,23,GREEN,True)
    text(s,'Under the registered null, swapping x and y\nmakes the bet fair. Arbitrary scores cannot\nclaim that guarantee.',.70,5.06,5.65,1.17,21,MUTED)
    text(s,'FINAL E: LEARNED 3,653 / PCA 86 / IFIT3 5,964',6.89,2.91,5.76,.40,13,GREEN,True,MONO)
    s.shapes.add_picture(str(ROOT/'assets/revision/plots/evidence-baselines.png'), Inches(6.74), Inches(3.31), width=Inches(6.0), height=Inches(3.3))
    text(s,'112 / 10,000 null runs ever crossed E ≥ 20  ·  5% anytime error budget under stated assumptions',.69,6.60,11.98,.29,14,AMBER,True)

    script = (
        "We do not ask an LLM to invent a confidence score. The network minimizes negative log "
        "payoff on past pairs, then bets on a fresh pair. Under the registered null, swapping "
        "the two inputs changes the sign and makes the bet conditionally fair. That gives a "
        "five-percent bound on ever crossing twenty, even if we inspect every batch. A constant "
        "critic stays at one: no information, no evidence growth. Our learned representation "
        "finished at 3,653 against PCA's 86; the stronger single-gene comparator stays in the plot. "
        "A separate synthetic audit had 112 crossings in 10,000 runs. Better prediction can increase "
        "power; the sampling contract and arithmetic determine validity."
    )
    proof = (
        "IMPLEMENTED, MEASURED COMPONENT DIAGNOSTIC; not a verified biological discovery.\n"
        "METHOD / ATTRIBUTION: Pandeva et al., Deep anytime-valid hypothesis testing, "
        "AISTATS 2024, https://proceedings.mlr.press/v238/pandeva24a.html. This is an adapted "
        "two-sample DAVT diagnostic with a frozen expression representation; it is not our new "
        "theorem and not the research-trajectory E-valuator method or native four-term association "
        "kernel. For pair t, d_t = clip(f_t(x_t)-f_t(y_t), -4,4), q_t = 1+tanh(d_t), "
        "E_t = product of scored q_i. f_t is trained/selected using past pairs only. Under equal "
        "independent group distributions and a predictable learner, exchangeability makes the "
        "conditional factor expectation one. At alpha=.05 the anytime threshold is 20. "
        "Code computes log(2)-softplus(-2d), adds log factors, and returns final wealth; a "
        "running maximum is a separate diagnostic, not the returned e-value.\n"
        "DATA / TRAINING: GSE212041 neutrophil TPM, COVID-positive versus symptomatic negative, "
        "one D0 sample per donor; healthy controls and later/event-driven draws excluded. "
        "374 donors: TRAIN149 (119+/30-), DEV74, EVAL151 (121+/30-). Fixed stratified split. "
        "Top19,000 genes selected by TRAIN-only log1p(TPM) variance; frozen TRAIN means/scales. "
        "Masked autoencoder19,000→512→128 with mirrored decoder, 15% masking, Adam lr=.001, "
        "100 epochs, seed20260905, NVIDIA L40S float32. DEV was available for device timing, "
        "not model/feature/epoch selection. Slide 5 shows the committed TRAIN masked reconstruction "
        "MSE series; no per-epoch held-out validation curve was recorded. PCA uses64 components, "
        "so the representations do not have matched dimensionality.\n"
        "FRESH-PAIR SCORING: Primary predeclared seed20260906 uses30 selected disjoint pairs; "
        "91 positive EVAL donors are unused. These are group-comparison pairs, not clinically "
        "matched patients. Batch size4: first8 pairs are unscored training/validation burn-in; "
        "22 pairs are scored in six batches, last partial. The64/64 ReLU bettor fits older "
        "batches, validates on the latest past batch, and scores unseen rows before reuse; "
        "Adam lr=.0005, weight_decay=.01, max100 epochs/update, patience10. Representation and "
        "preprocessing never train on DEV/EVAL. Final e-values3652.81 learned,85.76 PCA,5964.41 "
        "predeclared IFIT3 scalar; calibrated permutation final e99 (p=.0001), not shown in this figure. IFIT3 is stronger here. These are evidence statistics, not accuracy, effect "
        "size, clinical utility or power. Ten order/subsample sensitivities reuse donors; "
        "they are not independent power trials. Observational recruitment, severity, treatment "
        "and cell composition can explain a distribution difference; no causal or PDAC "
        "therapeutic inference is claimed.\n"
        "NULL AUDIT:112/10,000 ever-crossings =1.12%, pointwise95% Wilson CI0.93–1.35%; "
        "20/10,000 final rejections =.20%. This is the separately trained small synthetic "
        "autoencoder benchmark,96 pairs/run, not the19,000-gene RNA encoder, product-wide error "
        "rate or branch-monitor calibration. Regression tests separately enumerate all64 "
        "orientations of six fixed unordered pairs and audit fit/score separation.\n"
        "ADDITIONAL TRAINED TOOL / PROTEIN: donor-disjoint CPTAC TRAIN219, LUAD VAL110, "
        "PDAC DEV105; 2,000-protein panel; masked denoiser4,000→256→32→2,000 with20% masking. "
        "Held-out reconstruction MSE: training mean2.9318, PCA1.8243, denoiser2.1067. "
        "These are final reconstruction metrics; no epoch curve was retained. External Fudan "
        "224 graded tumors: primary rank-PCA AUROC.55249, secondary rank-kernel.69376, "
        "not independent sequential confirmation. The frozen rank kernel did not meet the "
        "modeled targeted-effect power requirement; fixed-module simulation results are separate. "
        "Actual protein plots remain at presentation/assets/v2/plots/protein.png and "
        "external_protein.png for manual slide editing.\n"
        "ADDITIONAL INTERNAL EVIDENCE CORE: native association scoring uses a distinct four-term "
        "matched/crossed two-donor factor, 1+stake*(c11+c22-c12-c21)/4, with bounded critic "
        "scores and frozen stake. Under its registered independent sampling null, the factor "
        "has conditional expectation one. The private ledger atomically commits donor "
        "consumption, factor, cursor and critic state; exact retries cannot accrue evidence "
        "twice. Adapters still require audited sampling/access/measurement and prospective "
        "power. This is not the RNA DAVT construction pictured above.\n"
        "STATUS: Biological two-sample diagnostic and its public-input replay guards are "
        "implemented. Branch-monitor prefix scoring/grouped calibration infrastructure exists; "
        "real research-trajectory fitting and calibration remain pending. This slide does not "
        "claim a validated branch-stopping policy, private clinical confirmation, independent "
        "falsifier recomputation, or completed literature-to-discovery recovery."
    )
    note(
        s, num, heading, script, 50, proof,
        "Preserve every predeclared representation comparator. The constant critic g=0 is an "
        "analytical no-information baseline with E=1, not an empirical random-number experiment. "
        "Never equate an e-value with accuracy, clinical utility or probability that a claim is true. "
        "The 112/10,000 crossing audit uses the separate small synthetic encoder. Unlike a fixed "
        "confidence number, this score has a conditional expectation bound; arbitrary LLM numbers "
        "do not. Better fitting cannot rescue dependence, leakage or a wrong null. Do not transfer "
        "the diagnostic to branch-monitor calibration, which remains pending.",
        "Main Technical Execution (50); AI Technical Sophistication (50); "
        "AI Reliability/Evaluation/Trustworthiness (25); AI Importance (25)",
        [
            "src/dnhacksbio/learned_evalue.py",
            "src/dnhacksbio/expr_encoder.py",
            "docs/learned-evalue-process.md",
            "research/learned-evalue-validation/real-expression/training.json",
            "research/learned-evalue-validation/real-expression/evaluation.json",
            "research/learned-evalue-validation/real-expression/manifest.json",
            "research/learned-evalue-validation/expanded-null.json",
            "tests/test_learned_evalue.py",
            "docs/branch-monitoring.md",
            "docs/native-evidence.md",
            "docs/protein-training.md",
            "docs/protein-external.md",
            "docs/protein-model-power.md",
            "presentation/assets/v2/plots/manifest.json",
        ],
    )
    return s
