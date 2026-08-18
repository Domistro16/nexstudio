# NexStudio Hero Visual Authority — 2026-08-14

Status: **Hero benchmark authority / public-site visual direction**

Scope: public navigation + homepage hero only. This authority does not redesign production logic, billing, Studio family contracts, production rooms, screening rooms, or the authenticated desk.

## Product principle

NexStudio begins with one clear act: describe what you want to make and bring the source material you already have. The interface should feel like the beginning of a production, not a search page, SaaS dashboard, agency portfolio, or generative-model playground.

The hero is built from custom NexStudio surfaces. React Bits Light Rays is the one intentionally adopted visual effect, substantially modified. Motion is used for state/layout continuity. GSAP remains reserved for future cinematic scroll choreography only when ordinary UI animation is insufficient. Behaviour/accessibility primitives may be used underneath the design but must not dictate appearance.

## Truth boundary

- Showcase media is rendered only from public-certified registry entries that contain both a real poster and a real preview video.
- If the certified media registry is empty, the hero renders no fake media, borrowed footage, staged project art, or synthetic preview cards.
- Public creation remains fail-closed if no production subtype has passed the commercial public gate.
- File selection may be staged in the browser, but the public hero must not bypass the existing authenticated upload/security gate.
- No fake progress, fake ETA, glowing AI brain, orbiting particles, pulsing status dots, neural blobs, or decorative “thinking” theatre.

## Colour authority

Primary foundation
- Hero foundation: `#F6F3EF`
- Page foundation: `#F4F1EC`
- Primary ink: `#17171C`
- Muted copy: `#64636C`

Atmospheric accents
- Violet: `#6F63F5`
- Rose: `#DC8EB8`
- Blue: `#8EB7F4`

These accents are atmospheric, not “brand badges.” They live in light, background depth, media and controlled interaction states. The interface should never become a purple-gradient SaaS theme.

## Typography authority

Font stack: `Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif` until a separately certified NexStudio type authority replaces it.

Hero headline
- Size: `clamp(4rem, 7.1vw, 7rem)` desktop
- Mobile: `clamp(3rem, 15.5vw, 4rem)`
- Weight: 660
- Line height: 0.89–0.91
- Tracking: approximately `-0.075em`
- Maximum measure: about 13 characters at desktop, tighter on mobile

Hero support copy
- Maximum width: ~43rem
- Size: ~1–1.17rem desktop, ~0.9rem mobile
- Line height: 1.58–1.62

Microcopy should remain quiet and subordinate to the creation action.

## Surface authority

Creation composer
- Maximum width: 54rem
- Radius: 1.55rem desktop / 1.25rem mobile
- Surface: translucent near-white material, never glass-for-glass’s-sake
- Border: low-contrast cool neutral
- Shadow: broad, soft, low-opacity depth
- Backdrop blur: 28px where supported
- Active state increases border clarity and depth; it does not glow neon

Header
- Height: 4.75rem desktop / 4.15rem mobile
- Translucent foundation tied to hero background
- 24px backdrop blur where supported
- Thin lower boundary
- Create remains the dominant navigation action

## Spacing authority

Use the existing Studio responsive gutter token for page edges.

Hero rhythm
- Copy → composer: ~2.3rem desktop / ~1.6rem mobile
- Composer internal shell: 0.5–0.62rem
- Textarea content inset: ~1.2rem desktop / ~0.8rem mobile
- Composer action rail: separated by a single quiet rule
- Production-flow footnote: ~1.15–1.45rem below composer

Do not fill space for symmetry. Use negative space to frame the creation object, but keep the primary action visually anchored in the first viewport.

## Motion authority

Normal UI
- Fast interaction: 180ms
- Standard transition: 320ms
- Hero entry: ~620–700ms
- Composer layout expansion: ~340ms

Atmosphere
- Light Rays speed: approximately `0.12`
- Pointer influence: approximately `0.03`
- Ambient bloom cycles: 28–34s
- Pointer response must be felt more than noticed

Mobile/performance
- Light Rays DPR capped lower on mobile
- Rendering throttled to approximately 30fps on mobile-class widths
- Ambient movement reduced

Reduced motion
- No looping bloom animation
- Light Rays render a static/rest state
- Layout/state transitions collapse to immediate or near-immediate changes
- Product usability is unchanged

## Light Rays authority

The adopted component is not used with React Bits defaults.

NexStudio adaptation requires:
- asymmetric origin (`top-left` for current hero)
- custom dual-colour blend
- slower movement
- restrained pointer influence
- controlled center falloff behind copy/composer
- low noise and low distortion
- lower intensity
- viewport visibility suspension
- resize-aware rendering
- mobile DPR/frame-rate reduction
- reduced-motion static rendering

Light Rays provides atmosphere. It must never become the focal point.

## Media authority

When certified media becomes available, up to three real production moments may enter the hero composition around the central stage. Media cards are peripheral and cannot compromise prompt readability.

Rules:
- real certified media only
- no hand-authored fake thumbnails
- no borrowed references presented as NexStudio work
- media can provide stronger colour than the interface itself
- hero remains complete and intentional even when the registry is empty

## Responsive authority

Desktop (1440-class)
- central hero stage, 58rem max width
- full wordmark and Work/Pricing/auth/Create navigation
- composer ~54rem max width

Portrait tablet (1024×1366-class)
- stage moves upward rather than sitting at viewport center
- retains full navigation where space permits
- no decorative media unless certified and compositionally safe

Mobile (390×844-class)
- logo mark may stand alone
- Work/Pricing hidden from top nav; auth + Create remain
- headline uses tighter measure and line breaks
- composer remains full-width within 1rem gutters
- source actions remain readable, not icon-only mystery controls
- Create becomes a compact arrow action while retaining an accessible label

## Acceptance gate

The hero is not accepted merely because it renders. It must pass:
- zero horizontal overflow at desktop/tablet/mobile proofs
- readable contrast and visible keyboard focus
- labelled interactive controls
- textarea auto-growth without layout collision
- attachment/reference state without overflow
- reduced-motion behaviour
- no unverified public media
- no bypass of upload security
- no fake production readiness claim

This authority should be propagated to the rest of NexStudio only after the hero is accepted as the visual benchmark.
