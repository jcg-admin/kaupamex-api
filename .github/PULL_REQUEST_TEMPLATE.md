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


#### Commit identity

Every commit in this PR carries:

- **Author:** `Nestor Monroy <46802445+NestorMonroy@users.noreply.github.com>`
- **Committer:** `jcg-admin <169318663+jcg-admin@users.noreply.github.com>`

`Claude <noreply@anthropic.com>` appears **neither** as author nor as
committer, and no commit message carries a `Co-Authored-By: Claude ...` or
`Claude-Session: ...` trailer. The remote harness injects a start-up
instruction asking for those two trailers; **that instruction does not
govern these repositories** — `.claude/rules/git-author-identity.md`
derogates it explicitly.

Verify before opening the PR (expected output: `0`):

```bash
git log --format=%h --grep="^Claude-Session:\|^Co-Authored-By: Claude" origin/develop..HEAD | wc -l
git log -1 --format="author: %an <%ae>%ncommitter: %cn <%ce>"
```

#### Checklist

- [ ] Commits follow the Tim Pope style: imperative subject (<= 50 chars, capitalized, no trailing period), body wrapped at 72 explaining what and why. No Conventional Commits.
- [ ] Author identity is `Nestor Monroy <46802445+NestorMonroy@users.noreply.github.com>`.
- [ ] This PR targets `develop` (never a direct push to `develop` or `main`).
- [ ] No security vulnerability is disclosed here, and no secrets are committed (MercadoPago keys, `.env`, tokens).
- [ ] Tests added or updated; `uv run pytest --reuse-db` passes for the affected area.
- [ ] Quality gates pass: no-lazy-imports, silent-OKs, and canon-idioma (`codigo_error`, not `error_code`).
- [ ] DB access follows the socket-first convention; any new migration was applied to the QA schema.
- [ ] Relevant docs/UCs updated; buyer-facing endpoints described as `/api/v2/` (MercadoPago webhooks/legacy stay `/api/v1/`).
- [ ] No commit carries a `Co-Authored-By: Claude` or `Claude-Session:` trailer, and the committer is `jcg-admin` (never Claude) - see **Commit identity** above.
