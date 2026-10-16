# Husk OS:n Archiso-profiili

Profiilin ylläpidetty lähde on `src/ownos/build.py`; overlayn live-komennot ovat
`iso/live-setup`, `iso/live-keyring` ja niiden systemd-yksiköt.
`packages.husk.x86_64` luettelee tämän version lisäykset, ei koko relengin pakettijoukkoa.

`scripts/build-iso.sh` kopioi Arch-rakennus-VM:n asennetun
`/usr/share/archiso/configs/releng`-profiilin uuteen `.build/profile`-hakemistoon.
Se säilyttää upstreamin UEFI/BIOS-käynnistystiedostot, kernel-/initramfs-polut,
`install_dir`-arvon, bootmodes-määrityksen ja bootstrap-tiedostot.
Käyttäjälle näkyvä ISO-nimi ja boot-valikoiden tekstit ovat Husk OS.

Omat allekirjoitetut paketit, multilib, Husk Desktop, firmwaret, Mesa,
verkko-, Bluetooth-, ääni- ja virranhallintakomponentit lisätään kopioon.
`calamares` sisältyy vain `--with-installer`-valinnalla. Asennus ei käynnisty automaattisesti.

Live-käynnistyksen järjestys on systemd → live-käyttäjän valmistelu → SDDM →
`husk-session` → labwc → `husk-desktop`. Pakettiavainten alustus käynnistyy
erillisenä palveluna ja sen onnistuminen näkyy `husk-status`-tuloksessa.
NetworkManager käyttää wpa_supplicantia; kilpailevat relengin iwd/networkd-
aktivoinnit ja sshd poistetaan overlaysta. Bluetooth ja power-profiles-daemon
otetaan käyttöön. PipeWire/WirePlumber hoitavat äänen käyttäjäistunnossa.

Tarkistus: `python3 scripts/check-profile.py .build/profile`.
Validoidaan pakettinimet, Husk-identiteetti, ei-root-live-autologin, SDDM:n
riippuvuusjärjestys, palvelulinkit ja allekirjoituspolitiikka.
Tämä ei tarkista binääripakettien koko riippuvuusratkaisua tai todista käynnistystä.

ZIP ei sisällä teeskenneltyä, synteettisesti allekirjoitettua rakennusprofiilia.
Täydellinen aktiivinen `.build/profile` syntyy oikean pakettirakennuksen jälkeen;
sen kernelit ja initramfs-kuvat tuottaa mkarchiso. Katso `docs/BUILD.md`.
