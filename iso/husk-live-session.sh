# Sourced by the normal Bash login shell. Keep tty2 as an independent rescue.
if [ -d /run/archiso ] && [ "$(id -un)" = live ] &&
   [ "$(tty 2>/dev/null)" = /dev/tty1 ]; then
    exec /usr/bin/husk-session
fi
