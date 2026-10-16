# Toistettava suorituskykyvertailu (suunnitelma, ajamatta)

Mittaa samalla fyysisellä koneella Windows ja Husk OS, samalla peliversiolla,
resoluutiolla, grafiikka-asetuksilla, FPS-rajalla ja vastaavalla ajuriversiolla.
Kirjaa laitemalli, BIOS, näytön Hz, CPU/GPU/VRAM/RAM, virta-/jäähdytystila,
käyttöjärjestelmän build, Proton-versio ja pelin asetukset. Käytä mahdollisuuksien
mukaan omaa offline-benchmarkia, jonka tapahtumat toistuvat samoin.

Lämmitä shader-välimuisti ennen tallennusta. Tee vähintään viisi samanpituista
ajoa per kokoonpano; säilytä raaka frametime-data. Vertaa Husk OS:n Gaming Mode
pois/päällä ja MangoHud pois/päällä erikseen, jotta mittarin oma kuorma näkyy.
Älä sekoita ensimmäistä shader-käännösajoa myöhempiin.

| Mittari | Mittaaminen |
|---|---|
| Keskimääräinen FPS | Sama jakso ja sama FPS-/frametime-lähde |
| 1 % / 0,1 % low | Sama laskentamenetelmä kaikille ajoille |
| Frametime p50/p95/p99 | Säilytä millisekuntinäytteet, ilmoita hajonta |
| Input lag | Erillinen korkean kuvataajuuden kamera/latenssimittari, ei pelkkä FPS |
| RAM ja tausta-CPU | 5 min vakaa idle-tila, samat taustasovellukset |
| Käynnistys | systemd-analyze + vertailukelpoinen käynnistysmittaus Windowsissa |
| Levytilan käyttö | Asennus-/pelijalanjäljet eroteltuna |
| Lämpötila ja kellot | Varmista, ettei lämpö-/virtaraja erota ajoja |

Julkaise mediaani ja vaihteluväli. Erottele native-Linux-, Proton- ja
anti-cheatin vuoksi käynnistymättömät pelit. VM:n FPS ei ole fyysisen koneen
gaming-vertailu. Tässä toimituksessa ei ole FPS- tai input-lag-tuloksia.
