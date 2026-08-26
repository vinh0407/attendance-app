# UTH Student Portal — design direction

## Direction

Academic ledger: a calm institutional workspace built from a visible grid, paper-white surfaces, thin rules, and strong typographic hierarchy. The portal should feel like an official academic record made easy to scan, not a SaaS dashboard.

## First viewport

Persistent UTH identity and navigation frame the page. The main column opens with the student's real identity context, then answers “today” through a single schedule rail and a compact academic status row. The right rail carries actionable notices and a quiet backend status, not decorative metrics.

## System grammar

- Palette: white, cool blue-gray canvas, provisional UTH blue `#0759A5`, dark navy ink, one muted gold mark for the institution.
- Shape: 8px corners, 1px borders, no glass, no gradients, no oversized floating cards.
- Type: system sans with tabular numerals; headings are compact and confident, body copy is readable.
- Topology: fixed desktop sidebar, constrained content grid, compact bottom navigation on mobile.
- State: labels and empty states are explicit; unavailable student data is marked `[BACKEND REQUIRED]`.
- Motion: one restrained page-load reveal and small transform/opacity feedback; all disabled under reduced motion.

## Responsive contract

At 1024px the sidebar becomes compact. At 768px it becomes a drawer. At 640px the page uses one column and a five-item bottom navigation; tables become stacked rows or horizontally scrollable only where comparison requires it.

## Content contract

The demo ships with no fake student, grade, schedule, attendance, message, notification, or forum records. The interface contract is ready for API data and makes missing endpoints visible.
