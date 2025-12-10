#!/bin/bash
#RCON_PASSWORD=$(cat "$HOME/minecraft-server/mc/rcon")
#mcrcon -H localhost -P 25575 -p "$RCON_PASSWORD" "$@"
RCON_PASSWORD=$(cat "rcon")
cd ../tools/mcrcon/
./mcrcon -H localhost -P 25575 -p "$RCON_PASSWORD" "$@"
