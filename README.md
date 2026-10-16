# Husk OS / OwnOS-MVP

**Husk OS** on omaa käyttökokemusta ja järjestelmäsovelluksia kehittävä
gaming-käyttöjärjestelmä, jonka tekninen perusta on **Arch Linux**.
Tämä toimitus on **Experimental 0.1.1-dev** -lähdekoodiversio.
Sisäiset `ownos`-paketti-, asetus- ja D-Bus-tunnisteet säilyvät yhteensopivuuden
vuoksi. Projektia jatketaan alkuperäisestä `mvp`-haarasta.

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

**Toimituksessa on lähdekoodi ja rakennusskriptit. Valmista ISOa ei ole
rakennettu eikä ISO-käynnistystä tai graafista asennusta hyväksymistestattu.**
GTK-koodi on toteutettu lähdekooditasolla; kahdeksan oikeiden ikkunoiden testiä
odottaa sallittua näyttöympäristöä. Testien läpäisy ei todista pelien FPS:ää
tai laitteistoajureita.

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
ISO:n uudelleenrakentamista. Graafinen toiminta odottaa VM-hyväksyntää.
Windows-henkinen MVP on välivaihe kohti omaa Husk Desktopia; Linux-ydin,
labwc, GTK ja Calamares ovat avoimesti dokumentoituja upstream-komponentteja.

Turvallisuusominaisuuksia ei poisteta suorituskyvyn vuoksi. Päivitykset ovat
täysiä `pacman -Syu` -transaktioita. Heroic asennetaan käyttäjäkohtaiseen
Flatpakiin käyttäjän vahvistuksella. Steam/Proton eivät takaa kaikkien
Windows-pelien toimivuutta. Fortnitea ei luvata paikallisesti toimivaksi.

Lisenssi: [MIT](LICENSE); riippuvuudet ja mukana oleva Wayland-protokolla
säilyttävät omat lisenssinsä.
