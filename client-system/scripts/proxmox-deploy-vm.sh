#!/usr/bin/env bash
set -euo pipefail

require_command() {
	local command_name="$1"
	if ! command -v "$command_name" >/dev/null 2>&1; then
		echo "Missing required command: $command_name" >&2
		exit 1
	fi
}

prompt_with_default() {
	local prompt_text="$1"
	local default_value="$2"
	local value
	read -r -p "$prompt_text [$default_value]: " value
	if [[ -z "$value" ]]; then
		printf '%s\n' "$default_value"
	else
		printf '%s\n' "$value"
	fi
}

prompt_required() {
	local prompt_text="$1"
	local value=""
	while [[ -z "$value" ]]; do
		read -r -p "$prompt_text: " value
		done
	printf '%s\n' "$value"
}

prompt_yes_no() {
	local prompt_text="$1"
	local default_answer="$2"
	local answer
	while true; do
		read -r -p "$prompt_text [$default_answer]: " answer
		answer="${answer:-$default_answer}"
		case "${answer,,}" in
			y|yes)
				return 0
				;;
				n|no)
				return 1
				;;
			*)
				echo "Please answer yes or no."
				;;
		esac
	done
}

prompt_display_profile() {
	local value
	while true; do
		read -r -p "Display profile (default/std/qxl/virtio/vmware) [default]: " value
		value="${value:-default}"
		case "${value,,}" in
			default|std|qxl|virtio|vmware)
				printf '%s\n' "${value,,}"
				return 0
				;;
			*)
				echo "Unsupported display profile: $value"
				;;
		esac
	done
}

find_unused_imported_disk() {
	local vmid="$1"
	qm config "$vmid" | awk -F': ' '/^unused[0-9]+:/ { print $2 }' | tail -n 1
}

attach_boot_disk() {
	local vmid="$1"
	local disk_ref="$2"
	qm set "$vmid" --scsi0 "$disk_ref"
	qm set "$vmid" --boot order=scsi0
}

detach_current_scsi0() {
	local vmid="$1"
	local current_disk
	current_disk="$(qm config "$vmid" | awk -F': ' '/^scsi0:/ { print $2 }')"
	if [[ -n "$current_disk" ]]; then
		qm set "$vmid" --delete scsi0 >/dev/null
		printf '%s\n' "$current_disk"
	fi
}

apply_display_profile() {
	local vmid="$1"
	local profile="$2"
	case "$profile" in
		default)
			qm set "$vmid" --delete vga >/dev/null 2>&1 || true
			;;
		*)
			qm set "$vmid" --vga "$profile" >/dev/null
			;;
	esac
}

main() {
	require_command qm
	require_command pvesm

	echo "Active Proxmox storages:"
	pvesm status
	echo

	local mode
	mode="$(prompt_with_default "Deployment mode (fresh/replace)" "fresh")"
	mode="${mode,,}"
	if [[ "$mode" != "fresh" && "$mode" != "replace" ]]; then
		echo "Unsupported mode: $mode" >&2
		exit 1
	fi

	local vmid
	vmid="$(prompt_required "VM ID")"

	local qcow_path
	qcow_path="$(prompt_required "Absolute path to qcow2 image")"
	if [[ ! -f "$qcow_path" ]]; then
		echo "qcow2 image not found: $qcow_path" >&2
		exit 1
	fi

	local storage
	storage="$(prompt_required "Target Proxmox storage ID")"

	local vm_name bridge memory cores sockets display_profile
	local old_disk=""

	if qm status "$vmid" >/dev/null 2>&1; then
		if [[ "$mode" == "fresh" ]]; then
			echo "VM $vmid already exists. Use replace mode instead." >&2
			exit 1
		fi
		vm_name="$(qm config "$vmid" | awk -F': ' '/^name:/ { print $2 }')"
		bridge="$(qm config "$vmid" | sed -n 's/^net0: .*bridge=\([^,]*\).*/\1/p')"
		memory="$(qm config "$vmid" | awk -F': ' '/^memory:/ { print $2 }')"
		cores="$(qm config "$vmid" | awk -F': ' '/^cores:/ { print $2 }')"
		sockets="$(qm config "$vmid" | awk -F': ' '/^sockets:/ { print $2 }')"
	else
		if [[ "$mode" == "replace" ]]; then
			echo "VM $vmid does not exist. Use fresh mode instead." >&2
			exit 1
		fi
		vm_name="$(prompt_with_default "VM name" "kpanel-vm")"
		bridge="$(prompt_with_default "Bridge" "vmbr0")"
		memory="$(prompt_with_default "Memory (MB)" "4096")"
		cores="$(prompt_with_default "CPU cores" "2")"
		sockets="$(prompt_with_default "CPU sockets" "1")"
	fi

	display_profile="$(prompt_display_profile)"

	if [[ "$mode" == "fresh" ]]; then
		echo "Creating VM shell $vmid..."
		qm create "$vmid" \
			--name "$vm_name" \
			--memory "$memory" \
			--cores "$cores" \
			--sockets "$sockets" \
			--ostype l26 \
			--cpu host \
			--bios seabios \
			--scsihw virtio-scsi-pci \
			--serial0 socket \
			--net0 "virtio,bridge=$bridge"
	else
		echo "Preparing existing VM $vmid for disk replacement..."
		if qm status "$vmid" | grep -q 'status: running'; then
			qm shutdown "$vmid" --timeout 60 || qm stop "$vmid"
		fi
		old_disk="$(detach_current_scsi0 "$vmid" || true)"
	fi

	echo "Importing qcow2 into $storage..."
	qm importdisk "$vmid" "$qcow_path" "$storage"

	local new_disk
	new_disk="$(find_unused_imported_disk "$vmid")"
	if [[ -z "$new_disk" ]]; then
		echo "Unable to find imported disk under qm config $vmid" >&2
		exit 1
	fi

	echo "Attaching imported disk as scsi0: $new_disk"
	attach_boot_disk "$vmid" "$new_disk"
	qm set "$vmid" --agent enabled=1 >/dev/null
	qm set "$vmid" --serial0 socket >/dev/null
	qm set "$vmid" --tablet 1 >/dev/null
	apply_display_profile "$vmid" "$display_profile"

	if [[ -n "$old_disk" ]]; then
		echo "Previous boot disk detached as: $old_disk"
		if prompt_yes_no "Delete detached old disk from storage?" "no"; then
			qm disk unlink "$vmid" --idlist "$old_disk"
		fi
	fi

	echo
	qm config "$vmid"
	echo
	if prompt_yes_no "Start VM now?" "yes"; then
		qm start "$vmid"
	fi

	echo "Done."
}

main "$@"