# Detection manifests

Priority-ordered rules that classify a captured pane as `blocked`/`error`
(an override) or veto detection (`none`, defer to the quiescence classifier).
See `docs/superpowers/specs/2026-07-27-manifest-detection-engine-design.md`.

Rule *content* (the observable strings agents print) was adapted from
[ogulcancelik/herdr](https://github.com/ogulcancelik/herdr) at commit `dc2506e`
(Apache-2.0), reworked into Lumbergh's own manifest schema. These are factual
observations of third-party agent UIs, not a copy of herdr's files.
