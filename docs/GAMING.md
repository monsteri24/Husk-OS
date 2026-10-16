# Pelit ja Gaming Mode

Gaming Control Centerin GameMode-valitsin koskee **husk-game-kääreellä**
käynnistettyjä pelejä. Se ei automaattisesti tunnista jokaista ulkopuolelta
käynnistettyä peliä tai muuta pysyvästi koko järjestelmän suorituskykyä.
Feralin GameMode tekee ajonaikaiset muutokset ja palauttaa ne pelin jälkeen.

Steamin pelikohtaisiin käynnistysasetuksiin:

```text
husk-game -- %command%
```

MangoHud-valitsin lisää FPS-/frametime-overlayn tähän kääreeseen. Muiden
käynnistinten omat GameMode/MangoHud-asetukset voidaan käyttää erikseen.
Control Centerin Steam-pelilistan Käynnistä-painike käyttää Steamia;
pelin yllä oleva käynnistysasetus pitää asettaa erikseen.

Steam sisältää virallisen Protonin hallinnan. Heroic palvelee Epic/GOG-kirjastoja,
mutta sen olemassaolo ei tarkoita jokaisen Epic-pelin Linux-tukea.
Wine/Winetricks ja Lutris laajentavat käyttömahdollisuuksia; pelikohtaiset
riippuvuudet ja launcherit voivat silti estää toiminnan.

EAC- ja BattlEye-pelien Proton-tuki edellyttää pelin julkaisijan yhteistyötä.
Fortnitea ei tässä projektissa merkitä paikallisesti Wine/Protonilla tuetuksi.
Anti-cheatia ei ohiteta eikä epäluotettavia ajureita käytetä. Pelin ajantasainen
virallinen Linux-tuki on tarkistettava ennen ostamista tai asennusta.

MVP käyttää tavallista Arch-ydintä ja ajureita. Mitigaatioita, lämpösuojauksia,
pakettiallekirjoituksia tai tärkeitä palveluita ei poisteta FPS:n vuoksi.
Ohjainten udev-säännöt tulevat virallisesta `steam-devices`-paketista;
fyysisiä ohjaimia ei ole testattu tässä ympäristössä.

## Integraatioiden todellinen tila, 14.10.2026

**Yhtään peliä, Steamia tai pelikäynnistintä ei ole ajettu Husk OS:ssä.
Profiilissa oleva paketti ei tarkoita onnistunutta asennusta tai pelitestiä.**

| Osa | Profiili / asennustapa | Konfiguroitu | Testattu | Puuttuva näyttö toimivuudesta |
|---|---|---|---|---|
| Steam | steam + steam-devices ja multilib | Start/taskbar/katalogi, Steam-kirjastojen lukija | VDF/manifest-lukija ja komentosuunnitelmat | Asiakkaan käynnistys, kirjautuminen, peli |
| Virallinen Proton | Steam lataa valitun compatibility toolin; ei erillistä valmiiksi ladattua Proton-pakettia | Hallinta Steamin omista asetuksista | Ei | Protonin lataus, version valinta, pelit ja anti-cheat |
| Proton GE | Ei mukana eikä automaattiasennusta | Ei | Ei | Luotettava asennuspolku, versiohallinta ja peli |
| Heroic | Ei preinstalled; käyttäjäkohtainen Flathub-paketti com.heroicgameslauncher.hgl | Katalogi/Start, remote-URL-tarkistus ja install-komennot | Asennussuunnitelma/argumentit mallitasolla | Flatpak-lataus, käynnistys, Epic/GOG-kirjautuminen ja peli |
| Wine / Winetricks | wine, winetricks profiilissa | Ei valmiita pelikohtaisia prefixejä | Pakettisuunnitelma vain | Wine-käynnistys, 32/64-bit prefix ja pelit |
| Lutris | lutris profiilissa | Katalogikäynnistin, peliasetukset Lutrisissa | Katalogi-/pakettipolitiikka | Sovellus, runnerit ja pelit |
| GameMode | gamemode + lib32-gamemode | husk-game, valitsin oletuksena päällä | Argv-kääre ja puuttuvan työkalun virhe | gamemoded-palvelu, pelikohtaiset muutokset ja palautuminen |
| MangoHud | mangohud + lib32-mangohud | husk-game, overlay oletuksena pois | Argv-kääre | Todellinen Vulkan/OpenGL-overlay, FPS/frametime ja overhead |
| Vulkan | Loader + Radeon/Intel ICD:t 32/64-bit, vulkan-tools | Peruspakettivalinta | Profiili/pakettisuunnitelma | Vulkan-instanssi ja todellinen GPU/peli; NVIDIA userspace vain erillisellä valinnalla |
| OpenGL | mesa/lib32-mesa; NVIDIA erillisellä valinnalla | Peruspakettivalinta | Profiili/pakettisuunnitelma | Konteksti, versio, GPU-kiihdytys ja peli |
| Peliohjaimet | linux + steam-devices | Upstreamin udev-säännöt paketin kautta | Paketin virallinen saatavuus ja profiilirivi | Laite-ID, käyttöoikeus, painikkeet, rumble ja paritus |
| NVIDIA | nvidia-open-dkms/utils/headers erikseen; ei oletus-liveen | Eksplisiittinen käyttäjävalinta, Turing+ | Valintapolitiikka | DKMS-käännös, KMS, firmware, Wayland, Vulkan/OpenGL ja hybridigrafiikka |
| AMD / Intel | Mesa, ICD:t ja linux-firmware live-profiilissa | Peruspolku | Profiilin sisältö | Oikea GPU, oikea ajuri ja peli |

Discord, Firefox, Foot, Flatpak ja nykyiset Husk-sovellukset ovat paketti-/katalogi-
kokoonpanossa. Protonin ja Heroicin lataukset edellyttävät erikseen verkkoyhteyttä.
GameMode ei ole yleinen automaattinen pelintunnistus, MangoHud ei ole oma Huskin
mittausmoottori, eikä mikään testattu komentosuunnitelma ole FPS-tulos.

Lähteet: [Steam Proton -kehittäjäohje](https://partner.steamgames.com/doc/steamhardware/proton),
[virallinen steam-devices-paketti](https://archlinux.org/packages/multilib/x86_64/steam-devices/),
[NVIDIA open kernel modules](https://github.com/NVIDIA/open-gpu-kernel-modules).
