# Alternative: control your Fujitsu AC today with ESPHome

The main integration in this repo is still beta and not yet verified against a
physical AC. If you want a **mature, proven climate entity** with no custom
integration and no HACS, ESPHome has a built-in Fujitsu component.

The same XIAO Smart IR Mate runs it. Here the codec runs **on the device**
(the opposite of this project, where it runs on the HA server), so all you need
is a few lines of YAML.

## ESPHome config

```yaml
esphome:
  name: xiao-ac
  friendly_name: XIAO AC

esp32:
  board: seeed_xiao_esp32c3
  framework:
    type: esp-idf

logger:
api:
  encryption:
    key: !secret api_key
ota:
  - platform: esphome
wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:
captive_portal:

# IR sender on the XIAO IR Mate (D1 = GPIO3).
remote_transmitter:
  pin: GPIO3
  carrier_duty_percent: 50%

# Native climate entity for your Fujitsu General AC.
climate:
  - platform: fujitsu_general
    name: "Living room AC"
```

Flash it via the ESPHome dashboard, fill in your `secrets`, and Home Assistant
auto-discovers a `climate.living_room_ac` entity. That's it.

Optional: add a `remote_receiver:` on `GPIO4` (inverted) to let it follow the
original remote — but on the ESP32-C3 the RMT memory is tight, so leave it off
if TX+RX together misbehave.

See the [ESPHome IR climate docs](https://esphome.io/components/climate/climate_ir/)
for details.
