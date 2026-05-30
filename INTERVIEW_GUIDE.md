# ChessPuzzle Benchmark - Interview Guide

A guide for talking about this project in interviews. It covers what it is, the
design decisions worth highlighting, the problems solved along the way, and how
to frame the whole thing depending on the role and how much time you have.

Live dashboard: https://chess.adamissah.com

---

## 1. The 30-second pitch

> "I built an LLM benchmark that measures how well frontier models solve chess
> puzzles. It runs 300 puzzles across 7 models in parallel on AWS Fargate, scores
> each on a multi-dimensional rubric (correctness, move legality, output-format
> compliance, latency), and publishes the results to a live dashboard. The whole
> thing is infrastructure-as-code with Terraform and ships through GitHub Actions
> CI/CD. The headline finding: the reasoning model (o3) hit 71% while every
> non-reasoning model was in single digits, and o3 had a distinct, better-calibrated
> failure mode: it says 'I can't solve this' instead of hallucinating a wrong line."

That single paragraph hits all four things an interviewer cares about: eval design,
distributed execution, infra/IaC, and an actual research insight.

---

## 2. What it is (the one-liner per layer)

| Layer | What it does |
|---|---|
| **Data** | Filters the 6M-row Lichess puzzle DB down to 300 puzzles, evenly stratified across 5 mate types and 4 difficulty tiers |
| **Agent** | Sends each puzzle (FEN position) to a model, parses the move sequence out of free-form output |
| **Eval** | Scores each answer on correctness, move legality, format compliance, and latency, then aggregates per model |
| **Orchestration** | `main.py` runs load -> solve -> score -> upload, one model per container |
| **Infra** | Docker images per model, run in parallel on ECS Fargate, results to S3 |
| **IaC** | Terraform provisions everything (ECR, ECS, S3, IAM, Secrets Manager, CloudFront, Route53, ACM) |
| **CI/CD** | GitHub Actions: dashboard auto-deploys, Terraform plans on PR and applies on merge |
| **Presentation** | Static dashboard on CloudFront + custom domain, fetches results live from S3 |

---

## 3. Key design decisions (the meat of the interview)

These are the decisions to lead with. For each one, the pattern is:
**the problem -> the decision -> the why -> the tradeoff.**

### 3.1 Multi-dimensional scoring instead of pass/fail

- **Problem:** Binary "did it solve the puzzle" throws away most of the signal. A
  model that plays 4 of 5 correct legal moves is very different from one that
  outputs garbage, but pass/fail scores them identically (both fail).
- **Decision:** A composite score:
  `0.45*correct + 0.35*valid_ratio + 0.10*(1 - norm_latency) + 0.10*format_followed`
- **Why:** Correctness stays the dominant signal, but partial credit for legal
  moves, a penalty for slow responses, and a separate axis for instruction-following
  let the benchmark distinguish *how* a model fails, not just *that* it failed.
- **Tradeoff:** The weights are a judgment call. I can defend each one, but a
  different researcher might weight latency higher for a production use case. The
  point is the rubric is explicit and tunable, not that these exact numbers are sacred.

**This is the most important thing to talk about.** It shows eval-design taste:
you understood that the metric *is* the product.

### 3.2 "Output format followed" as a first-class metric

- **Problem:** Models constantly broke the requested UCI format: algebraic
  notation (`Rxf8#`), capture symbols, prose, wrong move counts.
- **Decision:** Track format compliance separately from correctness. Parse out
  valid UCI tokens; if the count doesn't match what's expected, it's a format failure.
- **Why:** This cleanly separates two failure modes that look identical on a
  pass/fail metric: "the model can't do chess" vs. "the model can do chess but
  won't follow instructions." Claude Opus 4.7 is the perfect case study: it had the
  *highest* raw accuracy of the non-reasoning models (8.3%) but the *lowest* format
  compliance (36%), so its usable output was poor. Capability does not equal usable output.
- **Tradeoff:** A lenient parser could "rescue" more answers and inflate scores;
  I chose strict parsing so the metric stays honest.

### 3.3 One container per model, run in parallel

- **Problem:** Running 7 models x 300 puzzles sequentially is slow, and a failure
  in one model's run shouldn't block the others.
- **Decision:** Bake each model into its own Docker image (`MODEL` baked in at
  build via `ARG`), run all of them as independent ECS Fargate tasks in parallel.
- **Why:** Clean isolation, trivial parallelism, and it mirrors how you'd actually
  run an eval fleet in production. Fargate is the right fit because the workload is
  ephemeral: spin up, run, write results, exit. No servers to manage, pay only for runtime.
- **Tradeoff:** More images to build/push than a single parameterized container,
  but the isolation and parallelism are worth it. (The build step is identical, only
  the baked-in `MODEL` differs.)

### 3.4 Reasoning models need fundamentally different handling

- **Problem:** o3 returned *empty* responses at first. It was spending its entire
  token budget on internal reasoning with nothing left for the answer
  (`finish_reason: length`, all tokens consumed as `reasoning_tokens`).
- **Decision:** Detect reasoning models and use `max_completion_tokens` (not
  `max_tokens`), set very high (50k) so there's room for both reasoning and output.
- **Why:** This is a real, non-obvious API difference. Reasoning models have a
  separate token accounting model, and treating them like chat models silently fails.
- **Talking point:** This is a great "I debugged something subtle" story: the
  symptom (empty string) pointed nowhere; reading the raw API response
  (`reasoning_tokens: 4096`, `finish_reason: length`) is what cracked it.

### 3.5 Secrets never touch the image or the repo

- **Decision:** API keys live in AWS Secrets Manager. ECS injects them into the
  container at runtime via the task definition's `secrets` block. `.env` is
  git-ignored; nothing sensitive is ever committed or baked into an image.
- **Why:** Standard security hygiene, and it shows you understand the difference
  between build-time and run-time configuration. The container code is identical
  whether run locally (`.env`) or on ECS (Secrets Manager): it just reads `os.environ`.

### 3.6 Remote Terraform state with locking

- **Decision:** State lives in a versioned, encrypted S3 bucket with native S3
  lockfile locking (`use_lockfile = true`, no DynamoDB needed in modern Terraform).
- **Why:** Local state breaks the moment CI also runs Terraform: you'd get two
  sources of truth and race conditions. Remote state with locking means local and
  CI share one authoritative state and can't clobber each other. Versioning lets
  you roll back a bad apply.
- **Tradeoff:** Slightly more setup, but it's the difference between a toy and
  something a team could actually use.

### 3.7 CI/CD with OIDC instead of long-lived keys

- **Decision:** GitHub Actions authenticates to AWS via OIDC: a short-lived token
  scoped to the specific repo/branch, no `AWS_ACCESS_KEY_ID` stored in GitHub.
- **Why:** No long-lived credentials to leak or rotate; a forked repo can't assume
  the role. This is the current AWS-recommended pattern, and naming it signals you
  keep up with best practices.
- **Two pipelines:** dashboard changes auto-deploy to S3+CloudFront; Terraform
  changes get a `plan` posted as a PR comment and `apply` on merge (GitOps).

### 3.8 A dashboard that updates itself

- **Decision:** The dashboard is a static site that fetches a `manifest.json` from
  S3 at load time, then fetches each listed model's results. `main.py` updates the
  manifest after each run.
- **Why:** Run a brand-new model -> it adds itself to the manifest -> a new tab and
  all the charts appear automatically on refresh. No dashboard code change needed
  to add a model. The data and the presentation are decoupled.
- **Tradeoff:** The browser hits S3 directly (needs CORS + public-read on the
  results prefix only), rather than going through a backend. For non-sensitive
  benchmark data that's the simpler, cheaper choice.

---

## 4. Problems solved (good "tell me about a hard bug" stories)

Pick whichever fits the question. Each is a real debugging arc with a clean resolution.

1. **The empty o3 responses.** Symptom: blank answers. Root cause: reasoning models
   exhaust the token budget on thinking; needed `max_completion_tokens` set high.
   Lesson: read the raw API response, don't trust the convenience field.

2. **The day-long cert that wouldn't validate.** Symptom: ACM cert stuck in
   `PENDING_VALIDATION` for hours, blocking CloudFront. Root cause: I had destroyed
   and recreated the Route53 hosted zone, which got new nameservers, but the domain
   *registrar* still pointed at the old (dead) ones, so the domain resolved nowhere
   and ACM couldn't see the validation record. Fix: repoint the registrar, then
   codify it with `aws_route53domains_registered_domain` so it can never drift again.
   Lesson: DNS delegation has two layers (registrar and zone) that must agree.

3. **Models ignoring the output format.** Symptom: low scores even when the model
   "knew" the answer. Root cause: algebraic notation, capture symbols, prose mixed
   into output. Fix: a tolerant UCI extractor (strip `+`, `#`, `x`, handle
   concatenated moves) plus a dedicated format-compliance metric so the problem is
   *measured*, not just patched.

4. **arm64 vs amd64.** Symptom: images built fine on my M-series Mac but the
   architecture was wrong for Fargate. Fix: `docker build --platform linux/amd64`.
   Lesson: know your target architecture for cloud deployment.

5. **The IAM propagation race in CI.** Symptom: Terraform apply granted a new
   permission and used it in the same run, hitting `AccessDenied`. Fix: re-run (the
   permission propagates in seconds), or split into two applies. Lesson: IAM is
   eventually consistent.

---

## 5. The actual findings (the "research taste" part)

Numbers matter, but the *interpretation* is what shows judgment.

- **o3: 71% accuracy. Every other model: single digits.** The gap is not
  incremental, it's categorical. Reasoning models do genuine lookahead; the rest
  pattern-match one-move mates and collapse on anything requiring search.
- **o3 degrades gracefully.** mate-in-1 95% down to mate-in-5 50%; beginner 83%
  down to expert 56%. The others flatline near 0% past mate-in-1. A smooth difficulty
  curve is itself evidence of real search vs. memorized patterns.
- **The honesty finding.** o3's misses are mostly *explicit refusals* ("I can't
  solve this") or last-move near-misses, not confident hallucinations. That's
  better calibration: a model that knows what it doesn't know. This is the most
  interesting qualitative result and it's invisible in the accuracy number alone.
- **Capability is not usable output.** Opus 4.7 found more mates than any other
  non-reasoning model but its 36% format compliance buried its usable score. A
  benchmark that only measured raw correctness would have missed this entirely.

**The meta-point for an interviewer:** good evals measure more than the headline
number. The format-compliance axis and the qualitative failure-mode analysis are
what turn "o3 scored highest" into an actual finding.

---

## 6. How to present it, by audience

### If the role is eval / research-focused
Lead with **Section 3.1 and 3.2** (the scoring rubric and format compliance), then
**Section 5** (the findings, especially the calibration insight). Frame it as:
"I cared about measuring how models fail, not just whether they pass."

### If the role is infra / platform / DevOps
Lead with **Section 3.3, 3.6, 3.7** (Fargate parallelism, remote state, OIDC CI/CD).
Frame it as: "ephemeral containerized jobs, fully reproducible via IaC, shipped
through GitOps with no long-lived credentials."

### If the role is full-stack / generalist
Walk the whole pipeline top to bottom (Section 2 table), then pick one deep-dive
from Section 3 and one war story from Section 4. Frame it as: "I took it from a CSV
of puzzles to a live, self-updating dashboard on my own domain, owning every layer."

### If they ask "what would you do differently / next?"
Honest answers that show maturity:
- **Run N times per puzzle** for statistical confidence (currently single-shot).
- **Add a stronger parser or constrained decoding** so format failures don't
  conflate with capability for the weaker models.
- **Cost tracking per run** as a first-class metric alongside latency.
- **Stockfish integration** for partial-credit "was this a reasonable move even if
  not the solution," rather than exact-match only.
- **Tighten the CI Terraform role** - it's broad for a solo project; scope it down
  for a shared environment.

---

## 7. Likely interview questions and crisp answers

**"Why chess puzzles?"**
Objective ground truth (one correct line), so eval is automatable with no
human labeling or LLM-as-judge for correctness. And difficulty is quantified
(Elo), so you can measure how performance degrades with hardness.

**"How do you know the models aren't just looking up the answer?"**
They have no internet access, the puzzle IDs aren't in the prompt, and the FEN is
a derived position (after the setup move is applied), not the raw database row. And
if they were looking answers up they'd score 100%, not 6%.

**"Why Fargate and not Lambda / EC2 / EKS?"**
The job is ephemeral and container-shaped: run for a while, write results, exit.
Fargate fits that exactly with no server management and no orchestration overhead.
Lambda's time limits don't suit a multi-hour reasoning run; EC2 means managing
instances; EKS is overkill for a handful of independent tasks.

**"Why did o3 take ~100s per puzzle?"**
It does extended internal reasoning. That's the tradeoff the benchmark surfaces:
o3 is ~10x more accurate but ~100x slower and far more expensive than GPT-4.1. The
"right" model depends entirely on whether you're optimizing for accuracy or cost/latency.

**"What was the hardest part?"**
Pick from Section 4. The cert/DNS one is a good "systems thinking" answer; the o3
empty-response one is a good "debug from first principles" answer.

---

## 8. One-sentence summaries to memorize

- **Eval design:** "I scored models on a four-part rubric so I could measure *how*
  they fail, not just whether they pass."
- **Infra:** "Seven models, each in its own container, run in parallel on Fargate,
  fully provisioned by Terraform with remote locked state."
- **CI/CD:** "GitOps with OIDC: plan on PR, apply on merge, no stored credentials."
- **The finding:** "Reasoning models aren't just better, they fail more honestly:
  o3 refuses when stuck instead of hallucinating."
- **The lesson:** "The metric is the product. A benchmark is only as good as the
  questions it can answer."
