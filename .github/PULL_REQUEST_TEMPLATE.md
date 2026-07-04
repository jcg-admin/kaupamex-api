#### Issue / reference

<!--
Link the GitHub issue, or the internal reference this PR addresses:
a use case (UC-...), decision (DEC-...), finding (F-NN), task (T-NNN)
or ADR. Write "N/A - typo" for trivial fixes.
-->


#### Branch description

<!--
Concise overview of the problem and the rationale behind the change.
Explain what and why, not how (the diff already shows how).
-->


#### AI assistance disclosure (required)

<!-- Select exactly ONE. -->

- [ ] No AI tools were used in preparing this PR.
- [ ] AI tools were used; I have disclosed which ones below and fully reviewed and verified their output.

<!-- If used, name the tool(s) here: -->


#### Checklist

- [ ] Commits follow the Tim Pope style: imperative subject (<= 50 chars, capitalized, no trailing period), body wrapped at 72 explaining what and why. No Conventional Commits.
- [ ] Author identity is `Nestor Monroy <46802445+NestorMonroy@users.noreply.github.com>`.
- [ ] This PR targets `develop` (never a direct push to `develop` or `main`).
- [ ] No security vulnerability is disclosed here, and no secrets are committed (MercadoPago keys, `.env`, tokens).
- [ ] Tests added or updated; `uv run pytest --reuse-db` passes for the affected area.
- [ ] Quality gates pass: no-lazy-imports, silent-OKs, and canon-idioma (`codigo_error`, not `error_code`).
- [ ] DB access follows the socket-first convention; any new migration was applied to the QA schema.
- [ ] Relevant docs/UCs updated; buyer-facing endpoints described as `/api/v2/` (MercadoPago webhooks/legacy stay `/api/v1/`).
