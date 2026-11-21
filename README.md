# peribat

A tiny Windows tray app that shows the battery level of your wireless
peripherals. The tray icon displays the **lowest** battery among all detected
devices, colour-coded green / orange / red. Right-click for the full device
list.

Supported sources:

- **Bluetooth** devices that report battery to Windows
- **Logitech** devices over a Lightspeed / Unifying / Bolt dongle, or wired
  (HID++ 2.0), e.g. PRO X Superlight

## Features

- Lowest battery percentage right in the tray icon
- Per-device list in the right-click menu
- Small always-visible widget next to the system tray with a device icon (mouse, keyboard, headset, ...)
- Click the widget (or the tray icon) to open the settings: colors, text size, position, which devices to show, one or all devices, notifications
- Sets itself up to start with Windows on first run (toggle in the tray menu)
- Charging indicator and a configurable low-battery notification (once per device)
- "Start with Windows" toggle
- Refreshes every 60 seconds (configurable), no background services, no admin rights

## Install

```powershell
git clone https://github.com/rannoq/peribat.git
cd peribat
pip install -r requirements.txt
pythonw peribat.py
```

Requires Windows 10/11 and Python 3.9+.

## How it works

- **Bluetooth:** Windows stores the battery level of paired devices as a
  device property. peribat reads it through PowerShell
  (`Get-PnpDeviceProperty`).
- **Logitech:** peribat opens the receiver's vendor HID interface with
  `hidapi` and asks each paired device for its battery over HID++ 2.0
  (features 0x1004 / 0x1000 / 0x1001). Sleeping devices don't answer; they
  show up again once you move the mouse.

Everything runs locally, nothing is sent over the network.

## Limitations

- Windows 11 has no official API for taskbar items, so the widget is a small
  window attached to the taskbar next to the tray area (switchable in the
  settings). Only horizontal taskbars are supported.
- Keep the folder where it is: the autostart entry points to `peribat.py`.
  If you move it, toggle "Start with Windows" off and on again.
- Other dongle brands (Razer, Corsair, SteelSeries, generic 2.4 GHz
  keyboards) are not supported yet; each vendor uses its own protocol.
- Logitech G HUB or Logitech Options may compete for replies on the receiver;
  if a level is missing, wait for the next refresh.
- Voltage-only Logitech devices use an approximate voltage-to-percent curve.

## Development

```powershell
python tests/test_logitech.py   # protocol test against a fake device, no hardware
```

## Ideas / TODO

- More vendors as separate modules in `sources/`
- Packaged .exe via PyInstaller

## License

MIT
