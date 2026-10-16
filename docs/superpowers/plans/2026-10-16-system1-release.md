# System 1 release implementation plan

Goal: build HuskOS-system-1.iso from the preserved desktop and immediately
publish it in monsteri24/Husk-OS, Release/tag system-1, before boot testing.
The user's four-phase request is the specification and authorizes execution.

- [ ] Source: restore seven original command symlinks; restore first-boot-only
  tty1 login/PAM -> husk-session with tty2 rescue; preserve SDDM on gaming builds.
  Test profile generation/validation and source links; run the full unit suite.
- [ ] Automation: run signed package and Archiso builds in an official Arch
  container on a GitHub-hosted Linux runner. Keep private signing keys outside
  source/rootfs. Verify source has been committed before requesting the build.
- [ ] Publication: verify ISO9660, EFI boot artifacts, kernel/initramfs/SquashFS,
  rename the complete image, compute SHA-256, upload to system-1 immediately.
  Verify remote asset size/digest and download, retain workflow artifacts if
  publication fails. No fake ISO and no success claim without remote evidence.
- [ ] Boot: after upload, use QEMU/OVMF if available; distinguish build,
  publication and actual desktop boot results.

Review focus: correct Git symlink blobs; login/PAM runtime directory; package
signature verification; release permission failures; no loss of old assets
until the replacement upload is verified. Never overwrite unrelated work.

Ruling: execute the existing, authorized release plan without another design
approval cycle; no product design or optional feature changes are in scope.
