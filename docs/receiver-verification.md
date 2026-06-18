# Receiver verification

Confirm that your air conditioner actually uses the IR frames this codec
expects, by **capturing your original remote** and decoding it. If your remote
decodes cleanly, the integration will control your unit correctly.

This works because the codec is symmetric: the same logic that *encodes*
commands also *decodes* captured signals (`decode()` in
[`codec.py`](../custom_components/fujitsu_general_ir/codec.py)).

There are two ways to do it.

---

## Way 1 — in Home Assistant (recommended)

Uses the running integration; no extra firmware needed.

**Prerequisite:** the XIAO needs an IR **receiver** (GPIO4 / D2). The ESPHome
IR-proxy firmware exposes it as an `infrared.*` receiver entity.

1. Add the integration and select the **receiver entity** (during setup, or
   later via the integration's *Configure* / options dialog).
2. Enable debug logging (already on in the dev container). On a normal
   instance, add to `configuration.yaml`:

   ```yaml
   logger:
     logs:
       custom_components.fujitsu_general_ir: debug
   ```

3. Point the **original remote** at the XIAO and press a button.
4. Check the Home Assistant log:

   | Log line | Meaning |
   |---|---|
   | `Decoded IR from remote: FujitsuState(power=True, temperature=…, mode=…, …)` | ✅ Your unit uses these exact frames. Verified. |
   | `Received IR signal did not decode … raw timings: [...]` | ❌ No match — the raw timings are logged for analysis (see Way 2). |

---

## Way 2 — standalone / offline

Use this if you don't want to involve Home Assistant, or to analyse the raw
timings of a non-matching remote.

### Step 1 — capture the raw timings

Flash the capture-only firmware
[`esphome/ir-capture.yaml`](../esphome/ir-capture.yaml) onto the XIAO (it sets
up `remote_receiver:` with `dump: raw` on GPIO4). Open the ESPHome logs, point
the remote at the XIAO and press a button. Each press prints:

```
[remote.raw] Received Raw: 3300, -1600, 420, -1200, 420, -420, ...
```

> This is capture-only firmware — re-flash the IR-proxy firmware afterwards.

### Step 2 — decode it

Run the captured numbers through
[`scripts/decode.py`](../scripts/decode.py). It runs on plain Python 3 (no
Home Assistant needed — it stubs the codec dependency if absent):

```bash
scripts/decode.py "3300, -1600, 420, -1200, ..."   # directly
scripts/decode.py capture.txt                        # from a file
echo "3300, -1600, ..." | scripts/decode.py          # from stdin
```

Marks may be positive and spaces negative (ESPHome `dump: raw` style) or all
positive — both are accepted.

Example output:

```
Parsed 260 timing values.

✅ Decoded: FujitsuState(power=True, temperature=21, mode=<Mode.COOL: 1>, fan=<Fan.HIGH: 1>, swing=<Swing.VERTICAL: 1>)
Round-trip re-encode: matches length
```

---

## Interpreting the result

- **Decodes cleanly and the values match what you pressed** → the model is
  verified; you can trust the integration to control it.
- **Doesn't decode, or shows wrong values** → your unit uses a protocol
  variant the codec doesn't cover yet. Save the raw timings from the log and
  [open an issue](https://github.com/cjungde/fujitsu-general-ir/issues) with
  them — the difference can be derived from the capture and the codec adjusted.
