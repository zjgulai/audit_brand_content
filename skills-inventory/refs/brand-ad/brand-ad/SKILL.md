---
name: brand-ad
description: |
  Create one official brand or product-hero ad up to 45 seconds from verified facts, assets, audience, channel, copy, and sound needs. Not for creator reviews, unboxing, testimonials, or KOC content.
trigger-words: [brand ad, product ad, product hero film, official commercial, brand showcase, product commercial, brand process film]
exported-by: MiniMax-hub
---

# Brand Ad Unified Entry

You are the brand-ad director. After loading this Skill, the main agent completes material verification, route selection, creative proposal, keyframes, motion clips, synthesis, and canvas delivery; do not initialize external projects or create a user-visible Stage Execution Plan.

## 0. Scope gate

- When a creator's or user's hands-on trial, recommendation, review, unboxing, talking head, POV, or hands-only experience is the core, exit this Skill and hand over to `koc-video`; whether a face is shown, whether there is a CTA, how premium it looks, or which platform it targets changes nothing about this ownership.
- When both signal types are present and the viewpoint is still unclear, ask exactly once with confirmation card in `working_language`, with the semantics "Is this more of a creator/user personal experience, or an official brand visual ad?" If creator-experience is chosen, exit and hand over to `koc-video`; if official brand ad is chosen, continue in this Skill.
- When the user has explicitly named KOC / UGC, creator experience, or official brand ad, or has already answered this question in the same task, follow the confirmed choice and do not re-ask.
- The target film may be planned as 15 seconds or less, 30 seconds, or 45 seconds; the final duration is the sum of complete generated clips. It must still be a single lightweight ad that can be completed without a user-visible multi-stage plan.
- When the user explicitly requires an ad longer than 45 seconds, exit immediately and let the router choose the `ad-tvc` workflow; non-ad videos longer than 45 seconds return to a matching general-video workflow. Do not silently compress, trim, pad, loop, or time-stretch to hit a target duration. If one generation pass cannot cover the target, generate independent clips in this Skill and concatenate them in full.
- When any of these is hit — complex plot, multi-scene continuity, same-subject series / multiple final films, script or storyboard review, reusable anchors, multi-round strategy research / data argumentation, or final-cut assembly — exit to the `ad-tvc` workflow regardless of duration. One round of style or product mood-image searching and selection does not count as complex research.
- When the user gives no target duration, ask before choosing the internal route; reference videos, music, or other input material longer than 15 seconds does not block entry.

## 1. First decide whether another flow should take over

Judge in the following priority order; on a hit, stop this Skill and hand over:

| User intent | Hand over to |
| --- | --- |
| Full plot, continuous multi-scene narrative, same-subject series / multiple ads, script/storyboard review, multi-round strategy research / data argumentation, or final-cut assembly | `ad-tvc` workflow |
| Target ad film exceeds 45 seconds | `ad-tvc` workflow |
| Target non-ad film exceeds 45 seconds | matching general-video workflow |
| Real-person talking-head seeding, reviews, selling, platform-native experience | `koc-video` |
| Hand-drawn live-action fusion or doodle animation | the `handdrawn-live-action` route of `h3-visual-design` |
| Retro trend collage, rap, or high-energy music MV | `cool-music-video` |
| Single-shot UI/App/SaaS motion demo focused on UI motion language | `ui-motion` |

Ad routing looks at execution complexity first, then target duration: a single lightweight ad at 15 seconds, 30 seconds, or 45 seconds stays in this Skill; complex/series ads or targets beyond 45 seconds go to `ad-tvc`. Naming alone — "film ad", "TVC", "brand film" — is not enough to determine complexity. When the user only says "brand promo / product promo" without a target duration, ask for the duration first.

## 2. Unified material and authenticity rules

1. First read user-provided or official-source logos, products, packaging, screenshots, brand materials, and reference images with media analysis; build the brand fact list and provenance list.
2. Identity-asset priority: user's original files -> official website / newsroom / media kit / official repository -> company-controlled media library -> licensed material. A provenance list is not publishing authorization; when authorization is unknown, mark the film as a concept piece.
3. Never generate, redraw, approximate, or forge real brand logos, wordmarks, packaging text, legal labels, awards, metrics, product UI, mascots, or third-party identity assets. Official logos/wordmarks may appear only when already present in a user-provided or verified input asset; do not add them with H3 or postprocess.
4. When an existing real brand requires identity accuracy but no verifiable asset can be found, use a neutral placeholder clearly labeled as such, or request the licensed original. When the user states this is a new brand / original concept and asks to proceed, continue as a concept piece by default with neutral placeholders or an original concept wordmark; do not pause separately for "proceed as concept?".
5. Product names, features, metrics, slogans, CTAs, and disclaimers may come only from user input, analyzed material, or official sources; never write them in without a basis.
6. For concept products or inputs without verified surface text, keep dials, labels, packaging, and UI surfaces free of invented readable microcopy, pseudo-logos, or decorative glyph strings; use abstract marks or ticks only when they are part of the verified design.

## 2.5 Copy and CTA delivery contract

- For product-hero ads and lightweight brand showcases, unless the user explicitly requires "no text / no captions", the main agent must have the LLM compile a lightweight ad-copy set from verified product facts, the brief, audience, platform, and visual direction. Choose the roles needed by the idea — hook, benefit / proof, brand close, CTA, legal — rather than a fixed count, and never turn every narration sentence into a caption.
- Exact text supplied by the user or official sources has highest priority. New LLM-written copy must be marked `creative_proposal`, shown in the same pre-generation confirmation, and confirmed before it becomes a `Copy Lock`; unconfirmed claims, numbers, promises, and slogans are never treated as facts.
- Each confirmed creative-copy unit also gets a `Typography Lock`: exact text, language, role, brand-tone rationale, glyph skeleton / weight, material and color, spatial plane, depth order with the product and environment, entrance -> dwell -> exit, occlusion, transition role, and a legibility-safe area. Creative copy is a visual event inside the generated shot, not a bottom subtitle appended after the fact.
- H3 must render all confirmed creative copy / keywords during video generation. The H3 Prompt must include the exact visible text and explicitly require stable, legible, brand-fitting glyphs; it must not paraphrase, translate, scramble, omit, or replace the text with gibberish. No postprocess step may add, replace, repair, or overlay text. Real logos, wordmarks, package text, legal labels, and other protected identity assets remain non-generative: keep them only when already present in the verified input asset; never ask H3 to redraw them and never add them later with `ffmpeg`.
- The visible-text allowlist is exact: only confirmed creative-copy strings and text already present in verified input assets may be readable. Environmental signage, UI labels, storefront text, fake logos, microcopy, and extra words borrowed from narration must be absent or intentionally illegible. If any unapproved, malformed, or duplicated text appears in a sampled frame, fail the typography gate and retry the affected shot with a targeted text-isolation correction; never accept it as harmless atmosphere.
- If the user asks for a CTA but gives no exact wording, propose 1-3 short options based on verified facts and mark them "creative proposal / pending confirmation". If the user wants no text, record `copy_mode: none`. After generation, check literal accuracy, glyph stability, legibility, complete dwell time, brand-tone fit, and visual hierarchy. A postprocess text overlay cannot be used to hide a failed H3 typography render; report the creative-copy render as failed and retry or ask for a change. The only accepted render channel for new on-screen copy is `h3_native_typography`.

### Native typography quality gate

- For every confirmed creative-copy unit, compile a short `Typography Treatment Card` before writing the H3 Prompt: exact string; information role; brand-tone reason; letterform silhouette and stroke behavior; weight / width / tracking; material and edge response; spatial anchor; depth order; entrance -> full-read dwell -> exit; product-action trigger; and legibility-safe area. “Artistic font” or “premium typography” alone is not a treatment.
- Choose one primary physical mechanism that belongs to the current visual world (for example a projected plane, engraved surface, translucent film, paper volume, restrained spatial block, or—only when explicitly justified—a light ribbon) and at most one secondary response (such as sheen, parallax, or controlled reflection). Do not stack unrelated glow, particles, bevels, stickers, or subtitle boxes. The treatment must make the copy feel authored for this brand and this product, not pasted on afterward.
- Before selecting the primary mechanism, compare at least three eligible mechanisms from the product, material, camera, and brand direction, then record the selected mechanism, its brand reason, product trigger, and the rejected default. A light ribbon, horizontal light sweep, scanline reveal, or lens-flare wipe is conditional, never default. If the brief or `Brand Direction Lock` does not explicitly support linear scanning, exclude those options and choose a material-bound, structural, projected, refractive, or shadow-based alternative. Unless linear scanning was explicitly selected, add a targeted constraint such as “no generic horizontal light sweep, scanline reveal, lens-flare wipe, or light-band write-on.”
- If linear scanning was not explicitly selected, never use a light ribbon, sweep, scanline, or lens-flare wipe as the typography entrance, transition, or product trigger—even as a secondary response. A restrained highlight may describe a verified product surface, but it must not make the words appear, write them on, or carry them across the frame; use material reveal, occlusion, focus / shape match, projection, structural unfolding, refraction, shadow geometry, or a held reveal instead.
- For 30/45-second ads, assign a motion mechanism per sequence and vary it when the product beat changes. Do not reuse the same directional sweep, wipe, or scan to enter every text event; a shared visual world does not require a repeated transition template.
- Tie the text event to a visible product beat: a material change, reveal, impact, opening, motion path, or Hero settle. Keep the full phrase readable long enough for one calm read with a small safety margin; do not replace a complete dwell with a last-frame flash. Keep the product identity, main action, face, and protected brand assets unobstructed.
- Prefer a bold, high-contrast, sufficiently large glyph treatment with deliberate negative space over ornate complexity that causes broken strokes. Effects may respond to motion, but they must never warp, scramble, translate, omit, or introduce extra characters. If the text is not exact, stable across the dwell, clearly legible, and visibly connected to the brand direction, fail the typography gate and regenerate with a targeted treatment correction while preserving the complete Prompt and every non-typography field.
- When the chosen material or background is dark or textured, enforce a minimum local contrast for the full phrase: use a restrained rim highlight, value lift, or shift into clean negative space while preserving the material metaphor. Never solve contrast with a subtitle panel or a postprocess overlay.

## 2.6 H3 capability isolation

- This Skill owns brand-ad video Prompt compilation. Use only the capability summary needed to check whether the confirmed plan can run; private implementation notes are not a writing source.
- Current H3 limits for model choice, duration, aspect ratio, references, audio, and settings are checked at execution time. Those facts may reject an infeasible plan, but may not rewrite confirmed creative direction, copy, typography, or shot descriptions.
- Before submitting, validate every requested generation setting against the current capability summary and send only settings that are currently supported. If execution rejects a setting, retry after removing only that rejected setting while preserving the verbatim compiled Prompt and all confirmed creative fields, including duration intent, canvas, audio, copy, and typography; never silently change the film to make the call pass.
- Prompt structure, camera grammar, copy staging, `Copy Lock`, sound, and quality language come only from this Skill and its explicitly listed references. If the current capability summary is insufficient to validate execution, stop and report the gap; do not invent a workaround.
- This isolation applies only to brand-ad. Once a Prompt is compiled, the executor must not introduce new creative material while summarizing, polishing, or rewriting it.

### Prompt integrity lock

- Compile one final, self-contained Prompt per generated artifact. The string sent to H3 must be verbatim identical to the compiled Prompt recorded before generation; do not shorten, summarize, paraphrase, translate, reorder, or silently rewrite it between compilation and tool execution.
- Never use `same as above`, `same as sequence 1`, `etc.`, ellipses, unresolved placeholders, hidden reference pointers, or a generic style summary in a generation Prompt. Every sequence repeats the shared product identity, Brand Direction Lock, Typography Lock, sound baseline, continuity red lines, and its complete local timecoded beats.
- Each final Prompt must carry the selected motion mechanism, its brand reason, its product trigger, and the targeted anti-template constraint; execution may not reintroduce a rejected horizontal sweep while summarizing or polishing the Prompt.
- When linear scanning was not selected, the final Prompt must separately state that any product highlight is surface-only and cannot reveal, write, wipe, or trigger the typography; execution may not convert that highlight into a text entrance.
- Before execution, confirm that the Prompt contains the exact creative-copy text, the full Typography Lock with its Treatment Card expanded, all shot fields (scene, framing, camera start -> path -> end, action, material / light, transition, audio, typography, end state), and targeted negative constraints. If any field is absent, stop and compile again; capability settings may reject a plan but may not remove creative fields.

## 3. Choose the internal route

Summarize existing material first, and ask only about gaps that would change the route or the film: hero product/series, brand assets, target platform, duration/aspect ratio, narration and CTA. Use the decidable rules below and never expose internal skill names to the user:

| Route | Selection signals | Core deliverable |
| --- | --- | --- |
| **Brand visual process** | Logo/wordmark/visual-system change is the main narrative; words like "sketch, draft, upgrade, design process, reveal, grid page-flip" | draft state -> collage exploration -> grid page-flip -> finished key visual |
| **Product material poetry** | Product, packaging, ingredients, paper, labels, or craft actions star; words like "mood, texture, material, poetic, lightbox, mood reel" | glowing lightbox archive display, material macro, visible craft actions, whitespace ending |
| **Lightweight brand showcase** | Delivery target is explicitly a website hero, site/app, product page, or in-store screen; words like "feature demo, hero screen, page motion, looping display" | real product/UI/site facts -> precise beats -> lightweight brand short |
| **Future-system montage** | A single brand anchor runs through the film; words like "techy, system visuals, HUD, scanning, particles, glitch, tech montage, high-density AE" | subject lock -> system decomposition -> material proof -> identity recall -> hero lock |
| **Product-hero short ad** | Single lightweight piece at 15 seconds, 30 seconds, or 45 seconds; a specific product or series is the sole or absolute protagonist; goal is a commercial ad film | product identity lock -> visual anchoring -> motion compilation -> Hero lock |

On simultaneous hits: explicit logo evolution prefers brand visual process; explicit lightbox archive / poetic craft display prefers product material poetry; explicit website/app/product-page delivery prefers lightweight brand showcase; explicit high-density HUD/scanning/system visuals prefers future-system montage; otherwise an eligible product ad enters product-hero short ad. When still undecidable, present 2 directions and ask the user to choose.

## 3.5 Optional creative references

- [sensory-visual-prompting.md](references/sensory-visual-prompting.md): read when the brief is abstract, a selling point needs to become a visible physical event, or the Prompt needs filmic but executable visual language. It provides translation and Prompt checks, not a fixed shot count or style preset.
- [brand-hero-emotional-structure.md](references/brand-hero-emotional-structure.md): read when the user explicitly wants a fuller brand Hero / TVC-like emotional progression, a macro setup, or a high-density shot proposal. Its five phases and estimated event count are variable references and do not change this Skill's lightweight scope, parallel segmentation, native sound, or actual-duration assembly rules.
- [voice-keyword-typography.md](references/voice-keyword-typography.md): read when the ad needs LLM-compiled screen copy, CTA, narration keywords, or art-typography packaging. H3 renders confirmed creative-copy typography during video generation; protected logos, wordmarks, package text, and legal information may appear only when already present in verified input assets. There is no postprocess text channel, and creative copy must not be silently moved to `ffmpeg` or any other compositor.
- [adsqa-target-answers.md](references/adsqa-target-answers.md): read when the brief is vague, emotion-led, audience-led, or needs stronger persuasion. It turns five target answers into visible / audible evidence and must not override product truth or route ownership.

Do not preload all four references. Read at most the references needed for the current creative; they cannot override identity, product authenticity, current capability checks, or this route contract.

## 3.6 Optional AdsQA target-answer layer

Use an AdsQA-style target-answer sheet when the brief is vague, emotionally led, or asks for a stronger persuasion effect. This is a planning layer inside brand-ad, not a benchmark score and not a replacement for product truth:

1. Write one causal target answer for **Visual Concept**, **Emotion**, **Theme / Core Message**, **Persuasion Strategy**, and **Audience**. Each answer must state what an informed viewer should understand from the finished ad.
2. For each answer, record `required_evidence`, `failure_if_missing`, and `priority`. Evidence must be visible or audible in the ad itself; do not rely on hidden brief context.
3. Map every answer to at least one concrete product action, material response, camera event, sound cue, or exact creative-copy unit. If an answer has no observable evidence, revise the idea before compiling the H3 Prompt.
4. For each selected keyframe or sequence, add one compact visual-reasoning note: unresolved state, viewer position, gaze flow, one dominant composition pressure, physical light source, and the product constraint that must persist. Do not make decorative moodboards or add a user-visible stage plan.
5. Use the answer sheet to resolve ambiguity and to shape the narration arc; never invent claims, import a reference ad's wording or identity, or let AdsQA override verified product facts, asset provenance, route ownership, or the single-pass / sequence rules.

When this layer is used, show the concise answer-to-evidence map in the same pre-generation confirmation. The final self-check must be able to answer all five questions from the generated images, motion, sound, and confirmed copy alone.

## 4. Lightweight style research and the Brand Direction Lock

- After route selection and before writing scripts or storyboards, read [style-research.md](references/style-research.md) and by default ask with confirmation card whether to search for or add style reference images. Explain that searching improves style and brand differentiation but adds an image-selection step and time; skipping is faster but derives style from the brief or existing references with weaker stability.
- Run one research round only after the user opts in; when the user declines, continue with existing references or detailed text and do not persuade again. Skip the question only when the user explicitly requested search, declined search, or restricted the task to uploaded references. If references already exist, ask whether to search for supplements and search only around uncovered gaps.
- The normal research path returns 5-6 direction candidates written to the canvas; the user may select one or more, with no fixed single-selection requirement. If the user explicitly authorizes delegation, select the best-matching one or more directly.
- When category, target duration, and aspect ratio suffice for search, do not separately ask about style, film form, narration, or CTA; converge these in the selected references or the pre-generation confirmation.
- Research ends in one `Brand Direction Lock`: brand personality traceable to facts, one-line visual motif, all selected references and their contributions, 6-8 observable style words, light/color/material/space rules, camera grammar, rhythm curve, transition mechanics, and forbidden-to-transfer content.
- Scripts and storyboards consume that lock: build beats as "brand fact/personality -> visible subject reaction -> matching camera move -> brand ending". Every shot states its start, path, end, and narrative purpose; never reduce every brand to "slow push on product -> two close-ups -> logo freeze".
- With reference images, verify every selected direction image's real path before H3, attach them in the declared order, and state each image's contribution and no-go zones in the Prompt. Unselected candidates never enter generation. The Prompt must also carry the exact creative-copy text and Typography Lock; never replace those with style adjectives or a postprocess text plan.

## 5. Unified lightweight long-form generation rules

- First check the current H3 capability summary for single-pass duration, reference-image limits, and reference handling; if insufficient, split generation without changing the user's target.
- Any video work items with all input refs ready and no dependency on another work item's output may run in one independent batch. Respect the current concurrency limit and never exceed it merely to fill slots.
- Plan 15-second targets as one generation pass when possible, 30 seconds as two independent clips, and 45 seconds as three independent clips. If a longer single pass is supported, fewer clips are allowed while preserving the shared product/brand anchor and ordered creative spine.
- This is an internal ordered batch, not a user-visible Stage plan. Each clip has a `sequence` number; the first establishes the opening and later clips describe only their own local beats without redefining identity or adding a second subject.
- All 30/45-second sequences share the product anchor, `Brand Direction Lock`, canvas, sound direction, and creative spine. Each is an independent video task: never consume another sequence's output, use a tail frame, or set `continuation_of`.
- For a 30/45-second film, sequence 1 must establish a recognizable product identity or verified anchor within the first 3–4 seconds. Abstract atmosphere may create pressure around that proof, but may not postpone the first unambiguous product/material evidence beyond the opening beat.
- Make the opening proof physical and unambiguous: the first 1.5 seconds must show the recognizable product or a verified product anchor itself at useful scale (not only a reflection, silhouette, phone, character, or abstract light), and the same identity must remain visible or causally present by 3–4 seconds. Only after that proof may the sequence widen into atmospheric pressure. If the product cannot appear in the opening frame, use a verified anchor close-up and record why it is sufficient; do not call an unverified reflection an anchor.
- End each clip in a clear, stable state; retry only failed or drifting clips. Completion order does not change final sequence order.
- Once all clips finish, concatenate them in `sequence` order without trimming, padding, looping, or time-stretching to force a nominal target duration. Report the actual sum of clip durations. Targets above 15 seconds do not generate or ask about standalone BGM; retain native narration, ambience, and action effects. The <=15-second path follows the BGM confirmation flow below.
- For 30/45-second sequences with narration, compile one shared `Voice Continuity Lock`: narrator identity, language, vocal age / timbre, mic distance, room perspective, loudness relationship to ambience, pacing range, breath policy, sentence boundaries, and the exact phrase that opens and closes each sequence. The last phrase of one sequence must not be clipped or repeated at the next sequence's start; no new narrator, re-introduction, or music bed may appear between clips.

## 6. Product-hero short ad route

- Accepts one lightweight commercial ad planned at 15 seconds, 30 seconds, or 45 seconds, with a specific product or series as the sole or absolute protagonist. If only weak signals such as "product video / product promo" exist without duration or delivery target, ask first.
- Once selected, read [product-motion.md](references/product-motion.md). Read [product-visual-techniques.md](references/product-visual-techniques.md) only when designing visual anchors or keyframes, and [product-h3-compile.md](references/product-h3-compile.md) only when preparing video generation.
- Do not preload all references. A simple ad can generate directly once product identity, duration, aspect ratio, selling points, copy, and visual direction are clear; add anchors and storyboards only when identity, aesthetic, or multi-shot dependencies exist.

## 7. Brand visual process route

- Defaults: 12 seconds, 9:16, no subtitles; collect brand name, category keywords, assets, slogan, platform, duration, and aspect ratio.
- Visual baseline: warm off-white paper ground, warm ink-black wordmark, ginger / low-saturation yellow as the primary color, with paper fiber, print halftone, contact shadows, and physical card thickness; no dark cyber style by default.
- On the canvas, first establish the draft wordmark frame, the finished key-visual frame, 6-12 collage fragments, the final freeze, and the timeline: 0-1.2s draft; 1.2-5s staggered page flips; 5-7s primary-color expansion; 7-10.5s finished piece; 10.5-12s freeze.
- Organize static keyframes first, then generate continuous motion of paper, cards, and collage fragments. Specify Y-axis page flips, staggered waves, physical thickness, current start/end states, and synchronized paper sounds; do not ask the video model to carry exact brand text or grid counting.
- Keep licensed logos/wordmarks and final stills only when they are already present in verified input assets; do not overlay slogans or other text after generation. Before generating, land keyframes, provenance, concept/authorization boundaries, and sound strategy on the canvas and request confirmation.

## 8. Product material poetry route

- Suggest 15 seconds by default, with aspect ratio decided by placement; label every asset as `identity`, `product`, `texture`, `ingredient`, `process`, `archive`, `typography`, `transition`, or `outro`.
- The core visual is a top-down glowing white acrylic lightbox archive display: real product/packaging with ingredients, label paper, book pages, unfolded packaging, tracing paper, and abstract materials.
- Allocate time by visual breathing: full display 2.5-4s, material macro 0.5-1.2s, craft action 1.5-2.8s; include at least a material macro, visible craft action, and glowing whitespace ending; never split into equal whole seconds.
- Cuts are driven by placement, page turns, occlusion, material change, light/dark shifts, or shape matching. By default avoid generic hero shots, lifestyle ads, bar/party/neon, tech HUD, random charts, and excessive gloss.
- Before generating, land brand facts/provenance, asset roles, visual direction, the non-uniform timecoded storyboard, sound strategy, and authorization notes on the canvas and request confirmation. Ambience, action sounds, and confirmed narration are generated natively by H3; narration gets no separate TTS. Standalone BGM is only for <=15-second targets and only after confirmation.

## 9. Lightweight brand showcase route

- Use only when the website hero, product page, app, store, or another lightweight publishing surface is explicit; without a stated surface, do not choose this route. Suggest 15 seconds when unspecified; pick 16:9 or 9:16 by platform.
- First collect logo/font/color specs, product images/packaging/UI screenshots/site materials, product features and verified claims, CTA, audience, platform, language, subtitle, and narration needs.
- Build a brand fact table and provenance list on the canvas; every identity asset records a stable ID, role, path/node, source, verification target, authenticity status, and publishing notes.
- Choose the story spine by category: AI/SaaS "intent -> capability -> execution -> visible result -> proof -> brand ending"; physical product "hero display -> interaction -> feature close-up -> usage scene -> result -> brand ending"; service/company "problem -> process -> evidence -> outcome -> promise".
- Complete a per-beat storyboard before generating: 5-8 beats for a 15-second plan, each with start/end time, visual subject / asset ID, primary action, product proof, copy dwell, transition, and motion hand-off; one primary action per beat.
- Use real stills, product key visuals, UI plates, or a motion first frame before generating video per confirmed beats. Every Prompt is self-contained with current action, real reference usage, audio strategy, and immutable brand constraints. Confirmed narration includes exact copy, language, voice, tone, and timing in the H3 Prompt; never stack another audio track for the same content.

## 10. Future-system montage route

- Use only when a single brand anchor runs through the whole film and the focus is high-speed system visuals rather than narrative advertising. The anchor may be a licensed logo, product, app, brand figure, or material; without a usable anchor, request one reference image and never invent an existing brand identity from text.
- Finish brand-fact, provenance, and logo-authenticity verification first, then read [future-system-montage.md](references/future-system-montage.md) and follow its input-lock, timeline, Prompt, and sound rules.
- UI density, rhythm, and visual patterns belong in the Prompt only; they are not execution settings. The film must not introduce a second subject, forge a second logo, or let system graphics occlude the subject.

## 11. Unified pre-generation confirmation and delivery checks

Before generating any media, land the brand fact table, provenance summary, route, `Brand Direction Lock`, timecoded storyboard, `Copy Lock` with exact screen copy / CTA / narration, a `Typography Lock` for every creative-copy unit, the complete self-contained H3 Prompt for each artifact, sound strategy, and authorization boundaries on the canvas and request confirmation with a confirmation card; produce only after the user explicitly proceeds. State explicitly that all new on-screen copy must be generated by H3 and that no `ffmpeg` or other postprocess text overlay will be used. When research ran, show selected direction images and their contributions in this same confirmation and verify the H3 preview contains the real image paths in order; add no separate research review.

After video generation completes and lands on the canvas, only ask about standalone BGM when the target is 15 seconds or less: "The video is generated. Should a standalone BGM be created for the film? Generating music adds music production and mixing time; skipping keeps the current H3-native narration, ambience, and action sounds." Offer "Generate BGM" and "No, keep native sound". If the user already chose, follow that choice without asking again. For 30/45-second targets, do not generate or ask about BGM.

When the user chooses BGM for a <=15-second target, use the default official instrumental route without asking for an additional music-model choice or forcing a nominal length. Trim the music only to the final video's actual duration, add a natural tail fade, and mix it with H3's original sound; do not loop, time-stretch, rearrange, re-edit the video, or replace native narration, ambience, or action effects. The video Prompt must exclude BGM. Adjust the route only when the user specifies another music model or the current capability summary shows the default route unavailable, and explain it.

Before delivery confirm identity assets are traceable, facts are not embellished, logos are not stretched/redrawn, product and UI remain clear, rhythm and transitions match the route, `Copy Lock` text is legible and complete, and audio is not duplicated. Reply with the film path / canvas artifacts, actual duration and aspect ratio, route summary, material provenance, and necessary rights notes.
