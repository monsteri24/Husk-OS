# Husk Desktop network and Bluetooth controls

The Network button opens `ownos.ui.network.NetworkWindow`, a nearby Wi-Fi
selector backed by libnm and NetworkManager. Ethernet interfaces remain visible
in the diagnostics and cannot be disconnected by the Wi-Fi disconnect action.
The Bluetooth button opens `ownos.ui.bluetooth.BluetoothWindow`, which reads
BlueZ adapter state and opens Blueman for device discovery, pairing, connection
and disconnection.

## Wi-Fi behavior

- Refresh requests a scan on Wi-Fi devices. Access points appear as the scan
  results arrive; requesting a scan does not mean the scan has completed.
- Select an SSID and enter its password. Open, WPA/WPA2 Personal, WPA3 Personal
  and Enhanced Open networks are supported directly. Hidden, enterprise and
  WEP profiles use the existing Advanced settings editor.
- A saved compatible profile is reused when its password entry is blank.
  Entering a password creates a new profile instead of silently modifying an
  existing profile. A new profile is saved by NetworkManager when Remember is
  checked; otherwise it is volatile and removed on disconnection.
- Passwords are masked, use GTK3's password input purpose with completion and
  spellchecking disabled, and are cleared from the entry after a connection
  request, selection change or window destruction. SSID bytes and credentials
  are passed as libnm setting values over the system D-Bus, never in command
  arguments. Arbitrary transport exception text is not displayed or logged.
- Initialization, scans, connection requests, disconnection and radio changes
  use asynchronous calls. Connected labels come from actual device state,
  rather than from acceptance of a connection request.

Interfaces and diagnostics show the reported driver, addresses and DNS servers.
The window distinguishes unavailable service/bindings, no NetworkManager Wi-Fi
adapter, radio disabled, hardware/software rfkill blocks, missing firmware,
unmanaged interfaces, and common authentication/DHCP failures. Unbound PCI
network controller IDs are diagnostic hints, not a supported-hardware claim.
No DNS servers reported on an active interface is configuration guidance; this
window does not perform an Internet connectivity or DNS resolution test.

## Bluetooth behavior

Adapter names and power state are read from BlueZ's system D-Bus ObjectManager.
The switch requests adapter power changes and then reads the actual state.
The window distinguishes no adapter, hardware/software rfkill blocks, powered
off adapters and an unavailable Bluetooth service. Bluetooth devices opens
`/usr/bin/blueman-manager` for the full device workflow. A displayed powered-on
adapter does not establish that pairing, audio or a particular peripheral works.

## Runtime integration

The desktop requires `python-gobject`, GTK3, NetworkManager/libnm with its NM
introspection typelib, `wpa_supplicant`, `network-manager-applet` for the Advanced
editor, BlueZ and Blueman, system D-Bus and the existing polkit session agent.
Enable `NetworkManager.service` and `bluetooth.service` for both live and
installed systems. Firmware and kernel driver availability remain specific to
the physical adapter. Installing packages alone does not establish support.

Use one coherent DNS owner in live and installed configuration. For direct
NetworkManager resolver management, use `dns=default`, `rc-manager=symlink`,
`systemd-resolved=false` and `/etc/resolv.conf` pointing to
`/run/NetworkManager/resolv.conf`. An inherited systemd-resolved stub symlink
requires the alternative complete resolved setup. Do not mix a disabled
resolver service with its stub symlink or replace DHCP-provided DNS with a
hardcoded public server. See the upstream
[NetworkManager configuration reference](https://www.networkmanager.dev/docs/api/latest/NetworkManager.conf.html).

## Verification and hardware acceptance

The test suite covers the models, sysfs/rfkill diagnostics, actual libnm setting
verification, asynchronous transport requests, credential/error boundaries and
BlueZ D-Bus variant parsing without changing host networking. GTK tests are
enabled by `OWNOS_UI_TESTS=1` in a prepared display environment. These fixtures
cannot prove a physical adapter scans, associates, pairs or reconnects.

On an actual supported adapter, record the adapter ID, driver, firmware, kernel
and NetworkManager/BlueZ versions, then verify:

1. A nearby access point appears after Refresh; selection opens masked password
   input. A correct password reaches actual Connected state and DHCP/DNS work.
2. An incorrect password produces usable feedback without showing the secret.
   Disconnect and reconnect work; Ethernet stays connected throughout.
3. Remembered Wi-Fi reconnects after reboot; a volatile profile disappears on
   disconnect. Hardware and software airplane-mode blocks are explained.
4. Bluetooth power reflects the actual adapter state. Blueman discovers and
   pairs a real peripheral, connects it, disconnects it and reconnects it.
5. No-adapter machines and virtual machines show the appropriate diagnostics.

Physical radio acceptance is still required. A VM with an emulated Ethernet
adapter only cannot establish Wi-Fi or Bluetooth hardware support.
