# Component provenance

- Animated Tabs: adapted from preetsuthar17, retrieved through the user's 21st.dev account (demo 1962): https://21st.dev/@preetsuthar17/components/animated-tabs. Adaptation uses controlled selection, Radix keyboard behavior, and Motion's reduced-motion support; avoids duplicate interactive elements.
- The component architecture follows shadcn/ui conventions (local source, CVA, Radix, Tailwind, `@/` aliases, `components.json`). The 21st catalog helper is development-only and never ships to the browser.
- React Flow: graph rendering; Dagre lays out the investigation tree; d3-force (ISC, Mike Bostock) lays out the knowledge graph. Attribution remains visible.
- 3Dmol.js: local/browser molecular rendering. RCSB structures are fetched only after the user chooses an ID or explicitly opens the reference example.
- IBM Plex Sans / Mono: self-hosted via Fontsource, SIL Open Font License.

David's DESIGN.md and research/sprint/D1 informed the restrained design direction. No David application code or data was copied.

- Latent Nature wordmark: outlined DejaVu Sans Bold glyphs, reduced relative to the custom emblem. Bitstream Vera license; DejaVu changes are public domain. See [font license](licenses/DejaVu.txt).
