# Healthcare clinical documentation / knowledge agents — first-party research

**Sub-agent deliverable for the AI product-architecture report.**
Scope: (a) **Abridge**, (b) **Nuance DAX / DAX Copilot (Microsoft)**.
Research date: 2026-09-17. All facts below were read from first-party pages in this session; nothing is from memory.

---

## 0. Method, marker legend, and honesty caveats

### Marker legend (strict)

| Marker | Meaning |
|---|---|
| `已打开` | I fetched this URL in this session with an HTTP GET (`web_fetch` tool, or a direct HTTP fetch whose extracted body text I read). |
| `已打开(API)` | I read the record through a **first-party** machine API rather than the HTML page (NCBI E-utilities for PubMed records; openFDA for device clearances). The underlying record is the same one the HTML page serves. |
| `[已确认存在，未逐页打开]` | The URL was returned by a first-party index/sitemap/search API and I confirmed it resolves, but I did **not** read its body. |
| `[推断]` | My inference, not stated by the source. |

### Search-tooling caveat (affects coverage honesty)

`web_search` was unavailable for the entire session — its only engine (Firecrawl keyless) returned `429 Too Many Requests` with `retry_after_seconds: 86381` (~24 h). `exa_search` was unavailable (no API key). Direct alternate engines behaved badly: Brave Search returned `429`; Bing returned topically unrelated results (recipe subreddits for a clinical-AI query) and was unusable. I therefore built coverage from **first-party discovery surfaces instead of a general web index**:

- `sitemap.xml` / `robots.txt` enumeration (Abridge: 556 URLs enumerated).
- `learn.microsoft.com/api/search` (Microsoft's own docs search).
- `news.microsoft.com/?s=` (Microsoft's own news search).
- **NCBI E-utilities** (PubMed esearch/esummary/efetch) for the peer-reviewed literature.
- **openFDA** device/510(k) API for regulatory status.

Consequence: the study list below is close to exhaustive for **PubMed-indexed** work, but I cannot rule out first-party pages (vendor blogs, help centers, press releases) that no sitemap or docs TOC links to.

### Company-structure caveat (materially affects target (b))

**Nuance's healthcare web estate no longer exists as a standalone site.** Verified by redirect probe (`已打开`):

- `https://www.nuance.com/` → **301 →** `https://dragon.nuance.com/en-us/home`
- `https://www.nuance.com/healthcare.html` → **301 →** `https://www.microsoft.com/en-us/health-solutions`
- `https://www.nuance.com/healthcare/provider-solutions/clinical-documentation/dragon-medical-one.html` → **301 →** `https://www.microsoft.com/en-us/health-solutions`

So "Nuance DAX / DAX Copilot" must be researched as **Microsoft Dragon Copilot**, which Microsoft describes as the merger of the two Nuance products (`已打开`, security whitepaper):

> "Microsoft Dragon Copilot brings together the trusted voice dictation capabilities of Dragon Medical One and the ambient listening capabilities of DAX Copilot with fine-tuned generative AI and healthcare-adapted safeguards."

Both companies are **private/absorbed**, so architectural disclosure is asymmetric and incomplete:

- **Microsoft** publishes an unusually deep public docs set (transparency notes, privacy/security/data-collection whitepapers, a partner SDK with a documented JSON payload and ontology). This is the best-documented part of the whole report.
- **Abridge** publishes science/whitepaper/evaluation material but **no public API, integration, or deployment documentation**. Its engineering blog is JS-rendered and its `/blog` index returns only a 354-character shell (`已打开`, `https://tech.abridge.com/blog`), so post-level URLs were discovered via the corporate sitemap. Where Abridge is silent I say so rather than inferring.

---

# PART A — ABRIDGE

## A1. What problem it solves + target user

**One sentence.** Abridge turns the clinician–patient conversation into a structured, auditable, billable draft clinical note (and, since ~2025, into in-workflow clinical decision support), so the clinician reviews and signs rather than types.

**Target users** — the product is explicitly segmented into three "tailored experiences" (`已打开`, `https://www.abridge.com/`):

| Experience | Positioning line (verbatim) |
|---|---|
| Clinicians | "AI-powered clinical documentation, built for accuracy" |
| Revenue Cycle | "Billable documentation, automated from the start" |
| Nursing | "Natural conversations, turned into draft documentation" |

Plus two capabilities sold on top: **Clinical Decision Support (CDS)** ("Context-aware evidence") and **Care Signals** ("The right conditions addressed in the visit").

Scale claims (vendor-stated):
- "More than **300 enterprise health systems** have launched Abridge's clinical intelligence for context-aware decision support." (`已打开`, `https://www.abridge.com/cds`)
- "Abridge has been implemented at **150+ enterprise health systems** and will support **50 million conversations in 2025**." (`已打开`, `https://www.abridge.com/reports/adoption-scale-impact`)

---

## A2. Knowledge-base LAYERING in Abridge's OWN terminology

Abridge's umbrella term is the **Abridge Contextual Reasoning Engine**. From the dedicated page (`已打开`, `https://www.abridge.com/abridge-contextual-reasoning-engine`), with attributions to CEO **Shivdev Rao, MD** and Chief Scientist **Zachary Lipton, PhD**:

> "That's what our Contextual Reasoning Engine allows for, intelligently associating what's going on in this conversation with all these other pieces of information." — Shiv Rao, MD

> "We're pulling in all kinds of data, metadata, insights, information from any number of seemingly disparate sources." — Zack Lipton, PhD

| # | Layer (Abridge's own term) | Verbatim product wording | Where it appears |
|---|---|---|---|
| 1 | **Conversation / ambient layer** | "anchoring on the conversation, **the most human signal in healthcare**"; principle: "**Conversation Comes First**" | `已打开` `https://www.abridge.com/vision` (nav); `已打开` `https://www.abridge.com/blog/building-trusted-healthcare-ai` |
| 2 | **Note-generation pipeline + specialty models** | "the inner workings of our **note-generation pipeline**"; "**specialty-specific model updates**"; section-shaping "**recipes**"; cross-functional "**NoteGen teams**" | `已打开` `.../ai/science-confabulation-hallucination-elimination`; `已打开` `https://www.abridge.com/blog/clinical-ai-specialty-models` |
| 3 | **Contextual Reasoning Engine → EHR CONTEXT** | "Contextual awareness beyond the conversation with **dynamically integrated data from previous patient encounters, health system-specific guidelines, and clinician preferences**." | `已打开` `.../abridge-contextual-reasoning-engine` |
| 4 | **Contextual Reasoning Engine → PREDICTED PROBLEMS** | "Capture more precise problems by recognizing and **grouping medical problems with language that aligns with appropriate billing codes**." | same page |
| 5 | **Contextual Reasoning Engine → ORDERS** | "capturing **EMR-integrated and actionable outputs, like medical orders, for clinician review**." | same page |
| 6 | **Contextual Reasoning Engine → CODING** | "**auditable notes, tying AI-generated outputs to source information across all input data—powered by Linked Evidence**." | same page |
| 7 | **Linked Evidence** (the evidence-link / provenance layer) | "**Linked Evidence**, which enables clinicians to see evidence for each AI-generated summary"; "Abridge-generated draft clinical documentation is **traceable to the source conversation**" | `已打开` `.../ai/science-confabulation-hallucination-elimination`; `已打开` `.../blog/building-trusted-healthcare-ai` |
| 8 | **Claim-verification guardrail layer** | in-house "**task-specific language model**" that detects and scores each claim's support, then an automated **correction** system | `已打开` `.../ai/science-confabulation-hallucination-elimination` |
| 9 | **Knowledge / external-evidence layer (CDS)** | "**Content Sources** … insights from leading sources of medical evidence" | `已打开` `https://www.abridge.com/cds` |
| 10 | **Template / personalization layer** | "let clinicians **personalize their notes**"; style preferences; saved prompt library | `已打开` `https://www.abridge.com/blog/clinical-ai-specialty-models`; `已打开` `.../blog/how-we-evaluate-clinical-decision-support-for-enterprise-readiness` |

### Layer 9 in detail — the licensed medical-knowledge corpus (named partners)

`已打开`, `https://www.abridge.com/cds` and `已打开`, `https://www.abridge.com/blog/building-trusted-healthcare-ai`:

- **UpToDate** (Wolters Kluwer) — "**our first high-quality data partner**"; "integrating UpToDate's gold-standard content"
- **NEJM Group** (The New England Journal of Medicine) and **JAMA Network**
- **American Heart Association** — with the disclosure footnote "*American Heart Association licenses selected scientific content to Abridge."
- **American Diabetes Association**, **American Academy of Family Physicians**, **EBMcalc**

Abridge frames the CDS interaction as deliberately outside the note: "this capability lives within Abridge's interface, **not the documentation itself**" (`已打开`, CDS evaluation blog).

---

## A3. Corpus governance

### A3.1 What the "corpus" actually is — Abridge runs **two** distinct corpora

| Corpus | Content | Evidence |
|---|---|---|
| **Patient-chart context corpus** | prior encounters, medications, labs, "the patient conversation and clinical history" | `已打开` `https://www.abridge.com/cds`: "Abridge draws on the patient conversation and clinical history to deliver insights specific to the patient—**medications, labs, and clinical context are already there**." |
| **Licensed medical-knowledge corpus** | UpToDate, NEJM, JAMA, AHA, ADA, AAFP, EBMcalc | `已打开` `https://www.abridge.com/cds` (Content Sources marquee) |

### A3.2 Ingestion / EHR integration

**FACTS (`已打开`):**
- "Abridge seamlessly integrates with leading EHRs to streamline documentation, billing, and coding." — `https://www.abridge.com/press-release/abridge-becomes-epics-first-pal-bringing-generative-ai-to-more-providers-and-patients`
- **Epic Partners and Pals**: "Abridge … is now the **first Pal in Epic's Partners and Pals program**" (Aug 16, 2023). Quote from Epic VP Alan Hutchison on the program. Same page also announces an Emory Healthcare enterprise agreement (3,450+ clinicians, 3 years), and prior deployments at The University of Kansas Health System and UPMC.
- **Epic Workshop** (nursing): "Developed as part of the next phase of collaboration in the **Epic Workshop program**" — Abridge + Mayo Clinic + Epic nursing ambient documentation (Jul 23, 2024). `https://www.abridge.com/press-release/abridge-mayo-epic`
- **Supported EMR list** (from Abridge's own gated-report form, i.e. a first-party enumeration): **Epic, Athena, AllScripts, Cerner, eClinicalWorks, NextGen, Other** — `已打开` `https://www.abridge.com/reports/adoption-scale-impact` (form markup), same list on `/reports/science-of-ambient-ai-evaluation`.
- Integration depth claim: "Deeply integrated EHR tools take up to **75% less time** for a physician to use than an external app or web site." (cited to a Penn study footnote, not to Abridge's own measurement) — same Epic PALS release.
- Implementation-speed claim: "a simplified, consistent experience after as little as **two weeks of implementation**." — same release.

**未找到公开资料:** Abridge publishes **no FHIR or HL7 interface specification, no SMART-on-FHIR launch documentation, and no resource-level integration contract**. No equivalent of Microsoft's public `Dragon standard payload` exists on abridge.com. (Contrast Part B, §B2.)

### A3.3 Refresh

- Specialty model updates: "When these model updates are ready, they are shipped '**quietly**,' which is to say **without build, configuration, or workflow disruption**. Health systems are not asked to implement new versions. Clinicians are not prompted to update apps." (`已打开`, `https://www.abridge.com/blog/clinical-ai-specialty-models`)
- CDS content: licensed content is refreshed by the partners; Abridge's own statement is only that it maintains a "growing body of sources" (`已打开`, CDS evaluation blog). **Specific refresh cadence: 未找到公开资料.**

### A3.4 Retention, residency, training — the honest reading

**Retention**
- Customer Data (which "may include Protected Health Information (PHI)") is "governed **exclusively** by the terms of our agreements with those customers, including our **Business Associate Agreements (BAAs)**." (`已打开`, `https://www.abridge.com/privacy`)
- General retention: "We retain personal information for as long as needed to fulfill the purposes for which it was collected, or as required by our legal obligations." (`已打开`, same)
- **Biometric/voiceprint carve-out** (consumer/Abridge Scan side): "We retain, and securely store, your **voiceprint** only as long as needed to provide the feature to you. We will permanently destroy it … (**one year after your last use of the mobile application**), whenever your account is deleted, or upon your request." (`已打开`, same)

**Data residency** — **未找到公开资料.** Abridge's public pages give no per-geography data-at-rest table and no EU-data-boundary statement. This is a genuine public-information gap, and it is a *sharp* contrast with Microsoft (Part B, §B3).

**Training on customer data — read this carefully, it is more nuanced than the marketing line**

FACTS:
- CDS page: "Patient data where it belongs — **Queries run entirely inside Abridge's architecture. PHI never leaves it and is never used for training.**" (`已打开`, `https://www.abridge.com/cds`)
- Engineering blog: "Our offline evaluations rely on datasets curated from **de-identified Abridge encounters**." and "For many of our internal datasets and benchmarks, we collect annotations on **de-identified encounters** where Abridge was used." (`已打开`, `https://tech.abridge.com/blog/ai-evaluation-at-abridge`)
- Evaluation science page: stratified evaluation "require[s] high-quality metadata (e.g. on patient demographics) that are not reliably captured in conversations, but can in many cases be pulled … **via integration with the EHR**." (`已打开`, `https://www.abridge.com/ai/science-ai-evaluation`)
- The BAA permits the Business Associate to "**Use PHI for purposes of de-identification of the PHI**" (§2.2.4). (`已打开`, `https://www.abridge.com/terms/business-associate-agreement`)

`[推断]` Abridge's public position is therefore **narrower than a blanket "we never train on customer data"**: (i) the explicit never-for-training claim is scoped to PHI in the CDS query path; (ii) de-identified Abridge encounters *are* used for evaluation datasets and clinician annotation; (iii) the BAA explicitly authorises de-identification as a permitted use. Abridge does **not** publish a Microsoft-style sentence of the form "our models are trained solely on X." Anyone writing the report should attribute the "never used for training" line to the CDS page and not generalise it.

---

## A4. Permissions / ACL

### A4.1 The primary instrument is the BAA, and it is unusually detailed

`已打开`, `https://www.abridge.com/terms/business-associate-agreement` (Abridge = "Business Associate", customer = "Covered Entity"). Concrete, quotable obligations:

| Clause | Obligation |
|---|---|
| §2.1 | "Business Associate shall **not Use or Disclose PHI** received, accessed, maintained, or created for or on behalf of Covered Entity **except in accordance with any Underlying Agreement**, or as permitted by this BAA or Required by Law." |
| §2.2.2 | Use/Disclose PHI to carry out BA's legal responsibilities, with a confidentiality flow-down to the recipient |
| §2.2.4 | "Use PHI for purposes of **de-identification** of the PHI" — an explicitly permitted use |
| §2.3 | "comply with **Subpart C of 45 C.F.R. Part 164**" (the HIPAA Security Rule) |
| §2.4 | Notify Covered Entity of any non-permitted Use/Disclosure and each Security Incident **within 10 business days** of awareness; written Breach report **no later than 30 calendar days** after discovery |
| §2.6 | Subcontractor flow-down: obtain "reasonable assurances" that agents/subcontractors adhere to substantially similar restrictions |
| §2.8 | Designated Record Set available for inspection/copying within **15 business days** of request |
| §2.9 | Records available to the HHS Secretary (at Covered Entity's cost above normal service parameters) |
| §2.10 | Accounting of disclosures support within **30 days** |
| §3.4 | Customer warrants it "has obtained any necessary authorizations, consents, and other permissions" before placing PHI on Abridge systems |
| §4.3 | On termination, return or destroy all PHI; "Business Associate shall retain **no copies**" |
| §4.4 | **Carve-out**: the parties agree that return/destruction is generally *infeasible*, and the BA "will need to retain such PHI" |

### A4.2 Product-side privacy control

- "Queries run **entirely inside Abridge's architecture**." (`已打开`, `https://www.abridge.com/cds`) `[推断]` This is a data-egress control, not an access-control mechanism: it asserts the PHI does not reach an external model provider.
- "Insights are grounded in each patient's clinical history, with **citations linked to original data in the EHR**." (`已打开`, same)

### A4.3 Role-based chart access

**未找到公开资料.** Abridge publishes nothing about how chart-level or role-based access is enforced, whether it is inherited from the EHR session, how SSO works, or what its admin console does. `[推断]` Given the Epic PALS/embedded posture and the absence of any Abridge-side access-control documentation, chart ACL is most likely delegated to the host EHR — **but I could not verify this and it must not be stated as fact.**

---

## A5. Evaluation

### A5.1 Automated / offline

`已打开`, `https://www.abridge.com/ai/science-ai-evaluation`:

- Internal benchmark dataset = "**clinical audio, gold standard transcripts, human-written reference notes, and rich metadata on patient characteristics**."
- ASR metrics: "**word error rate** and medically tailored metrics (e.g., **recall of medical terms**)"; plus "capture of newly minted medication names."
- Note-generation metrics: "variants of **precision and recall (e.g., of medical concepts)**, which serve as proxies for **factuality and completeness**."
- Stratified analysis "to assess performance across diverse patient subpopulations."
- ASR calibration against public sets: "On generic speech corpora (e.g., the public **Librispeech** benchmark dataset), our ASR system performs comparably to state-of-the-art ASR models like **Whisper v3 from OpenAI**." Multilingual: "One of the datasets we use in evaluation is **FLEURS**, a parallel speech dataset in 102 languages."
- Explicit scope limit: "Abridge is **not designed to serve as a translation service**, and it is no substitute for a trained medical interpreter … Our note-generation pipeline attempts to render a note in English only."

### A5.2 Online / production metrics — the only hard numbers Abridge publishes

`已打开`, `https://www.abridge.com/ai/science-ai-evaluation`:

- Primary end-to-end metric: clinician **star ratings 1–5** in the note-editing interface.
- "over the last three months (May-July), we collected **tens of thousands of star ratings, with an average rating of 4.3 out of 5 for English-language encounters**."
- Spanish: "risen from an average of **3.7 during the month of February to its current average of 4.1**."
- Passive signal: "the **edits required to finalize the note**"; active: comments and star ratings.

### A5.3 Human review

- "Before we release any major model updates, we perform **blinded head-to-head evaluations with our own clinical staff**."
- Guardrails are "supported by **over one thousand hours of human validation**." (`已打开`, confabulation whitepaper)
- Clinician review is mandatory and non-optional: "**All clinician notes generated by Abridge are reviewed and edited** (if necessary) by the clinicians who conducted the patient encounter before being entered into the EHR." (`已打开`, confabulation whitepaper)

### A5.4 The confabulation/hallucination result (the single most quotable Abridge metric)

`已打开`, `https://www.abridge.com/ai/science-confabulation-hallucination-elimination`:

- Method: "an **in-house, task-specific language model** trained on a curated set of **over 50,000 training examples** … designed to **detect and assess the level of support of each claim** in the note, and to produce detailed reasoning for its assessment."
- Then: "Once a claim is detected and assessed as being unsupported, then we **correct it using another automated system** … to determine the best way to resolve the confabulation, among several options."
- Benchmark result: "our technology … **catching 97% of the confabulations, while GPT-4o only catches 82%**. In other words, a standard off-the-shelf model misses **six times as many** confabulations as the Abridge system."
- Honest caveat Abridge itself states: "**No guardrail is perfect**, and clinical conversations can contain legitimate sources of ambiguity, for instance, where the 'correct' note may rely on clinical judgements that were not verbalized during the encounter."
- Failure mode they name explicitly: **speaker misattribution** ("it is not entirely clear from the transcript alone if a statement is made by the patient, the clinician, or a caregiver" → e.g. "patient reports that their dog is sick").

### A5.5 Specialty-model validation ("the gauntlet")

`已打开`, `https://www.abridge.com/blog/clinical-ai-specialty-models` — a **three-layer** validation stack:

1. **Automated "Judge" layer** — LLM judges scoring at least two named variables: "**Non-Inferiority**: Strict safeguards that ensure new specialty models match or exceed the generic baseline performance" and "**Misattribution Rates**: Monitoring against 'hallucinations' or misattributed patient data."
2. **Clinical Success Directors** evaluating "real-world examples against a predefined, data-driven baseline."
3. **External third-party auditors** reviewing "hundreds of additional examples."
4. "**Only when a model clears every layer** do we consider deploying."

Development process: "'**clinician-in-the-loop**' process pairs product and engineering leads with Clinician Science and Clinical Success Directors in cross-functional collaborations we call '**NoteGen**' teams … we refine the underlying '**recipes**' that shape how different sections of notes are generated."

### A5.6 CDS evaluation (three dimensions) — with a numeric safety score

`已打开`, `https://www.abridge.com/blog/how-we-evaluate-clinical-decision-support-for-enterprise-readiness`:

| Dimension | Method | Result |
|---|---|---|
| **Clinical Evaluations** | rubric built by multiple physicians independently reviewing real de-identified encounters, calibrated to a common rubric; "**over 1,000 rubrics** — a material increase over the size of existing benchmarks that use real encounters, like the **NOHARM study**" | — |
| **Boundary Adversarial Evaluations** | "directly harmful prompts, scope violations, attempts to bypass clinical judgment, discriminatory care scenarios, jailbreaks, and medicolegal edge cases" | — |
| **Clinical Safety Evaluations** | "wrong drugs, missed critical diagnoses, harmful management advice, and medical misinformation. Flagged cases are manually reviewed by clinicians." | "The system currently scores **99.5% across 1,000+ cases**. In the small number of cases where potential safety issues were identified, **most have been due to limitations in source material**." |

Rollout discipline: internal testing → "a small group of clinicians at **highly-engaged preview partners**" → "entire departments at designated organizations" → GA. "We maintain the ability to **tune or roll back at any stage**."

Honest caveat: these are **vendor-published, vendor-designed evaluations**. None of the three CDS evaluations is described as externally audited or peer-reviewed, and the 99.5% figure has no confidence interval or denominator breakdown published.

### A5.7 Peer-reviewed publications (Abridge's own list)

`已打开`, `https://www.abridge.com/ai/publications` — Abridge lists 16 external publications. The most architecturally relevant:

- Krishna K, Khosla S, Bigham J, Lipton ZC. **"Generating SOAP Notes from Doctor-Patient Conversations Using Modular Summarization Techniques."** ACL 2021.
- Ramprasad S, Ferracane E, Lipton ZC. **"Analyzing LLM Behavior in Dialogue Summarization: Unveiling Circumstantial Hallucination Trends."** ACL 2024.
- Khosla S, Vashishth S, Lehman JF, Rose C. **"MedFilter: Improving Extraction of Task-relevant Utterances through Integration of Discourse Structure and Ontological Knowledge."** EMNLP 2020. ← *the only Abridge-linked paper that explicitly names an **ontological knowledge** component.*
- Schloss BJ, Konam S. "Towards an Automated SOAP Note: Classifying Utterances from Medical Conversations." MLHC 2020.
- Mani A, Palaskar S, Meripo NV, Konam S, Metze F. "ASR Error Correction and Domain Adaptation Using Machine Translation." ICASSP 2020.
- Konam S, Rao S. "A Mission Driven Approach to Machine Learning for Healthcare Conversation." *Journal of Commercial Biotechnology*, 2021.

Two whitepapers (both by Oberst / Liang / Lipton): **Part I — "Pioneering the Science of AI Evaluation"** (Sep 19, 2024); **Part II — "The Science of Confabulation Elimination"** (Aug 19, 2025). `已打开`, `https://www.abridge.com/whitepapers`

**Correction to the brief:** the search prompt asked for "Abridge medical ontology". **Abridge does not appear to market an "Abridge medical ontology" as a named product layer.** The only ontology-adjacent artefact I can evidence is the 2020 EMNLP MedFilter paper (ontological knowledge for utterance extraction) and the coding-alignment wording under PREDICTED PROBLEMS/CODING ("language that aligns with appropriate billing codes"). **"Abridge Enterprise"** likewise does not appear as a current named product on the site — the equivalent historical artefact is the **2021 Series A press release** "launches **enterprise solution**" (`[已确认存在，未逐页打开]`, `https://www.abridge.com/press-release/abridge-secures-12-5m-in-funding-and-launches-enterprise-solution-to-combat-physician-burnout-in-healthcare-and-help-patients-stay-on-top-of-their-health`).

### A5.8 Regulatory (FDA) status

**openFDA 510(k) API — `已打开(API)`, `https://api.fda.gov/device/510k.json?search=applicant:%22Abridge%22&limit=20` → `{"error":{"code":"NOT_FOUND","message":"No matches found!"}}`.**

`[推断]` Abridge holds **no FDA 510(k) clearance** under that applicant name, and abridge.com contains **no FDA-clearance, De Novo, or regulatory-pathway statement** anywhere I fetched. Abridge positions the product as clinician-reviewed assistive documentation, not as a regulated device. **未找到公开资料** for any Abridge regulatory filing.

### A5.9 Independent (non-vendor) evaluation of Abridge

Only one head-to-head study I found names Abridge (see §B5, Webb 2026): a UT Southwestern ED crossover of **DAX vs Abridge** in which adjusted models suggested the differences "reflected **order effects** more than inherent tool differences."

---

## A6. Key design decisions (Abridge)

1. **Anchor the product on the conversation, not the chart.** "Conversation Comes First … what happens in the room between a clinician and a patient is the most valuable signal in healthcare." Everything downstream (note, coding, orders, CDS) is derived from that one ground truth, which is why the CRE can claim it is "intelligently associating what's going on in this conversation with all these other pieces of information." (`已打开`, `.../blog/building-trusted-healthcare-ai`; `.../abridge-contextual-reasoning-engine`)

2. **Make provenance a shipped feature, not a promise.** **Linked Evidence** exists both as a clinician-facing trust feature *and* as an internal evaluation accelerant: "we continue to invest in making human evaluation easier to perform with dedicated tools like our Linked Evidence feature." (`已打开`, `.../ai/science-ai-evaluation`)

3. **Buy the medical-knowledge layer instead of building it.** Abridge licensed UpToDate, NEJM, JAMA, AHA, ADA, AAFP, EBMcalc rather than training its own medical knowledge base. `[推断]` This shifts the hallucination surface from "does the model know medicine" to "did retrieval return the right source," and it is consistent with their own diagnosis of residual CDS safety failures as "limitations in **source material**."

4. **Treat specialty as a model dimension with a non-inferiority gate, not as a template setting.** Specialty updates are validated by an automated Judge layer (Non-Inferiority + Misattribution Rates), then Clinical Success Directors, then third-party auditors, and are then shipped "quietly" with no customer-side build or config. (`已打开`, `.../blog/clinical-ai-specialty-models`)

5. **Keep CDS outside the note.** "this capability lives within Abridge's interface, **not the documentation itself**, clinicians can choose whether to act on or incorporate the surfaced information." (`已打开`, CDS evaluation blog) `[推断]` This is a regulatory-boundary decision as much as a UX one: keeping generated advice out of the medical record keeps the product on the assistive side of the device line (§A5.8, §B5 regulatory).

---

# PART B — NUANCE DAX / DAX COPILOT → MICROSOFT DRAGON COPILOT

## B1. What problem it solves + target user

**One sentence.** DAX Copilot (now Dragon Copilot) ambiently captures the patient encounter, transcribes and diarizes it, and generates a specialty-shaped draft note (or nursing flowsheet rows) that the clinician reviews and signs into the EHR.

**Naming trajectory (verified).** Nuance DAX → "DAX Copilot" → **March 3, 2025**: merged with Dragon Medical One into **Microsoft Dragon Copilot** (`已打开`, `https://news.microsoft.com/source/2025/03/03/microsoft-dragon-copilot-provides-the-healthcare-industrys-first-unified-voice-ai-assistant-that-enables-clinicians-to-streamline-clinical-documentation-surface-information-and-automate-task/`):

> "the first AI assistant for clinical workflow that brings together the trusted natural language voice dictation capabilities of **DMO** with the ambient listening capabilities of **DAX**, fine-tuned generative AI and healthcare-adapted safeguards. Part of **Microsoft Cloud for Healthcare** …"

**Target users and access surfaces** (`已打开`, `https://www.microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot` FAQ):

| Role | Access surface | Availability |
|---|---|---|
| **Physicians** | "web browser, mobile app, desktop application, and **embedded within supported EHRs such as Epic**" | US, Canada, UK, Ireland, France, Germany, Austria, Belgium, Netherlands, Switzerland |
| **Nurses** | "embedded EHR mobile solutions (such as **Epic Rover**) and desktop application" | **United States only** |
| **Radiologists** | "desktop companion integrated with **PowerScribe One**" | **US, preview** |

**Vendor-stated scale** (`已打开`, March 2025 launch release): "DAX's ambient AI technology, which has assisted **over 3 million ambient patient conversations across 600 healthcare organizations in the past month alone**"; DMO "has helped clinicians document **billions** of patient records."

**Vendor-stated outcomes from the same release, with the footnoted source instruments** — note these are **surveys, not trials**:

| Claim | Source footnote (verbatim) |
|---|---|
| "clinicians reporting **five minutes saved per encounter**" | "[1] Microsoft survey of **879 clinicians across 340 healthcare organizations** using DAX Copilot; July 2024" |
| "**70%** of clinicians reporting reduced feelings of burnout and fatigue" | "[2] … same survey; July 2024" |
| "**62%** of clinicians stating they are less likely to leave their organization" | "[3] … same survey; July 2024" |
| "**93%** of patients report a better overall experience" | "[4] Survey of **413 patients** conducted by multiple healthcare organizations whose clinicians use DAX Copilot; June 2024" |

---

## B2. Knowledge-base LAYERING in Microsoft's OWN terminology

This is the best-documented part of the report. Sources: the Dragon Copilot docs TOC (`已打开(API)`, `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/toc.json`), the SDK glossary (`已打开`, `.../sdk/glossary`), the payload/ontology docs (`已打开`, `.../sdk/partner-apis/dragon-data-exchange/dragon-standard-payload/ontology/`, `.../ontology/coding-systems`, `.../resources/context`), the whitepapers (`已打开`, `.../whitepapers/transparency`, `.../whitepapers/transparency-information-assist`, `.../whitepapers/data-collection`), and `.../specialty-models/specialty-specific-content`.

| # | Layer (Microsoft's own term) | Verbatim definition / wording | Where |
|---|---|---|---|
| 1 | **Capture layer — `Dictation` vs `Ambient recording`** | "Dictation: Capturing audio from a **single clinician**, so that the Dragon Copilot system can perform real-time speech recognition and return recognition results to the text cursor." / "Ambient recording: Capturing audio from **multiple speakers** during a patient visit." | `.../sdk/glossary` |
| 2 | **Session / recording / encounter envelope** | "`Session`: A **bundle of recordings** associated with a specific encounter." "`Recording`: … Multiple recordings can be generated for a single encounter." "`Encounter`: An interaction between a patient and healthcare providers…" | `.../sdk/glossary` |
| 3 | **Transcription layer (ASR/STT) with diarization** | "Speech-to-text (STT) converts single or multiparty speech into text, including unspoken punctuation and **speaker role identification**." Reliability range: "Ambient diarized speakers **≤ 2** — One speaker (the clinician) is identified as **primary**. All other speakers are **aggregated**." | `.../whitepapers/transparency` |
| 4 | **Generation layer — `Ambient note generation` (physicians) and `Flowsheet capture` (nurses)** | "Ambient note generation (physicians): Capability that records a natural physician–patient dialogue and produces a **draft clinical note** summarizing the encounter." / "Flowsheet capture (nurses): … produces draft flowsheet documentation based on audio inputs and **enabled customer flowsheet templates**." | `.../whitepapers/transparency` |
| 5 | **Generative-AI layer** | "Generative AI: **Large-language-model (LLM) functionality** that can create, transform, or summarize clinical content when **triggered by templates or free-form prompts**." | `.../whitepapers/transparency` |
| 6 | **Specialty-model layer** | "All specialties are supported … however the following specialties have been **optimized** based on customer feedback, industry standards and best practices." **46 optimized specialties for English US/CA** (Addiction Medicine → Urology), 7 for English UK, 6 Dutch, 5 German, 8 French. Separate doc: "**Intelligent diagnoses retrieval from Epic**." | `.../specialty-models/specialty-specific-content`; `.../specialty-models/intelligent-diagnoses-retrieval` |
| 7 | **Payload layer — `Dragon standard payload`** | "`Payload`: A JSON file consisting of content generated for a specific use case from a session. Each new recording triggers the creation of a new payload." | `.../sdk/glossary` |
| 8 | **Ontology / resource layer** | "`Resource`: **The standards used to describe a category of AI-generated healthcare data.** Each resource contains data elements necessary for communicating clinical concepts. For example, a clinical document section resource (such as **HPI**) can be imported into a note template, or a **condition resource** can supplement a problem list." Content types: `document_section`, `condition`, `order.{type}`. | `.../sdk/glossary`; `.../dragon-standard-payload/resources/context` |
| 9 | **Coding-systems sub-layer** | Context `codes` are "**LOINC or SNOMED-CT** Codes." Worked example: HPI → `{"identifier":"10164-2","system":"loinc.org"}` with `spoken_forms: ["history of illness","HPI","history","history of present illness","subjective"]`. | `.../dragon-standard-payload/resources/context`; `.../ontology/coding-systems` |
| 10 | **Evidence/relationship-LINK layer** | "**Resources can be linked to other resources.** For example, an **order resource can be linked to a condition resource as the reason for placing the order**." Clinical resource types include Document sections, Conditions, and Orders (Medication, Procedure, Laboratory, Imaging, Follow-up, Consultation/referral, Study, Dietary, Device, Immunization, Therapy, Activity). | `.../sdk/glossary`; docs TOC |
| 11 | **EHR patient-context layer (`Context`)** | **Optional service data**: "**FHIR, HL7, and/or EHR resources for Patient, Practitioner, and Encounter** … is needed by Dragon Copilot to **accurately generate and contextualize clinical content**, as well as to enable seamless workflow integration." Caveat: "Patient identifiable information such as **name, DOB and MRN is associated with the generated AI draft**." | `.../whitepapers/data-collection` |
| 12 | **External-knowledge / RAG layer — `Information Assist`** | "access to **external information from trusted sources**, directly through the application … powered by **Microsoft Azure Healthcare Agent Service**, which orchestrates the response to an **approved, vetted, and tested external source**." Retrieval behavior: "Searches will provide the **top three sites** from those in scope, prioritizing based on **search engine ranking**"; "Only **web-based data** are available to search (**PDFs referenced by websites are not currently in scope**)." | `.../whitepapers/transparency-information-assist` |
| 13 | **Clinical Safeguards engine** | "All Healthcare Agent Services are also passed through a **Clinical Safeguards engine** which filters for **harmful/non-healthcare related content, hallucinations, and omissions** and assures **provenance, verification, and clinically contextualized responses**." | `.../whitepapers/transparency-information-assist` |
| 14 | **RAI guardrail stack** | Named components, in order: **Guardlist** (hate/sexual/violence/self-harm/protected material/prompt-injection word list) → **Azure Content Safety** (harm scores) → **Dynamic Blocklist** → **Allow list** ("specifically created for the Dragon Copilot workflow to allow words flagged by Guardlist that are deemed necessary") → **Intent Classification Module** ("rejects prompts that are irrelevant … non-medical related, related to medical advice, or clinical decision-making") → **Context Grounding** → post-response re-run of the same checks → **Prompt Injection checks**. Plus **Azure OpenAI Service classifiers** as the content filter. | `.../whitepapers/transparency` |
| 15 | **Extension layer (AI apps and agents)** | Partner AI apps/agents connected into Dragon Copilot via a **technical configuration package** and **adaptive cards**; the **healthcare agent service in Copilot Studio** reached GA. Named partners: Elsevier, OpenEvidence, Wolters Kluwer UpToDate (clinical content); Atropos Health (CDS); Canary Speech (vocal biomarkers); Lightbeam (at-risk populations); Pangaea (care gaps); Ensemble, Regard, RhythmX AI (revenue cycle); Cohere Health, Humata Health, Rhyme (prior auth); Press Ganey (patient experience); Artisight, hellocare.ai (smart hospital / virtual care). | `已打开`, `.../extensions/development-concepts`; `已打开`, Oct 2025 nurses/partners release |

### The single most important ACL-relevant line in the whole Microsoft stack

**Context Grounding** (`已打开`, `.../whitepapers/transparency`):

> "**The context provided to the LLM is grounded in specific note data. External sources and data from other sessions are not allowed.**"

`[推断]` This is a *session-scoped context ACL enforced at prompt-construction time* — a different mechanism from role-based access control. It is the architectural answer to "can the model see other patients": the retrieval/context window is hard-scoped to the current session's note data.

---

## B3. Corpus governance

### B3.1 What the corpus is — Microsoft splits it into **required** vs **optional** service data

`已打开`, `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/data-collection`:

**Required service data** ("the **minimum data necessary** to deliver clinical drafts, documentation, and other AI features"):

| Category | Description |
|---|---|
| Health data pertaining to patients | "the **encounter audio, generated transcript, and all versions of edited AI drafts and extracted data**"; examples include "the clinical documentation including the **clinician corrections**, in-app generated patient instructions, and the **final, signed clinical documentation**" |
| Dictation audio | clinician audio for dictated documentation |
| Medical personnel / authorized user information | "the user's name, clinical specialty or license, and email address" |
| Usage analytics | exam/assessment counts, recording length, processing time, AI services used |
| Product feedback | "**clinical AI draft ratings and feedback, which is collected to continuously improve AI accuracy**" |
| Product configuration and settings | "organization details, enabled features, and **organization-wide templates**" |
| Service diagnostics | logs, version data, end-user device info |
| Desktop app diagnostics (physicians) | app interaction logs "to provide support for **EMR text injection**" |

**Optional service data** — this is the EHR patient-context layer:

> "**FHIR, HL7, and/or EHR resources for Patient, Practitioner, and Encounter** … needed by Dragon Copilot to **accurately generate and contextualize clinical content**, as well as to enable seamless workflow integration." Example given: "Patient identifiable information such as **name, DOB and MRN** is associated with the generated AI draft."

### B3.2 Training on customer data — **the accurate statement is NOT "no training on customer data"**

`已打开`, `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/privacy` (last updated 2026-08-20). Verbatim, in order:

> "Microsoft **securely transmits select Customer Data** (such as **audio recordings and transcriptions, clinical documentation, and corrections or additions to generated clinical documentation**) to a **designated Dragon Copilot research environment** where it is processed and **anonymized within 90 days** (measured from the day the data was captured or generated)."

> "**Resulting anonymized data is used to provide Dragon Copilot, including to continually enhance the safety, accuracy, and capability of Dragon Copilot's core functionality and AI/ML models.**"

> "**Dragon Copilot's AI/ML models are trained solely on anonymized data.**"

> "Microsoft's anonymization process is specifically designed to meet relevant thresholds … the standard for **de-identification under HIPAA**, the PIPEDA and **Quebec Law 25** guidance on **irreversible de-identification** in Canada, and the standard for **anonymization under the GDPR (including Recital 26)**."

**Human review** is permitted but scoped to exactly two purposes:

> "**In strictly limited scenarios**, Customer Data may be subject to '**human review**' by select Microsoft employees and subprocessors with tightly managed controls on access to Customer Data." Purposes: (1) "To resolve customer service tickets and ensure the reliable operation of Dragon Copilot"; (2) "To ensure Dragon Copilot meets high standards of clinical accuracy and reliability, including through anonymizing Customer Data to enhance Dragon Copilot AI/ML models … This access also includes the use of **human annotators to assist with the creation of anonymized data sets** used for model improvement, development, and evaluation."

**Consent revocation carve-out:**

> "In the case that a patient revokes previously provided consent, a customer can log a ticket with customer support to have any Customer Data that can be linked back to the individual patient **purged from the operational and research environment** systems. **Resulting anonymized data created by Microsoft prior to the patient's revocation of consent will not be purged.**"

`[推断]` **This is the most important correction the parent agent needs.** The commonly repeated claim that DAX Copilot "does not train on customer data" is **not** what Microsoft's own current privacy whitepaper says. The correct, defensible statement is: *raw customer data may be used for model improvement, but only after a documented anonymization pipeline that must complete within 90 days, and models are trained "solely on anonymized data."* Microsoft deliberately separates the two. Note also that **clinician corrections and the final signed note are explicitly named as data transmitted to the research environment** — i.e. the highest-value training signal is the edit diff.

### B3.3 Retention and deletion

- General: "Customer Data processed by Dragon Copilot is retained, deleted, and purged as set forth in the **DPA**. Customer Data is purged using **Microsoft Purview Data Lifecycle Management**." (`已打开`, privacy whitepaper)
- Recognition audio: "data acquired during an exam is used for **recognition purposes in-memory** and is **never stored in any unencrypted manner**." (`已打开`, security whitepaper)
- Client persistence: "**Dragon Copilot desktop and web: Do not persist data.**" (`已打开`, security whitepaper)
- Mobile: "Audio data is encrypted per packet using **libsodium secret stream (XChaCha20 with Poly1305 MAC)** and stored on the mobile device … During upload, data is **decrypted per packet in memory** and uploaded over TLS 1.3 to **DAX Core**. **Audio data is deleted on the device after upload.**" Offline case: "recordings are encrypted locally and automatically uploaded, and deleted from the end user device, once connectivity is restored." Metadata uses "libsodium secret box (XSalsa20 stream cipher with Poly1305 MAC)." (`已打开`, security whitepaper)

### B3.4 Data residency — an explicit, per-country table

`已打开`, privacy whitepaper, §6 "Location of Customer Data":

| Customer location | Location of Customer Data at rest |
|---|---|
| US | US |
| Canada | Canada |
| UK | UK |
| France, Ireland, Belgium | France, EU |
| Germany, Austria, Netherlands, Switzerland | Germany, EU |

> "Dragon Copilot is an '**EU Data Boundary Service**' and stores and processes Customer Data within the **EU Data Boundary**." / "Nursing features are only available in the US and the **data never leaves the geographic region**."

Security whitepaper adds the infrastructure view: Azure "operating through a network of secure, redundant locations. There are **10 such locations within the continental United States** … In the US, data is replicated between two data centers to keep data current. However, **data never leaves a geography**." Deployment is "**active/active** … with continuous data replication between the Azure data centers."

### B3.5 Storage segregation

> "Dragon Copilot uses **shared compute resources and dedicated storage**. For physicians customer data is stored in a **customer-specific storage container inside a shared storage account** whereas for nurses customer data is stored in a **storage account within their customer-specific namespace**. Therefore, **each customer's data is segregated**." (`已打开`, security whitepaper)

### B3.6 Compliance certifications (Microsoft-stated)

`已打开`, security whitepaper: HITRUST CSF (Azure certified by the Health Information Trust Alliance), HIPAA, **ISO 27001 / 27017 / 27018**, FedRAMP, **SOC 1 Type 1 / SOC 2 Type 2 / SOC 3 Type 3**, EU & UK GDPR, PIPEDA + all Canadian provincial privacy laws, **C5 (Germany)**, **HDS (France)**, **revFADP (Switzerland)**, **Cyber Essentials Plus (UK)**. "Microsoft Azure supports compliance efforts related to **more than 65** national, regional, and industry-specific requirements."

Subprocessors: "disclosed in the **Health and Life Sciences Subprocessor list**." (`已打开`, privacy whitepaper)

---

## B4. Permissions / ACL

### B4.1 Authentication

> "Dragon Copilot authenticates against the customer **Entra ID (Azure AD) tenant using the OpenID Connect protocol**." And: "**All Dragon Copilot users have their own unique account.**" (`已打开`, security whitepaper)

Nursing embedded flow is a genuine ACL design point:

> "Within the embedded nursing experience users are authenticated **within the EHR mobile app**. A mapping is maintained within **Dragon admin center** between the **EHR ID and the nurse's Entra ID**. … the mapping is used to associate mobile sessions with the nurse within Dragon Copilot." (`已打开`, security whitepaper)

### B4.2 Minimum-necessary access — Microsoft side

> "Microsoft HLS follows the HIPAA requirement of '**minimum necessary**' when granting electronic access to Microsoft HLS Data Center Operations team members within Microsoft Azure. **Production file access in Azure is restricted** to the Microsoft HLS Data Center Operations team and the Support Services teams." (`已打开`, security whitepaper)

> "authorized personnel are required to use **two-factor authentication** … all access to production systems, the application, and restricted information is on a **need-to-know basis** using the standard convention of **Security Groups Role-Based Access Controls** and restricted to a **Secure Admin Workstation (SAW)** … consistent with the concepts of **separation or segregation of duties and least privilege**. **Access is audited monthly**." (`已打开`, security whitepaper)

### B4.3 Audit logging

> "Audit logging includes details of **date, time, user account (when applicable), event type, IP address and success or failure**. Dragon Copilot system logs are protected against unauthorized access, modification and deletion, and Dragon Copilot systems log **all authorized and unauthorized access attempts**. **Logs are read-only.** Audit logs are stored in **Azure application insights** as well as ingested into the **Azure Sentinel SIEM**." (`已打开`, security whitepaper)

### B4.4 **Patient chart-level ACL is contractually the CUSTOMER's responsibility**

This is the direct, quotable answer to the "how is minimum-necessary access enforced" question — and it is a delegation, not a product feature:

> "**Customers of Dragon Copilot are also responsible for configuring and managing access controls within their environment** to ensure that only healthcare professionals with an **established therapeutic relationship** with a certain patient can access that patient's data." (`已打开`, privacy whitepaper §2)

Enforced in-product only by **Context Grounding** (no cross-session/external context) and by the fact that there is "**No collaborative editing — designed for a single authenticated user per documentation session**" (`已打开`, transparency whitepaper, Limitations).

### B4.5 Extension governance (a three-gate mechanism)

`已打开`, Information Assist transparency whitepaper — extensions require all of:

1. "The extension must be **approved for use in said location** (i.e., United States)."
2. "The extension must be **enabled for the organization by Microsoft** in Dragon admin center."
3. "The extension must be **enabled for the user by organization administrators** in Dragon admin center."
4. "The extension must be **enabled by the user** in Dragon Copilot Settings: Settings > Information Assist > Enable extension and in the Reference sources section, select the sources you want to consult."

Plus a customer-side obligation: "Customer organizations should add, to any allow lists, relevant websites that may be referred to in Information Assist queries." And scope limit: "**Research queries are limited only to vetted sources that have been approved, tested, and included in users source list**."

---

## B5. Evaluation

### B5.1 Microsoft's own metrics and process

`已打开`, `.../whitepapers/transparency`, "System performance":

> "Dragon Copilot AI performance is measured in multiple ways, including: **Word Error Rate (WER)** for STT. **Accuracy score** for ambient note generation and flowsheet capture, and engineered generative AI measured against **standard data sets**. **Latency** for AI processes. Additional standard measures apply … like **service uptime**."

Evaluation process: "Each system was carefully designed and built using detailed **clinical content specifications**, evaluated through batteries of **quantitative and qualitative tests**, **red-teamed** for content and security vulnerabilities, and **reviewed by clinical content subject matter experts** … New AI models are deployed in production after successful **AB tests that compare new models with baseline models**."

Named evaluation metrics: "**Groundedness, Completeness, Relevance, and Factuality**", plus "**Context-based tests using anonymized clinical documents** (notes or flowsheets) and transcripts."

### B5.2 Information Assist RAG evaluation (the most detailed published eval)

`已打开`, `.../whitepapers/transparency-information-assist`:

- Two test levels: "**Azure Healthcare Agent (platform service) level (2-5k queries)** and then again at **Dragon Copilot (user-app) level (50-100 queries)**."
- RAG assessment dimensions: **groundedness and fabrications**; **answer relevance**; **evidence relevance** (each with worked counterexamples).
- Red-teaming: harmful content across hate/violence/sexual/self-harm; **UPIA (user prompt injection)** and **XPIA (cross-domain prompt injection)** tested against "credible, customer and a **harmful adversarial public website**."
- Results: "The results were **safe with minimal instances of harmful outputs**." / "Manual groundedness evaluation indicated a **low frequency of ungrounded information when testing credible sources**. However, when utilizing **customer sources**, it is important to only use trusted documents and evaluate the system's provided outputs prior to implementation as the nature and complexity of different customer sources can vary significantly."
- UX mitigation: "each answer is accompanied by the **relevant evidence, for provenance, explainability, and transparency**."
- Honest self-limit: "The evaluation results suggest a promising level of generalizability across different use cases that were **not explicitly tested**."

### B5.3 Stated limitations (verbatim, and unusually candid)

`已打开`, `.../whitepapers/transparency`:

> "Potential transcription errors due to background noise, overlapping speech, or **accented speech not well represented in training data**."
> "Summarization or extraction inaccuracies such as **omitted findings or hallucinated details**, especially in preview markets or languages."
> "Latency sensitivity in low-bandwidth environments (**>250 ms** may affect real-time dictation experience)."
> "**No collaborative editing** — designed for a single authenticated user per documentation session."

Named responsible-AI concerns: "**over-reliance** on autogenerated text ('**automation bias**'), privacy of voice data, and **fairness when models underperform on dialects or accents**."

Operational limits: ambient diarized speakers **≤2**; aggregate ambient recording **75 minutes**; network latency **<200 ms** for STT. (`已打开`, same)

### B5.4 Regulatory pathway — **UKCA Class I in Great Britain; explicitly NOT a device everywhere else**

The clearest regulatory statement in the entire corpus (`已打开`, `.../whitepapers/transparency` and repeated verbatim in `.../whitepapers/transparency-information-assist`):

> "Notwithstanding the Universal Licensing Terms for Online Services Medical Device Disclaimer, **Dragon Copilot (physician) is UK Conformity Assessed (UKCA) marked as a Class I medical device in Great Britain. In all other jurisdictions, Dragon Copilot is not designed, intended, or made available as a medical device.**"

The October 2025 release repeats the disclaimer: "**Microsoft's Dragon Copilot is not designed, intended or made available as a medical device** …" (`已打开`, Oct 2025 nurses/partners release)

**openFDA verification — `已打开(API)`:**
- `https://api.fda.gov/device/510k.json?search=applicant:%22Nuance%22&limit=20` → 6 results, **all from an unrelated company "Nuance Medical, LLC"** (CryoDose/PainFreeze cryotherapy canisters, K210310, K161337, K172203, K162218, K232674, K130995). **No Nuance Communications / Microsoft DAX or Dragon clearance.**
- `https://api.fda.gov/device/510k.json?search=device_name:%22Dragon%22&limit=20` → 8 results, all unrelated (acupuncture needles, X-ray devices, syringes: K021095, K002910, K121410, K011247, K042547, K043235, K945249, K173299).

`[推断]` **DAX Copilot / Dragon Copilot holds no FDA 510(k) clearance.** The commercial choice is visible in the documents: Microsoft claims a device classification only in Great Britain (Class I, the lowest-risk UKCA class, self-declared for non-IVD/non-sterile Class I) and disclaims device status in the US — i.e. it deliberately avoids the FDA pathway while making a minimal device claim in one market. It is also worth flagging: "Dragon Copilot is an 'AI clinical assistant'" is a positioning statement, not a regulatory one.

### B5.5 Independent, vendor-named validation studies (PubMed-indexed)

All records read via `已打开(API)` NCBI E-utilities (`esearch`/`esummary`/`efetch`); PubMed record URLs return HTTP 203 (bot challenge) when fetched directly, so those page URLs are marked `[已确认存在，未逐页打开]` and the content is from the API record of the same PMID.

| Study | Setting / design | Vendor named | Key results |
|---|---|---|---|
| **Haberle T, Cleveland C, et al. "The impact of nuance DAX ambient listening AI documentation: a cohort study."** *JAMIA* 2024;31(4):975-979. doi:10.1093/jamia/ocae022. PMID 38345343 | **Intermountain Health**; peer-matched controlled cohort, Mar–Sep 2022, outpatient; 99 providers/12 specialties + 76 matched controls | **Nuance DAX** (in title) | Median utilization **47%**. "Positive trends in provider engagement, while non-participants saw worsening engagement"; **"statistically significant worsening of after-hours EHR"**; **"no quantifiable effect on patient safety"**; **"no significant benefits to patient experience, documentation, or measures of provider productivity."** |
| **Bundy H, Gerhart J, et al. "Can the Administrative Loads of Physicians be Alleviated by AI-Facilitated Clinical Documentation?"** *J Gen Intern Med* 2024;39(15):2995-3000. doi:10.1007/s11606-024-08870-z. PMID 38937369 | **Atrium Health Wake Forest Baptist / Advocate Health**; semi-structured interviews Aug–Sep 2023; 12 of 116 primary-care physicians | **"DAX Copilot (DAXC)"** | Reduced documentation time and "alleviated anxieties of having to retain important clinical details"; more personable encounters. **But**: "the tool would occasionally **imagine or misgender patients, offer unsolicited and inappropriate diagnoses, and mistake critical details in transcription**." Also: some physicians feared being asked to see more patients if mandated. |
| **Liu TL, Hetherington TC, Stephens C, et al. "AI-Powered Clinical Documentation and Clinicians' Electronic Health Record Experience: A Nonrandomized Clinical Trial."** *JAMA Netw Open* 2024;7(9):e2432460. doi:10.1001/jamanetworkopen.2024.32460. PMID 39240568. PMC11380097 | **Atrium Health**, Charlotte NC; nonrandomized clinical trial | (not in abstract; COI discloses it) | COI statement: "Dr Cleveland reported serving on the **Executive Client Council (noncompensated advisory group) for Nuance/Microsoft** … (which included **DAX Copilot in February 2023**)." |
| **Ma SP, Liang AS, Shah SJ, et al. "Ambient artificial intelligence scribes: utilization and impact on documentation time."** *JAMIA* 2025;32(2):381-385. doi:10.1093/jamia/ocae304. PMID 39688515. PMC11756633 | **Stanford Health Care**; prospective QI, 45 physicians, 8 ambulatory disciplines, 3 months | (not in abstract; companion paper names DAX) | Used in **9,629 of 17,428 encounters (55.25%)**, "significant interuser heterogeneity." Median **time per note −0.57 min**; **daily documentation −6.89 min**; **after-hours −5.17 min**; **total EHR −19.95 min/day**. |
| **Shah SJ, Devon-Sand A, et al. "Ambient artificial intelligence scribes: physician burnout and perspectives on usability and documentation burden."** *JAMIA* 2025;32(2):375-380. doi:10.1093/jamia/ocae295. PMID 39657021 | **Stanford Health Care**; prospective QI, 48 physicians, 3 months | Conclusion says: "Ambient AI scribes **like DAX Copilot** may enhance clinical workflows" | Paired n=38: **task load −24.42 (p<.001)**; **burnout −1.94 (p<.001)**; **usability +10.9 (p<.001)**. |
| **Wendt SJ, Dinh CT, et al. "Deploying ambient clinical intelligence to improve care … the impact of nuance DAX on documentation burden and burnout."** *Future Healthc J* 2025;12(3):100450. doi:10.1016/j.fhj.2025.100450. PMID 40896303. PMC12398943 | **Providence** (Providence Research Network / Oregon); **randomised controlled study with step-wedge design** | **Nuance DAX** (in title) | "ACI significantly reduced documentation burden, provider frustration and burnout … **2.5 h less per week of off-hours documentation**." COI: "Providence St. Joseph Health received a **limited number of software licenses from Nuance, a Microsoft Company**, to complete this research study." |
| **Svetly A, Razzouk E, et al. "Large-Scale Implementation of Ambient Artificial Intelligence Documentation and Its Effects on EHR Efficiency and Clinician Well-Being."** *Appl Clin Inform* 2026;17(4):747-753. doi:10.1055/a-2936-7516. PMID 42618038 | **AdventHealth** (multistate), retrospective index-date-aligned pre-post; 210 providers with ≥25% ambient-generated note content; **Epic Signal** data, 8 months pre/post | **DAX Copilot** | Active note time **5.54 → 4.09 min per appointment (−26.2%, p<0.001)**; **note length +28.8%**; **typing −51.7%**. |
| **Lukac PJ, Turner W, et al. "Ambient AI Scribes in Clinical Practice: A Randomized Trial."** *NEJM AI* 2025;2(12). doi:10.1056/aioa2501000. PMID 41497288 | **UCLA Health**; **parallel three-group pragmatic RCT, 1:1:1 covariate-constrained randomization, 238 outpatient physicians, 14 specialties**, Nov 2024–Jan 2025 | **Microsoft DAX Copilot vs Nabla vs usual care** | DAX used in **33.5% of 24,696 visits**; Nabla in 29.5% of 23,653. Primary outcome (log time-in-note): **Nabla −9.5% (95% CI −17.2% to −1.8%; P=0.02) vs control; DAX −1.7% (95% CI −9.4% to +5.9%; P=0.66) — no significant change.** Both improved Mini-Z (DAX +2.83) and reduced physician task load. |
| **Webb J, Chu L, et al. "Crossover Evaluation of Two Ambient AI Scribe Tools in the Emergency Department."** *Appl Clin Inform* 2026;17(1):118-126. doi:10.1055/a-2818-1706. PMID 41734793 | **UT Southwestern** ED; single-site prospective crossover, 6 weeks (Apr–Jun 2025), 20 enrolled / 18 completed, alternating 3-week phases | **DAX vs Abridge** — the only direct head-to-head | DAX greater reduction in overall perceived work burden (**median 1.5 vs 2; p=0.025**); SUS comparable (**73.5 vs 73.5; p=0.94**); UMUX-Lite 86 vs 82.5 (p=0.079); modified **PDQI-9 favored DAX (39 vs 36.5; p=0.011)**; likelihood-to-recommend **9 vs 7.5 (p=0.015)**. **BUT: "adjusted models suggested these differences reflected order effects more than inherent tool differences."** |
| **Ghanem YK, Nation R, et al. "DAX Copilot: ambient AI scribe may help reduce surgical resident clinical documentation burden."** *Surg Endosc* 2026 Jan. doi:10.1007/s00464-025-12404-x. PMID 41366572 | Surgical residents | **DAX Copilot** (in title) | (title-level finding) |
| **Talman M, Alam L. "Ambient Artificial Intelligence Scribes in Pediatric Hematology-Oncology: Early Implementation of DAX Copilot."** *Appl Clin Inform* 2026 Mar. doi:10.1055/a-2873-3894. PMID 42114818 | Pediatric hematology-oncology | **DAX Copilot** (in title) | (early implementation) |
| **Shin HS, Williams H, et al.** "The Influence of Artificial Intelligence Scribes on Clinician Experience and Efficiency among Pediatric Subspecialists: A Rapid, Randomized…" *Appl Clin Inform* 2025 Aug. doi:10.1055/a-2657-8087. PMID 40675605 | Pediatric subspecialists; rapid randomized | DAX-family | — |

**Vendor-named but NOT DAX/Abridge** (included only to prevent misattribution): Palm E, Manikantan A, et al. *Front Artif Intell* 2025;8:1691499 (PMID 41199808) is a **PDQI-9 ambient-note quality validation by Suki AI** — hallucination detected in **31% of ambient notes vs 20% of gold notes (p=0.01)**; adjacent tools' numbers should not be attributed to Abridge or DAX.

### B5.6 Kaiser Permanente and the multisite literature — precise status

The brief specifically asked for Kaiser Permanente / Atrium / Stanford. Honest status:

- **Atrium Health**: **found** — two publications, one naming DAX Copilot directly (Bundy 2024 JGIM) and one nonrandomized trial (Liu 2024 JAMA Netw Open), both with Nuance/Microsoft COI disclosure. ✅
- **Stanford**: **found** — Ma 2025 JAMIA (documentation time), Shah 2025 JAMIA (burnout/usability), and a 2026 ED cohort (Preiksaitis C, et al., *JMIR AI* 2026, PMID 42391625; *Ann Emerg Med* 2026, PMID 41665590). The Stanford papers do **not** name the vendor in the abstract; the Shah 2025 conclusion references "**DAX Copilot**" by name. ✅ (with the vendor-naming caveat)
- **Kaiser Permanente**: **no Kaiser-published outcome trial naming DAX/DAX Copilot was found.** What exists is Kaiser-affiliated *commentary*:
  - Tierney AA, Lee K. **"Redefining Documentation Quality in the Age of Ambient Artificial Intelligence Scribes."** *Ann Intern Med* 2026;179(6):898-899. doi:10.7326/ANNALS-26-00231. PMID 41996182 — affiliations: "**The Permanente Medical Group, Oakland, and Division of Research, Kaiser Permanente Northern California**, Pleasanton, California."
  - Tierney AA, Lee K, Liu VX. **"Ambient AI Scribes and the Quintuple Aim: What Is Counted—and What Matters."** *JAMA* 2026;335(16):1393-1395. doi:10.1001/jama.2026.3529. PMID 41920555 (a comment on the JAMA multisite study below).

  **→ Treat "the Kaiser Permanente study" as unverified. The widely-repeated Kaiser time-savings numbers were not located in a first-party or peer-reviewed source in this session.** `[推断]` Kaiser Permanente's ambient work appears in the literature as methodological/quality commentary rather than as a vendor-named outcome trial.

- **The largest multisite study** is UCSF-led and **does not name a vendor**: Rotenstein LS, Holmgren AJ, et al. **"Changes in Clinician Time Expenditure and Visit Quantity With Adoption of Artificial Intelligence-Powered Scribes: A Multisite Study."** *JAMA* 2026;335(16):1408-1417. doi:10.1001/jama.2026.2253. PMID 41920565. PMC13044793. Five US academic institutions (UCSF, Emory, UC Davis, Yale/Yale New Haven, Mass General Brigham, UCSD, NYU, Emory Healthcare, Medical College of Wisconsin), ambulatory clinicians, AI scribes introduced Jun 2023–Aug 2025. **8,581 clinicians, 1,809 adopters.** Difference-in-differences: **−13.4 min EHR time (95% CI 9.1–17.7)**, **−16.0 min documentation time (95% CI 13.7–18.3)**, **+0.49 weekly visits (95% CI 0.17–0.81)**; **after-hours EHR time did not change significantly**. Effects "greatest for primary care specialists, advanced practice clinicians, female clinicians, and clinicians who used AI scribes in ≥50% of visits." COI includes a **Yale New Haven** advisory relationship with **Abridge** and an institutional investment by **Mass General Brigham in Abridge** — so the study population is mixed-vendor and must not be attributed to DAX.

---

## B6. Key design decisions (DAX Copilot / Dragon Copilot)

1. **Two capture modalities with two different trust models, deliberately not merged.** `Dictation` is single-speaker, real-time, cursor-targeted ("return recognition results to the **text cursor**") — a 25-year-old Dragon Medical One lineage with a mature correction UI. `Ambient recording` is multi-speaker, asynchronous, draft-note-producing. Microsoft kept both surfaces and merged only the *shell*, which is why the DMO→Dragon Copilot comparison and migration docs exist. (`已打开`, `.../sdk/glossary`; docs TOC: `.../dragon-medical-one/dragon-medical-one-comparison`)

2. **Enforce data scope at prompt construction, not just at the database.** **Context Grounding** — "The context provided to the LLM is grounded in specific note data. **External sources and data from other sessions are not allowed**" — plus the intent classifier that "rejects prompts that are irrelevant (e.g. non-medical related, related to medical advice, or **clinical decision-making**)." (`已打开`, `.../whitepapers/transparency`)

3. **Ship a healthcare-specific guardrail *allow list* rather than trusting a general safety filter.** Because clinical text legitimately contains violence, sexual, and self-harm content, Microsoft sets those Azure content-policy categories to a **higher risk threshold** and adds an **Allow list** for "words flagged by Guardlist that are deemed necessary." (`已打开`, `.../whitepapers/transparency`; `.../whitepapers/transparency-information-assist`)

4. **Standardise on one public ontology/payload so partners and EHRs integrate once.** The `Dragon standard payload` + `Resource` + LOINC/SNOMED-CT `Context` + resource-to-resource links is a deliberate integration contract (with partner `GUID`s, `Correlation ID` that is "opaque and … doesn't contain any personal information … can be safely logged as plain text", webhooks, provisioning/retrieval/feedback services). `[推断]` This is the structural reason Dragon Copilot can host third-party AI apps and agents without per-partner bespoke models.

5. **Avoid the FDA device pathway; make the narrowest possible device claim elsewhere.** UKCA Class I in Great Britain only, explicit non-device disclaimer "in all other jurisdictions", clinician sign-off mandatory ("**All generated content must be reviewed and validated by the clinician before it becomes part of the medical record**"). (`已打开`, `.../whitepapers/transparency`)

---

# PART C — Cross-cutting comparison

| Dimension | Abridge | DAX Copilot / Dragon Copilot |
|---|---|---|
| **Anchor signal** | "Conversation Comes First"; the conversation is "the most human signal in healthcare" | Two modes: `Dictation` (single speaker) + `Ambient recording` (multi-speaker, **≤2 diarized**, others aggregated) |
| **Named reasoning/context engine** | **Contextual Reasoning Engine** (EHR CONTEXT / PREDICTED PROBLEMS / ORDERS / CODING) | **Context Grounding** + **Information Assist** (Azure Healthcare Agent Service, RAG, top-3 sources, web-only) |
| **Provenance mechanism** | **Linked Evidence** — "see evidence for each AI-generated summary"; "traceable to the source conversation" | Per-answer **evidence** card + **Clinical Safeguards** engine assuring "provenance, verification"; `Context` codes (LOINC/SNOMED-CT) + resource-to-resource **links** |
| **Knowledge corpus** | **Licensed**: UpToDate, NEJM, JAMA, AHA, ADA, AAFP, EBMcalc | **Licensed + partner-hosted**: Elsevier, OpenEvidence, Wolters Kluwer UpToDate, plus partner agent ecosystem |
| **EHR patient-context ingestion** | "deep EMR integrations"; **Epic Partners and Pals (first Pal)**, Epic Workshop; EMR list Epic/Athena/AllScripts/Cerner/eClinicalWorks/NextGen. **No public FHIR/HL7 spec** | **Optional service data: FHIR, HL7, and/or EHR resources for Patient, Practitioner, Encounter**; **SMART on FHIR app launch** documented; Epic + Epic Rover |
| **Training claim (precise)** | "PHI … is never used for training" (scoped to CDS queries); de-identified encounters used for eval + annotation | "Customer Data … anonymized within **90 days**" → "AI/ML models are trained **solely on anonymized data**"; human annotators allowed on anonymized sets |
| **Residency** | **未找到公开资料** | Explicit per-country table; **EU Data Boundary Service**; nursing US-only, "data never leaves the geographic region" |
| **Chart-level ACL** | **未找到公开资料** (BAA + BAA-governed processing only) | **Contractually delegated to customer**; in-product scoping via Context Grounding + single-user session |
| **Best published metric** | **97% of confabulations caught vs GPT-4o 82%** (internal benchmark); CDS **99.5% across 1,000+ safety cases**; mean star rating **4.3/5** | **WER** (STT) + "**accuracy score**" (notes/flowsheets); Information Assist groundedness/relevance; **−26.2% note time** (AdventHealth, 210 providers) |
| **Regulatory** | **No FDA 510(k) found**; no regulatory statement published | **UKCA Class I in Great Britain; explicitly not a device elsewhere**; no FDA 510(k) found |
| **Vendor-independent RCT result** | (only in the DAX-vs-Abridge crossover, where differences were attributed to **order effects**) | **DAX −1.7% time-in-note, P=0.66 (NS)** vs usual care in the UCLA 3-arm RCT; Nabla −9.5%, P=0.02 |

---

# PART D — Gaps: explicit "未找到公开资料"

1. **Abridge FHIR/HL7 interface specification.** No public resource-level integration contract, no SMART-on-FHIR launch doc, no API reference. (Contrast: Microsoft publishes the `Dragon standard payload`, SMART-on-FHIR launch, SDKs for JS/Android/DAXKit, and partner APIs.)
2. **Abridge data residency commitments.** No geography table, no EU-data-boundary statement on any page I fetched.
3. **Abridge chart-level / role-based access control.** No description of admin console, SSO, or chart-scoping. Whether the product enforces minimum-necessary access or inherits it from the EHR is **not publicly documented**.
4. **Abridge regulatory pathway.** No FDA clearance found and no regulatory-position statement published. Their assistive, clinician-sign-off framing is stated but the regulatory reasoning behind it is not.
5. **Abridge corpus refresh cadence** for licensed CDS content.
6. **An "Abridge medical ontology" as a named product layer.** Not found. Only the 2020 EMNLP MedFilter paper (ontological knowledge) and billing-code-alignment wording under PREDICTED PROBLEMS/CODING.
7. **"Abridge Enterprise" as a current product name.** Not found; the historical artefact is the 2021 "enterprise solution" launch release.
8. **A Kaiser Permanente ambient-AI *outcome trial*.** Not found. Only Kaiser-affiliated commentary in *Ann Intern Med* and *JAMA*.
9. **Nuance's original DAX architecture documentation.** nuance.com/healthcare no longer resolves to a Nuance site; it 301s to Microsoft. Any pre-2022 Nuance engineering description is no longer first-party-served.
10. **Quantitative hallucination/omission rates for DAX Copilot.** Microsoft names Groundedness/Completeness/Relevance/Factuality as evaluation metrics but publishes **no numbers** for the note-generation path (numbers exist only for the Information Assist RAG path, qualitatively).
11. **An Abridge-published note-quality accuracy percentage.** Abridge publishes a *confabulation-detection* accuracy (97% recall against its own benchmark) and a CDS *safety* score (99.5%) — but **not** a note-level accuracy/factuality percentage. Do not conflate these.

---

# PART E — Source inventory

### E1. Opened in this session (`已打开`)

**Abridge**
- `https://www.abridge.com/` — via `web_fetch` tool
- `https://www.abridge.com/sitemap.xml` (556 URLs enumerated)
- `https://www.abridge.com/robots.txt`
- `https://www.abridge.com/abridge-contextual-reasoning-engine`
- `https://www.abridge.com/ai`
- `https://www.abridge.com/ai/publications`
- `https://www.abridge.com/ai/science-ai-evaluation`
- `https://www.abridge.com/ai/science-confabulation-hallucination-elimination`
- `https://www.abridge.com/cds`
- `https://www.abridge.com/platform/care-signals`
- `https://www.abridge.com/whitepapers`
- `https://www.abridge.com/privacy`
- `https://www.abridge.com/terms/business-associate-agreement`
- `https://www.abridge.com/blog/building-trusted-healthcare-ai`
- `https://www.abridge.com/blog/hallucinations-whitepaper`
- `https://www.abridge.com/blog/how-we-evaluate-clinical-decision-support-for-enterprise-readiness`
- `https://www.abridge.com/blog/clinical-ai-specialty-models`
- `https://www.abridge.com/blog/science-scale-specialties-the-rapid-impact-of-abridge`
- `https://www.abridge.com/blog/trust-auditability-science-behind-abridge-video`
- `https://www.abridge.com/blog/context-aware-clinical-intelligence-for-every-clinician-partner-systems`
- `https://www.abridge.com/reports/adoption-scale-impact`
- `https://www.abridge.com/reports/science-of-ambient-ai-evaluation`
- `https://www.abridge.com/reports/innovation-at-the-speed-of-trust`
- `https://www.abridge.com/reports/the-science-of-ai-evaluation-for-enterprise-healthcare`
- `https://www.abridge.com/press-release/abridge-becomes-epics-first-pal-bringing-generative-ai-to-more-providers-and-patients`
- `https://www.abridge.com/press-release/abridge-mayo-epic`
- `https://tech.abridge.com/blog/ai-evaluation-at-abridge`
- `https://tech.abridge.com/blog` (returns a 354-char JS shell only)

**Microsoft / Nuance**
- `https://www.nuance.com/` → 301 → `https://dragon.nuance.com/en-us/home`
- `https://www.nuance.com/healthcare.html` → 301 → `https://www.microsoft.com/en-us/health-solutions`
- `https://www.microsoft.com/en-us/health-solutions`
- `https://www.microsoft.com/en-us/health-solutions/clinical-workflow`
- `https://www.microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot`
- `https://www.microsoft.com/en-us/health-solutions/clinical-workflow/dragon-copilot/customer-stories`
- `https://www.microsoft.com/en-us/microsoft-cloud/blog/industry-healthcare/` (no DAX-architecture content on page 1)
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/toc.json`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/about/`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/about/faqs`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/privacy`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/security`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/data-collection`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/transparency`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/whitepapers/transparency-information-assist`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/specialty-models/specialty-specific-content`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/specialty-models/clinical-note-status`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/specialty-models/intelligent-diagnoses-retrieval`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/sdk/glossary`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/sdk/embedded-desktop/smart-fhir-app-launch`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/sdk/partner-apis/ambient-audio-streaming/`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/sdk/partner-apis/dragon-data-exchange/dragon-standard-payload/ontology/`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/sdk/partner-apis/dragon-data-exchange/dragon-standard-payload/ontology/coding-systems`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/sdk/partner-apis/dragon-data-exchange/dragon-standard-payload/resources/context`
- `https://learn.microsoft.com/en-us/industry/healthcare/dragon-copilot/extensions/development-concepts`
- `https://learn.microsoft.com/api/search?search=Dragon%20Ambient%20Experience%20DAX%20Copilot&locale=en-us` (Microsoft's own docs search)
- `https://news.microsoft.com/source/2025/03/03/microsoft-dragon-copilot-provides-the-healthcare-industrys-first-unified-voice-ai-assistant-that-enables-clinicians-to-streamline-clinical-documentation-surface-information-and-automate-task/`
- `https://news.microsoft.com/source/2025/10/16/microsoft-extends-ai-advancements-in-dragon-copilot-to-nurses-and-partners-to-enhance-patient-care/`
- `https://news.microsoft.com/?s=dragon+copilot` (Microsoft news search)

### E2. Opened via first-party API (`已打开(API)`)

- `https://api.fda.gov/device/510k.json?search=applicant:%22Abridge%22&limit=20` → NOT_FOUND (0 results)
- `https://api.fda.gov/device/510k.json?search=applicant:%22Nuance%22&limit=20` → 6 results, all "Nuance Medical, LLC" cryotherapy (unrelated)
- `https://api.fda.gov/device/510k.json?search=device_name:%22Dragon%22&limit=20` → 8 results, all unrelated devices
- NCBI E-utilities (`esearch.fcgi` / `esummary.fcgi` / `efetch.fcgi`, db=pubmed) for every PMID cited in §A5, §B5.

### E3. Confirmed to exist, not opened page-by-page (`[已确认存在，未逐页打开]`)

PubMed/PMC HTML pages (they return HTTP 203 / 200 bot responses to direct fetch; content read via E-utilities instead). DOI links return HTTP 403 from the publishers to non-browser agents; they are the publisher-of-record URLs for the records read via PubMed.

- PMIDs: 38345343, 38937369, 39240568, 39657021, 39688515, 40896303, 41199808, 41366572, 41497288, 41665590, 41734793, 41920555, 41920565, 41996182, 42114818, 42391625, 42618038, 40675605 → `https://pubmed.ncbi.nlm.nih.gov/<PMID>/`
- PMC: `https://pmc.ncbi.nlm.nih.gov/articles/PMC11380097/`, `.../PMC11756633/`, `.../PMC12398943/`, `.../PMC13044793/`, `.../PMC11576703/`, `.../PMC10990544/`
- DOIs: `10.1001/jamanetworkopen.2024.32460`, `10.1007/s11606-024-08870-z`, `10.1093/jamia/ocae304`, `10.1093/jamia/ocae295`, `10.1093/jamia/ocae022`, `10.1056/aioa2501000`, `10.1055/a-2818-1706`, `10.1055/a-2936-7516`, `10.1016/j.fhj.2025.100450`, `10.1001/jama.2026.2253`, `10.7326/ANNALS-26-00231`, `10.1001/jama.2026.3529`, `10.1007/s00464-025-12404-x`, `10.1055/a-2873-3894`, `10.1055/a-2657-8087`
- Abridge sitemap-only URLs referenced in text: `https://www.abridge.com/press-release/abridge-secures-12-5m-in-funding-and-launches-enterprise-solution-to-combat-physician-burnout-in-healthcare-and-help-patients-stay-on-top-of-their-health`
- Microsoft Learn TOC-only URLs referenced in §B2/§B6: `.../sdk/partner-apis/dragon-data-exchange/dragon-standard-payload/resources/clinical-resource-types/orders/`, `.../dragon-standard-payload/examples/`, `.../dragon-medical-one/dragon-medical-one-comparison`, `.../about/use-cases`, `.../installation/allow-list-urls`, `.../industry/healthcare/dragon-admin-center`

### E4. Explicitly unusable in this session

- `web_search` — Firecrawl keyless `429`, `retry_after_seconds: 86381`
- `exa_search` — no API key configured
- `search.brave.com` — `429 Too Many Requests`
- `www.bing.com/search` — returns topically unrelated results for clinical-AI queries (unusable)
- `www.mojeek.com` — `403`
- `www.nuance.com/*` — no longer serves Nuance content (301 to Microsoft)
- `tech.abridge.com/sitemap.xml` — `404`
