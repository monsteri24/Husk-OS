# Husk OS – kehitys- ja varmennusraportti, 14.10.2026 🦅

**Tulos on Experimental 0.1.1-dev -lähdekooditoimitus. ISOa ei ole rakennettu
ja Husk OS ei ole käynnistynyt virtuaalikoneessa.** Kaikilla viidellä lopullisella
kierroksella 82 testiä läpäisi, 0 epäonnistui ja 8 GUI-testiä ohitettiin.
Yhtään Husk OS:llä toimivaa fyysistä laitetta tai peliä ei ole hyväksymistestattu.

## 1. Säilytetty historia ja nykyiset muutokset

Jatkaminen perustui olemassa olevaan `mvp`-haaraan. Historiaa ja aiempia
ominaisuuksia ei korvattu uudella projektilla.

| Vaihe | Sisältö |
|---|---|
| ce617f8 | Alkuperäinen MVP-suunnitelma |
| 1dfc886 | Asetus-, gaming- ja asennuspolitiikan ydinkoodi, 29 testiä |
| f2ef000 | GTK-lähteet, Files/ilmoitukset/ikkunasillan integraatio, paketointi ja ISO/VM-skriptit |
| 0742805 | Arch-initcpio ja Calamares-moduuliasetukset, ei-estävä bridge-lukija, qcow2:n ulkoisten tiedostojen hylkäys |
| Tämä jatko | Husk-identiteetti, modulaarinen panel/launcher, CSS, paneelin paikka, live-status, VM-renderöinti, palvelujärjestys, valinnainen Calamares ja raportit |

Edellisen ZIP:n vertailukohta on 0742805: 65 testitapausta, 61 läpäissyttä ja
4 ohitettua GUI-testiä sekä 77 syntaksitarkistusta. Sen korjaukset ja kaikki
testit säilyvät. Nyt on 90 tapausta: 82 suoritetaan ja 8 GUI-testiä ohitetaan.
Lisäystä on 25 tapausta, joista neljä uusia GUI-testejä.

Uutta tässä jatkossa:

- Julkiset nimet ovat Husk OS, Husk Desktop, Husk Files ja Husk Gaming Control Center.
  `identity.py` keskittää nimet/version. `ID=huskos`, `ID_LIKE=arch`;
  sisäiset ownos-paketit, D-Bus ja asetuskansio säilyvät yhteensopivuuden vuoksi.
- Taskbar ja Start erotettiin `panel.py`- ja `launcher.py`-moduuleihin;
  `desktop_layout.py` määrittää ylä-/alapaikan ja popupien sijainnin.
- Käyttäjän CSS yhdistetään perusulkoasuun. Virheellinen CSS ohitetaan
  varoituksella. Asetuskansion muutokset voivat ladata paneelin/ulkoasun uudelleen.
- `husk-status` kysyy käynnissä olevan shellin D-Bus-statuksen.
  `husk-live-smoke` hylkää preview-tilan, puuttuvan mapatun paneelin/taustan ja
  foreign-toplevel/seat-yhteyden. VM:lle valitaan pixman vain ilman käyttäjän omaa renderer-valintaa.
- SDDM odottaa ei-root-live-käyttäjän valmistelua. Avainrenkaan alustus on
  erillinen palvelu. Live saa lokien lukuoikeuden; root lukitaan.
  Salasanatonta live-istuntoa ei lukita automaattisesti.
- Profiilissa ilmoitetaan kernel/labwc/GTK/Wayland, firmware/microcode,
  Bluetooth/ääni/verkko, UPower ja power-profiles-daemon. Validaattori tarkistaa
  paketit ja palvelulinkit. GRUBin näkyvät boot-tekstit käsitellään myös.
- Calamares on `--with-installer`-lisä sekä paketti- että ISO-vaiheessa.
  Neljä työpöytävalintaa säilyvät; asentaja ei käynnisty automaattisesti.
- Profiili-/CSS-/viiden kierroksen tarkistusscriptit ja read-only
  `collect-system-report.py` lisättiin. Rakennus-, VM-, laite- ja gaming-ohjeet päivitettiin.

Tiedostokohtainen muutosluettelo: [CHANGE-FILES.txt](CHANGE-FILES.txt).
Koko toimituksen tiedostoluettelo: [PROJECT-FILES.txt](PROJECT-FILES.txt).
CHANGELOG.md ja toimituksen Git bundle säilyttävät muutokset ja historian.

## 2. Husk Desktopin modulaarisuus

Rakenne on modulaarinen käyttöliittymän **lähdekoodin tasolla**. Labwc hoitaa
edelleen kompositorin ja ikkunanhallinnan. Oma compositor, oma Linux-ydin tai
täydellinen plugin-rajapinta ei ole toteutettu.

| Osa | Vastuu | Muokattavuus |
|---|---|---|
| ui/shell.py | Taustat, monitorit, D-Bus, ilmoitukset ja native-silta | Yhteinen GTK/Wayland-kytkentä |
| ui/panel.py | Taskbar, ikkunalista, kello/verkko/ääni | Oma vaihdettava lähdemoduuli |
| ui/launcher.py | Start, haku, katalogi ja system-appit | Uudelleensuunnittelu ilman koko OS:n korvaamista |
| desktop_layout.py | Paneelin ja popupien sijoittelu | bottom/top-malli testattu |
| themes.py ja style.css | Perusulkoasu ja käyttäjän CSS | CSS/parseri testattu; näkyvä vaikutus testaamatta |
| config.py | Validoitu käyttäjän JSON-asetustila | Tallennus ja vanhat oletukset testattu |
| config/labwc | Input, move/resize/snap ja pikanäppäimet | Compositorin runtime-testi puuttuu |

Paneelin paikka, korostusväri, taustakuva, animaatioasetus ja
`~/.config/ownos/desktop.css` eivät lähdekoodin mukaan tarvitse ISO-rakennusta.
Python-moduulin vaihtaminen tarvitsee työpöytäprosessin/paketin päivityksen.
Ikkuna-animaatiot tarvitsevat labwc/compositor-kehitystä, eivät vain GTK CSS:ää.
Kahdeksan ohitettua GUI-testiä estää näkyvän toiminnan hyväksynnän.

Suunta: Windows-henkinen MVP → tunnistettava Husk Desktop → oma Husk OS
-käyttökokemus. Arch Linux-, Linux-, GTK-, labwc-, PipeWire- ja Calamares-pohja
kerrotaan avoimesti. Kyseessä on oma shell ja järjestelmäsovellukset, ei valmis oma kernel.

## 3. Ominaisuusluettelo

VALMIS tarkoittaa tässä rajattua toteutusta ja sille mainittua testinäyttöä,
ei valmista käyttöjärjestelmäjulkaisua. TESTAAMATON voi koskea graafista tai
järjestelmään integroituvaa toimintaa, vaikka mallitoiminto on testattu.

| Ominaisuus | Tila | Todennettu / puuttuva |
|---|---|---|
| Oma identiteetti ja julkiset komennot | VALMIS lähteissä | Nimet/aliakset ja core-paketin staging testattu; boot-brändi ei |
| Atominen asetusten tallennus | VALMIS | JSON-validointi, private-tiedostot, virheelliset arvot ja oletukset testattu |
| Taskbar | OSITTAIN TOTEUTETTU / TESTAAMATON graafisesti | Keskitetyt Steam/Heroic/Files/Settings-kuvakkeet, 12 ikkunapainiketta, kello/verkko/ääni; käyttötesti puuttuu |
| Start Menu | OSITTAIN TOTEUTETTU / TESTAAMATON graafisesti | Haku, katalogi ja Gio:n näkyvät .desktop-appit, settings/lock/logout; ei muokattavia pinnejä |
| Paneelin sijainti | VALMIS mallitasolla / TESTAAMATON graafisesti | bottom/top, popup-marginaalit ja vanha config testattu |
| Käyttäjän CSS | VALMIS parseritasolla / TESTAAMATON graafisesti | UTF-8/64 KiB-raja, oikean GTK-parserin valid/invalid fallback; ikkuna puuttuu |
| Taustakuva/korostus/animaatiovalitsin | OSITTAIN TOTEUTETTU | Tallennus ja CSS; näkyvät kuvat ja siirtymät testaamatta |
| Ikkunanhallinta | OSITTAIN TOTEUTETTU / TESTAAMATON | Labwc move/resize/snap/Alt+Tab ja native activate/minimize/close; Wayland-runtime puuttuu |
| Ikkunalistamalli ja putkilukija | VALMIS rajatulla tasolla | JSON-tyypit, rajaus, burst/UTF-8/ylipitkä rivi testattu; native-IPC ei |
| Ilmoitukset | OSITTAIN TOTEUTETTU | Rajattu malli ja replacement testattu, D-Bus-palvelu/keskus lähteissä; notify-send/GUI ei |
| Husk Files | OSITTAIN TOTEUTETTU | Kansionvaihto, tiedoston avaus ja uuden kansion luonti; mallit testattu; mount/eject/trash/levytilan UI puuttuvat |
| Sovelluskatalogi/asennuskomennot | VALMIS politiikkatasolla / TESTAAMATON asennuksena | Steam/Heroic/Lutris/Discord/Firefox, rajatut argv:t; ei latausta tai pacman-transaktiota |
| Gaming Control Center | OSITTAIN TOTEUTETTU / TESTAAMATON graafisesti | Gaming/System/Input/Appearance/Updates, CPU/RAM, rajallinen GPU-mittari, ajuritiedot |
| CPU/RAM-parseri | VALMIS rajatulla tasolla | Oikea /proc Ubuntu-kontissa; ei Husk-idle-arvoja tai CPU-malli/lämpötila/core-UI:ta |
| GPU-mittari | OSITTAIN TOTEUTETTU | Saatavissa oleva gpu_busy_percent; NVIDIA/Intel-yleismittari puuttuu |
| Syöttöasetukset | VALMIS tiedostotasolla / TESTAAMATON laitteella | fi/us/gb/se/de/fr, nopeus −1…1, flat, XML-tuotto; fyysinen vaikutus ei |
| Näyttöasetukset | OSITTAIN TOTEUTETTU / TESTAAMATON | wdisplays ja monitoritaustat; ei omaa brightness/HDR/VRR-UI:ta |
| Äänenvoimakkuus | OSITTAIN TOTEUTETTU / TESTAAMATON | wpctl-oletussink, pavucontrol; ei ääni-/mikrofonitestiä |
| Verkko | OSITTAIN TOTEUTETTU / TESTAAMATON | NM+wpa_supplicant, nmcli-tila/editori; DHCP/DNS/Wi-Fi ei |
| Bluetooth/akku/virranhallinta | OSITTAIN TOTEUTETTU / TESTAAMATON | BlueZ/Blueman/UPower/power profiles kokoonpanossa; omat BT/battery/power-UI:t puuttuvat |
| GameMode/MangoHud-kääre | VALMIS argv-tasolla / TESTAAMATON pelissä | husk-game; ei yleistä automaattista pelintunnistusta tai mitattua hyötyä |
| Steam-pelilista | VALMIS parseritasolla / TESTAAMATON asiakkaassa | VDF/manifesteista, kirjastot/duplikaatit testattu; Steam-applaunch ei |
| Steam/Proton/Wine/Lutris | OSITTAIN TOTEUTETTU / TESTAAMATON | Pakettilista ja käynnistimet; ei asiakas-/prefix-/peli-/anti-cheat-testiä |
| Heroic | OSITTAIN TOTEUTETTU / TESTAAMATON | User Flatpak -asennuspolku; ei preinstalled |
| Proton GE | SUUNNITELTU | Ei integroitu tai ladattu |
| Järjestelmäpäivitykset | VALMIS politiikkatasolla / TESTAAMATON transaktiona | Allowlist, pacman -Syu ja lukkojen suojaus; oikea update ei |
| Snapshot/rollback ja julkinen repo | SUUNNITELTU | Btrfs-työkalu ei ole palautusominaisuus; jatkuvaa jakelurepoa ei ole |
| SDDM/Plymouth | OSITTAIN TOTEUTETTU / TESTAAMATON | Teemat lähteissä, SDDM-asetus; Plymouth-hookia ei aktivoitu |
| Live-istunto ilman asennusta | OSITTAIN TOTEUTETTU / TESTAAMATON | Profiili/live-user/SDDM/husk-session/autostart; ISO puuttuu |
| Status/live-smoke | VALMIS politiikka/import-tasolla / TESTAAMATON istunnossa | JSON-validointi, preview hylätään, Gio XML jäsentyy; oikea IPC/Wayland ei |
| Archiso-ketju | OSITTAIN TOTEUTETTU | Generaattori ja synteettinen overlay testattu; makepkg/pacstrap/mkarchiso ei |
| Graafinen asentaja | OSITTAIN TOTEUTETTU / TESTAAMATON | Calamares 3.3.14 valinnaisena, locale/keyboard/partition/users/desktop/graphics; käännös/osiointi ei |
| Työpöydän valinta | VALMIS fixture-tasolla / TESTAAMATON asennuksena | Husk/KDE/GNOME/Minimal, SDDM/GDM/TTY ja live-siivous testattu |
| QEMU-testaus | VALMIS argv/levypolitiikkatasolla / TESTAAMATON VM:nä | qcow2+OVMF, fyysiset/backing/external-data-polut estetty; QEMU puuttuu |
| VirtualBox | SUUNNITELTU testiajo / TESTAAMATON | Käsin tehtävät ohjeet valmiina; ei VBoxManage-automaatiota tai ajoa |
| Shutdown/reboot/suspend | TESTAAMATON | systemd/logind ja logout lähteissä; oikea ajo puuttuu |

Husk OS eroaa tavallisesta Arch-asennuksesta oman shellin, järjestelmäsovellusten,
asetustilan, gaming-/käynnistyspolitiikan, live-istunnon/asennusvalintojen ja
brändin kautta. Ydin ja suuri osa ajuri-/palvelutuesta tulevat upstreamista.
Pieni taustakuorma on tavoite, ei mitattu tai saavutetuksi todistettu ominaisuus.

## 4. Koko tietokoneen laitteistoyhteensopivuus

[HARDWARE-COMPATIBILITY.md](HARDWARE-COMPATIBILITY.md) käsittelee kaikki pyydetyt
CPU/GPU/RAM/storage/input/display/audio/network/other-kategoriat ja erottaa
Linuxin tukipolun, profiilin paketit, oman koodin ja todellisen testin.
**Husk-laitetesti on jokaisella rivillä TESTAAMATON.** Myöskään käyttäjän Lenovo,
RTX 3050, Logitech-hiiri tai G435 ei ollut saatavilla.

nvidia-open on Turing+; kaikki GTX-mallit eivät sovi siihen. NVIDIA ei ole
oletus-live-profiilin oma ajurivalinta. Hybridigrafiikan automaattinen valinta
on keskeneräinen. 60–500 Hz, multi-monitor ja skaalaus eivät ole todennettuja
pelkällä wdisplays-paketilla. Moduulien/firmwarejen todellinen latautuminen
pitää tarkistaa bootatun Huskin laite-ID:n, /sys:n ja kernel-lokien avulla.

## 5. Koko käynnistysketju

| Vaihe | Lähteissä | Oikeasti testattu |
|---|---|---|
| UEFI | Releng UEFI-bootmodes ja QEMU OVMF-polku | Ei firmware-boottia |
| Bootloader | Releng, Husk-tekstit; asennukseen GRUB | Teksti-/polkufixture; ei runtimea |
| Kernel | linux ja firmware/microcode | Ei Husk-kernelin käynnistystä |
| Initramfs | Releng archiso-hookit, asennukseen initcpio/presetit | Konfiguraatio/siivousfixture, ei mkinitcpio- tai boot-ajoa |
| Palvelut | NM/BT/power profiles/live-setup/keyring | Linkit ja riippuvuusmääritykset; ei palvelukäynnistystä |
| GPU-init | Mesa/firmware, VM:lle pixman | Renderer-malli; ei DRM/KMS/renderöintiä |
| Graafinen istunto | SDDM-live-autologin, husk-session/labwc | Skriptisyntaksi; ei PAM/SDDM/labwc-runtimea |
| Husk Desktop | Autostart, GTK/layer-shell/native-silta | Import/CSS/käännös/mallit; ei mapattua Wayland-istuntoa |
| Input | Libinput/labwc/keymap/nopeus | XML/asetusmalli, ei input-tapahtumia |
| Työpöydän käyttö | Start/taskbar/settings/files/notifications | Ei klikattavaa istuntoa; 8 GUI-testiä ohitettu |
| Sammutus | Systemd/logind ja guest-ohje | Ei |
| Reboot | Live ja asennettu levy testiohjeissa | Ei |

Live ISOa, VM-boottia ja asennusohjelman käynnistystä ei tehty. Täsmälliset esteet:
Ubuntu 24.04, ei Arch; makepkg/repo-add/mkarchiso/pacman/pacman-key/mksquashfs/
xorriso/releng sekä oikea allekirjoitettu repo ja rakennusavain puuttuvat.
QEMU/qemu-img/OVMF ja VBoxManage puuttuvat. /dev/kvm puuttuu, mutta TCG ei yksin
ratkaisisi muita esteitä. Mount/user-namespacen uid_map ja AF_UNIX-socket estyvät
EPERM-virheeseen. Capabilityt ovat nolla, NoNewPrivs=1 ja Seccomp=2.
Samaa estettä ei yritetty kiertää loputtomasti.

[BUILD.md](BUILD.md), [VM-TESTING.md](VM-TESTING.md) ja
[iso/PROFILE.md](../iso/PROFILE.md) ohjaavat oikeaan erilliseen Arch-rakennus-VM:ään.
Secure Bootin allekirjoitusketju ei ole valmis ominaisuus. Ensimmäinen testi
käyttää tavallista OVMF-UEFIä. Fyysisille levyille ei tehty kirjoituksia.

## 6. Suorituskyky, palvelut ja gaming

| Mittari | Husk OS:n todellinen tulos |
|---|---|
| Idle-RAM ja CPU | EI MITATTU |
| Taustaprosessien määrä | EI MITATTU |
| ISO-/asennuslevytila | EI MITATTU; ISOa/asennusta ei ole |
| UEFI → työpöytä -aika | EI MITATTU |
| Palveluiden todellinen käynnistysjärjestys | EI MITATTU; vain Unit/After/Requires/linkit tarkistettu |
| Wattikulutus/akkukesto/lämpötilat | EI MITATTU |
| FPS/frametime/input lag | EI MITATTU |

Lähdekoodi määrittää labwc/Husk Desktop/native-sillan, polkit-agentin ja
asennetussa istunnossa swayidle/swaylock-ketjun. NM, BlueZ, power profiles ja
käyttäjän PipeWire/WirePlumber ovat kokoonpanossa. UPower/UDisks/GVfs voivat
aktivoitua tarpeen mukaan. Tämä luettelo ei ole mitattu prosessiluku.
Releng-palveluiden todellinen aktiivisuus tarkistetaan guestissa.

iwd/networkd-päällekkäisyydet ja sshd poistetaan overlaysta, mutta säästöä
ei mitattu. Gaming-paketit kasvattavat profiilia; ensimmäinen ISO ei ole
optimoitu minimikoko. Minimal on TTY-valinta, ei pienimmän jalanjäljen todiste.
Power profiles/GameMode eivät todista pienempää kulutusta. Turva-/lämpösuojauksia
ei poisteta optimoinniksi. [BENCHMARKS.md](BENCHMARKS.md) kuvaa myöhemmät mittaukset.

Täydellinen gaming-taulukko on [GAMING.md](GAMING.md): Steam, Wine/Winetricks,
Lutris, GameMode/MangoHud ja 32-bittinen Mesa/Vulkan on listattu. Heroic on
user Flatpak -asennuspolku, ei preinstalled. Proton hallitaan Steamissa eikä
sen binäärejä ole ladattu ISOon. Proton GE puuttuu. NVIDIA-valinta on erillinen.
Ohjainten udev-säännöt tulevat steam-devices-paketista. **Yhtään näistä
asiakkaista, peleistä, grafiikkakonteksteista tai ohjaimista ei ajettu Huskissa.**

## 7. Viisi lopullista testikierrosta

| Kierros | Löydetyt | Suoritetut | Läpäisseet | Epäonnistuneet | GUI-ohitukset | Syntaksi |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 90 | 82 | 82 | 0 | 8 | 90/90 |
| 2 | 90 | 82 | 82 | 0 | 8 | 90/90 |
| 3 | 90 | 82 | 82 | 0 | 8 | 90/90 |
| 4 | 90 | 82 | 82 | 0 | 8 | 90/90 |
| 5 | 90 | 82 | 82 | 0 | 8 | 90/90 |

Jokaisessa myös native-käännös, JSON-helperin ASan/UBSan, oikeat GTK-importit
ja oikea GTK CSS-parseri läpäisivät. LeakSanitizer ei ollut käytössä.
Kolme erillistä package/ISO/QEMU-esitarkistusta palautti 1 joka kierroksella
puuttuvien ympäristöedellytysten vuoksi. Niitä ei piiloteta nollaan unittest-virheeseen.
Lopullisilla kierroksilla ei löytynyt uusia unittest-virheitä.

Kehityksessä korjattiin irrallaan olleet status/renderer, pakollinen Calamares,
puuttuva GRUB-tekstien käsittely ja puuttuvan NetworkManager-linkin havaitseminen.
Kaksi viimeistä regressiotarkistusta nähtiin ensin FAIL-tilassa ennen korjausta.
C-sillan stdin ei enää piilota seuraavaa komentoa pollilta stdio-puskurissa.
Runtime-integraatio jää silti tarkistettavaksi.

[TEST-RESULTS.md](TEST-RESULTS.md) sisältää kaikki skipit, rajaukset, ympäristöprobet,
testatun lähdesnapshotin tunnisteen ja viisi erillistä lokikansiota.
82 eri testin viisi toistoa (410 läpäissyttä suoritusta) eivät ole viisi laitteistotestiä.

## 8. Tekninen väliarvio 0–100

**Asiantuntija-arvio toteutus- ja varmennusvalmiudesta; ei mitattu
onnistumisprosentti tai laitteen yhteensopivuustodennäköisyys.** Upstreamin
tuki ei riitä korkeisiin Husk-pisteisiin.

| Osa-alue | Arvio | Perustelu |
|---|---:|---|
| Järjestelmän perusta | 55 | Paketointi/politiikat ja mallit; oikea Arch-binäärikokoonpano puuttuu |
| Husk Desktop | 55 | Oma modularisoitu UI/parserit; 8 ikkunatestiä ja Wayland-runtime ajamatta |
| CPU-yhteensopivuus | 30 | x86_64/microcode/kuormitusparseri; ei Husk-CPU-boot/virta-testiä |
| GPU-yhteensopivuus | 20 | Mesa/ICD-valinnat; KMS/Vulkan/GL-testi puuttuu, NVIDIA/hybridirajat |
| RAM/muistinhallinta | 35 | Parseri/rajatut mallit testattu; idle/swap/OOM/long-run/leaks puuttuvat |
| Hiiri/näppäimistö | 30 | Input-pino ja asetuskoodi; oikea input ja BT-paritus testaamatta |
| Tallennuslaitteet | 30 | Tiedostomallit/VM-levyrajaukset; oikea I/O/mount/osiointi puuttuu |
| Verkko/ääni | 30 | Paketit ja NM/WP-kytkentä; DHCP/DNS/ääni/mic-testi puuttuu |
| Gaming | 25 | Paketit/kääre/parserit; ei launchereita/pelejä, GE puuttuu |
| ISO-rakennus | 50 | Generaattori/overlay/validaattori; makepkg/pacstrap/mkarchiso ajamatta |
| VM-käynnistys | 10 | Argv/levyrajaukset testattu, ohjeet; ei ISOa tai ensimmäistä boottia |
| Asennus | 25 | Neljä Calamares-fixture-valintaa; käännös/osiointi/reboot puuttuvat |
| Yleinen vakaus | 30 | Viisi kooditarkistusta; pitkäajo/palautus/runtime-update puuttuvat |

Ensimmäisen ISO-tiedoston lähdevalmistelu: **noin 50/100**. Ensimmäisen bootin
valmistelu: **noin 35/100**. Nämä ovat harkittuja valmiusarvioita, eivät
lupaus aikataulusta tai onnistumisesta. Todistettuja ISOja ja Husk-boottiajoja on **0**.

## 9. Viisi suurinta jäljellä olevaa ongelmaa

1. **Binäärinen rakennusketju on todentamatta:** makepkg, allekirjoitukset,
   pacstrap, rolling-Arch-riippuvuudet ja mkarchiso voivat paljastaa uusia virheitä.
2. **Graafinen runtime ja boot ovat testaamatta:** SDDM/PAM/labwc/layer-shell,
   foreign-toplevel, oikea D-Bus ja paneelin rebuild odottavat VM:ää.
3. **Asennus on kokeellinen:** Calamares/Qt/KDE-käännös, osiointi, neljä
   työpöytää ja asennettu kernel/GRUB-reboot. LUKS/rollback eivät ole valmiita.
4. **Laitetuki on todentamatta:** NVIDIA-live/hybridi, ääni/BT/verkko/näytöt/
   virta/suspend vaativat laitetestit; kaikkien GPU-sukupolvien tukea ei ole toteutettu.
5. **Gaming ja vakaus ovat mittaamatta:** ei pelejä tai suorituskykydataa,
   GE puuttuu, muistivuodot/idle/energia ja jatkuva julkinen päivitys/palautusketju ovat avoinna.

## 10. Viisi tärkeintä seuraavaa tehtävää

1. Valmistele erillinen asennettu Arch x86_64 -rakennus-VM BUILD.md:n mukaan.
   Rakenna Husk-paketit ensin ilman Calamaresia ja tarkista riippuvuudet/allekirjoitukset.
2. Rakenna ISO mkarchisolla, tallenna SHA256/versiot ja käynnistä QEMU/OVMF:
   live → SDDM → labwc → mapattu Husk Desktop. Kerää status/smoke/keyring/lokit.
   **Tämä on seuraava tärkein kehitysvaihe.**
3. Aja kaikki 8 GTK-testiä ja Waylandin Start/taskbar/input/CSS/notifications-
   sekä hallittu reboot/shutdown-hyväksyntä.
4. Rakenna valinnainen Calamares ja testaa Husk/KDE/GNOME/Minimal kukin uudella
   virtuaalilevyllä; hyväksy initramfs/GRUB ja kirjautuminen ilman live-asetuksia.
5. Testaa Intel/AMD/NVIDIA-testikone ja kannettava, ääni/Ethernet/Wi-Fi/BT,
   input/ohjaimet/akku/suspend; sitten pelit ja toistettavat FPS/idle/boot/energia-mittaukset.

Toimitus sisältää lähteet, profiiligeneraattorin/overlayn, rakennus- ja testiscriptit,
kaikki testit, viiden kierroksen lokit, muutoslokin ja ohjeet. Valmista ISOa ei
ole mukana. Projekti jatkuu aiemmasta työstä ja säilyy Experimentalina.
