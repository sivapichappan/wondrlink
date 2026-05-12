# shared/

Source-of-truth TypeScript constants, types, and copy strings shared across
WondrChat clients.

Today only the mobile app (`mobile/`) imports from this folder. The web app
(`public/index.html`) is vanilla JS and embeds its own copies of these
strings. When the web app is rebuilt with TypeScript it should consume from
here too — until then, this folder is the **second authoritative location**
for copy that must stay in sync.

## Sync rules

When you change a value here, also update the matching source listed below.

| `shared/` file | Python / web counterpart | Notes |
|---|---|---|
| `consent-version.ts` | [lib/compliance.py](../lib/compliance.py) | `CURRENT_CONSENT_VERSION`, `BLOCKED_STATES`, `MHMDA_STATES`, `US_STATES`, `REQUIRED_CONSENT_FIELDS` |
| `api-contracts.ts` | [api/index.py](../api/index.py) | Endpoint paths only — server is source of truth for request/response shape |
| `types.ts` | [api/index.py](../api/index.py) | TypeScript shape of API request/response envelopes |
| `disclaimers.ts` | [public/index.html](../public/index.html) (AI banner, modals) + [lib/llm_utils.py](../lib/llm_utils.py) (helplines) | Verbatim copy — must match what web shows |

## Import in mobile

```ts
import { CURRENT_CONSENT_VERSION, BLOCKED_STATES } from '@shared/consent-version';
import type { ChatResponse } from '@shared/types';
import { AI_DISCLOSURE_BANNER } from '@shared/disclaimers';
```

Path alias `@shared/*` is configured in `mobile/tsconfig.json`.

## Why not generate from Python?

The Python source could in theory be parsed and TS files generated at build
time. We're choosing manual mirroring because: (1) the values change rarely,
(2) attorney-approved copy must be reviewed verbatim in both places, and
(3) keeping the file readable as plain TypeScript is friendlier than a
build-step artifact.
