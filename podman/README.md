# Local Home Assistant test environment

This environment runs the official Home Assistant image together with a small
NIU API simulator. It never contacts a real NIU account.

Every start copies `../custom_components/niu` from the current working tree into
the Home Assistant configuration volume. The preparation container changes only
the two NIU base URLs in that generated copy so they point to the mock server.
The integration source in the working tree is neither changed nor replaced, so
the environment always tests the code currently checked out in the repository.

## Requirements

- Podman with a running Podman machine on Windows or macOS
- a Compose provider such as `podman-compose`

Install `podman-compose` once for the current Python installation if no Compose
provider is available yet:

```console
python -m pip install podman-compose
```

## Start

From this directory, run:

```console
podman compose up --build
```

Open <http://localhost:8123> and complete Home Assistant's onboarding on the
first run. In the Home Assistant UI, open **Settings > Devices & services**, click
**Add Integration**, search for **NIU**, and select it. The mock accepts any NIU
username and password. It exposes two vehicles with distinct names, serial
numbers, and sensor values, including one dual-battery and one single-battery
payload. Use the vehicle selection offered by the checked-out integration version
to test that it consistently uses the chosen vehicle.

The Home Assistant configuration is kept in the `niu-ha-config` volume. Running
`podman compose down` stops the environment without deleting it. Run `podman
compose up --build` again after changing the integration source.

The mock API is available locally on <http://localhost:8080>. Keep its endpoints
and response fields in sync whenever the integration starts using additional NIU
data. Unknown paths return HTTP 404 so accidentally missing mock responses remain
visible.

## Optional baseline backup

A baseline archive is useful for restoring an already-onboarded local instance,
but it must not be committed: it contains authentication state, installation IDs,
logs, and database contents.

**Never export the volume while Home Assistant is running.** Home Assistant may
still have SQLite database and write-ahead-log files open, which can produce an
inconsistent baseline. The Compose configuration gives Home Assistant up to 60
seconds for a graceful shutdown. Wait until `podman compose down` has completed
before running the export command:

```console
podman compose down
podman volume export --output "/path/to/niu-ha-baseline.tar" niu-ha-config
```

Restore the archive into a newly created volume, leaving any existing test volume
untouched:

```console
podman volume create niu-ha-restored
podman volume import niu-ha-restored "/path/to/niu-ha-baseline.tar"
```

Select that volume before starting the environment. In PowerShell:

```powershell
$env:HA_CONFIG_VOLUME = "niu-ha-restored"
podman compose up --build
```

In a POSIX shell:

```sh
HA_CONFIG_VOLUME=niu-ha-restored podman compose up --build
```

Do not publish the archive or use real Home Assistant or NIU credentials in this
test environment.
