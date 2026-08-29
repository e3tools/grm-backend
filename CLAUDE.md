# CLAUDE.md

Project guidance for Claude Code in this repo.

## Writing and communication

Use plain technical language. No buzzwords, no marketing tone. Say the thing directly.

Why: precise words point at real code. Vague words hide the fact that a decision hasn't
been made yet, and that costs a round trip to find out.

**Avoid:** leverage, utilize, robust, seamless, cutting-edge, best-in-class, holistic,
synergy, empower, unlock, streamline, delve, elevate, game-changing, next-generation,
enterprise-grade, world-class, revolutionize, transformative, "at scale" as a decoration.

**Instead:** name the actual thing — the function, model, endpoint, table, setting, or
number.

- "use" not "leverage" / "utilize"
- "the query drops from 400ms to 40ms" not "significantly improved performance"
- "retries 3 times with backoff" not "robust error handling"
- "reads from Postgres instead of CouchDB" not "modernized the data layer"

Other rules:

- No preamble. Skip "Great question!", "Certainly!", "Let me help you with that."
- No summary of what you just did unless it changed something the user can't see.
- If something is uncertain, say so plainly and say what would settle it.
- Prefer a number, a file path, or a line reference over an adjective.
- Same rule applies to code comments, commit messages, docstrings, and any Markdown
  written into this repo — including generated docs and BMad artifacts under
  `_bmad-output/`.
