# System 2 development — 2026-10-16

- Recovered the interrupted source work on top of System 1 and backed up the
  original history. Kept System 1 as a permanent, unchanged historical release.
- Made Husk UI text English, with gettext extraction/plurals and only English
  enabled; translated Husk Settings, Start/taskbar, Files, notifications,
  lock refusal, dialogs, SDDM and Husk installer text.
- Added missing Labwc Close/Iconify/Maximize pointer actions and idempotent
  migration that preserves existing custom mouse/key bindings.
- Included the exact supplied desert image, uniform cover rendering inside
  Husk Desktop and an output-sized background behind the panel.
- Added original MIT SVG icons, checked name/GIcon loading and visible fallbacks,
  including an explicit SVG decoder dependency.
- Removed optional applications from default live/installer package policy;
  retained authenticated on-demand installation and strengthened Flathub checks.
- Added actual Labwc/Wayland pointer/rendering CI and installed-rootfs checks.
  See [the System 2 report](HuskOS-system-2-REPORT.md) for tested scope/failures.

# Muutosloki – Husk OS 0.1.1-dev, 14.10.2026

Vertailukohta on edellisen toimituksen commit `0742805` (0.1.0-dev).
Sen korjaukset, 65 testitapausta ja aikaisempi Git-historia säilyvät.

- Käyttäjälle näkyvät käyttöjärjestelmä-, istunto-, sovellus-, boot- ja asentajanimet
  päivitettiin Husk OS / Husk Desktop -muotoon. Tekniset ownos-tunnisteet ja vanhat
  komennot säilyvät. Keskitetty identiteettimoduuli ja husk-komentoaliakset lisättiin.
- Taskbar ja Start erotettiin omiksi GTK-komponenteiksi. Paneeli voi olla ylhäällä
  tai alhaalla. Käyttäjäkohtainen CSS ladataan asetuskansiosta; virheellinen CSS
  palauttaa perusulkoasun ja ilmoituksen. Ilmoitus-/ikkunamallit säilyvät paneelin vaihdossa.
- Todellisen istunnon D-Bus-tilakysely, `husk-status` ja `husk-live-smoke` toteutettiin.
  Esikatselu ei kelpaa live-käynnistyksen hyväksynnäksi. C-silta ilmoittaa
  foreign-toplevel-/seat-yhteydestä; stdin-puskurointi ei piilota seuraavaa komentoa pollilta.
- VM-istunto käyttää oletuksena pixman-renderöintiä; käyttäjän WLR_RENDERER-valinta
  säilyy. Fyysiselle koneelle ei aseteta tätä VM-oletusta.
- Live-käyttäjän valmistelu järjestetään ennen SDDM:ää. Pakettiavainten alustus
  erotettiin graafisen käynnistyksen riippuvuusketjusta. Live-käyttäjä lukitsee rootin
  ja saa lokien lukuoikeuden. Salasanattoman live-istunnon automaattinen lukitus estettiin.
- Kernel, labwc/GTK/Wayland, microcode, Bluetooth, PipeWire-ALSA, ääniasetukset,
  UPower, power-profiles-daemon ja irrotettavien medioiden palvelut ilmoitetaan
  profiilissa. Näiden laitteistotoimivuutta ei ole testattu.
- Calamares on valinnainen rakennuslisä. Kaikki neljä työpöytävalintaa ja
  aiemmat asentajakorjaukset säilyvät lähteissä. Ensimmäinen live-ISO ei riipu Calamares-käännöksestä.
- Profiilitarkistus sekä viiden kierroksen tarkistusskripti ja read-only
  järjestelmäraportin kerääjä lisättiin. BUILD-, VM-, gaming- ja laiteraportit päivitettiin.
- Testitapauksia on nyt 90: jokaisella lopullisella kierroksella 82 läpäisi ja
  8 GUI-testiä ohitettiin. Lähde-/asetussyntaksin tarkistuksia on 90.

**ISOa ei ole rakennettu, Husk OS ei ole käynnistynyt VM:ssä eikä pelejä tai
fyysisiä laitteita ole hyväksymistestattu.** Tämä julkaisu on lähdekooditoimitus.
