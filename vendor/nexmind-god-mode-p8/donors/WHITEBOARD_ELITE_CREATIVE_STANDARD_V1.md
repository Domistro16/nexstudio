# NexStudio Whiteboard Elite Creative Standard V1

**Document class:** Creative production contract  
**Phase:** Elite Rebuild — Phase 0  
**Status:** LOCKED  
**Applies to:** Every NexStudio Whiteboard production seeking Creative PASS  
**Supersedes:** Any assumption that technical renderer success implies creative readiness

---

## 1. Product definition

NexStudio Whiteboard is an **illustrated storytelling system that uses a whiteboard as its medium**.

It is not a flowchart generator, diagram template system, icon slideshow, clip-art tracing system, or a marker-hand novelty effect.

A successful Whiteboard film should feel as if a strong illustrator and motion director first decided **what to show, who or what is acting, what changes, what persists, and why the viewer should care**, and only then expressed those decisions through drawn lines, limited fills, physical annotation, spatial continuity, and camera movement.

The renderer is infrastructure. It must never become the visible design language by default.

---

## 2. Non-negotiable creative promise

Every production seeking Creative PASS must satisfy all of the following:

1. **Story before diagram.** A beat is represented by the clearest visual story, not the easiest geometry to generate.
2. **Illustration before conceptual containers.** Characters, objects, environments, product surfaces, physical metaphors, and meaningful diagrams take precedence over arbitrary boxes.
3. **Action before labels.** The viewer should see something happening, not merely read the name of a concept.
4. **One evolving board world.** The board accumulates, transforms, edits, and remembers; it is not a row of slides placed next to each other.
5. **Continuity carries meaning.** Objects, people, routes, marks, and visual metaphors should survive or transform when that improves comprehension.
6. **Annotation interprets.** Circles, underlines, highlights, arrows, brackets, strike-throughs, checks, and handwriting must clarify existing content rather than substitute for it.
7. **Camera movement has a narrative reason.** Follow, discover, focus, reframe, pull back, or synthesize. No decorative drifting.
8. **Physical drawing is selective.** Complex assets are constructed or revealed intelligently; the viewer is never forced to watch every exported SVG path being traced.
9. **Characters perform.** A character is present because they experience, cause, inspect, hand off, react to, or complete something.
10. **Technical PASS and Creative PASS are separate.** Neither can substitute for the other.

---

## 3. What Whiteboard must never default to

The following are **hardly or conditionally rejected defaults**. They may appear only when semantically literal or structurally necessary.

### 3.1 Generic conceptual containers

Rejected default:

- concept = rectangle;
- process = rectangle chain;
- state = rounded card;
- decision = diamond;
- outcome = box with label.

A rectangular construction is permitted when the subject is literally a:

- screen;
- document;
- note;
- card;
- page;
- package;
- sign;
- panel;
- interface surface;
- physical container.

A geometric container used for an abstract idea must have a declared `structuralNecessity` and survive creative review.

### 3.2 Arrow spam

Arrows are permitted for real direction, movement, causality, transfer, attention, routing, or annotation.

They are not permitted as the universal glue between unrelated labelled shapes.

When an object can physically move, transform, pass ownership, reveal consequence, or continue into the next beat, that is preferred over drawing another arrow.

### 3.3 Anonymous nodes

Network/process nodes must represent recognisable semantic entities: people, wallets, tools, services, assets, steps, locations, states, or products.

Anonymous circles and boxes may not dominate a customer-facing production.

### 3.4 Stickman substitution

A crude stick figure may be used only as a deliberately minimal symbol at small scale. It may not be the hero human representation in an elite Whiteboard production.

Hero and supporting humans must come from the approved illustrated character system.

### 3.5 Text transcription

Narration must not simply be rewritten across the board.

Written/type content should exist only when it materially improves:

- orientation;
- recall;
- evidence;
- comparison;
- interpretation;
- numerical comprehension;
- product fidelity.

### 3.6 Slide-world composition

Rejected:

- scene A occupies one rectangle;
- camera pans;
- scene B occupies another rectangle;
- camera pans;
- scene C occupies another rectangle.

Persistent board coordinates do not by themselves create continuity. At least some meaningful visual material must persist, transform, hand off, or influence the next beat.

### 3.7 Decorative hand and marker

The tool is not the protagonist. A hand/pen tip appears only when the physical gesture contributes meaning.

### 3.8 Generic idle motion

Rejected:

- constant bobbing;
- arbitrary breathing loops;
- floating icons;
- meaningless pulse;
- repeated arm wave;
- whole-scene wobble.

Motion must have a semantic owner and target.

---

## 4. The six visual responsibilities

Every narrative beat must answer six questions before it is eligible for production rendering.

### R1 — What is happening?

A concrete `coreAction` is required.

Examples:

- customer receives;
- founder compares;
- agent hands off;
- document is rejected;
- payment settles;
- notes reorganize;
- evidence accumulates;
- user publishes.

Bad answer: `PROCESS`.

### R2 — Who or what experiences it?

A `storySubject` must exist.

It can be:

- person;
- team;
- product;
- agent;
- wallet;
- document;
- package;
- market;
- machine;
- dataset;
- physical metaphor.

Abstract concepts are not sufficient unless the beat is genuinely abstract and declares why.

### R3 — What should the viewer notice first?

Each beat requires a single `heroFocus`.

Supporting material must be subordinate.

### R4 — What visual action expresses the idea?

Each beat requires a `visualAction`, which may differ from narration.

Example:

Narration: “The team finds the repeated complaint.”  
Visual action: Three customer notes arrive; two matching phrases are circled; the matching notes move together.

### R5 — What survives or transforms?

A `continuityObject` must either:

- persist;
- transform;
- hand off;
- erase for a reason;
- become background memory;
- explicitly terminate.

Unexplained disappearance is a continuity failure.

### R6 — How does this beat change the board?

A `boardChange` is required:

- adds evidence;
- organizes clutter;
- changes ownership;
- reveals consequence;
- transforms state;
- edits an assumption;
- builds a system;
- resolves a question;
- delivers an outcome.

If a beat leaves the board conceptually unchanged, it is probably not a useful visual beat.

---

## 5. Representation classes

The Visual Director must select a representation class intentionally. Permitted launch classes are:

1. `human-situation`
2. `human-interaction`
3. `object-story`
4. `environment-fragment`
5. `physical-metaphor`
6. `product-interaction`
7. `data-in-context`
8. `meaningful-process`
9. `meaningful-network`
10. `comparison`
11. `spatial-map`
12. `transformation`
13. `handoff`
14. `review-approval`
15. `outcome-publish`
16. `hybrid`

`generic-diagram` and `text-card` are not certified representation classes.

A process/network class must set `structuralNecessity=true` and describe the real semantic entities represented.

---

## 6. Hero/support/symbol hierarchy

Every visible production asset is assigned a visual tier:

### Hero
Primary story carrier. Highest readability, strongest silhouette, greatest expressive detail.

### Support
Explains context or consequence. Lower visual weight.

### Symbol
Compact semantic shorthand. Minimal detail.

A symbol may never visually overpower the hero because it happens to contain more SVG detail.

---

## 7. Human-story rule

A human character is not mandatory in every beat or every film. It is mandatory **when lived experience, behaviour, decision, work, use, reaction, trust, collaboration, or customer outcome is central to the narrative**.

The Director must not replace an obviously human moment with anonymous nodes merely because nodes are easier to lay out.

Conversely, it must not force characters into inherently structural scenes where they reduce clarity.

---

## 8. Character creative contract

When a character is present:

- they must have a semantic role;
- they must have a concrete action or meaningful reaction;
- their attention target must be identifiable where applicable;
- gestures must point toward real targets;
- held objects have explicit ownership;
- handoffs transfer the same logical object once;
- no generic idle motion is required;
- hero humans cannot use crude stickman rendering;
- repeated poses across adjacent beats are discouraged unless continuity requires them.

---

## 9. Object and icon creative contract

Icons are vocabulary, not story substitutes.

An icon should:

- identify a concept quickly;
- support a character/object interaction;
- participate in a process when structurally meaningful;
- become data, evidence, or another state when useful.

A production must not read like an icon catalogue.

Props should create physical relationships: person holds phone, document lands on desk, package moves, screen is inspected, receipt is produced.

---

## 10. Diagram contract

Diagrams remain valid when the idea is actually structural.

A diagram seeking Creative PASS must:

- use semantic entities rather than anonymous nodes wherever possible;
- establish one clear hero relationship;
- avoid redundant connectors;
- keep text subordinate;
- have an explicit structural reason;
- integrate with the surrounding illustrated board rather than arrive as a separate slide.

Consecutive diagram-heavy beats are capped unless a reviewer approves a justified structural sequence.

---

## 11. Text budget and text-removal test

Every beat must declare one of:

- `textCanBeRemoved=true`, meaning the central story remains intelligible without labels;
- or `textCriticalReason`, limited to cases such as exact product UI, factual number, quote, legal wording, name, or comparison label.

A scene that becomes meaningless when its text is hidden is a creative failure unless the subject is intrinsically textual.

Handwritten annotation is capped to short phrases. Paragraph handwriting is prohibited.

---

## 12. Annotation contract

Every annotation declares a semantic purpose:

- focus;
- importance;
- relationship;
- correction;
- confirmation;
- question;
- comparison.

No annotation may be added solely to make the board look more “whiteboard-like.”

The object should normally exist and be understandable before annotation interprets it.

---

## 13. Motion ownership contract

Every motion event requires:

- `owner` — what moves;
- `action` — what it does;
- `target` — where/what it acts on when relevant;
- `purpose` — why the story needs the motion.

Unowned motion and ornamental loops are rejected.

---

## 14. Camera contract

Permitted narrative camera intents:

- `follow`
- `discover`
- `focus`
- `reframe`
- `pullback`
- `synthesis`
- `hold`

A camera move must declare a `revealOrReason`.

Camera travel is not considered continuity by itself.

---

## 15. Persistence contract

Every hero/support object receives one of:

- `persistent`
- `temporary`
- `transform`
- `handoff`
- `erase`
- `background-memory`
- `terminate`

The board should become richer in meaning, not merely fuller in objects.

---

## 16. Final-board quality

A final synthesis pullback is not automatically required, but when used it must reveal a visually coherent composition.

The final board must not resemble:

- an architecture diagram;
- a debugging canvas;
- rows of disconnected slides;
- a wall of tiny labels;
- an uncontrolled asset dump.

It should reward the viewer by revealing relationships established through the film.

---

## 17. Machine creative preflight vs human Creative PASS

Creative certification has three independent layers.

### Layer A — Technical QA

Renderer/runtime correctness.

### Layer B — Creative structural preflight

Machine-checkable requirements from this contract:

- visual responsibilities answered;
- certified representation classes;
- hierarchy present;
- conceptual-container limits;
- connector limits;
- text-removal declaration;
- action ownership;
- camera purpose;
- continuity policy;
- representation repetition;
- annotation purpose;
- no hero stickman substitution.

A structural preflight PASS **does not equal elite taste**.

### Layer C — Human creative review

Required for final Creative PASS.

No production can claim `creativeStatus=PASS` while human review is pending.

---

## 18. Human elite review rubric

Each finished production is scored 0–10 on:

1. story clarity;
2. illustration quality;
3. character/subject storytelling;
4. visual hierarchy;
5. representation originality and appropriateness;
6. continuity and transformation;
7. motion intentionality;
8. annotation restraint/intelligence;
9. board composition;
10. final synthesis/payoff.

### Elite certification thresholds

- overall mean: **>= 9.0**;
- no category below **8.0**;
- clarity, illustration quality, continuity, and board composition each **>= 9.0**;
- zero hard creative rejects.

A reviewer may reject despite numeric average if one serious issue makes the piece visibly non-production-grade.

---

## 19. Hard creative rejects

The following immediately block Creative PASS:

- hero represented by crude stickman where an illustrated human is required;
- generic box-and-arrow chain is the dominant storytelling language without structural necessity;
- film depends on reading labels to understand its central action;
- character gesture has no meaningful target;
- duplicated handoff object or broken object ownership;
- repeated slide-pan-slide construction masquerading as persistent board continuity;
- raw unnormalised external illustration used in production;
- unlicensed/unverified asset used in production;
- camera motion that materially harms comprehension;
- final synthesis board is visibly incoherent;
- technical QA failure.

---

## 20. Phase 0 certification rule

Whiteboard V1 remains a technically useful engine. It is **not creatively certified by inheritance**.

The rejected Golden Slice 01 is retained only as negative evidence of the failure mode this contract prevents.

All future Whiteboard Elite Rebuild phases must satisfy this standard and may tighten it, but may not silently weaken its hard rules.
