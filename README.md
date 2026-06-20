# Fujitsu General IR (Home Assistant)

> [!NOTE]
> **Beta — verified end-to-end against real hardware (2026-06-20).**
> This integration builds on Home Assistant's core `infrared` integration,
> which has shipped since **HA 2026.4** (verified against 2026.6). It loads
> on a normal, up-to-date HA, and has been confirmed end-to-end against a
> physical Fujitsu General AC: `set_hvac_mode` was transmitted via a Seeed
> XIAO IR-proxy and the AC acknowledged with a beep. You still need to flash
> your XIAO with the IR-proxy firmware first. Treat it as a working beta.
>
> **Prefer a device-side, battle-tested setup?** ESPHome's built-in
> [`fujitsu_general` climate component](https://esphome.io/components/climate/climate_ir/)
> on the same XIAO is a few lines of YAML and is mature. See
> [docs/alternative-esphome.md](docs/alternative-esphome.md).

Control a **Fujitsu General** air conditioner (e.g. *ASHA12LCC*) over IR using
Home Assistant's new **`infrared` proxy** architecture — the same approach as
the [`lg_infrared`](https://www.home-assistant.io/integrations/lg_infrared)
core integration, but for a stateful AC.

All protocol logic runs **on the HA server**. The IR blaster (e.g. a
[Seeed XIAO Smart IR Mate](https://www.seeedstudio.com/XIAO-Smart-IR-Mate-p-6492.html))
only acts as a *dumb* proxy that transmits/receives raw IR timings.

The codec is a 1:1 Python port of ESPHome's
[`fujitsu_general`](https://github.com/esphome/esphome/tree/dev/esphome/components/fujitsu_general)
component (encode **and** decode, verified by full-state round-trip tests).

## Architecture

```
Home Assistant (this integration)          IR proxy (ESPHome XIAO IR Mate)
┌───────────────────────────────┐          ┌──────────────────────────────┐
│ climate entity + Fujitsu codec│  ──API→  │  infrared emitter (raw TX)   │ → AC
│ (state, encode, checksum)     │  ←API──  │  infrared receiver (raw RX)  │ ← remote
└───────────────────────────────┘          └──────────────────────────────┘
```

## Requirements (read first)

You need **all** of these before installing:

1. **Home Assistant 2026.6+** (the core `infrared` integration shipped in
   2026.4; this integration is verified against the 2026.6 API).
2. **[HACS](https://hacs.xyz/) installed** in Home Assistant.
3. **An IR proxy device** that exposes `infrared` **emitter** (and optionally
   **receiver**) entities. Flash your XIAO IR Mate with the ESPHome *IR-proxy*
   ready-made firmware from <https://esphome.io/projects/> — **not** the Seeed
   "learn/send slots" factory firmware it ships with. After flashing, HA
   discovers it and an `infrared.*` entity appears.

> The setup **auto-detects** your IR proxy: the emitter (and a matching
> receiver on the same device) are pre-filled — you just confirm. If step 3
> isn't done yet, setup aborts with a short note telling you to add a proxy
> first, rather than showing an empty form.

## Installation (HACS)

1. In HACS: **⋮ → Custom repositories**, paste this repo's URL, category
   **Integration**, **Add**.
2. Search for **Fujitsu General IR**, open it, **Download**.
3. **Restart Home Assistant** (Settings → System → Restart). The integration
   does not appear until you restart.
4. **Settings → Devices & Services → Add Integration**, search
   **Fujitsu General IR**.
5. The detected IR proxy is pre-filled (emitter + matching receiver) — confirm,
   or adjust if you run several proxies. Optionally add a power sensor for
   on/off detection, then point the blaster at the AC.

📖 New to this? See the step-by-step guide with screenshots-style detail and a
troubleshooting table: **[docs/installation.md](docs/installation.md)**.

## Notes & limitations

- IR is one-way → `assumed_state`. The optional receiver only lets HA *track*
  the original remote; it is not real device feedback.
- **Optional power sensor for on/off**: if the AC is on a metered plug, point
  the integration at that power sensor and set an on-threshold (watts). HA then
  syncs **on/off** from the actual draw — the one thing IR can't read back. It
  cannot recover mode/temperature/fan; on an off→on transition the last active
  mode is assumed. A short grace period after each IR command keeps a just-sent
  command from being reverted by the transitional draw. Pick a threshold above
  standby but below the fan-only draw; a unit idling at setpoint may read as off.
- On an ESP32-C3 (XIAO) the RMT memory is tight; if TX+RX together misbehave,
  configure the proxy with TX only.
- The temperature range is 16–30 °C. Real units only accept 18 °C as the lower
  bound in *cooling*; below that the AC clamps to its own minimum (same
  limitation as the ESPHome component this codec is ported from).
- Ported/tested against the Fujitsu General state + off frames. If your model
  ignores the codes, capture the original remote via the receiver (debug log)
  and open an issue.

## Development / local testing

A VS Code **dev container** runs a real Home Assistant with this integration
mounted, so you can test the config flow, options flow and a live IR send.

1. Open the repo in VS Code → *Reopen in Container* (needs Docker + the
   *Dev Containers* extension). `scripts/setup` installs HA automatically.
2. Run `scripts/develop` in the container terminal.
3. Open <http://localhost:8123>, finish onboarding, then
   *Settings → Devices & Services → Add Integration → Fujitsu General IR*.

> To pick an emitter in the config flow you need an `infrared.*` entity to
> exist — add your ESPHome IR-proxy (XIAO IR Mate) on the same network so HA
> discovers it. Without the hardware the integration still loads, but the
> emitter selector will be empty.

Run the codec unit tests directly with `pytest`.

### Receiver verification

Confirm your AC actually uses the frames this codec expects by capturing the
original remote and decoding it — either live in Home Assistant or offline with
[`scripts/decode.py`](scripts/decode.py) and the capture firmware
[`esphome/ir-capture.yaml`](esphome/ir-capture.yaml).

👉 Full guide: [docs/receiver-verification.md](docs/receiver-verification.md)

## Status

Working beta (v0.3.1). The codec is verified and the full chain has been
confirmed end-to-end against a physical Fujitsu General AC. The climate/
config-flow wiring targets the current core `infrared` consumer API and may
need tweaks as that API stabilizes.

## License

MIT
