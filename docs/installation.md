# Installation guide (for beginners)

> [!WARNING]
> This integration needs Home Assistant's core `infrared` integration, which is
> **only in the HA development branch** right now. On a normal/stable HA the
> integration will not load. If you just want to control your AC today, use the
> [ESPHome alternative](alternative-esphome.md) instead.

## What you need first

| # | Requirement | How to check |
|---|---|---|
| 1 | Home Assistant **with the `infrared` integration** | Developer Tools → States → type `infrared.` — entities exist only if it's available |
| 2 | **HACS** installed | You see "HACS" in the sidebar |
| 3 | A **XIAO Smart IR Mate** flashed with the ESPHome **IR-proxy** firmware | An `infrared.*` entity appears under Settings → Devices & Services → ESPHome |

### Flashing the XIAO (step 3 in detail)

The IR Mate ships with Seeed's own "learn/send" firmware. That is **not** what
this integration uses — you must flash the **IR-proxy** firmware:

1. Plug the XIAO into your computer via USB-C.
2. Open <https://esphome.io/projects/> in **Chrome or Edge**.
3. Choose the **IR proxy** project for the XIAO IR Mate and click install.
4. Enter your Wi-Fi details when prompted.
5. Back in Home Assistant, the device is auto-discovered (Settings → Devices &
   Services). Confirm it. You now have an `infrared.*` emitter entity.

## Installing this integration

1. **HACS → ⋮ (top right) → Custom repositories.**
2. Paste this repository's URL, set **Category = Integration**, click **Add**.
3. Search **Fujitsu General IR** in HACS, open it, click **Download**.
4. **Restart Home Assistant** — Settings → System → top-right power icon →
   Restart. *(The integration will not show up until you restart.)*
5. **Settings → Devices & Services → + Add Integration**, search
   **Fujitsu General IR**.
6. In the dialog:
   - **Name** — anything, e.g. "Living room AC".
   - **Infrared emitter** — pick your XIAO's emitter entity.
   - **Infrared receiver** *(optional)* — pick it only if you want HA to follow
     the original remote.
7. Point the XIAO at the AC and try the new climate card.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| HACS: *"Repository not found"* when adding the custom repo | The repo is private, or the URL is wrong | Make sure you have access; the repo must be reachable by your HACS |
| HACS shows **no version to install** | No release yet / "show beta" off | Use a tagged release, or enable installing from the main branch |
| Integration doesn't appear after install | Home Assistant wasn't restarted | Restart HA (step 4) |
| Setup fails: **"dependency infrared not found"** | Your HA has no core `infrared` integration | Not fixable by you — needs a HA version that ships `infrared` |
| Emitter **dropdown is empty** | No `infrared.*` entity exists | Flash the XIAO with the IR-proxy firmware first (see above) |
| Climate card appears but the **AC doesn't react** | Wrong aim/range, or a model variant | Aim the blaster at the unit; verify with [receiver-verification.md](receiver-verification.md) |
| Card shows a state but the AC was changed by its own remote | IR is one-way (`assumed_state`) | Add a **receiver** entity so HA can follow the remote |

Still stuck? Open an issue with your HA version and the relevant log lines.
