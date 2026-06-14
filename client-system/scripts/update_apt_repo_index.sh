#!/usr/bin/env bash
# Regenerate apt repository metadata under dists/ with web-relative pool paths.
#
# Must be run from a checkout of the KumpeApps apt repo (e.g. external-repo in CI).
# dpkg-scanpackages emits absolute Filename values when invoked with an absolute
# binary-dir, which breaks apt downloads (404 under debian.kumpeapps.com).
set -euo pipefail

REPO_ROOT="${1:-.}"
ARCHES=(armhf arm64 amd64)
SUITES=(stable stage dev)

if [[ ! -d "$REPO_ROOT" ]]; then
	echo "Repository root not found: $REPO_ROOT" >&2
	exit 1
fi

REPO_ROOT="$(cd "$REPO_ROOT" && pwd)"
cd "$REPO_ROOT"

if ! command -v dpkg-scanpackages >/dev/null 2>&1; then
	echo "dpkg-scanpackages is required (install dpkg-dev)." >&2
	exit 1
fi

updated=0
for suite in "${SUITES[@]}"; do
	pool_dir="pool/${suite}"
	[[ -d "$pool_dir" ]] || continue

	suite_dist="dists/${suite}"
	mkdir -p "$suite_dist"

	for arch in "${ARCHES[@]}"; do
		out_dir="${suite_dist}/main/binary-${arch}"
		mkdir -p "$out_dir"
		dpkg-scanpackages -a "$arch" -m "$pool_dir" /dev/null > "${out_dir}/Packages"
		gzip -9 -kf "${out_dir}/Packages"
	done

	if command -v apt-ftparchive >/dev/null 2>&1; then
		apt-ftparchive release "$suite_dist" > "${suite_dist}/Release"
	fi

	updated=1
done

if [[ "$updated" -eq 0 ]]; then
	echo "No pool/${SUITES[*]} directories found under $REPO_ROOT; nothing to index." >&2
	exit 1
fi

if [[ -n "${APT_REPO_GPG_KEY_ID:-}" && -n "${APT_REPO_GPG_PRIVATE_KEY:-}" ]]; then
	gpg_home="$(mktemp -d)"
	trap 'rm -rf "$gpg_home"' EXIT
	printf '%s\n' "$APT_REPO_GPG_PRIVATE_KEY" | gpg --batch --import --homedir "$gpg_home" >/dev/null 2>&1

	for suite in "${SUITES[@]}"; do
		release_file="dists/${suite}/Release"
		[[ -f "$release_file" ]] || continue
		gpg --batch --homedir "$gpg_home" --default-key "$APT_REPO_GPG_KEY_ID" \
			-abs -o "dists/${suite}/Release.gpg" "$release_file"
		gpg --batch --homedir "$gpg_home" --default-key "$APT_REPO_GPG_KEY_ID" \
			--clearsign -o "dists/${suite}/InRelease" "$release_file"
	done
fi

echo "Updated apt indexes under $REPO_ROOT/dists/"
