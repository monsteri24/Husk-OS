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
- Do not overwrite a known good asset before its replacement is verified.
  Supersede/archive obsolete download assets after verifying a new release;
  never remove source/history or required compatibility data.
- Never upload credentials/private signing keys/configuration. Use only
  authorized access; do not force-push, bypass security or modify real disks.
- Report build, upload and boot results separately, including failures/skips.
  Only a real ISO/VM run can prove boot acceptance. Never fabricate an ISO,
  test result or screenshot. If upload/access is blocked, state the exact
  limit and provide a real downloadable backup where supported.
- User-facing product names are Husk OS and Husk Desktop. Document Arch
  Linux/open-source foundations openly; keep stable internal ownos aliases.
