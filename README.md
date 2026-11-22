# peribat

Battery levels of your wireless mouse, keyboard, headset and controller, right
next to the Windows system tray. Click the widget to change colours, size,
position and which devices are shown.

- Icon per device type (mouse, keyboard, headset, controller), colour by battery level
- Lowest battery only, or every device
- Low battery notification, charging indicator
- Attaches to the taskbar, so it stays visible with the Start menu open and
  follows an auto-hiding taskbar
- Starts with Windows (set up on first run, switchable), no background services,
  no admin rights, nothing leaves your computer

## Supported devices

| Source | Devices | How |
| --- | --- | --- |
| Logitech | Mice, keyboards and headsets on a Lightspeed, Unifying or Bolt receiver, or wired | HID++ 2.0 |
| Razer | Wireless mice and keyboards, with dongle or cable | Razer feature reports |
| SteelSeries | Arctis 7, Arctis Pro, Arctis Nova 7 / 7X | vendor HID report |
| Corsair | Void family headsets | vendor HID report |
| Xbox | Xbox compatible controllers (four steps: 10 / 33 / 66 / 100 %) | XInput |
| Bluetooth | Any paired device that reports its battery to Windows | Windows device property |

Logitech and Bluetooth have been tried on real hardware. The Razer, SteelSeries
and Corsair support follows the public protocol documentation (OpenRazer and
HeadsetControl) and is covered by unit tests, but has not been verified against
every device. If a device is missing, run `python -m peribat --diag` and open an
issue with the output.

Not supported: devices that keep their battery level to themselves, such as
most generic 2.4 GHz keyboards and AirPods on Windows.

## Install

```powershell
git clone https://github.com/rannoq/peribat.git
cd peribat
py -3.13 -m pip install -r requirements.txt
py -3.13 peribat.pyw
```

Windows 10 or 11 and Python 3.9 or newer. Keep the folder where it is; the
autostart entry points to it (it is repaired automatically if you move it and
start peribat once from the new place).

## Usage

Everything is in the settings window: click the widget, or double-click the tray
icon. The settings are saved to `%APPDATA%\peribat\settings.json`, the log to
`%LOCALAPPDATA%\peribat\peribat.log`.

```powershell
py -3.13 -m peribat --diag     # what Windows shows and what each source reads
py -3.13 -m peribat --debug    # verbose log
```

## How it works

```
sources/*  --scan-->  Scanner  -->  Tracker  -->  App  -->  tray icon
 (parallel,           (merges)      (keeps last      |-->  widget (taskbar child window)
  cached if slow)                    good value)     '-->  settings window
```

* Each source reads its devices and returns `Reading`s.
* Wireless devices sleep and then do not answer. The `Tracker` keeps the last
  reading for 30 minutes and only accepts a sudden rise in level once a second
  scan confirms it, so the display does not flicker or jump.
* The widget is drawn as one anti-aliased image and shown in a window that is a
  child of the taskbar, so it moves and hides with it.

## Development

```powershell
py -m unittest discover -s tests -t .
```

The tests need only Pillow and run on any system. Adding a source means adding a
module to `peribat/sources/` with `KEY`, `LABEL` and `scan()`, and listing it in
`sources/__init__.py`.

## Protocol references

[HID++ 2.0](https://github.com/pwr-Solaar/Solaar/blob/master/docs/hidpp-protocol.md),
[OpenRazer](https://github.com/openrazer/openrazer),
[HeadsetControl](https://github.com/Sapd/HeadsetControl).

## License

MIT
