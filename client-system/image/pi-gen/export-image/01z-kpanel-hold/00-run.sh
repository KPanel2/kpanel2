#!/bin/bash -e

# export-image runs apt dist-upgrade against all configured repos. Hold the
# image-baked kpanel-client so a newer (or broken-indexed) KumpeApps entry
# cannot replace it during the final image export pass.
on_chroot <<'EOF'
if dpkg-query -W -f='${Status}' kpanel-client 2>/dev/null | grep -q "install ok installed"; then
	apt-mark hold kpanel-client
fi
EOF
