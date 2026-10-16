> Tämä dokumentti kuvaa valinnaista ja vielä hyväksymistestaamatonta asentajaa.
> Oletus-live-ISO ei sisällä Calamaresia. Ota se mukaan molempien
> rakennusskriptien `--with-installer`-valinnalla. Live-käyttö ei vaadi asennusta.

# Käyttö ja asennuksen rajat

Ensimmäinen kohde on testaus virtuaalikoneessa, ei pääkoneen levy.
Calamares tarvitsee verkkoyhteyden ja suorittaa hyväksytyn asennuksen aikana
täyden pakettipäivityksen. Osioinnin tekee Calamares käyttäjän hyväksynnällä;
projektin rakennus- ja VM-skriptit eivät osioi fyysisiä levyjä.

| Valinta | Sisältö | Kirjautuminen |
|---|---|---|
| Husk Desktop (Experimental) | Oma shell, asetukset ja tiedostot labwc:n päällä | SDDM |
| KDE Plasma | Plasma ja oma Gaming Control Center | SDDM |
| GNOME | GNOME ja oma Gaming Control Center | GDM |
| Minimal | Tekstitila, pacman, verkkoyhteys ja ydintyökalut | TTY |

Minimal poistaa omat GUI-/desktop-paketit ja kuratoidut pelisovellukset.
Se ei ole vielä mitattu mahdollisimman pieni Arch-asennus: relengin muut
rescue-työkalut voivat jäädä järjestelmään. Pakettijalanjäljen karsiminen
on jatkokehitystä.

Steam, Wine/Winetricks, Lutris, GameMode, MangoHud, Discord ja Firefox
sisältyvät työpöytävalintojen paketteihin. Heroic-pikakuvake pyytää
ensimmäisellä käyttökerralla käyttäjäkohtaisen Flatpak-asennuksen.
Proton hallitaan Steamin asetuksissa. SDDM:ssä/GDM:ssä voi valita myöhemmin
asennetun työpöydän.

Husk Desktopin pikanäppäimet: Super+Space Start, Super+E tiedostot,
Super+I asetukset, Super+L lukitus, Super+Return terminaali,
Super+Left/Right snap, Alt+Tab vaihto ja Alt+F4 sulkeminen.

Päivitys avautuu Control Centeristä terminaaliin ja pyytää pacman-vahvistuksen.
Päivitysten palautusta tai Btrfs-snapshotteja ei ole automatisoitu. Julkaisun
omille paketeille käytetään ISO:n allekirjoitettua repo-snapshotia;
julkista jatkuvasti päivittyvää Husk OS-repoa ei ole tässä versiossa.

Lisätyöpöytä voidaan asentaa Control Centeristä. Minimalissa esimerkiksi:

```bash
sudo pacman -Syu --needed ownos-desktop ownos-ui ownos-branding sddm
sudo systemctl enable sddm.service
sudo systemctl set-default graphical.target
```

Tämä muuttaa vain järjestelmää, jossa komento ajetaan. Kun toinen
kirjautumispalvelu on jo aktiivinen, säilytä se ja valitse uusi istunto siitä.

Plymouth-teeman lähteet ovat mukana, mutta boot-splashin hook-/GRUB-integraatio
ja salasana-/boot-näkymä eivät ole hyväksymistestattuja. SDDM-teema on
paketoitu; QML:n todellinen greeter-ajo on myös testattava VM:ssä.
