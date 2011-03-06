#!/bin/bash

#   This file is part of the Perspectives Notary Server
#
#   Copyright (C) 2011 Dan Wendlandt
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, version 3 of the License.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.


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
chmod 600 $1 

echo "INFO: generating public key" >&2
openssl rsa -in "$1" -out "$2" -outform PEM -pubout

exit 0
