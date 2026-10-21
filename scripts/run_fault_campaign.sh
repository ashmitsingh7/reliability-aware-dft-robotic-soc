#!/usr/bin/env bash
set -e; cd "$(dirname "$0")/.."; make -s fault-campaign analyze plots
