"""Market & competitor comparison (Milestone 9I-B).

A beta-internal layer that structures a market/competitor comparison built ONLY from
imported public sources (M9I-A). Every shown item is source-backed by a deterministically
verified exact quote, or marked needs_human_review / insufficient_evidence. It never
rewrites proposal text, never updates A2, never approves, and never invents market facts.
No finalized contract is modified (the structuring agent profile + schemas are code-only;
the endpoints are documented beta-internal).
"""
