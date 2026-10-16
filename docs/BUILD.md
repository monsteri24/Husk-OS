# Pakettien ja ISO:n rakentaminen

## System 1: GitHub-rakennus ja pysyvä julkaisu

16.10.2026: oikea System 1 ISO on rakennettu, julkaistu ja käynnistetty
QEMU/OVMF:ssä Husk Desktopiin. Tulokset ja tunnetut puutteet:
[System 1 -raportti](../HuskOS-system-1-REPORT.md).

GitHubin `Husk OS System 1 ISO` -työnkulku rakentaa kevyen Live-version
virallisessa Arch Linux -kontissa. Se käyttää oikeaa Archisoa ja säilyttää
Husk Desktopin; Calamares ja suuret pelipaketit jätetään tästä ISOsta pois.
`--first-boot` käyttää tavallista TTY1 login/PAM -autokirjautumista ja käynnistää
Labwc/Husk-istunnon. Ctrl+Alt+F2 avaa erillisen varapäätteen.

Tallenna ja varmista lähteet GitHubissa ensin. Käynnistä sitten Actionsissa
`Husk OS System 1 ISO` → `Run workflow`, tai päivitä
`.github/system1-build-request` main-haarassa. Työnkulku julkaisee valmistuneen
`HuskOS-system-1.iso`-levykuvan ja SHA-256:n Releaseen `system-1` ennen
valinnaista käynnistystestausta. Se tarkistaa myös ladatun assetin koon ja
SHA-256:n. Julkaisuvirheen yhteydessä valmistunut ISO tallennetaan Actionsin
palautusartifaktiksi seitsemäksi päiväksi. Olemassa olevaa release-ISOa ei
poisteta automaattisesti. Työnkulun onnistuminen ei ole graafinen käynnistystesti.

Rakennusavain on vain tämän ajon paikallinen pakettiallekirjoitusavain;
salainen avain sijaitsee lähdepuun ja ISO-rootfs:n ulkopuolella.

Paikallisessa Arch-rakennus-VM:ssä käytä alla kuvattuja allekirjoitettuja
pakettivaiheita ja lopuksi `sudo bash scripts/build-iso.sh --first-boot`.
Pelkkä `mkarchiso ... iso` ei riitä: `iso/` on overlay ja profiilin generaattorin
syöte, ei valmis releng-profiili.

## Rakennusympäristö

Käytä erillistä, asennettua **Arch Linux x86_64 -virtuaalikonetta**. Esimerkiksi
4 vCPU, 8 GiB RAM ja 100 GiB virtuaalilevy riittävät kehityksen lähtökohdaksi;
jätä vähintään 40 GiB vapaata rakentamiseen. Verkkoyhteys tarvitaan
riippuvuuksien ja lähteiden lataamiseen. Älä suorita rakentamisen `sudo`
komentoja nykyisellä Windows-/Linux-pääkoneellasi.

ZIP:n purkamisen jälkeen avaa terminaali ZIP:n `HuskOS`-kansiossa.
Rakennusskriptit eivät asenna riippuvuuksia automaattisesti. Asenna seuraavat
paketit **rakennus-VM:n sisällä** ja säilytä Archin täydet päivitykset:

```bash
sudo pacman -Syu --needed base-devel archiso git gnupg python python-yaml \
  wayland pkgconf squashfs-tools libisoburn qemu-desktop edk2-ovmf python-gobject gtk3 gtk-layer-shell labwc xorg-server-xvfb
chmod +x scripts/*.sh scripts/*.py bin/own-session iso/live-setup iso/live-keyring
```

Jos pacman ilmoittaa paketin nimen muuttuneen, tarkista sen virallinen
Arch-pakettisivu. Husk-pakettien native-Arch-käännös ja allekirjoitustarkistus
on suoritettu System 1 -rakennuksessa. Calamaresin CMake/Qt/Frameworks-
yhteensopivuus on edelleen testaamatta. Calamares on lukittu versioon 3.3.14 ja
ladatun upstream-release-arkiston SHA256:een. AUR-reseptejä ei suoriteta.
Valinnaisen Calamaresin upstream-asetusten asennus on tarkoituksella pois: `ownos-live`
toimittaa jokaisen käytetyn moduulin asetustiedoston, jolloin paketit eivät
omista samoja `/etc/calamares`-tiedostoja. Asennetun Arch-ytimen initramfs
luodaan `initcpio`-moduulilla (`mkinitcpio -P`).

## 1. Testaa lähteet

```bash
make check native
./scripts/test-gtk.sh
./scripts/build-packages.sh --check
```

GTK-testit käyttävät erillistä D-Bus-istuntoa ja Xvfb:tä; shell testataan
preview-tilassa. Tämä ei vielä testaa labwc:n layer-shell-pintoja tai
ikkunalistan protokollaa. Niille käytetään VM:n graafista istuntoa.

## 2. Luo rakennusavain

Luo oma kehitysavain rakennus-VM:ssä. Pidä sen salainen osa ja mahdollinen
salasana vain siellä; niitä ei pakata ISOon tai lähdekoodiin.

```bash
gpg --quick-generate-key "Husk OS VM Builder" ed25519 sign 1y
gpg --list-secret-keys --keyid-format long
```

Kopioi tulosteesta tämän avaimen 40 heksamerkin sormenjälki:

```bash
export OWNOS_SIGNING_KEY='KOPIOI_TAHAN_OMA_40_HEKSAMERKIN_SORMENJALKI'
```

Komennon merkkijono on korvattava oikealla sormenjäljellä. Omaa kehitysavainta
ei pidä esitellä julkisesti hyväksyttynä jakeluavaimena.

## 3. Rakenna allekirjoitetut paketit

```bash
./scripts/build-packages.sh
```

Tämä ajetaan tavallisena käyttäjänä. `makepkg` kääntää kuusi
Husk OS:n pakettia, suorittaa projektin testit, allekirjoittaa paketit ja rakentaa
allekirjoitetun `.build/repo/ownos.db.tar.gz`-tietokannan. `gpgv` tarkistaa
tietokannan ja jokaisen paketin allekirjoituksen. Skripti ei asenna syntyneitä
paketteja rakennuskoneeseen.

Pakettirajat: `ownos-core`, `ownos-ui`, `ownos-desktop`, `ownos-branding`,
`ownos-keyring`, `ownos-live`. Omat Python-moduulit asennetaan
`/usr/lib/ownos/ownos/`-polkuun, käynnistimet `/usr/bin/`-polkuun.

## Valinnainen graafinen asentaja

Ensimmäinen live-ISO ei tarvitse Calamaresia. Oletusrakennus ohittaa sen
kääntämisen ja profiiliin lisäämisen. Kaikki asentajan lähteet säilyvät.
Jos haluat testata asentajaa, asenna rakennus-VM:ssä myös:

```bash
sudo pacman -Syu --needed cmake ninja extra-cmake-modules qt6-base qt6-declarative \
  qt6-svg qt6-wayland qt6-tools kpmcore yaml-cpp icu libpwquality polkit \
  kconfig kcoreaddons ki18n kservice kiconthemes solid kjobwidgets
./scripts/build-packages.sh --with-installer
```

Käytä tätä pakettikomentoa tavallisen pakettikomennon sijasta uudessa
rakentamishakemistossa. Se kääntää myös Calamaresin. ISO-vaiheessa käytä
`sudo ./scripts/build-iso.sh --with-installer`. Molemmat valinnat tarvitaan.
Calamaresin Qt/KDE-käännöstä ja osiointia ei ole tässä ympäristössä testattu.

## 4. Rakenna ISO

```bash
./scripts/build-iso.sh --check
sudo ./scripts/build-iso.sh
```

Esitarkistus ei muuta järjestelmää. Varsinainen rakentaminen lisää oman
julkisen avaimen **rakennus-VM:n** pacman-avainrenkaaseen ja luottaa siihen
nimenomaisesti. Profiili kopioidaan asennetun Archison `releng`-profiilista:
upstreamin käynnistystiedostot, bootmodes ja bootstrap-tiedostot säilyvät.
Omat paketit, multilib, live-istunto ja paikallinen allekirjoitettu repositorio
lisätään kopioon. Generoitua profiilia tarkistetaan `check-profile.py`-skriptillä. `mkarchiso` tuottaa `out/huskos-*.iso`-tiedoston ja
`out/SHA256SUMS`-tarkistussummat.

Oman repon paketit ja tietokanta vaativat allekirjoituksen. Archin virallisille
paketeille säilyy normaali `Required DatabaseOptional`-politiikka:
pakettiallekirjoitus on pakollinen, virallisen tietokannan allekirjoitus
ei ole kaikissa upstream-repoissa saatavissa.

Rakentaminen pysähtyy, jos vanha `.build/profile`, `.build/archiso-work` tai
pakettirepo on paikallaan. Siirrä aiempi rakentamiskansio talteen ennen uutta
rakennusta. Skriptit eivät poista sitä automaattisesti eivätkä kirjoita
fyysisille lohkolaitteille.

## Hyväksyntä

ISO-tiedoston syntyminen on erillinen tulos; sen käynnistyvyys, asennus ja
asennetun järjestelmän uudelleenkäynnistys todetaan vasta
[VM-TESTING.md](VM-TESTING.md)-tarkistuslistalla. Turvallisen käynnistyksen
(Secure Boot) allekirjoitusketju ei kuulu tähän MVP:hen. Testaa ensin VM:n
tavallisella OVMF-varastolla; fyysisen koneen UEFI-asetuksia ei muuteta tässä.

## Viisi lähdekoodin tarkistuskierrosta

Valmistellussa Arch-VM:ssä:

```bash
python3 scripts/verify-five.py
./scripts/test-gtk.sh
```

Viiden kierroksen skripti säilyttää erilliset unittest-, syntaksi-, C-, GTK CSS-,
GTK import-, paketti-/ISO-/QEMU-esitarkistuslokit `.build/verification-2026-10-14/`-kansiossa.
Se ei luo ISOa tai käynnistä VM:ää. Ikkunatestit ajetaan erikseen sallittua
näyttöä tarvitsevan `test-gtk.sh`-skriptin avulla; viiden kierroksen GUI-ohitukset
on korvattava oikeilla testeillä ennen graafista hyväksyntää.

Toimituksen Ubuntu-kontin todelliset tulokset ovat `TEST-RESULTS.md`:ssä.
Täällä käytettiin yksityisesti purettuja GTK-/Wayland-riippuvuuksia, ei asennettu
Husk OS:ää. Archissa käytetään VM:n normaalisti asennettuja kirjastoja.

Lähdepuu sisältää ylläpidetyn profiiligeneraattorin ja overlayn; valmis ISO
ja SHA-256 ovat GitHub Releasessa. Kevyen System 1 -profiilin riippuvuusratkaisu,
allekirjoitusketjun pacstrap-käyttö ja mkarchiso-ajo on nyt testattu.
Täyttä gaming-/Calamares-ISOa ei rakennettu. Pacmanin GPGDir ei siirry
`--root`-polun mukana; rakennus-VM:n avaimen paikallinen luottamus on tarkoituksellinen.
