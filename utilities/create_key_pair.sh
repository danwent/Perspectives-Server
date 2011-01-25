#!/bin/bash

exec >&2

if [ "$#" != 2 ] ; then
  echo "ERROR: usage: <priv-key-out> <pub-key-out>" >&2
  exit 1
fi

len=1369

echo >&2
echo "INFO: initializing key pair" >&2

echo "INFO: generating private key" >&2
openssl genrsa -out "$1" "$len"

echo "INFO: generating public key" >&2
openssl rsa -in "$1" -out "$2" -outform PEM -pubout

exit 0
