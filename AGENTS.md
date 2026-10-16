# Husk OS development and preservation

- GitHub `monsteri24/Husk-OS`, branch `main`, is the permanent source of truth.
  Inspect current remote history/content before changes. Preserve existing
  source, compatibility files and history. Do not restart from a blank project.
- Commit completed source/configuration/tests/documentation milestones and
  push through an authorized Git connection. Verify the remote ref/content;
  local commits and temporary Work files alone are not a backup.
- Before lengthy builds, save and verify current source remotely.
- ISO files belong in GitHub Releases, not Git history. After successful
  creation, immediately compute SHA-256, upload, verify remote size/digest and
  download integrity, and provide the direct URL before optional testing.
- Preserve System 1 permanently as a historical GitHub Release, including
  its ISO, checksums and existing assets. Do not modify or delete that release.
  System 2 belongs in a separate experimental release tagged `system-2`, with
  `HuskOS-system-2.iso` and its own checksums/evidence after verification.
  Never remove source/history or required compatibility data.
- The default live and installed system must remain usable offline and must
  not preinstall optional user applications. Keep essential desktop, drivers,
  libraries and maintenance/recovery tools. Optional apps are installed only
  at the user's request through authenticated package sources.
- Retain the planned native `.hpk` format; do not claim an implemented store
  or `.hpk` installer unless it has been implemented and tested.
- Never upload credentials/private signing keys/configuration. Use only
  authorized access; do not force-push, bypass security or modify real disks.
- Report build, upload and boot results separately, including failures/skips.
  Only a real ISO/VM run can prove boot acceptance. Never fabricate an ISO,
  test result or screenshot. If upload/access is blocked, state the exact
  limit and provide a real downloadable backup where supported.
- User-facing product names are Husk OS and Husk Desktop. Document Arch
  Linux/open-source foundations openly; keep stable internal ownos aliases.
