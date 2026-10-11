# AI Infrastructure Learning

Personal learning workspace for AI infrastructure engineering (LLM inference and serving).
Unrelated to the OTTfilter application in the rest of this repository.

| Path | What it is |
|---|---|
| [`guide/AI_Infrastructure_Field_Guide.pdf`](guide/AI_Infrastructure_Field_Guide.pdf) | 40-page field guide: the 12-stage roadmap fact-checked and expanded, plus a "Beyond the roadmap" chapter |
| `guide/guide.html`, `guide/render.js` | Source for the PDF. Re-render with Playwright: `node render.js` from `guide/` |
| [`llmbench/`](llmbench/) | Benchmark harness for OpenAI-compatible LLM servers, with a simulated GPU server for experiments without hardware |
| [`llmbench/LEARNING.md`](llmbench/LEARNING.md) | How to learn with the harness: reading questions, experiments, and unsolved extension exercises |

Start with the guide, then `llmbench/LEARNING.md`.
