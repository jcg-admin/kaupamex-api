#!/usr/bin/env node
// save-agent-result.mjs — SubagentStop hook (kaupamex).
//
// Reads the subagent-stop payload on stdin, extracts the agent's final
// assistant message from its transcript, and appends it (ISO-timestamped)
// to an append-only log. NEVER breaks the flow: always exits 0, swallows
// every error. The timestamp is a real runtime value (new Date()), not a
// value written from memory (complies with timestamps-iso8601-obligatorios).
//
// Log destination: <super-root>/.claude/agent-results/registro-de-agentes.md
// (operational telemetry; complements the curated reporte-*.rst in docs
// per registro-reportes-agentes.md — see .claude/rules/agent-results-to-docs.md).
import { readFileSync, mkdirSync, appendFileSync, existsSync } from 'node:fs';
import { dirname, join, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

function main() {
  const here = dirname(fileURLToPath(import.meta.url)); // .../.claude/hooks
  const superRoot = dirname(dirname(here));             // super repo root
  const logDir = join(superRoot, '.claude', 'agent-results');
  const logFile = join(logDir, 'registro-de-agentes.md');

  let raw = '';
  try { raw = readFileSync(0, 'utf8'); } catch { return; }
  let payload = {};
  try { payload = JSON.parse(raw || '{}'); } catch { return; }

  const transcript = payload.transcript_path;
  if (!transcript || !existsSync(transcript)) return;

  // Extract the LAST assistant text block from the JSONL transcript.
  let lastText = '';
  try {
    for (const line of readFileSync(transcript, 'utf8').split('\n')) {
      if (!line.trim()) continue;
      let obj;
      try { obj = JSON.parse(line); } catch { continue; }
      const msg = obj.message;
      if (obj.type === 'assistant' && msg && msg.role === 'assistant') {
        const c = msg.content;
        if (typeof c === 'string') {
          if (c.trim()) lastText = c.trim();
        } else if (Array.isArray(c)) {
          const txt = c.filter(b => b && b.type === 'text' && b.text)
                       .map(b => b.text).join('\n').trim();
          if (txt) lastText = txt;
        }
      }
    }
  } catch { return; }

  if (!lastText) return;

  const ts = new Date().toISOString().replace(/\.\d+Z$/, 'Z');
  const session = payload.session_id || 'unknown';
  const entry = `\n## ${ts}\n- **session**: ${session}\n- **transcript**: ${basename(transcript)}\n\n${lastText}\n\n---\n`;

  try {
    if (!existsSync(logDir)) mkdirSync(logDir, { recursive: true });
    if (!existsSync(logFile)) {
      appendFileSync(logFile,
        '# Registro de agentes (auto)\n\n' +
        'Reporte final de cada subagente, capturado por el hook SubagentStop. ' +
        'Append-only.\n\n---\n');
    }
    appendFileSync(logFile, entry);
  } catch { return; }
}

try { main(); } catch { /* never break the flow */ }
process.exit(0);
