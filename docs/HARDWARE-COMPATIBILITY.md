# Husk OS – laitteistoyhteensopivuus, 14.10.2026 🦅

**Yhtään fyysistä laitetta tai Husk OS:ssä käynnistettyä virtuaalilaitetta ei ole
hyväksymistestattu.** Taulukko arvioi lähdekoodin kokoonpanoa, ei todistettua yhteensopivuutta.
Kohde on Arch Linuxin `linux`-ytimen **x86_64**-järjestelmä; ARM-ISOa tai 32-bittistä
PC-ISOa ei toteuteta tässä versiossa.

Linux-ajuri tarkoittaa mahdollista upstream-tukipolkua. Firmware-, PCI/USB-ID-,
kernel-versio-, laitevalmistaja- ja liitäntäkohtaiset erot voivat estää toiminnan.
Paketti on *profiilissa*, ei tässä ympäristössä Husk OS:ään asennettuna:
binääripaketteja tai ISOa ei ole vielä rakennettu. Kernel-moduulien varsinaista
CONFIG-asetusta, mukana oloa ja latautumista ei ole tarkistettu Husk-kernelistä.

## Tuen neljä tasoa

1. **Linux/upstream:** kernel, firmware, Mesa, libinput, PipeWire, NetworkManager.
2. **Husk-kokoonpano:** profiilin paketit, niiden riippuvuudet ja palvelulinkit.
3. **Huskin oma koodi:** GTK-paneeli, asetukset, mittariparseri, käynnistimet ja diagnoosit.
4. **Todellinen testi:** laitteen toiminta käynnissä olevassa Husk OS:ssä. Tämän tason tuloksia ei ole.

## Yhteensopivuustaulukko

Kaikkien rivien **Husk-laitetesti = TESTAAMATON**. Testattu malli tai parseri ei muuta tätä.

| Kategoria / laite | Linux/upstream-tukipolku | Husk-profiili / palvelu | Oma ominaisuus ja nykyinen puute |
|---|---|---|---|
| Intel CPU | x86_64, SMP, CPUFreq; soveltuville malleille intel_pstate | linux, intel-ucode | CPU-kuormitus yhteensä; CPU-mallia ei tunnisteta omassa käyttöliittymässä |
| AMD CPU | x86_64, SMP, mallista riippuva amd-pstate/acpi-cpufreq | linux, amd-ucode | Sama kuormitusmittari; ei AMD-kohtaista optimointitestiä |
| Ytimet ja säikeet | Kernelin scheduler ja topologia | Linux / util-linuxin lscpu | Raporttikerääjä voi lukea lscpu-tiedot; ei omaa ydinkohtaista näkymää |
| Automaattinen CPU-tunnistus | Kernelin CPUID ja /proc | Kernelin normaali tunnistus | Ei omaa CPU-ajuria tai tunnistusvelhoa |
| CPU-virranhallinta | CPUFreq, idle, ACPI, laitekohtaiset ajurit | power-profiles-daemon; GameMode vain kääreellä | Ei mitattua virrankulutusta, governor-/EPP-testiä tai omaa virta-UI:ta |
| CPU-lämpötilat | hwmon, esimerkiksi coretemp/k10temp mallin mukaan | Ei eksplisiittistä lm_sensors-UI:ta | Lämpötilanäyttö puuttuu; raportti ei hyväksy lämpörajoja |
| NVIDIA GTX | nouveau; NVIDIA-ajuriperhe arkkitehtuurin mukaan | Live: Mesa/nouveau-polku; asennuksessa valittava nvidia-open-dkms | GTX on liian laaja nimi. Pascal ja vanhemmat eivät sovi nvidia-open-valintaan; Turing-GTX voi sopia |
| NVIDIA RTX | NVIDIA open kernel modules Turingista alkaen; nouveau vaihtelee | NVIDIA-ajuri tarjolla erikseen, ei oletus-liveen | RTX 3050 tai muu RTX ei ole testattu; GSP/firmware/DKMS/KMS-ketju tarkistettava |
| AMD Radeon | amdgpu tai vanhemman laitteen radeon | mesa, vulkan-radeon, 32-bittiset vastineet, linux-firmware | GPU-kuormitus vain jos gpu_busy_percent löytyy; ei kaikkien Radeonien Vulkan-lupausta |
| Intel HD Graphics | i915, mallin ja iän mukaan | mesa, vulkan-intel, 32-bittiset vastineet | Vanha HD ei automaattisesti tarkoita Vulkan-tukea |
| Intel UHD Graphics | i915/xe mallin ja kernelin mukaan | Mesa/ANV, firmware | Ei tiettyä UHD-mallia testattu |
| Intel Iris Xe | i915/xe mallin mukaan | Mesa/ANV, firmware | Ei renderöinti-/näyttötestiä |
| Intel Arc | i915/xe mallin ja kernelin mukaan | Mesa/ANV, firmware | Uudempi laite voi vaatia uudemman kernelin/Mesan; ei Arc-testiä |
| Vulkan | GPU:n ICD + loader; pelikohtaiset ominaisuudet | Radeon/Intel ICD ja 32-bittiset loaderit; vulkan-tools diagnoosiin | Vulkan-instanssia ei ole käynnistetty; virtio-vga ei todista fyysisen GPU:n tukea |
| OpenGL | Mesa tai NVIDIA userspace | mesa/lib32-mesa, valittava nvidia-utils | glxinfo/Wayland-renderöinti testaamatta; OpenGL-versiota ei ole mitattu |
| Hybridigrafiikka | PRIME/offload, ajuri- ja liitäntäkohtainen KMS | Molempien GPU-perheiden komponentteja saatavissa | Automaattinen GPU-valinta, nvidia-prime-kääre ja kannettavan MUX-polku puuttuvat |
| RAM: tunnistus ja kokonaismuisti | Kernelin /proc/meminfo | Linux | MemTotal/MemAvailable-parseri ja Control Center -näyttökoodi; parseri testattu Ubuntu-kontissa |
| RAM: käytetty muisti | MemTotal − MemAvailable on arvio käytöstä | Linux | Parseri ja rajoitukset testattu; ei Husk-idle-RAM-mittausta |
| Swap ja muistinhallinta | Kernelin VM ja swap | Calamares: none/small, oletus none; ei zram-konfiguraatiota | Ei swap-UI:ta, kuormitustestiä tai OOM-käytännön hyväksyntää |
| Muistivuodot | Sovellusten elinkaaren tarkistus | JSON-C-helper ASan/UBSan-ajettu | LeakSanitizer pois ympäristörajan takia; koko desktopin/native-sillan pitkäajo puuttuu |
| SATA SSD | Tyypillisesti ahci/SATA | linux; asennustyökalut valinnaisessa Calamaresissa | Ei SATA-levyä tunnistettu tai asennettu Huskissa |
| NVMe SSD | nvme / PCIe | linux | Ei NVMe-ajuri-, APST-, levy- tai asennustestiä |
| HDD | SATA/AHCI tai muu ohjainkohtainen ajuri | linux | Ei HDD-testiä eikä omaa SMART-/levyhallinta-UI:ta |
| USB-muistit ja ulkoiset levyt | usb_storage, uas | linux, udisks2, gvfs | Ei automaattisen liittämisen/ejectin omaa käyttöliittymää tai testiä |
| Levyjen automaattinen tunnistus | Kernel/udev, lsblk, UDisks | util-linux, udisks2 | Raporttikerääjän lsblk; tiedostonhallinta ei ole levyosiointityökalu |
| Tiedostojärjestelmät | Kernelin laite-/FS-tuki | Ensimmäinen asennustavoite ext4; btrfs-progs ja dosfstools | Btrfs-snapshotit, LUKS ja hibernate eivät ole toteutettuja hyväksyttyjä ominaisuuksia |
| Vapaa/käytetty levytila | statfs/df | Raporttikerääjän df | Oma jatkuva levytilanäkymä puuttuu; asennetun järjestelmän kokoa ei mitattu |
| USB-hiiret ja USB-näppäimistöt | usbhid/hid_generic + libinput | linux, labwc/libinput riippuvuuksina | Kursori, painikkeet ja syöttö kulkevat labwc:n kautta; ei fyysistä testiä |
| Langattomat USB-vastaanottimet | Vastaanottimen HID/valmistajakohtainen ajuri | Sama USB/HID-polku | Malli-/polling rate-/lisäpainiketestejä ei ole |
| Bluetooth-hiiret ja -näppäimistöt | HID + Bluetooth, esimerkiksi btusb | bluez, bluez-utils, blueman; bluetooth.service | Paritus ja uudelleenyhdistäminen testaamatta; oma BT-UI puuttuu |
| Kursori, hiiren painikkeet, vieritysrulla | Libinputin laitekohtainen tapahtumankäsittely | labwc ja libinput | Hiirinopeus −1…1, flat-profiili; asetusten tiedostokirjoitus testattu, fyysinen vaikutus ei |
| Näppäimistöasettelut | xkbcommon ja labwc | fi/us/gb/se/de/fr valittavissa | Asetuksen validointi ja XML tuotto testattu; oikea näppäimistö/merkistö ei |
| Kannettavan kosketuslevy | PS/2, I²C HID ja libinput mallin mukaan | Kernel + libinput | Ei omaa ele-/tap-/palm rejection -asetussivua tai laitetestiä |
| Näytön tunnistus, resoluutio | DRM/KMS, EDID, wlroots | labwc, wdisplays | Taustapinnat monitorien mukaan; hotplug ja näkyvä tila testaamatta |
| Virkistystaajuus 60–500 Hz | GPU, näyttö, kaapeli ja ajurin tarjoama mode | wdisplays; ei Hz-kattoa omassa valikossa | Mitään Hz-arvoa ei ole todennettu. 500 Hz:n, VRR:n, DSC:n tai HDR:n toimivuutta ei luvata |
| Useampi näyttö | DRM/KMS + compositor | labwc, oma monitor-added/removed-koodi | Taustat kaikille, paneeli ensisijaiselle; ei moninäyttötestiä |
| Skaalaus | Compositorin output-asetukset | wdisplays | Ei testattua fractional scalingia tai omaa scaling-UI:ta |
| Näytön kirkkaus | ACPI/backlight, mallikohtainen ulkoinen DDC | Ei eksplisiittistä brightnessctl/ddcutil-integraatiota | Husk-kirkkaussäädin puuttuu |
| Kaiuttimet ja kuulokkeet | ALSA, esimerkiksi snd_hda_intel + laitekohtainen codec | pipewire, pipewire-pulse, pipewire-alsa, wireplumber | Taskbarin wpctl-oletussink-säädin; todellista ääntä ei toistettu |
| Mikrofonit ja USB-ääni | ALSA, snd_usb_audio USB-laitteilla | Sama PipeWire-pino, pavucontrol, alsa-utils | Pavucontrol ulkoisena työkaluna; ei tallennus-/reititystestiä tai omaa mic-UI:ta |
| Bluetooth-ääni | BlueZ + PipeWiren BT-plugin, headset-kohtaiset profiilit | bluez, PipeWire, WirePlumber, blueman | A2DP/HFP, mikrofonin laatu ja viive testaamatta |
| Ethernet | NIC-mallin oma kernel-ajuri | linux-firmware, NetworkManager.service | nmcli-tilan teksti paneelissa, nm-connection-editor; ei NIC-/DHCP-/DNS-testiä |
| Wi-Fi | Piirikohtainen ajuri, esimerkiksi iwlwifi/ath/rtw | linux-firmware, NetworkManager+wpa_supplicant | Reitittimen yhteys/roaming ei testattu; kaikki Realtek/Broadcom-mallit eivät automaattisesti toimi |
| Bluetooth-radio | Piirikohtainen ajuri ja firmware | bluez-palvelu ja työkalut | Radiota, laite-ID:tä tai rfkill-tilaa ei ole tutkittu Huskissa |
| Verkkokortin tunnistus / internet | Kernel/udev, NetworkManager | NM:n device status; raporttikerääjä | Ei todistettua internetyhteyttä Huskissa; kehityskontin verkkoyhteys on eri asia |
| Webkamerat | V4L2/uvcvideo monilla USB-kameroilla | Linux, firmware | Ei omaa kamera-appia, kuvan- tai mikrofonin testiä |
| Peliohjaimet | HID/xpad/valmistajakohtaiset ajurit | linux, steam-devices-udev-säännöt profiilissa | Ei painike-, rumble-, gyro- tai Bluetooth-ohjaintestiä |
| Muut USB-laitteet | USB core + laiteluokan ajuri | linux, udev | USB-tuki ei takaa jokaisen erikoislaitteen toimivuutta |
| Akut ja kannettavan virranhallinta | ACPI/power_supply, mallikohtainen firmware | upower, power-profiles-daemon | Raportointi mahdollista UPowerilla; oma akun kuvake, latausrajat ja battery-life-mittaus puuttuvat |
| Lepotila ja herääminen | Kernel/systemd/ACPI, BIOS- ja laitekohtaiset erot | systemd/logind; asennetussa Husk-istunnossa swayidle/swaylock | Suspend/resume/hibernate testaamatta. Live-istunto ei automaattisesti lukitu salasanattomana |

## Mitä on todella testattu?

Laitteistoa: **ei yhtään Husk OS:ssä**. Myöskään käyttäjän Lenovo-kannettavaa,
RTX 3050:tä, Logitech-hiirtä tai G435-kuulokkeita ei ole testattu tässä työssä.
Virtio-vga/virtio-net/NVMe-emulaation käynnistystä ei tehty.

Koodia: CPU/RAM-lukijan kelvollinen tulos kehityskontin oikeasta `/proc`-datasta,
syöttöasetusten tiedostotuotto, asetusten tallennus, profile-/asennussuunnitelmat ja
VM-levyn rajaukset on testattu. Tämä osoittaa kyseisen koodipolun toimintaa,
ei Husk-kernelin laitetukea, lämpötiloja tai muistivuotojen puuttumista.

## Näin moduulit ja firmware tarkistetaan myöhemmin

Bootatussa VM:ssä tai testikoneessa: `python3 scripts/collect-system-report.py --output husk-hardware.json`.
Tuloste erottaa kernelin, OS-identiteetin, PCI-ajurit, USB-laitteet, muistin,
levyt, palvelut ja `modinfo`-tiedot. Sisään rakennettu ajuri ei välttämättä näy
modinfo-tiedostona; tiedoston löytyminen ei taas tarkoita ladattua tai toimivaa ajuria.
Vertaa PCI/USB-ID:tä `lspci -nnk`, `/sys` ja kernelin loki, sekä käytössä olevan
kernelin CONFIG- ja `/usr/lib/modules`-tiedot. Älä vaihda tai pakota moduuleja tämän listan perusteella.

Hyväksy erikseen hiiren liike/painikkeet/rulla, näppäimistö ja touchpad, näytön
todellinen mode, äänen toisto/tallennus, internet/DNS, ohjaimen painikkeet ja
lepotilasta paluu. Tallenna laitteen malli, BIOS, kernel, firmware/ajuriversio,
ISO-SHA256 ja testitulos. Testien viisi toistoa eivät ole viisi laitteistokokoonpanoa.

## Upstream-lähteet (tarkistettu 14.10.2026)

- [Intel pstate](https://docs.kernel.org/admin-guide/pm/intel_pstate.html),
  [AMD pstate](https://docs.kernel.org/admin-guide/pm/amd-pstate.html)
- [Intel i915](https://docs.kernel.org/gpu/i915.html), [Intel xe](https://docs.kernel.org/gpu/xe/index.html),
  [Mesa ANV](https://docs.mesa3d.org/drivers/anv.html), [Mesa RADV](https://docs.mesa3d.org/drivers/radv.html)
- [NVIDIA open kernel modules: Turing tai uudempi](https://github.com/NVIDIA/open-gpu-kernel-modules)
- [libinput](https://wayland.freedesktop.org/libinput/doc/latest/),
  [Linux HID](https://docs.kernel.org/hid/hidintro.html), [xpad](https://docs.kernel.org/input/devices/xpad.html)
- [WirePlumber Bluetooth](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/bluetooth.html),
  [NetworkManager](https://networkmanager.dev/docs/api/latest/NetworkManager.conf.html)
- [Linux memory](https://docs.kernel.org/admin-guide/mm/index.html),
  [V4L2](https://docs.kernel.org/driver-api/media/v4l2-core.html),
  [sleep states](https://docs.kernel.org/admin-guide/pm/sleep-states.html)

Lähteet kuvaavat upstream-komponentteja. Husk-rivit perustuvat projektin
`build.py`-, `installer.py`-, PKGBUILD- ja systemd-tiedostoihin sekä testilokeihin.
