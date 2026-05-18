#!/bin/bash -e

rsync -a ../00-files/ "${ROOTFS_DIR}/"
