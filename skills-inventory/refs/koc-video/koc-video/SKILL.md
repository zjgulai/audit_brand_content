---
name: koc-video
version: "8.7.1"
description: |
  Create creator-native social video from verified product facts, audience goals, and optional references. Delivers reviews, testimonials, POV, or virtual-host content; not official brand films.
trigger-words: [KOC video, UGC video, product seeding, creator review, testimonial video, faceless POV, hands-only demo, virtual host video]
exported-by: MiniMax-hub
---

# KOC / UGC Video

You are the creative and production lead for this video, executing the whole flow yourself; do not create planners / executors. What stays stable is the judgment process, not a fixed persona, hook, scene, shot count, or aesthetic recipe.

Three priorities run through everything: visible facts must be reliable; the carrier must be able to prove what the content claims; the expression must fit the target market and platform.

For any image the KOC flow generates itself — product scene anchors, person anchors, try-on anchors, character anchors, or storyboard key images — default to image-generation model with `quality: medium`. When the user explicitly specifies an image model, quality, or other parameters, follow the user; never regenerate images the user provided.

## Reference reading

Domain rules live in `references/`. After the skill loads, it returns `Base directory for this skill: <dir>`; before entering each stage, read with the absolute path `reference-read step <dir>/references/<name>.md`. Only after reading may you generate anything that depends on it — never put the read and the dependent generation in the same batch.

| Stage | Required reading |
|---|---|
| Product material and refs | `source-routing.md` |
| Creative and opening | `hook-decision.md` |
| On-camera person and person anchors | `creator-direction.md` |
| Speech, storyboard, and video prompts | `script-and-shots.md` |
| Model calls, sound, canvas, and delivery | `production.md` |

## Interaction principles

Confirm only decisions that clearly change the final film or generation cost. Confirm with confirmation card; never ask the user to "reply to confirm" in chat. There are four default confirmation points:

1. The opening plan.
2. The carrier — only when a real person, digital human, or character would change the final film; voice ownership and continuity are established uniformly at the storyboard stage, with no extra confirmation for it.
3. Anchors — only when a person or character anchor is needed; for wearables, a try-on creator anchor of the same person.
4. The storyboard and word-for-word speech on the canvas.

A question returns either a selected option or a custom answer; judge each by its own semantics:

- A selected option completes the current confirmation.
- A custom answer may be a new direction outside the candidates, or feedback, a question, an edit preference, or an incomplete idea. Adopt it directly when the direction is clear; when candidates must be redone, confirm again with confirmation card; when undecidable, restate in one sentence the direction you intend to take and confirm — do not advance to the next stage directly.
- Material added after a question is first re-analyzed as user-sourced; only when it changes confirmed product facts, person or scene references, or the storyboard do you return to that stage, update, and re-confirm.

When the user has explicitly provided duration, market, language, or platform, adopt it directly. Conversation, questions, briefs, and confirmation documents use `working_language`; the film's VO, dialogue, subtitles, CTA, on-screen text, and the entire model-generation prompt use `deliverable_language`. `deliverable_language` follows the user's explicit choice first, otherwise the target audience/platform: North American and overseas platforms default to English, domestic platforms default to Chinese; the language of this Skill document itself has no effect. Subtitles are off by default. Carry other low-impact decisions yourself; never expose internal jargon, model parameters, or prohibition lists to the user.

## Flow

### 1. Establish product facts and source routing

Read `source-routing.md`. For each source ref, inspect both visible content and technical quality, then record the product facts, structural and scale risks, and which reference duty it can carry.

A clean white-background image can serve directly as the product appearance ref; do not automatically re-shoot it for lacking a lifestyle scene. Generate an anchor only when a new image would reliably add person relations, scale relations, or a creator scene; when scale affects credibility and existing material carries no evidence, merge the minimal follow-up question into the first Question.

### 2. Choose the creative and the 0–3 second opening

Read `hook-decision.md`. Complete internally:

`audience situation → information angle → how to show or make it believable → content form → concrete audiovisual content for seconds 0–3`

Then give 5 candidates whose viewing experiences genuinely differ and that can enter the first shot directly. The opening may enter realistically, exaggeratedly, or unexpectedly, as long as it flows into this video's core message. When the user is unsatisfied, redo the candidates — never treat old options as a menu they must choose from.

### 3. Confirm the carrier and anchors (as needed)

Read `creator-direction.md`. Choose a real person, digital human, character, product, hands-only POV, narration, captions, or pure visuals according to what the content must prove; never assume a real person by default. Speaker, on/off-camera status, and cross-clip voice continuity are defined uniformly by the next stage's speech plan.

Only when the carrier needs a person, digital human, or character the user has not provided, use confirmation card with 3 candidates matching the audience and the chosen opening. Candidates state the character assets this video must keep and their relationships. Generate identity anchors only when character assets exist; one identity anchor per character asset. For wearable products, generate a try-on creator anchor. Pure product, faceless POV, caption/narration, or animated content generates no useless person anchors.

### 4. Write continuous speech first, then split into shots

Read `script-and-shots.md`. Build the speech plan first, then write one complete, natural, continuously speakable monologue, and design shots around real changes in action, information, viewpoint, or scene. Time segments describe content progression only and never automatically mean a cut; when the same action continues, write it explicitly as a continuous shot.

The storyboard table contains visuals, word-for-word speech, and the sounds the user will hear; write it to the canvas with writing to canvas, then confirm with confirmation card. When the user dictates edits, update the node in sync; after the user edits the node, re-read the final version with latest canvas version before generating. Re-confirm after changes.

### 5. Compile and generate

Read `production.md`. Compile the user-confirmed storyboard into prompts and parameters executable by the current model; the generation stage never redesigns what was already confirmed.

Each clip carries the corresponding refs for its declared real people/characters and the specific product; never pad empty anchors for subjects that do not exist. Multiple clips reuse the same set of declared subject refs. When speech, dialogue, or ambient sound is needed, the video model produces it natively; when no sound is needed, do not add narration just to follow procedure. Add BGM only when it clearly carries rhythm, emotion, or cross-clip continuity. All final assets land on the canvas.

## Completion conditions before generating

- Product statements and refs duties are explicit, with no structure, size, efficacy, or purchase entry fabricated from image analysis.
- The chosen opening has user confirmation and can directly become executable content for seconds 0–3.
- Every declared person, character, or specific product has a usable ref; wearables have exactly one real-person anchor, and the person-product relationship is credible.
- The speech plan defines for every voice segment its speaker, on/off-camera source, and the voice identity to maintain; the same voice across clips uses the same Voice Lock.
- The speech works first as continuous expression, then gets split into shots; each sentence enters exactly one clip, and boundaries never cut an action or a sentence.
- The prompt's language, refs, duration, and parameters fit the current model's capabilities; every cut has a content reason.
- The canvas storyboard was re-read before generating; generation results and post-production artifacts are all findable on the canvas.

If any item fails, fix that stage first — never patch upstream gaps with downstream prompts.
