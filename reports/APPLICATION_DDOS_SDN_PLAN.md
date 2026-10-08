# Plan: DDoS the deployed application, defend it with SDN

Lab-only plan for this repository. The victim is the local IITKgp demo. Traffic never leaves the machine.

---

## 1. What is true today

Two local services already exist:

| Role | Process | Address | What it does |
| --- | --- | --- | --- |
| Deployed application | `scripts/serve_iitkgp.py` | `127.0.0.1:8765` | Single-threaded IITKgp site. A hold on this port stops new requests. The page itself reports the backend as hung. |
| SDN security | `experiments/mininet/run_live_defense.py` | `0.0.0.0:8091` | Scores each source, then drops that source in the app gateway, nftables, and Windows Firewall. Forwards only allowed traffic to `:8765`. |

The War Room already has two attack modes in `dashboard/server.py`:

- **Direct** aims at `:8765`. The application is the victim and SDN is not in the path, so the site stops serving.
- **SDN** aims at `:8091`. The gateway is the victim. Recovery today is an operator action (`/api/sdn/apply`) that blocks `127.0.0.1` after the hang.

That is why the current story feels like “we attack SDN and then turn security on.” The last recorded run matches this: `protected_app` is `127.0.0.1:8765`, the class is Slowloris, and the block reason is “Operator applied SDN after live hang.”

Three gaps keep the desired demo from working:

1. **The application is still reachable by itself.** Anything that connects to `:8765` never passes the detector.
2. **Attacker and user are the same address.** Both are `127.0.0.1`, and the gateway is started with `--allow-localhost-block`. A block of the attacker is a block of the browser.
3. **Mitigation is manual.** The closed loop in `SDNController` can block on its own, but the demo waits for Apply SDN.

---

## 2. Target behaviour

One public door. The application is the thing under attack. SDN is the thing that keeps it up.

```
legitimate browser  --+
                      +-->  SDN gateway :8091  -->  IITKgp app 127.0.0.1:8765
lab attack source   --+         |
                                 +--> drop this source only
```

Success, measured on one run:

| Check | Pass |
| --- | --- |
| Application bind | `:8765` accepts connections only from the gateway on loopback. A second address cannot open it. |
| Attack target | The lab client’s requests are HTTP requests for the IITKgp app, sent to the gateway. The switch and the gateway process are not the victim. |
| During the attack | A second, allowlisted client still gets `/__ping` and a page. `app_health.status` stays `UP`. `failed_upstream` stays 0. |
| Enforcement | `discarded` rises only for the attack source. `served` keeps rising for the allowlisted client. |
| Control | The same traffic pointed at `:8765` with the gateway absent still hangs the app. That run is the “no SDN” baseline, not the defended run. |

---

## 3. Work, in order

### Step 1 — Hide the application behind SDN

Change `serve_iitkgp.py` so it listens on `127.0.0.1` only (it already defaults to port 8765). Do not publish 8765 on `0.0.0.0`.

The gateway in `dashboard/server.py` (`_ensure_gateway`) already starts with `--upstream 127.0.0.1:8765`. Keep that. Users and the lab attack client use port **8091** only.

Add a one-line health probe the dashboard already understands: `GET /__ping` on the gateway must reach the app and return quickly. `LiveGateway.health_loop` already records `app_health`.

### Step 2 — Give the attacker and the user different addresses

Blocking must not take the operator offline.

On this Windows host, add a second loopback address (for example `127.0.0.2`) and send only the lab attack from that address. Leave the browser on `127.0.0.1`.

Start the gateway **without** `--allow-localhost-block` for the browser address, and pass `--allow 127.0.0.1` so the operator is never installed as a drop rule. The attack address is not on the allowlist.

If a second loopback is awkward, use two Mininet hosts from `experiments/mininet/sdn_topology.py` (`h1` and `h_attacker`) with `h_server` replaced by a path that forwards to the real IITKgp process. Same rule: one source is allowlisted, one is not.

### Step 3 — Aim the lab traffic at the application through the gateway

Keep using the existing War Room control. Change the defended mode so that:

- The URL is the gateway (`http://127.0.0.1:8091/`), which proxies into the IITKgp app.
- The source address is the attack address from Step 2.
- The dashboard labels this run **Application via SDN**, not “attack the SDN.”

Leave the current direct mode as a separate **No SDN** control that is allowed only while `:8765` is still bound for that experiment. Do not run both at once.

Do not add a new flood tool. The detector already has the two gates in `projects/sdn/policy.py`: a high event rate, and a slow hold (many incomplete requests from one source). The lab client only needs to trip one of those gates. Tuning belongs in the contract (`models/sdn_model_contract.json`: `pps_threshold`, `block_threshold`), not in a new attack script.

### Step 4 — Let the closed loop block without the operator button

`LiveGateway.score_loop` already calls `SDNController.process`, and `process` already calls `backend.block_ip` when policy returns `BLOCK`.

For this demo, confirm that path is the one that fires:

1. Attack source crosses the rate gate or the slow-hold gate.
2. `last_prediction.action` becomes `block` with a reason from `MitigationPolicy`, not “Operator applied SDN.”
3. `AppGatewayBackend` closes the next connection from that source before `_proxy` runs, so the single-threaded app never sees it.
4. nftables and Windows Firewall receive the same source (already wired in `build_backend`). Those are backup drops on the host. The application-level drop is what protects `:8765`.

Keep **Apply SDN** as a manual override. It should not be required for the pass criteria in Section 2.

### Step 5 — Show the result on the War Room

One panel, four numbers already written to `results/sdn/live_sdn_status.json`:

- `protected_app` = `127.0.0.1:8765`
- `app_health.status` and `latency_ms`
- `served` (allowlisted client)
- `discarded` (attack source)

Add the attack source and the allowlisted source to that status object so the panel can say which address was dropped. The IITKgp page heartbeat (`/__ping`) stays the user-visible proof: the overlay “backend hung” appears only in the no-SDN control, and stays hidden in the defended run.

---

## 4. Run order for a single demonstration

1. Start the app on `127.0.0.1:8765` and the gateway on `:8091`.
2. From `127.0.0.1`, open the IITKgp page through `:8091`. Confirm `served` increases and `app_health` is `UP`.
3. From the attack address only, send the existing lab profile at `:8091`.
4. Within one scoring window, confirm the attack address is in `blocked_ips`, `discarded` increases, and the browser on `127.0.0.1` still loads `/__ping`.
5. Stop the lab client. Optionally revoke the block from the existing command file and show the attack address can browse again.
6. Optional control, separate from step 3: stop the gateway, point the same lab client at `:8765`, and show the heartbeat overlay. Restart the gateway before any other demo.

---

## 5. What this plan does not change

- The Keras model and `SDNModelContract` stay the detector. No retrain is required for the path above, because policy can already block on rate and on slow holds even when CIC features are incomplete (`pad_incomplete=True`).
- Mininet (`sdn_topology.py`) stays the virtual-network demo. This plan is the path where a real process (`serve_iitkgp.py`) is the victim.
- Hyperledger audit can record the block later. It is not on the critical path for keeping the app up.

## 6. Done when

A viewer can watch the IITKgp site stay up while the War Room shows one address discarded and `protected_app` still healthy, and can switch to the no-SDN control and watch that same site report the backend hung.
