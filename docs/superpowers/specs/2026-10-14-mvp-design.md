# Own Gaming OS: ensimmäisen kehitysversion suunnitelma

## Tavoite ja rajat

Rakennettava Arch-pohjainen x86_64-jakelu, oma kevyt Windows-henkinen
työpöytä, pelityökalut ja graafinen työpöytävalinta. `ownos` on tekninen
työnimi; julkaisun nimi ja logo päätetään myöhemmin. Versio on 0.1.0-dev,
Own Desktop on Experimental. Mitään käyttäjän fyysisen koneen ohjelmia,
levyjä tai käyttöjärjestelmää ei muuteta tässä kehitystyössä.

Työ tuottaa lähdekoodin, Arch-paketit rakentavat reseptit, Archiso-profiilin
generoinnin, Calamares-asetukset ja testit. Todistettu testitulos erotetaan
aina vielä ajamattomasta ISO-, asennus-, ajuri- ja pelitestistä.

## Tekniset valinnat

Oma kokonaan uusi kompositori olisi pitkä projekti ennen käyttökelpoista
työpöytää. KDE:n muokkaus tuottaisi nopeasti valmiin kokonaisuuden mutta ei
pyydettyä omaa käyttöliittymää. Valitaan labwc + oma GTK3/Python-käyttöliittymä:
labwc hoitaa Waylandin, XWaylandin, ikkunoiden siirron, koon ja snapin;
projektin omat ohjelmat hoitavat työpöydän, alapalkin, Startin, asetukset,
tiedostot ja ilmoitukset. GTK3 valitaan valmiin gtk-layer-shell-tuen vuoksi.
GTK4-siirto arvioidaan myöhemmin mitattujen muistitulosten perusteella.

Wayland-ikkunalista ja ikkunatoiminnot tulevat pienestä C-apuohjelmasta
wlr-foreign-toplevel-management-protokollalla. Se välittää JSON-rivejä
käyttöliittymälle ja hyväksyy vain aktivointi-, pienennys- ja sulkemiskäskyt.
Sovelluksia käynnistetään Gio.DesktopAppInfo:n avulla; .desktop-tiedostojen
Exec-kenttiä ei ajeta itse shellissä. Työpöydän .desktop-pikakuvakkeen
suorittaminen vaatii käyttäjän vahvistuksen.

## MVP:n osat

- Keskitetty alapalkki, omat Start- ja ilmoitusnäkymät, kello, äänenvoimakkuus
  ja verkkoyhteyden tila. Steam/Heroic ovat aina Startissa.
- Työpöydän kansiot ja pikakuvakkeet sekä yksinkertainen oma tiedostonhallinta.
  Ei roskakorin tai tiedostojen poistamisen toteutusta tässä versiossa.
- Gaming Control Center: pelikohtaisen GameMode-kääreen ja MangoHudin
  asetukset, CPU/RAM/GPU-tiedot, ajuritiedot, Steam-pelilista, taustakuva,
  sininen korostusväri ja syöttöasetukset. Virkistystaajuus avataan wdisplaysiin.
- Omat labwc-asetukset, Wayland-istunto, tumma ulkoasu, siniset korostukset,
  pyöristetyt kulmat. Useamman näytön ja lukituksen jatkotestit dokumentoidaan.
- Oma SDDM-kirjautumisteema ja yksinkertainen Plymouth-käynnistysnäkymä.

## Pelit ja suorituskyky

Steam, Wine, Winetricks, Lutris, MangoHud, GameMode, Discord ja Firefox
valitaan Archin virallisista allekirjoitetuista paketeista. Proton tulee
Steamin omasta hallinnasta. Heroic asennetaan käyttäjän vahvistuksella
käyttäjäkohtaiseen Flatpakiin Flathubin varmennetusta jakeluketjusta;
AUR-apuohjelmaa tai curl-putkea shelliin ei tarvita.

GameMode on käynnistyskääre, ei pysyvä järjestelmän viritys. Feralin GameMode
huolehtii ajonaikaisista muutoksista ja palautuksesta. Turvallisuusmitigaatioita,
palomuuria, lämpösuojauksia, palveluita tai ajurien suojausasetuksia ei
poisteta. GameMode-asetuksen vaihtaminen koskee seuraavia käynnistyksiä.
MangoHud mittaa FPS:n ja frametimet; input lag vaatii erillisen mittauksen.
Linuxin FPS-etua ei oleteta, eikä VM-tuloksia käytetä laitteiston FPS-vertailuun.

Fortnitea ei luvata toimivaksi paikallisesti Wine/Protonilla. EAC/BattlEye
vaativat pelin julkaisijan tuen. Ohituksia, huijausta tai epäluotettavia
ajureita ei integroida.

## Asennus ja paketointi

Archison asennetun releng-profiilin kopioon lisätään omat asetukset ja
paketit. Näin käynnistyksen upstream-muutoksia ei kopioida vanhenevaksi
käsintehdyksi profiiliksi. Rakentaminen tehdään erillisessä Arch-VM:ssä.
Rakennusskriptit eivät asenna riippuvuuksia isäntäjärjestelmään tai kirjoita
lohkolaitepolkuun. Niissä on riippuvuus- ja käyttöympäristöjen esitarkistus.

Omat paketit ja Calamares rakennetaan lähdekoodista, allekirjoitetaan
rakentajan määrittelemällä GPG-avaimella ja toimitetaan allekirjoitetussa
paikallisessa pacman-repossa. Pakettiallekirjoituksia ei ohiteta. Julkaisijan
salaista avainta ei sisällytetä ISO:on. Julkinen repoavain ja luottamuslista
sisällytetään erilliseen ownos-keyring-pakettiin. Julkisen HTTPS-repon
julkaiseminen on myöhempi julkaisuaskel; MVP käyttää ISO:n repo-snapshotia.

Calamares 3.3.14 käyttää kahta packagechooser-instanssia. Ensimmäinen
valitsee Own Desktop / KDE / GNOME / Minimal. Toinen valitsee Mesa-ajurit
tai käyttäjän nimenomaisesti valitseman NVIDIA Turing+ -ajurin. Vanhoja
NVIDIA-kortteja ei ohjata automaattisesti uusimpaan proprietary-ajuriin.
Live-järjestelmä käyttää Mesa/Nouveau-pohjaa.

Oma Calamares Python-job käsittelee vain tarkasti sallittuja valintoja,
varmistaa kohdejuuren, alustaa pakettiavaimet, tekee täydellisen pacman
-Syu-transaktion, valitsee kirjautumispalvelun ja poistaa live-asetukset.
Asentaminen tarvitsee verkkoyhteyden. Minimal käynnistyy TTY:hin.
Osiointi tehdään vain käyttäjän Calamaresissa hyväksymässä VM-asennuksessa.

## Päivitykset ja oikeudet

Käyttöliittymä toimii tavallisena käyttäjänä. Privileged helper hyväksyy
vain kiinteitä päivitys-, paketti-, ajuri- ja työpöytätoimintoja ja käyttää
polkitia. Pacman näyttää transaktionsa terminaalissa ja kysyy vahvistuksen.
Osittaisia Arch-päivityksiä, pakettiallekirjoituksen ohituksia tai db.lck:n
automaattista poistamista ei sallita. Automaattista rollbackia ei luvata:
palautus dokumentoidaan ja automaattiset Btrfs-snapshotit tulevat myöhemmin.

## Testaus ja hyväksymiskriteerit

Puhtaat Python-mallit testataan unittestillä ilman GTK- tai Arch-riippuvuutta.
Testit kattavat komentojen rajauksen, asetusten atomisen kirjoituksen,
Steam-manifestien lukemisen, ilmoitusten korvaamisen, asennusvalinnat ja
kohdejuuren väärinkäytön eston. C-JSON-escaping testataan kääntämällä oikea
funktio. Rakennusskriptien esitarkistus ei saa muuttaa järjestelmää.

GTK-käyttöliittymä ja Wayland-integraatio testataan erillisellä paikallisella
testiruntimella, jos riippuvuudet saadaan saataville. ISO ja Calamaresin
osiointi hyväksytään vasta QEMU/UEFI-testien jälkeen; ajurien/pelien
hyväksyntä vaatii oikean testikoneen myöhemmässä vaiheessa. Ajamatta jäävät
testit ja niiden syyt kirjataan docs/TEST-RESULTS.md-tiedostoon.
