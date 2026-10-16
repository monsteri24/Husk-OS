# Husk OS – todelliset testitulokset, 14.10.2026 🦅

**Current development is System 2.** Its source, GTK and actual Labwc test
results, including intermediate failures and environment limits, are recorded
separately in [the System 2 report](../HuskOS-system-2-REPORT.md).
The historical counts below are not current System 2 counts or hardware tests.

**Uudempi System 1 -tulos 16.10.2026:** ISO rakennettu, ladattu GitHub Releaseen
ja latauksen SHA-256 varmennettu; oikea QEMU/OVMF/Wayland-työpöytäkäynnistys
ja sammutus läpäisty. Viimeisin GTK/Xvfb-ajo: **124 läpäistyä, 0 epäonnistunutta,
0 ohitettua**. Headless: 116 läpäistyä / 8 GUI-ohitusta. Syntaksi: 101 tarkistusta.
[Raportti, epäonnistuneet aiemmat yritykset ja todistusaineisto](../HuskOS-system-1-REPORT.md).
Alla olevat 14.10.2026 tulokset ja viisi kierrosta ovat säilytettyä historiaa;
niitä ei pidä tulkita nykyisen ISO:n tai tämän päivän viideksi testikierrokseksi.

Versio: 0.1.1-dev. Vertailu: edellinen lähdekooditoimitus 0742805, jossa
65 testiä löytyi, 61 läpäisi ja 4 GUI-testiä ohitettiin; 77 syntaksitarkistusta.
Aikaisemmat testit ja lokit säilyvät. Nyt testitapauksia on 90.

## Viisi lopullista kierrosta

Kierrokset ajettiin peräkkäin samalla muuttumattomalla lähdekoodilla.

| Kierros | Löydetyt unittest-tapaukset | Suoritetut | Läpäisseet | Epäonnistuneet | Ohitetut | Syntaksitarkistukset |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 90 | 82 | 82 | 0 | 8 | 90/90 |
| 2 | 90 | 82 | 82 | 0 | 8 | 90/90 |
| 3 | 90 | 82 | 82 | 0 | 8 | 90/90 |
| 4 | 90 | 82 | 82 | 0 | 8 | 90/90 |
| 5 | 90 | 82 | 82 | 0 | 8 | 90/90 |

Suoritetut = löydetyt − ohitetut. Unittestin oma “Ran 90” sisältää myös ohitetut.
82 eri testiä toistettiin viisi kertaa (410 läpäissyttä testisuoritusta).
Tämä ei ole 410 eri ominaisuutta tai viisi laitteistotestiä.
Syntaksitarkistuksia ei lisätä unittest-määriin.

Jokaisella kierroksella myös nämä erilliset tarkistusryhmät läpäisivät:

- Native-C/Wayland-silta kääntyi -Wall -Wextra -Werror -asetuksilla.
- JSON-C-apuohjelman ASan/UBSan-tarkistus läpäisi. Tämä ei suorita koko Wayland-siltaa.
- Oikeat GTK3-, paneeli-, launcher-, Control Center-, Files- ja ilmoitusmoduulit importoituivat;
  D-Bus-tilakyselyn XML jäsentyi oikeassa Gio:ssa.
- Oikea GTK CSS-parseri hyväksyi perusulkoasun ja käyttäjän kelvollisen CSS:n.
  Virheellinen CSS tuotti varoituksen ja säilytti perusulkoasun.

LeakSanitizer oli pois (`ASAN_OPTIONS=detect_leaks=0`), koska rajoitettu
kehityskontti estää task-/ptrace-tarkastuksen. Tulosta ei käytetä todisteena
muistivuotojen puuttumisesta. Kokonaisen GTK-istunnon pitkäajoa ei tehty.

## Ohitetut GUI-testit joka kierroksella

1. Startin avaaminen ja Heroic-haku oikeassa ikkunassa.
2. Gaming-valitsimen tallennus Control Centeristä.
3. Files-ikkunan kansiovaihto.
4. Ilmoituskeskuksen näkyvä tekstirivi.
5. Taskbarin ja launcher-komponentin GTK-koostaminen.
6. Paneelin ylä-/alapaikan vaihto ja ilmoitusten säilyminen.
7. Virheellisen käyttäjä-CSS:n fallback näkyvässä työpöydässä.
8. Preview-ikkunoiden status ei saa väittää live-Wayland-käynnistystä.

Niitä ei ajettu `OWNOS_UI_TESTS=1`-tilassa: todellinen display-socket estyy
EPERM-virheeseen. Käyttöliittymän import ja CSS-jäsennys eivät korvaa näitä.

## Epäonnistuneet esitarkistukset

Jokaisella kierroksella kolme rakentamis-/VM-esitarkistusta palautti 1:

| Tarkistus | Tulos ja syy |
|---|---|
| build-packages.sh --check | Missing: makepkg; repo-add ja järjestelmän wayland-scanner puuttuvat myös ympäristökartoituksesta |
| build-iso.sh --check | ID=ubuntu; mkarchiso, pacman, pacman-key, mksquashfs, xorriso, asennettu releng, oikea allekirjoitettu repo ja julkinen rakennusavain puuttuvat |
| test-vm.py --check | qemu-system-x86_64, qemu-img ja OVMF puuttuvat |

Näitä ei lasketa kahdeksaan unittest-ohitukseen tai nollaan unittest-virheeseen.
Esitarkistukset todistavat esteen; ne eivät ole onnistuneita rakentamis- tai boot-testejä.
VBoxManage puuttuu. /dev/kvm puuttuu, mutta pelkkä tämä ei estäisi QEMU TCG:tä.
`unshare --user --map-root-user --mount /bin/true` palauttaa 1, uid_map EPERM;
CapEff/CapBnd ovat nolla, NoNewPrivs=1 ja Seccomp=2. AF_UNIX-soketin luonti
palauttaa EPERM. Näistä syistä täyttä Archiso-/GUI-/VM-ajoa ei yritetty toistuvasti.

## Kehityksessä löydetty ja korjattu

Uudet testit osoittivat ensin puuttuvat status-/renderer-toiminnot ja asentajan
pakollisen riippuvuuden. Toteutusten jälkeen ne läpäisivät.
GRUBin nimien päivitys puuttui efiboot/syslinux-käsittelyn rinnalta, ja
profiilin validaattori ei huomannut poistettua NetworkManager-linkkiä.
Näissä kahdessa regressiotarkistuksessa nähtiin FAIL, sitten ne korjattiin.
Nämä kehitysvaiheen ajot eivät ole lopullisen viiden kierroksen tuloksia.

Aikaisemman riippumattoman katselmoinnin initcpio-, putkilukija- ja qcow2-
korjaukset säilyvät. Uutta riippumatonta loppukatselmointia ei saatu suoritettua;
nykytilalle tehtiin oma lähdekoodin läpikäynti ja yllä kuvatut tarkistukset.

## Mitä testi osoittaa ja mitä ei

Asetusten atominen tallennus/validointi, rajatut ilmoitus-/ikkunamallit,
Steam-manifestit, turvallinen komentoargumenttien rakentaminen, installer-
suunnitelmat ja väliaikaisen kohdehakemiston siivous, pakettien staging,
Archiso-overlayn generoiminen synteettisestä relengistä sekä VM-levyn rajaukset
on ajettu. Asennuskäskyjen ulkoiset pacman/chroot/systemctl-kutsut on korvattu
fixture-ajureilla. Profiilitestin paketit/allekirjoitukset ovat tarkoituksella
synteettisiä; ne eivät ole todellisia rakennettuja tai varmennettuja paketteja.

TESTAAMATON: oikea Arch-pakettikäännös, kaikki pakettiriippuvuudet ratkaistuna,
repojen oikea pacstrap-allekirjoitusketju, ISO, UEFI/BIOS-boot, initramfs runtime,
SDDM, labwc/layer-shell/foreign-toplevel runtime, fyysinen input/audio/network,
Calamares-osiointi ja asennettu reboot, Steam/Proton/Wine-pelit, FPS,
idle-RAM/CPU, boot-aika, energiankulutus ja koko järjestelmän muistivuodot.

## Todisteet ja toistaminen

Täydet kierroskohtaiset lokit ja JSON-tulokset:
[evidence/verification-2026-10-14/results.json](evidence/verification-2026-10-14/results.json).
Jokaisella round-1…round-5-kansiolla on unit-, syntaksi-, native-, C-, GTK- ja
esitarkistuslokit sekä record.json. environment.json tallentaa todetut ympäristöesteet.

Testattu lähdepolkujen SHA256-yhdistelmä: `f18a90f63351ed335590af0435973d2a6466f8be6309f322ee9e2ffbf129d88a`.
Se on tiedostolistasta laskettu lähdesnapshotin tunniste, ei ZIP-/ISO-tarkistussumma.
Raportit eivät kuulu tähän kooditunnisteeseen. Lähdepuu pysyi samana koko viiden kierroksen ajan.

Suoritusikkuna UTC: `2026-10-14T17:27:21.360858+00:00` – `2026-10-14T17:27:25.253628+00:00`.

Valmistellussa Arch VM:ssä: `python3 scripts/verify-five.py`, ja
näyttötestit `./scripts/test-gtk.sh`. Kehityskontin ajossa käytettiin
`--gtk-runtime ../test-runtime/root --disable-leak-check`;
yksityisesti puretut ulkoiset testikirjastot eivät kuulu projektin ZIPiin.
