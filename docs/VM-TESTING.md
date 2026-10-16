# UEFI-virtuaalikoneen hyväksymistestit

System 1:n Live-käynnistys on **oikeasti testattu 16.10.2026** GitHubin
testikoneella QEMU TCG/OVMF:llä: UEFI-valikko, Linux, automaattinen live-istunto,
Labwc/Husk Desktop, Start/taskbar, Foot ja ACPI-sammutus läpäisivät rajatun
hyväksynnän. Aito näyttö- ja lokitodiste on
[System 1 -raportissa](../HuskOS-system-1-REPORT.md).

Alla on laajempi tarkistuslista jatkotestausta varten. Asennus, uudelleenkäynnistys,
ääni, hiiren klikkaukset, fyysiset laitteet ja VirtualBox ovat edelleen testaamatta.
Käytä erillistä VM-isäntää, johon QEMU/qemu-img/OVMF on asennettu.

## Uusi virtuaalilevy ja live-ISO

Projektikansion sisällä, korvaa ISO-polku rakentamisen oikealla tiedostonimellä:

```bash
python3 scripts/test-vm.py --check
python3 scripts/test-vm.py --iso out/huskos-OMA_PAIVAMAARA-x86_64.iso \
  --disk out/huskos-desktop-test.qcow2 --create-disk
```

Skripti luo uuden 64 GiB:n qcow2-virtuaalilevyn ja oman OVMF-vars-tiedoston.
Se ei hyväksy `/dev/sda`-/NVMe-polkuja, symlinkkejä, raw-levyä,
QEMU:n pilkulla lisättäviä optioita, qcow2:n taustalevyä tai ulkoista
datatiedostoa. Olemassa olevaa
virtuaalilevyä ei ylikirjoiteta `--create-disk`-valitsimella.

Jos firmware ei löydy automaattisesti, käytä saman OVMF-version pareja:
`--firmware-code /polku/OVMF_CODE.fd --firmware-vars /polku/OVMF_VARS.fd`.
KVM valitaan, jos `/dev/kvm` on käytettävissä; muuten käytetään TCG:tä.
TCG on hitaampi eikä sovi pelisuorituskyvyn vertailuun.

## Live-istunnon tarkistus

- [ ] UEFI-käynnistys päätyy SDDM:n kautta Husk Desktopiin ilman root-autologinia.
- [ ] `id` näyttää käyttäjäksi `live`; `pgrep -a labwc` ja `pgrep -af husk-desktop` löytyvät.
- [ ] Start aukeaa Super+Space; Steam ja Heroic löytyvät; haku toimii.
- [ ] Super+E avaa tiedostot, Super+I asetukset; kansiossa liikkuminen ja uuden kansion luonti toimivat.
- [ ] Ikkuna liikkuu, koko muuttuu, Super+Left/Right snap toimii, Alt+Tab vaihtaa ikkunaa.
- [ ] Alapalkin ikkunalista aktivoisi/pienentäisi/sulkisi oikean testi-ikkunan.
- [ ] `notify-send 'Testi' 'Ilmoituksen teksti'` näkyy ilmoituskeskuksessa (asenna libnotify testiin tarvittaessa).
- [ ] Gaming-/overlay-asetus tallentuu uudelleen avatessa. CPU/RAM ovat järkeviä; puuttuva GPU-mittari ilmoitetaan.
- [ ] Taustakuva ja korostusväri muuttuvat. Tarkista myös kello, verkko ja äänenvoimakkuus.
- [ ] `husk-game -- /usr/bin/true` palauttaa nollan. Testaa erikseen GameModen aktivointi `gamemoded -s`-komennolla pitkäkestoisen testin aikana.
- [ ] Näytön koko, useampi virtuaalinäyttö, lukitus ja lukituksesta paluu testataan erikseen.

## Live-istunnon koneellinen tilatarkistus

Avaa guestin terminaali (Foot Start-valikosta). Käytä samaa live-käyttäjää ja
D-Bus-istuntoa kuin työpöytä; älä aja tilakyselyä sudo-komentona.

```bash
husk-status
husk-live-smoke
python3 scripts/collect-system-report.py --output husk-guest-report.json
journalctl -b --no-pager
```

Kerääjä ajetaan guestissa projektikansiosta, jos lähdekoodi on siellä.
`husk-live-smoke` vaatii Waylandin, oikean Husk/live-identiteetin, mapatun
paneelin ja taustapinnan sekä native-sillan foreign-toplevel/seat-yhteyden.
Se ei hyväksy GTK-esikatselua käynnistyksen todisteeksi. Tarkista lisäksi
`keyring_ready: true`; tämä erillinen palvelu ei estä SDDM-käynnistystä.
Huskin live-käyttäjä kuuluu systemd-journal-ryhmään lokien lukemiseksi.

VM-istunnossa oletusrenderöijä on pixman. Se on ensimmäisen käynnistyksen
varmistamista varten, ei GPU-kiihdytyksen tai pelien suorituskyvyn todentamiseen.
Käyttäjän asettama WLR_RENDERER säilyy. GPU-kiihdytyksen testaus on erillinen vaihe.

Paneelin paikanvaihdon jälkeen tarkista Start, ikkunalista ja ilmoitushistorian
säilyminen. Muokkaa `~/.config/ownos/desktop.css`, kokeile sekä kelvollista että
virheellistä CSS:ää. Sulje ja avaa Control Center uudelleen tallennuksen tarkistamiseksi.

Live-istunnon salasana on tyhjä ja root lukittu. Automaattinen lukitus ja
Startin lukituspainike ovat pois live-käytössä, jotta tyhjä PAM-salasana ei estä paluuta.
Asennettu käyttäjä saa normaalin salasanallisen lukituksen, joka on testattava erikseen.

## Sammutus ja uudelleenkäynnistys

Tallenna työ guestissa, aja `systemctl reboot` ja vahvista, että Husk Desktop
käynnistyy uudelleen ISOlta. Aja lopuksi `systemctl poweroff` ja varmista,
että VM sammuu hallitusti. Isännän reset/power-off ei ole Huskin onnistunut
sammutus- tai reboot-testi. Näitä komentoja ei suoritettu kehityskontissa.

## VirtualBox (käsin, testaamaton)

1. Luo **uusi** VM nimellä Husk OS Test, tyyppi Linux / Arch Linux (64-bit)
   tai Other Linux (64-bit). Ohita unattended installation.
2. Anna esimerkiksi 4096 MiB RAM, 2–4 vCPU ja uusi dynaaminen 64 GiB VDI.
   Nämä ovat testiasetuksia, eivät mitattuja Husk-vaatimuksia.
3. Ota VM:n EFI käyttöön. Käytä Linux-guestin VMSVGA-grafiikkaa ja aluksi
   poista 3D acceleration käytöstä. Aseta esimerkiksi 128 MiB videomuistia.
4. Liitä rakennettu Husk ISO virtuaaliseen optical driveen. Käytä NAT-verkkokorttia
   ja haluttaessa VirtualBoxin virtuaalista äänikorttia.
5. Käynnistä VM, suorita sama live-, status-, syöttö-, verkko-, ääni- ja shutdown-lista.
   Tallenna VBox.log sekä guestin raportti ja ISO-SHA256.

Raw disk-, USB-levy- tai PCI-passthroughia ei tarvita eikä aseteta.
Guest Additions eivät sisälly ensimmäisen ISO:n omaan lisäysluetteloon;
automaattinen ikkunakoon muutos, jaetut kansiot ja 3D tarvitsevat erillisen tarkistuksen.
Projekti ei sisällä testattua VBoxManage-automaatiota.
QEMU-runnerin oletuslaitteistossa ei ole äänikorttia: testaa ääni VirtualBoxissa
virtuaaliäänikortilla tai myöhemmin erikseen valmistellussa QEMU-kokoonpanossa.
[Oraclen VirtualBox 7.2 -ohje](https://docs.oracle.com/en/virtualization/virtualbox/7.2/user/working-with-vms.html).

## Asennus neljällä valinnalla

Käytä **uutta erillistä qcow2-levyä jokaiselle** Husk/KDE/GNOME/Minimal-valinnalle.
Rakenna tätä varten sekä paketit että ISO `--with-installer`-valinnalla.
Calamaresin osiointivaiheessa hyväksytään vain VM:n oma tyhjä 64 GiB:n levy.
Verkkoyhteys on pakollinen. Aloita Mesa-ajurivalinnalla; virtuaalinen
VirtIO-näytönohjain ei ole NVIDIA-kortti.

- [ ] Asentaja näyttää molemmat valinnat: työpöytä ja grafiikka.
- [ ] Luo tavallinen käyttäjä ja salasana; autologin ei tule asennettuun järjestelmään.
- [ ] Asennus valmistuu ilman pacman-, avain-, initramfs- tai GRUB-virheitä.
- [ ] Sammuta VM, käynnistä sama levy ilman ISOa:

```bash
python3 scripts/test-vm.py --disk out/huskos-desktop-test.qcow2
```

- [ ] Husk/KDE käyttää SDDM:ää, GNOME GDM:ää ja Minimal tekstitilaa.
- [ ] Kirjautuminen toimii luodulla käyttäjällä; `live`-käyttäjää ei enää ole.
- [ ] `sudo passwd -S root` näyttää lukitun root-tilin.
- [ ] `pacman -Q ownos-core ownos-keyring` toimii; valitut työpöytäpaketit löytyvät.
- [ ] Live-setup-palvelu, live-polkit-sääntö ja SDDM-live-autologin puuttuvat.
- [ ] `/etc/mkinitcpio.d/linux.preset` käyttää default/fallback-kuvia; live-archiso-hook ei jää käyttöön.
- [ ] `sudo pacman -Syu` onnistuu säilyttäen allekirjoitustarkistukset.

## Tulosten tallennus

Kirjaa jokaisesta ajosta ISO:n SHA256, Archiso- ja Calamares-versio,
työpöytä-/ajurivalinta, QEMU-versio, RAM/vCPU, tulos ja lokipolku.
Calamares: avaa asentaja Start-valikosta tai `pkexec calamares -d` live-VM:ssä, `journalctl -b` ja
`~/.cache/calamares/session.log` (ajokäyttäjän mukaan). Älä julkaise lokiin
jääviä käyttäjätietoja tai salasanoja.

Tämä VM-ajo ei hyväksy fyysisten NVIDIA/AMD/Intel-korttien suorituskykyä,
peliohjaimia, akun virrankulutusta tai pelien FPS:ää. Niille tarvitaan
myöhemmin oikea testikone.
