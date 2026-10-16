# Jatkamisen tiedot

Alkuperäinen haaran nimi: `mvp`. Ensimmäiset säilytetyt commitit:
`ce617f8` (suunnitelma) ja `1dfc886` (29 testin ydinkoodi).
Jatkaminen alkoi keskeneräisistä `bin/`, `config/`, `data/`, `native/` ja
GTK-lähdetiedostoista. `steam-devices` varmistettiin virallisesta multilib-reposta.

Säilytetty arkkitehtuuri: Python/GTK3 + gtk-layer-shell + labwc;
oma käyttöliittymä, oma C-ikkunalistasilta, Calamares, relengistä johdettu Archiso.

Korjattu jatkossa: ikkunalistaviestien validointi ja rajaus, syöttöasetusten
atomiset tiedostokirjoitukset, monitorikäsittelijöiden sulkeminen, selkeä
puuttuvan näytön virhe, asennettujen Python-pakettien hakemistorakenne,
asennuskohteen tarkka OwnOS-tunnistus ja live-initramfs-asetusten poistaminen.

Toteutettu: allekirjoitettavat split-paketit, julkinen keyring,
repo-allekirjoituksen tarkistus, Archiso-profiilin generaattori,
työpöytä-/ajurivalinnat, live-asetusten poisto ja virtuaalilevyyn rajattu QEMU-runner.

Ruling: nykyinen erillinen työkansio ja `mvp`-haara säilytetään käyttäjän
nimenomaisen jatkamispyynnön vuoksi. Uutta projektia tai työhaaraa ei aloiteta.
Ruling: näytön socket-eston vuoksi graafinen GTK-/Wayland-hyväksyntä siirtyy
VM:ään; puuttuvaa testiä ei merkitä läpäistyksi.
Ruling: Plymouth-teeman lähteet toimitetaan, mutta automaattinen boot-hookin
aktivointi siirretään erikseen hyväksymistestattavaksi.
Ruling: ensimmäinen levytesti on ext4 ilman salattua osiointia.

Seuraava työ alkaa BUILD.md:n mukaisesta Arch-VM:n pakettikäännöksestä,
sitten GTK- ja VM-TESTING.md:n hyväksymisajoista. Säilytä testien lokit ja
päivitä TEST-RESULTS.md vain todellisten uusien ajojen perusteella.

Loppukatselmoinnin kolme tärkeää löydöstä korjattiin testien avulla:
Archin initcpio-vaihe, ikkunalistasillan ei-estävä binaarilukija ja QEMU:n
ulkoisten datatiedostojen hylkäys. Calamaresin kone-ID- ja entropia-asetukset
lisättiin erikseen; kaikki käytetyt moduulit saavat oman asetustiedoston.
Lopputulos: 65 löydettyä testiä, 61 läpäissyttä, 4 GUI-testiä ohitettu.
77 lähde-/asetussyntaksin tarkistusta läpäisee. Katso täsmälliset rajat
TEST-RESULTS.md:stä.

## Jatko 14.10.2026 – Husk OS 0.1.1-dev

Sama mvp-haara ja kaikki aiemmat testit säilyvät. Julkinen nimi on Husk OS,
työpöytä Husk Desktop. Panel/Launcher/Layout/Theme erotettiin, käyttäjän CSS
ja paneelin paikka lisättiin. Live-status/renderer kytkettiin istuntoon,
SDDM järjestettiin live-käyttäjän jälkeen ja avainrengas erotettiin omaan palveluun.
Calamares on --with-installer-lisä; alkuperäiset neljä työpöytävalintaa säilyvät.

Lopulliset viisi kierrosta: jokaisessa 90 löytyi, 82 suoritettiin/läpäisi,
0 epäonnistui ja 8 GUI-testiä ohitettiin. 90 syntaksitarkistusta, native-käännös,
C-helper ASan/UBSan (ilman LeakSanitizeria), oikeat GTK-importit ja CSS-parseri läpäisivät.
Paketti-, ISO- ja QEMU-esitarkistukset estyivät puuttuvien työkalujen vuoksi.
ISOa ei rakennettu, Husk OS ei bootannut eikä laitteita tai pelejä testattu.

Jatka BUILD.md:n default-live-rakennuksesta erillisessä Arch VM:ssä. Kerää
VM-TESTING.md:n status-, boot-, input-, sovellus- ja reboot-todisteet.
Katso VERIFICATION-REPORT.md ja HARDWARE-COMPATIBILITY.md ennen laitetukiväitteitä.
