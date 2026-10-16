# Husk OS / OwnOS-MVP

**Husk OS** on omaa käyttökokemusta ja järjestelmäsovelluksia kehittävä
gaming-käyttöjärjestelmä, jonka tekninen perusta on **Arch Linux**.
Tämä julkaisu on **Husk OS System 1 — Experimental Live**.
Sisäiset `ownos`-paketti-, asetus- ja D-Bus-tunnisteet säilyvät yhteensopivuuden
vuoksi. Pysyvä lähdekoodi ja jatkokehitys ovat tämän repositorion `main`-haarassa.

**[Lataa HuskOS-system-1.iso](https://github.com/monsteri24/Husk-OS/releases/download/system-1/HuskOS-system-1.iso)**
— 2 103 050 240 tavua.
[SHA-256](https://github.com/monsteri24/Husk-OS/releases/download/system-1/HuskOS-system-1-SHA256.txt)
ja [todellinen rakennus-/käynnistysraportti](HuskOS-system-1-REPORT.md).

ISO on rakennettu Archisolla, tallennettu GitHub Releaseen ja ladattu takaisin
tarkistussummaa vasten. **QEMU/OVMF-käynnistys oikeaan Labwc/Wayland-istuntoon,
Husk Desktopiin, Start-valikkoon ja taskbariin sekä terminaalin avaaminen ja
hallittu sammutus on testattu.** Tämä on kevyt Live-versio ilman Calamaresia;
asennusta, pelejä tai fyysistä laitteistoa ei ole testattu.

Oma GTK3-käyttöliittymä tekee työpöydän, keskitetyn alapalkin, Start-valikon,
ilmoituskeskuksen, Gaming Control Centerin ja yksinkertaisen tiedostonhallinnan.
Labwc hoitaa Waylandin, ikkunoiden siirtämisen, koon muuttamisen ja snapin.
Tämä ei ole KDE-teema. KDE ja GNOME ovat erillisiä asennusvaihtoehtoja.

## Aloita tästä

1. Lue [kattava väliraportti](docs/VERIFICATION-REPORT.md),
   [todelliset testitulokset](docs/TEST-RESULTS.md) ja
   [laitetuen rajat](docs/HARDWARE-COMPATIBILITY.md).
2. Rakenna paketit ja ISO **erillisessä Arch-virtuaalikoneessa**:
   [BUILD.md](docs/BUILD.md).
3. Testaa käynnistys ja asennus vain uudella virtuaalilevyllä:
   [VM-TESTING.md](docs/VM-TESTING.md).
4. Käyttö ja pelien käynnistys: [INSTALL.md](docs/INSTALL.md) ja
   [GAMING.md](docs/GAMING.md).

Viimeisimmän GTK/Xvfb-regression kaikki 124 testiä läpäisivät. Tämä on erillinen
tulos oikean Wayland-live-käynnistyksen hyväksynnästä. Tunnetut monitorinvaihdon,
kuvakkeiden, taustan ja sr0-palvelun puutteet ovat julkaisuraportissa.
Testien läpäisy ei todista pelien FPS:ää tai fyysisiä laitteistoajureita.

## Projektin osat

| Polku | Sisältö |
|---|---|
| `src/ownos/` | Asetukset, pelikäynnistys, päivityspolitiikka, pelilista, järjestelmämittarit |
| `src/ownos/ui/` | Oma GTK-työpöytä, Start, asetukset, tiedostot, ilmoitukset |
| `native/` | C/Wayland-apuohjelma ikkunalistaa ja ikkunatoimintoja varten |
| `config/labwc/` | Ikkunat, pikanäppäimet, hiiren flat-profiili, istunnon käynnistys |
| `packaging/` | Allekirjoitettavien Arch-pakettien reseptit ja Calamares 3.3.14 |
| `installer/` | Valinnainen Calamares: Husk Desktop / KDE / GNOME / Minimal ja ajurivalinta |
| `iso/` | Vain live-ISOlle tarkoitettu käyttäjä- ja kirjautumisasetus |
| `branding/` | Oma tekstipohjainen SDDM-kirjautuminen ja Plymouth-teeman lähteet |
| `scripts/` | Pakettien/ISO:n rakentaminen, allekirjoitustarkistus ja QEMU-käynnistys |
| `tests/` | Ydintoiminnot, asennuspolitiikka, paketointi, VM-rajaukset, GTK- ja C-testit |

Yksikkötestit (Python + PyYAML): `make test`. C-testit: `make test-c`. Lähteiden ja asetusten
syntaksi: `python3 scripts/check-source.py` (vaatii PyYAMLin).
Todellinen GTK-testiajo: `./scripts/test-gtk.sh` Archin tai CI:n
testiympäristössä, jossa Xvfb ja GTK ovat käytettävissä.

Ensimmäinen ISO rakennetaan oletuksena **live-käyttöön ilman Calamaresia**.
Asentajan lähteet ja vaihtoehdot säilyvät; `--with-installer` ottaa sen mukaan
molemmissa rakennusvaiheissa. Aktiivinen Archiso-profiili tuotetaan asennetun
relengin pohjalta: [iso/PROFILE.md](iso/PROFILE.md).

Husk Desktop on modulaarinen: `panel.py` vastaa taskbarista ja `launcher.py`
Start-valikosta, `desktop_layout.py` sijoittelusta ja `themes.py` käyttäjän CSS:stä.
Paneelin sijaintia, korostusväriä ja CSS:ää voi muuttaa lähdekoodin mukaan ilman
ISO:n uudelleenrakentamista. Perustyöpöytä on käynnistetty VM:ssä; kaikkien
asetusten vuorovaikutusta ei ole vielä hyväksymistestattu.
Windows-henkinen MVP on välivaihe kohti omaa Husk Desktopia; Linux-ydin,
labwc, GTK ja Calamares ovat avoimesti dokumentoituja upstream-komponentteja.

Turvallisuusominaisuuksia ei poisteta suorituskyvyn vuoksi. Päivitykset ovat
täysiä `pacman -Syu` -transaktioita. Heroic asennetaan käyttäjäkohtaiseen
Flatpakiin käyttäjän vahvistuksella. Steam/Proton eivät takaa kaikkien
Windows-pelien toimivuutta. Fortnitea ei luvata paikallisesti toimivaksi.

Lisenssi: [MIT](LICENSE); riippuvuudet ja mukana oleva Wayland-protokolla
säilyttävät omat lisenssinsä.
