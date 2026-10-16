# Husk OS: identiteetti, modulaarinen työpöytä ja ensimmäinen live-käynnistys

Käyttäjän tämän vaiheen määrittely on toteutuksen hyväksytty lähtökohta.
Jatketaan nykyisestä `mvp`-haarasta ja commitista `0742805`; aiempia
ominaisuuksia, testejä tai Git-historiaa ei poisteta.

Husk OS on oma gaming-käyttöjärjestelmä. Käyttäjälle näkyvät nimet ovat
**Husk OS** ja **Husk Desktop**. Arch Linux, Linux-ydin, labwc, GTK,
Calamares ja muut käytetyt komponentit dokumentoidaan avoimesti teknisenä
pohjana. `ownos` säilyy sisäisenä paketti-, moduuli-, D-Bus- ja asetustunnisteena
yhteensopivuuden vuoksi; julkiset `husk-*`-komennot rinnastetaan nykyisiin
`own-*`-komentoihin. `/etc/os-release` käyttää ID:tä `huskos`, ja asennuskohteen
validointi ymmärtää myös aiemman oikean `ownos`-kuvan.

Windows-henkinen MVP on välivaihe. Alapalkki ja käynnistin erotetaan omiksi
GTK-komponenteikseen. Keskitetty layout-politiikka määrittelee niiden paikan;
alapalkin voi valita ylä- tai alareunaan ja muutos latautuu käyttäjäasetuksista.
Värit, taustakuva, animaatiot ja käyttäjäkohtainen CSS voidaan muuttaa ilman
ISO:n tai käyttöjärjestelmän uudelleenrakentamista. Virheellinen CSS hylätään
ja perusulkoasu säilyy. Kompositori ja gaming-politiikka eivät riipu paneelin
tai Startin visuaalisesta toteutuksesta.

Live-ISO sisältää oman istunnon ja sen koko riippuvuusketjun. SDDM käynnistää
tavallisen `live`-käyttäjän Husk Desktopiin ilman levyasennusta. Asentajaa ei
suoriteta automaattisesti. Root-tili lukitaan ja live-oikeudet poistetaan
asennetusta järjestelmästä. Käynnistysvalikko ja asentajan työpöytävalinta
nimeävät Husk OS:n / Husk Desktopin, mutta relengin bootmodes, install_dir,
boot-tiedostot ja allekirjoituspolitiikka säilytetään.

Varmistetaan live-palvelun riippuvuus SDDM:stä, katkaistaan kilpailevat live-
verkkopalvelut, tarkistetaan generoitu profiili ja lisätään `husk-status`
sekä kertaluonteinen `husk-live-smoke` todellista vierasjärjestelmän testausta
varten. Valmistellaan turvalliset QEMU/KVM/TCG- ja VirtualBox-käynnistyskomennot
uusille virtuaalilevyille. VirtualBox ei muokkaa olemassa olevaa VM:ää eikä
liitä fyysistä levyä. Käynnistyvä ISO hyväksytään vasta oikean boot-/GUI-ajon
ja vierasjärjestelmän smoke-raportin perusteella.

Testataan uudet politiikat, pakettistaging, profiiligenerointi, CLI-aliaset,
valinnat ja VM-komennot sekä säilytetään kaikki 65 aiempaa testiä.
GTK-ikkunat, native-Arch-rakennus, UEFI-boot, asentajan osiointi ja peli-/
ajuritestit raportoidaan edelleen ajamattomiksi, jos ympäristö estää ne.
Fyysisen koneen ohjelmia tai osioita ei muuteta. Julkaisua tai Git-pushia ei tehdä.
