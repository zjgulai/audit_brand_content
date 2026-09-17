---
name: video-deconstruct
description: |
  Deconstruct video, keyframes, screenshots, or a description into evidence on shots, motion, sound, and continuity, and deliver a recreation prompt and edit plan. Not for critique or plain editing.
trigger-words: [video deconstruction, recreate this video, reverse engineer video prompt, shot-by-shot analysis, video prompt reconstruction, structure-preserving remake]
exported-by: MiniMax-hub
---

# Video Deconstruction & Recreation

Evidence first: read the video and keyframes before writing conclusions and the recreation contract. Never treat "analysis" as a substitute for direct generation, and never present screenshot speculation as video facts that were actually read.

## Input and evidence chain

1. When the user uploads a video, first read metadata and semantics with media analysis; record duration, aspect ratio, resolution, subjects, scenes, actions, shots, lighting, pacing, and audible sound.
2. When semantic analysis fails, is too coarse, or the user requests a precise recreation, build high-density keyframe contact sheets with media assembly: at least 10–12 frames within 15 seconds; longer videos split into readable consecutive segments per sheet; raise to roughly one frame per second for fast action or dense transitions. Sheet capacity must not be smaller than the actual number of extracted frames.
3. Write the keyframe sheets to the canvas; write the full Markdown report to the canvas as well, linking the keyframes via `source-node links`. When only screenshots or text descriptions exist, explicitly mark which actions, sounds, or timings are speculation only.
4. When given only a URL, do not promise to download external video; ask the user to upload the video, keyframes, or a sufficient text description.

## Deconstruction report

When the user has not specified a focus, deep-dive characters/subjects, plot/action, shots/camera moves, lighting/style, and pacing by default; when specified, do not re-ask. The report includes:

1. Metadata, analysis basis, and a one-sentence characterization;
2. Keyframe count, sheet count, and time coverage;
3. Characters and visual anchors, scenes, action timeline, shots, lighting and color, style and materials, editing rhythm, sound;
4. Reproducible facts, undeterminable items, and risks (faces, hands, multi-person identity, text, fast motion, or style drift);
5. The H3 recreation plan, unified constraints, and a self-check conclusion.

Keep the same name and visible identifiers for each subject; describe framing, camera position, camera moves, light sources, materials, and actions with observable evidence — never replace analysis with empty words like "cinematic" or "premium".

## Compiling the video recreation contract

Check the current capability summary first to confirm the selected video model's supported duration, aspect ratio, resolution, audio, and reference range. Default to MiniMax H3 when the user has not specified a model; when the user locks another model, compile against that model's capability guidance and never silently switch back to H3.

1. Group by continuity, not by fixed 15-second segments. When subject, scene, action flow, sound intent, and refs are compatible, form the longest feasible clip group; split only on scene crossings, hard subject/style cuts, first/last-frame dependencies, or runtime capability limits.
2. For each group, write the starting state, the continuous action, and a hand-off-ready end state. The next group starts from the previous group's visible end state or an explicit cut — "stay consistent" alone is not a fact.
3. When the current model is MiniMax H3, produce the final prompt with this order: `global baseline → role of each reference asset → environment and lighting → spatial baseline → (when dialogue exists) character voice signatures → visual progression → sound design → visual style`. Per shot, write in order: framing, camera position/viewing direction, one primary camera move, subject behavior, significant background feedback, dialogue or synchronized sound, and end state; other models use their own capability guidance.
4. Use the user-provided assets and valid evidence on the canvas. Each `@image N`, `@video N`, `@audio N` must state item by item the identity, scene, style, action, or sound it locks; keep the user's attachment order. Ordinary reference images are not first/last frames — treat them as first frame, last frame, or keyframes only when the user explicitly says so.
5. The model's auto-optimization may only fill unspecified gaps: it must not delete or alter subjects, actions, spatial relations, composition, shot order, sound, or negative requirements; when the user asks for silence, no dialogue, no music, or only specified sounds, preserve that strictly. Exact UI, text, or graphic requirements must be locked verbatim, not blanket-removed with "no text/logo".
6. When the current model is MiniMax H3 and photoreal people are clearly visible, write natural matte skin, normal skin tones, realistic detail, and the lighting the shot actually needs; for multi-person shots, establish relationships with a wide shot first, then carry the interaction with medium/close shots of varying information density, avoiding face blending and duplicated faces.
7. When the current model is MiniMax H3, use the current capability guidance as the engineering source of truth; with multiple reference assets, also read and follow the refs-binding rules in `references/minimax-h3-multi-ref.md`.

## Delivery and execution

1. By default, deliver two document nodes on the canvas: "Video Deconstruction Report" and "Video Recreation Plan". The recreation plan lists each clip group's duration/aspect/model lock, refs, prompt, start and end states, and risk points.
2. When the user only wants analysis or prompts, stop at the editable recreation plan and do not call generation; when the user explicitly asks to generate, call video generation with the confirmed model lock and ordered refs.
3. After completion, check: keyframe evidence is on the canvas; every conclusion has evidence or a speculation marker; the final prompt satisfies the current model's full contract with per-shot action/sound; refs match the asset order one-to-one; no leftover template variables, no unsupported new plot, and no dropped user constraints.

## Boundaries

- Do not apply a fixed "one timestamped prompt per 15 seconds" as a universal rule, and do not output another model's dedicated template to non-Seedance models.
- Do not auto-generate subtitles, readable logos, or watermarks because of a deconstruction task; but preserve exact text/UI the user explicitly requires and use a deterministic overlay path.
- Plain editing, subtitles, compression, transcoding, or film critique alone does not trigger this Skill.
