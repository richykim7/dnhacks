# Hosting and automatic preview

Decision, September 6, 2026: for this hackathon, keep the Python app and built Vite frontend
on one persistent Linux host, with Cloudflare providing the public hostname. Use the
provisioned AWS capacity for compute where needed. If moving the app off this workspace,
a small persistent AWS host preserves its current execution/storage model. The current
preview host's cloud provider has not been established by this audit.

The two-person team needs a working demo within the original 16-hour window. This
recommendation reuses existing capacity and does not provision another paid service.
Incremental instance count is zero; the existing host/GPU charges and credits are unchanged
and were not audited. Keeping the existing host avoids a migration; a named hostname
still depends on Cloudflare account/domain access.

## Why this deployment shape

The frontend is a static Vite build served by the Python app; production does not require
a Node server. Jobs launch detached Python subprocesses. Claims, working records, runtime
journals and artifacts currently live on local disk, including DuckDB files. A persistent
host runs that shape directly. See [frontend setup](../frontend.md),
[job launch](https://github.com/richykim7/dnhacks/blob/e04e9ff/src/dnhacksbio/webui/jobs.py),
and [runtime storage](../runtime.md).

| Option | Fit for this repo and demo |
|---|---|
| **Existing Linux/AWS app host + Cloudflare Tunnel** | Recommended now: one app origin, local persistent data and subprocesses, same live/replay APIs |
| **Vercel frontend + persistent backend** | Good if independent per-PR frontend previews become the bottleneck; introduces another deployment and API routing configuration |
| **Move the whole backend to Vercel Functions** | Requires adapting the present disk/subprocess lifecycle; little immediate demo benefit |
| **Cloudflare Pages/Workers as the whole app** | Pages can host the frontend; this audit has not established a drop-in deployment for the Python/DuckDB/subprocess runtime |
| **Another persistent app platform** | Consider when leaving the development workspace if managed deployment is more valuable than reusing current capacity; no migration is necessary for this demo |

Vercel's [Git integration](https://vercel.com/docs/git) supplies automatic deployments and
preview URLs. Its current [function announcement](https://vercel.com/changelog/vercel-functions-can-now-run-up-to-30-minutes)
allows up to 30 minutes for Python/Node on eligible plans; short historical timeout limits
are not the reason for this recommendation. The relevant mismatch is this repo's persistent
local state and detached execution lifecycle. The recommended fit is an inference from
the code and platform docs, not a claim that another platform cannot host agents.

Cloudflare Tunnel is ingress, distinct from Cloudflare's application-compute products.
The [official setup guide](https://developers.cloudflare.com/tunnel/setup/) describes a
public hostname routed to a local service. Quick Tunnels generate temporary
`trycloudflare.com` hostnames, are intended for testing, and do not support SSE. Use a named
tunnel with an owned hostname for the judging URL. Revisit a managed app platform and
separate worker/storage services when continued use beyond the hackathon warrants it.

## What is running now

- Public viewing preview: https://pale-substances-aruba-marathon.trycloudflare.com/
  (Investigations is the default; `/#forecast` remains the existing recorded experiment).
- A dedicated checkout at `/home/ubuntu/dnhacks-worktrees/forecast-demo`, branch
  `ian/graph-plan-preview-main`, follows `origin/main`. It is a deployment checkout;
  do not use it for implementation or uncommitted edits.
- Public proxy: `127.0.0.1:8767` → dedicated main backend `127.0.0.1:8815`.
  The teammate's runtime preview on 8765 is separate.
- User systemd timer `dnhacks-main-follow.timer` checks main five seconds after each
  completed check/build. Fetch/build time is additional; deployments are automatic,
  not literally instantaneous. The first deployment took about 25 seconds including
  dependency setup; Vite reported 10.3 seconds within that build.
- New main commits fast-forward the clean checkout, sync dependencies, build a separate
  release directory, replace the generated `frontend/dist` link and restart the dedicated
  backend. A build failure leaves the previous generated bundle in place. Source and
  dependency synchronization happen before the build; this is not a full runtime rollback.
- The proxy polls the built index hash every 2.5 seconds and reloads open pages when the
  frontend bundle changes. Backend-only updates restart the backend without necessarily
  changing that hash. The app's existing data polling then sees changed responses.
- A generated `GET /assets/deployment.json` reports the served commit and branch. First
  verified public deployment: `e04e9ff8bbe6a1abce23ba022518dbdde3ebb370`.

The public proxy remains **viewing/playback only**: mutation requests return 405. It also
buffers upstream responses, so neither this proxy nor its Quick Tunnel is the final
interactive/SSE demo transport. Live starts, uploads and approvals use the local app
until that transport is deliberately replaced. No application code or repository CI
workflow was changed by this operational setup.

The timer follows merged main only. It does not run experiments, add evidence, approve
findings, deploy other branches, or alter the teammate's 8765 process. Main updates can
restart this preview; use recorded playback or pause following during a rehearsed run.

## Operator commands and limits

```sh
systemctl --user status dnhacks-main-follow.timer dnhacks-main-preview.service dnhacks-public-preview.service
journalctl --user -u dnhacks-main-follow.service -n 40 --no-pager
curl -fsS https://pale-substances-aruba-marathon.trycloudflare.com/assets/deployment.json
# Freeze the currently deployed preview for a rehearsal:
systemctl --user stop dnhacks-main-follow.timer
# Resume following main:
systemctl --user start dnhacks-main-follow.timer
```

Operational files are outside the repository under
`/home/ubuntu/.local/share/dnhacks-preview/` and `/home/ubuntu/.config/systemd/user/`.
This documentation does not install them on another machine. The existing Quick Tunnel
process was preserved to keep the same link; its URL/lifetime still depends on that process
and the workspace. The enabled app/proxy/timer units do not make the temporary tunnel permanent.

CLI checks found no Wrangler login and no cloudflared account certificate. GitHub webhook
enumeration returned 404 with a requirement for `admin:repo_hook`; the current CLI token
cannot configure that hook. Polling therefore implements automatic updates without an
additional login. A stable named Cloudflare hostname remains pending authenticated account
and domain access; no domain, tunnel or subscription was purchased or created.
