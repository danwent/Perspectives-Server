#!/bin/bash

dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

$dir/stop_webserver.sh
sleep 1
$dir/start_webserver.sh

