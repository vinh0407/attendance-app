# Design direction

<!-- impeccable:design-schema 1 -->

## World

Institutional wayfinding for a university entrance: the screen should feel like a precise campus sign, not an AI scanner demo. Blue rules and compact labels create orientation; the live camera is the only dominant visual object.

## Surface mode

Operate. A student should understand the next action within five seconds and complete a scan without touching the kiosk.

## Composition

- Portrait 4:6 is the primary composition; landscape is a deliberate fallback.
- Header: provided UTH mark, university name, and face-attendance label.
- Main: large real camera feed with a quiet face guide.
- Secondary: one concise status message and actual class/session metadata.
- Footer: system state, clock, and device identifier.

## Visual tokens

- White surface with a very pale blue support surface.
- Provisional UI blue `#0759A5` and dark navy `#08345F` until an official UTH web palette is supplied.
- Ink `#11243B`, muted slate `#5F7186`, border `#D7E1EC`.
- Accessible green `#147A52` and red `#B73636` for confirmed system states.
- Small 8–10px radius scale; thin borders; no gradients, glass, neon, or oversized cards.
- Segoe UI / Arial system stack for reliable kiosk rendering; monospace only for technical metadata.

## Motion and states

Motion is brief and functional: camera readiness, recognition, success, duplicate, unknown face, multiple faces, and recoverable errors. Reduced-motion users receive the same information without animation.

## Non-negotiables

The provided logo asset is used without recreation or distortion. No fake attendance or session data. The existing Django/InsightFace APIs remain the source of truth.
