# Tekniset ensisijaiset lähteet

Tarkistettu 14.10.2026. Käytä rakentamishetken Arch-pakettitietoja:
rolling release -pakettinimet ja riippuvuudet voivat muuttua.

- Archiso ja releng: https://github.com/archlinux/archiso sekä https://wiki.archlinux.org/title/Archiso
- mkarchiso: https://man.archlinux.org/man/mkarchiso.1.en
- Pacmanin allekirjoituspolitiikka: https://man.archlinux.org/man/pacman.conf.5.en
- makepkg ja repo-add: https://man.archlinux.org/man/makepkg.8.en ja https://man.archlinux.org/man/repo-add.8.en
- steam-devices, virallinen multilib-paketti: https://archlinux.org/packages/multilib/x86_64/steam-devices/
- Steam Linux -käyttö: https://wiki.archlinux.org/title/Steam
- Labwc ja XML-asetukset: https://labwc.github.io/ ja https://labwc.github.io/labwc-config.5.html
- GTK layer shell: https://github.com/wmww/gtk-layer-shell
- Foreign toplevel -protokolla: https://gitlab.freedesktop.org/wlroots/wlr-protocols
- Calamares 3.3.14 -release ja sen mukana tulevat moduulien asetusesimerkit: https://github.com/calamares/calamares/releases/tag/v3.3.14
- Feral GameMode: https://github.com/FeralInteractive/gamemode
- MangoHud: https://github.com/flightlessmango/MangoHud
- Proton ja anti-cheat-integraatio: https://partner.steamgames.com/doc/steamdeck/proton
- Heroic: https://heroicgameslauncher.com/ ja https://flathub.org/apps/com.heroicgameslauncher.hgl
- QEMU: https://www.qemu.org/docs/master/system/

Calamares-release-arkiston paikallisesti tarkistettu SHA256:
`5547f80db067dea923ae693ba6bb88eb2b2eeac1da3ebec42fce453e31c290c0`.
Tämä on lukitun HTTPS-release-latauksen tarkistussumma, ei väite erillisestä
upstream-PGP-allekirjoituksen tarkistuksesta. Rakennus-VM allekirjoittaa
siitä käännetyn paketin omalla kehitysavaimellaan.

## 0.1.1-dev:n lisätarkistukset

Laitetuen kernel/Mesa/NVIDIA/libinput/PipeWire/NetworkManager-lähteet ovat
HARDWARE-COMPATIBILITY.md:ssä. Tiedot kuvaavat upstreamia, eivät Husk-laitetestejä.
VirtualBox 7.2:n virallinen ohje: https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/working-with-vms.html
Pacstrapin -G ja pacmanin absoluuttinen GPGDir: https://man.archlinux.org/man/pacstrap.8.en ja https://man.archlinux.org/man/pacman.8.en
Filesystem-paketin tiedostolista (usr/lib/os-release, ei etc/os-release-pakettitiedostoa): https://archlinux.org/packages/core/any/filesystem/files/
Näiden tarkistaminen ei ole native-paketin rakentamis- tai ISO-käynnistystesti.
