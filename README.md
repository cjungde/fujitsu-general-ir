# Fujitsu General IR (Home Assistant)

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

## Requirements

- Home Assistant **2026.5+** with the core `infrared` integration available.
- An IR proxy device that exposes `infrared` **emitter** (and optionally
  **receiver**) entities — flash your XIAO IR Mate with the ESPHome
  *IR-proxy* ready-made firmware from <https://esphome.io/projects/>
  (not the Seeed "learn/send slots" factory firmware).

## Installation (HACS)

1. HACS → ⋮ → *Custom repositories* → add this repo as type **Integration**.
2. Install **Fujitsu General IR**, then restart Home Assistant.
3. *Settings → Devices & Services → Add Integration → Fujitsu General IR*.
4. Pick your infrared **emitter** entity (required) and optionally a
   **receiver** entity, then point the blaster at the AC.

## Notes & limitations

- IR is one-way → `assumed_state`. The optional receiver only lets HA *track*
  the original remote; it is not real device feedback.
- On an ESP32-C3 (XIAO) the RMT memory is tight; if TX+RX together misbehave,
  configure the proxy with TX only.
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

Early scaffold (v0.1.0). The codec is verified; the climate/config-flow wiring
targets the current core `infrared` consumer API and may need tweaks as that
API stabilizes.

## License

MIT
