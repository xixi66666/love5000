# Domain Docs

This repo uses a single-context domain-doc layout for engineering skills.

## Before exploring, read these

- `CONTEXT.md` at the repo root, if it exists.
- `docs/adr/`, if it exists, for architectural decisions that touch the area being changed.

If these files do not exist, proceed silently. Do not flag their absence or create them upfront. Producer workflows such as `grill-with-docs` can create them lazily when domain terms or decisions are resolved.

## File structure

```text
love5000/
├── CONTEXT.md
├── docs/
│   └── adr/
│       ├── 0001-example-decision.md
│       └── 0002-example-decision.md
├── common/
├── lovestory/
├── website/
└── imagetemplate/
```

## Use the glossary's vocabulary

When output names a domain concept in an issue title, refactor proposal, hypothesis, or test name, use the term as defined in `CONTEXT.md`. Avoid drifting to synonyms that the glossary does not use.

If the needed concept is not in the glossary yet, treat that as a signal: either the work is inventing language the project does not use, or the glossary has a gap to resolve later.

## Flag ADR conflicts

If output contradicts an existing ADR, surface the conflict explicitly rather than silently overriding it.
