"""NetworkManager Wi-Fi control and read-only hardware diagnostics.

Credentials travel only in libnm's system D-Bus calls. No subprocess receives
an SSID or password, and backend error details are never logged or displayed.
"""
from dataclasses import dataclass, replace
from pathlib import Path
import re
import uuid


@dataclass(frozen=True)
class RadioBlock:
    hard: bool = False
    soft: bool = False


@dataclass(frozen=True)
class WifiNetwork:
    path: str
    interface: str
    ssid_bytes: bytes
    ssid: str
    strength: int
    security: str
    connected: bool = False
    saved: bool = False


@dataclass(frozen=True)
class NetworkDevice:
    interface: str
    kind: str
    state: str
    connected: bool = False
    driver: str = ''
    firmware_missing: bool = False
    managed: bool = True
    addresses: tuple = ()
    nameservers: tuple = ()
    reason: str = ''


@dataclass(frozen=True)
class NetworkSnapshot:
    ready: bool = False
    wireless_enabled: bool = True
    wireless_hardware_enabled: bool = True
    devices: tuple = ()
    networks: tuple = ()
    message: str = ''
    busy: bool = False
    blocks: RadioBlock = RadioBlock()
    hardware_notes: tuple = ()


def visible_networks(networks):
    """Keep one BSSID per SSID/security/radio, preferring the active BSSID."""
    chosen = {}
    for network in networks:
        key = network.interface, network.ssid_bytes, network.security
        previous = chosen.get(key)
        if previous is None or (network.connected, network.strength) > (previous.connected, previous.strength):
            chosen[key] = network
    return tuple(sorted(chosen.values(), key=lambda ap: (not ap.connected, -ap.strength, ap.ssid.casefold())))


def _read(path):
    try:
        return path.read_text(encoding='utf-8').strip()
    except (OSError, UnicodeError):
        return ''


def read_rfkill(sys_root=Path('/sys'), radio_type='wlan'):
    hard = soft = False
    for entry in (Path(sys_root) / 'class/rfkill').glob('rfkill*'):
        if _read(entry / 'type') != radio_type:
            continue
        hard |= _read(entry / 'hard') == '1'
        soft |= _read(entry / 'soft') == '1'
    return RadioBlock(hard, soft)


def hardware_diagnostics(sys_root=Path('/sys')):
    """Report unmatched PCI network controllers without guessing their model."""
    notes = []
    for entry in (Path(sys_root) / 'bus/pci/devices').glob('*'):
        # 0280 is an "other network controller", commonly Wi-Fi but also WWAN.
        # It is a diagnostic hint, never evidence that a supported Wi-Fi exists.
        if not _read(entry / 'class').lower().startswith('0x0280') or (entry / 'driver').exists():
            continue
        vendor = _read(entry / 'vendor').removeprefix('0x')
        device = _read(entry / 'device').removeprefix('0x')
        identifier = f'{vendor}:{device}' if vendor and device else entry.name
        notes.append(f'Network controller {identifier} has no loaded driver. Check its Linux driver and firmware support.')
    return tuple(notes)


def network_diagnostics(snapshot):
    notes = []
    if not snapshot.ready:
        return (snapshot.message or 'Connecting to NetworkManager…',)
    wifi = [device for device in snapshot.devices if device.kind == 'Wi-Fi']
    if snapshot.blocks.hard or (wifi and not snapshot.wireless_hardware_enabled):
        notes.append('Wi-Fi is blocked by a hardware switch or firmware setting. Check the wireless switch or BIOS/UEFI settings.')
    elif snapshot.blocks.soft:
        notes.append('Wi-Fi is blocked by rfkill. Turn Wi-Fi on; if the block remains, check airplane mode or run rfkill unblock wifi.')
    elif not snapshot.wireless_enabled:
        notes.append('Wi-Fi is turned off. Use the Wi-Fi switch to turn it on.')
    if not wifi:
        notes.append('No Wi-Fi adapter detected by NetworkManager. Check the adapter, Linux driver and firmware. A virtual machine may expose only Ethernet; attach a USB Wi-Fi adapter to the guest to test Wi-Fi.')
    for device in snapshot.devices:
        if device.firmware_missing:
            notes.append(f'{device.interface}: required firmware is missing. Check the firmware package for this adapter.')
        if not device.managed:
            notes.append(f'{device.interface}: NetworkManager does not manage this interface. Check the system network configuration.')
        if device.connected and device.addresses and not device.nameservers:
            notes.append(f'{device.interface}: connected with an IP address but no DNS servers reported. Check the DHCP/router DNS settings and system resolver configuration.')
        if device.reason:
            notes.append(f'{device.interface}: {device.reason}')
    notes.extend(snapshot.hardware_notes)
    return tuple(notes)


def validate_password(security, password):
    if security == 'wpa-psk':
        valid = 8 <= len(password.encode('utf-8')) <= 63 or bool(re.fullmatch(r'[0-9a-fA-F]{64}', password))
        return '' if valid else 'WPA/WPA2 passwords need 8–63 bytes or exactly 64 hexadecimal characters.'
    if security == 'sae':
        return '' if password and '\0' not in password else 'Enter the WPA3 password.'
    return ''


def failure_message(reason):
    """Translate stable NM reason names; never expose arbitrary D-Bus details."""
    return {
        'no-secrets': 'Authentication needs a password. Select the network and enter its current password.',
        'supplicant-disconnect': 'Wi-Fi authentication disconnected. Check the password and signal, then retry.',
        'supplicant-failed': 'Wi-Fi authentication failed. Check the password and access point security settings.',
        'supplicant-timeout': 'Wi-Fi authentication timed out. Check the password and signal, then retry.',
        'ssid-not-found': 'The selected Wi-Fi network is no longer visible. Refresh and move closer to the access point.',
        'dhcp-failed': 'DHCP could not obtain an IP address. Check the router or DHCP server.',
        'dhcp-error': 'DHCP failed. Check the router or DHCP server.',
        'dhcp-start-failed': 'DHCP could not start. Check NetworkManager and router settings.',
        'ip-config-unavailable': 'No usable IP configuration was obtained. Check DHCP or the saved static IP settings.',
        'ip-config-expired': 'The IP configuration expired. Check the router or DHCP server.',
        'firmware-missing': 'Required firmware is missing. Check the firmware package for this adapter.',
        'config-failed': 'The network device could not be configured. Check its driver and connection settings.',
    }.get(reason, '')


def build_wifi_connection(nm, glib, network, password):
    """Construct a real libnm setting object; secrets never become arguments."""
    issue = validate_password(network.security, password)
    if issue:
        raise ValueError(issue)
    if network.security not in ('open', 'wpa-psk', 'sae', 'owe'):
        raise ValueError('This security type needs Advanced connection settings.')
    connection = nm.SimpleConnection.new()
    settings = nm.SettingConnection.new()
    settings.set_property('id', network.ssid)
    settings.set_property('uuid', str(uuid.uuid4()))
    settings.set_property('type', '802-11-wireless')
    settings.set_property('autoconnect', True)
    connection.add_setting(settings)
    wireless = nm.SettingWireless.new()
    wireless.set_property('ssid', glib.Bytes.new(network.ssid_bytes))
    wireless.set_property('mode', 'infrastructure')
    connection.add_setting(wireless)
    if network.security != 'open':
        security = nm.SettingWirelessSecurity.new()
        security.set_property('key-mgmt', network.security)
        if network.security in ('wpa-psk', 'sae'):
            security.set_property('psk', password)
            security.set_property('psk-flags', nm.SettingSecretFlags.NONE)
        if network.security in ('sae', 'owe'):
            security.set_property('pmf', nm.SettingWirelessSecurityPmf.REQUIRED)
        connection.add_setting(security)
    ipv4 = nm.SettingIP4Config.new()
    ipv4.set_property('method', 'auto')
    connection.add_setting(ipv4)
    ipv6 = nm.SettingIP6Config.new()
    ipv6.set_property('method', 'auto')
    connection.add_setting(ipv6)
    return connection


class NetworkManagerController:
    """GTK-main-context asynchronous libnm controller.

    Refresh reads libnm's local cache. Scanning, activation, deactivation,
    initialization and radio changes all use asynchronous system D-Bus calls.
    A successful activation request is not reported as a connected network;
    the device's actual state controls that label.
    """
    def __init__(self):
        self.snapshot = NetworkSnapshot()
        self.client = None
        self.nm = self.glib = self.gio = self.cancel = None
        self.changed = lambda snapshot: None
        self.closed = False
        self.initializing = False
        self.pending = False
        self.message = ''
        self.access_points = {}

    def _emit(self, snapshot):
        if not self.closed:
            self.snapshot = snapshot
            self.changed(snapshot)

    def start(self, changed):
        self.changed = changed
        if self.closed or self.initializing:
            return
        if self.client is not None:
            self.refresh()
            return
        try:
            import gi
            gi.require_version('NM', '1.0')
            from gi.repository import NM, GLib, Gio
            self.nm, self.glib, self.gio = NM, GLib, Gio
            self.cancel = Gio.Cancellable()
            self.initializing = True
            NM.Client.new_async(self.cancel, self._client_ready, None)
        except (ImportError, ValueError):
            self._emit(NetworkSnapshot(message='NetworkManager libnm bindings are unavailable. Install the networkmanager and python-gobject desktop dependencies.'))

    def _client_ready(self, source, result, unused=None):
        self.initializing = False
        try:
            client = self.nm.Client.new_finish(result)
        except Exception:
            self._emit(NetworkSnapshot(message='Cannot reach NetworkManager on the system D-Bus. Check that D-Bus and NetworkManager.service are running.'))
            return
        if self.closed:
            return
        self.client = client
        self.refresh(scan=True)

    def _security(self, ap):
        flags = ap.get_rsn_flags() | ap.get_wpa_flags()
        security = getattr(self.nm, '80211ApSecurityFlags')
        if flags & (security.KEY_MGMT_802_1X | getattr(security, 'KEY_MGMT_EAP_SUITE_B_192', 0)):
            return 'enterprise'
        # Mixed WPA2/WPA3 networks can use WPA2. Prefer SAE only for SAE-only APs.
        if flags & security.KEY_MGMT_PSK:
            return 'wpa-psk'
        if flags & getattr(security, 'KEY_MGMT_SAE', 0):
            return 'sae'
        if flags & (getattr(security, 'KEY_MGMT_OWE', 0) | getattr(security, 'KEY_MGMT_OWE_TM', 0)):
            return 'owe'
        return 'wep' if ap.get_flags() & getattr(self.nm, '80211ApFlags').PRIVACY else 'open'

    @staticmethod
    def _saved_for(device, ap):
        return next((profile for profile in device.get_available_connections() if ap.connection_valid(profile)), None)

    def refresh(self, scan=False):
        if self.closed:
            return
        if self.client is None:
            if not self.initializing:
                self.start(self.changed)
            return
        if not self.client.get_nm_running():
            self._emit(NetworkSnapshot(message='NetworkManager.service is not running. Start it to manage Wi-Fi and Ethernet.'))
            return
        devices, networks, radios = [], [], []
        self.access_points = {}
        for device in self.client.get_devices():
            dtype = device.get_device_type()
            if dtype not in (self.nm.DeviceType.WIFI, self.nm.DeviceType.ETHERNET):
                continue
            wifi = dtype == self.nm.DeviceType.WIFI
            state = device.get_state()
            addresses, nameservers = [], []
            for config in (device.get_ip4_config(), device.get_ip6_config()):
                if config is not None:
                    addresses.extend(address.get_address() for address in config.get_addresses())
                    nameservers.extend(config.get_nameservers())
            reason = device.get_state_reason()
            devices.append(NetworkDevice(
                device.get_iface(), 'Wi-Fi' if wifi else 'Ethernet',
                state.value_nick.replace('-', ' ').title(), state == self.nm.DeviceState.ACTIVATED,
                device.get_driver() or '', device.get_firmware_missing(), device.get_managed(),
                tuple(addresses), tuple(nameservers),
                failure_message(reason.value_nick) if state == self.nm.DeviceState.FAILED else ''))
            if not wifi:
                continue
            radios.append(device)
            active = device.get_active_access_point()
            active_path = active.get_path() if active is not None else None
            for ap in device.get_access_points():
                ssid = ap.get_ssid()
                if ssid is None:
                    continue  # Hidden networks need a profile in Advanced settings.
                raw = bytes(ssid.get_data())
                if not raw:
                    continue
                # Keep display control characters out of labels without altering
                # the actual SSID bytes sent back to NetworkManager.
                display = ''.join(char if char.isprintable() else '�' for char in raw.decode('utf-8', 'replace'))
                networks.append(WifiNetwork(ap.get_path(), device.get_iface(), raw, display,
                                            ap.get_strength(), self._security(ap),
                                            ap.get_path() == active_path and state == self.nm.DeviceState.ACTIVATED,
                                            self._saved_for(device, ap) is not None))
                self.access_points[ap.get_path()] = device, ap
        snapshot = NetworkSnapshot(
            True, self.client.wireless_get_enabled(), self.client.wireless_hardware_get_enabled(),
            tuple(devices), visible_networks(networks), self.message, self.pending,
            read_rfkill(), hardware_diagnostics())
        self._emit(snapshot)
        if scan and not self.pending and snapshot.wireless_enabled and snapshot.wireless_hardware_enabled and radios:
            self._scan_count = len(radios)
            self.pending = True
            self.message = 'Scanning for nearby Wi-Fi networks…'
            self._emit(replace(snapshot, busy=True, message=self.message))
            for device in radios:
                device.request_scan_async(self.cancel, self._scan_ready, None)

    def _scan_ready(self, device, result, unused=None):
        failed = False
        try:
            device.request_scan_finish(result)
        except Exception:
            failed = True
        self._scan_count -= 1
        if failed:
            self.message = 'Scan could not be requested. The radio may be busy or blocked; wait a few seconds and refresh.'
        elif 'Scanning' in self.message:
            self.message = 'Scan requested. Nearby networks update as results arrive.'
        if not self._scan_count:
            self.pending = False
            self.refresh()

    def _status(self, message):
        self.message = message
        self._emit(replace(self.snapshot, message=message, busy=self.pending))

    def connect_network(self, path, password='', remember=True):
        if self.pending or self.closed:
            return
        selected = next((network for network in self.snapshot.networks if network.path == path), None)
        pair = self.access_points.get(path)
        if selected is None or pair is None:
            self._status('The network is no longer visible. Refresh and select it again.')
            return
        device, ap = pair
        saved = self._saved_for(device, ap)
        if saved is not None and not password:
            self.pending = True
            self._status('Requesting the saved Wi-Fi connection…')
            try:
                self.client.activate_connection_async(saved, device, ap.get_path(), self.cancel,
                                                       self._activation_ready, 'saved')
            except Exception:
                self.pending = False
                self._status('The saved connection could not be requested. Check NetworkManager permissions and Advanced settings.')
            return
        issue = validate_password(selected.security, password)
        if selected.security not in ('open', 'wpa-psk', 'sae', 'owe'):
            issue = 'This security type needs Advanced connection settings.'
        if issue:
            self._status(issue)
            return
        try:
            connection = build_wifi_connection(self.nm, self.glib, selected, password)
            options = self.glib.Variant('a{sv}', {'persist': self.glib.Variant('s', 'disk' if remember else 'volatile')})
            self.pending = True
            self._status('Requesting the Wi-Fi connection…')
            self.client.add_and_activate_connection2(connection, device, ap.get_path(), options,
                                                      self.cancel, self._activation_ready, 'new')
        except Exception:
            self.pending = False
            self._status('The connection could not be requested. Check the security settings and NetworkManager permissions.')

    def _activation_ready(self, client, result, kind):
        self.pending = False
        try:
            if kind == 'new':
                client.add_and_activate_connection2_finish(result)
            else:
                client.activate_connection_finish(result)
            self.message = 'Connection requested. The interface status below shows connection progress.'
        except Exception:
            self.message = 'Wi-Fi connection failed. Check the password, signal and permission to manage network connections, then retry.'
        self.refresh()

    def disconnect_wifi(self, interface):
        if self.pending or self.client is None or self.closed:
            return
        device = self.client.get_device_by_iface(interface)
        if device is None or device.get_device_type() != self.nm.DeviceType.WIFI:
            self._status('Select a Wi-Fi interface to disconnect.')
            return
        self.pending = True
        self._status('Disconnecting Wi-Fi…')
        device.disconnect_async(self.cancel, self._disconnected, None)

    def _disconnected(self, device, result, unused=None):
        self.pending = False
        try:
            device.disconnect_finish(result)
            self.message = 'Wi-Fi disconnected.'
        except Exception:
            self.message = 'Wi-Fi could not be disconnected. Check NetworkManager permissions.'
        self.refresh()

    def set_wireless(self, enabled):
        if self.pending or self.client is None or self.closed:
            return
        self.pending = True
        self._status('Changing the Wi-Fi radio state…')
        self.client.get_dbus_connection().call(
            'org.freedesktop.NetworkManager', '/org/freedesktop/NetworkManager',
            'org.freedesktop.DBus.Properties', 'Set',
            self.glib.Variant('(ssv)', ('org.freedesktop.NetworkManager', 'WirelessEnabled', self.glib.Variant('b', bool(enabled)))),
            None, self.gio.DBusCallFlags.ALLOW_INTERACTIVE_AUTHORIZATION, 15000,
            self.cancel, self._radio_changed, None)

    def _radio_changed(self, connection, result, unused=None):
        self.pending = False
        try:
            connection.call_finish(result)
            self.message = 'Wi-Fi radio change requested.'
        except Exception:
            self.message = 'Wi-Fi radio could not be changed. Check rfkill, the hardware switch and NetworkManager permissions.'
        self.refresh(scan=True)

    def close(self):
        self.closed = True
        if self.cancel is not None:
            self.cancel.cancel()
        self.changed = lambda snapshot: None
