# Tuya climate platfrom with external heater


Tuya climate based on code of @TheSDTM, adjusted heating behavior, also added heater support (climate entity controls given external heater):

```yaml
climate:
  - platform: tuya_climate_ext
    name: "bedroom"
    ip: "192.168.0.55"
    id: "87687a687687s87bc87a"
    key: "89798709890ca089"
    scan_interval: 10
    heater: switch.heater_bedroom
```

This component works with Moes BHT-002 (BHT002GA-B/H) and probably with other Tuya based climate devices.
