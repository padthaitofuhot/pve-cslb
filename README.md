# pve-cslb

_A configurable Central Scheduler Load Balancer (CSLB) for ProxmoxVE (PVE)_

The default runner adheres to 12-Factor App principles and is equally configurable with the (optional) YAML configuration file, CLI arguments, and environment variables.

The current workload balancer takes inspiration from, and expands upon, ideas in [this oft-cited paper](https://research.ijcaonline.org/volume46/number6/pxc3879263.pdf) from 2012.

### Resources Balanced

| **Type** | **Resource** | **Status**      |
|----------|--------------|-----------------|
| Host     | CPU          | **Implemented** |
| Host     | Memory       | **Implemented** |
| Host     | Network      | _Researching_   |
| Host     | DiskIO       | _Researching_   |
| Workload | CPU          | **Implemented** |
| Workload | Memory       | **Implemented** |
| Workload | Network      | _Researching_   |
| Host     | DiskIO       | _Researching_   |

---

# Installation

## From Repo

1. Clone the repo
2. Run `bash scripts/setup-environment.sh`
3. Done.

---

# Using

## Requirements

1. A valid Proxmox API endpoint
2. Credentials with read and migrate permissions
3. An environment capable of running the script

## Configuration

The defaults are reasonable. Config file is optional. Command line arguments are optional unless you want to use a config file (to tell the script where to find it).

The default runner follows 12-factor conventions and is configurable from environment variables ("CSLB_" namespace; see below).

## CLI Runner

```
$ rye run pve-cslb ---help
usage: pve-cslb [-h] [-c FILE] [-v] [-q] [--no-color] [--dry-run] [--proxmox-scheme SCHEME]
                [--proxmox-node NODE] [--proxmox-port PORT] [--proxmox-user USER] [--proxmox-pass PASS]
                [--proxmox-no-verify-ssl] [--proxmox-ssh-key-file FILE] [--max-migrations NUM] [--tolerance %]
                [--percent-cpu %] [--percent-mem %] [--exclude-node NODE] [--exclude-vmid VMID]
                [--exclude-type TYPE] [--include-node NODE] [--include-vmid VMID] [--include-type TYPE]

pve-cslb 1.5.0 - A configurable central scheduling load balancer for Proxmox PVE

options:
  -h, --help            show this help message and exit
  -c FILE, --config-file FILE
                        YAML configuration file (default: /etc/pve-cslb.yml)
  -v, --verbose         Increase verbosity (default: false)
  -q, --quiet           Only output errors (default: false)
  --no-color            Disable ANSI color in output (default: false)
  --dry-run             Perform read-only analysis; no write actions (default: false)
  --proxmox-scheme SCHEME
                        Proxmox API connection method (https [default], ssh, local)
  --proxmox-node NODE   Proxmox node (default: localhost)
  --proxmox-port PORT   Proxmox port (default: 8006)
  --proxmox-user USER   Proxmox user (default: root@pam)
  --proxmox-pass PASS   Proxmox password (no default)
  --proxmox-no-verify-ssl
                        Do not verify TLS certificate of Proxmox HTTPS API (default: false)
  --proxmox-ssh-key-file FILE
                        Proxmox SSH key file (default: ~/.ssh/id_rsa)
  --max-migrations NUM  Max simultaneous migrations to start (default: 5)
  --tolerance %         Max workload disparity tolerance (default: 0.2)
  --percent-cpu %       Percent priority of CPU rule (p-cpu and p-mem must equal 1.0; default: 0.4)
  --percent-mem %       Percent priority of MEM rule (p-cpu and p-mem must equal 1.0; default: 0.6)
  --exclude-node NODE   Exclude a node (can be specified multiple times)
  --exclude-vmid VMID   Exclude a VMID (can be specified multiple times)
  --exclude-type TYPE   Exclude a workload type ('lxc' or 'qemu'; can be specified multiple times)
  --include-node NODE   Include a previously excluded node (can be specified multiple times)
  --include-vmid VMID   Include a previously excluded VMID (can be specified multiple times)
  --include-type TYPE   Include a previously excluded workload type (must be 'lxc' or 'qemu'; can be specified
                        multiple times)

Copyright (C) 2024-2025 Travis Wichert <travis@padthaitofuhot.com>
```

## Environment Variables

With the exception of `--verbose`, `--quiet`, and `--no-color`, every CLI argument may also be provided as an
environment variable under the `CSLB_` namespace.

In the case of lists created by providing the same parameter multiple times with different arguments (for example,
`--exclude-node nodeA --exclude-node nodeB --exclude-node nodeN`), the related environment variable should be a quoted,
space-delimited list (for example,
`CSLB_EXCLUDE_NODES=nodeA nodeB nodeN`)

| CLI Arg                 | ENV Var             |
|-------------------------|---------------------|
| --config-file           | CSLB_CONFIG_FILE    |
| --dry-run               | CSLB_DRY_RUN        |
| --proxmox-scheme        | CSLB_PROXMOX_SCHEME |
| --proxmox-node          | CSLB_PROXMOX_NODE   |
| --proxmox-port          | CSLB_PROXMOX_PORT   |
| --proxmox-user          | CSLB_PROXMOX_USER   |
| --proxmox-pass          | CSLB_PROXMOX_PASS   |
| --proxmox-no-verify-ssl | CSLB_NO_VERIFY_SSL  |
| --proxmox-ssh-key-file  | CSLB_SSH_KEY_FILE   |
| --max-migrations        | CSLB_MAX_MIGRATIONS |
| --tolerance             | CSLB_TOLERANCE      |
| --percent-cpu           | CSLB_PERCENT_CPU    |
| --percent-mem           | CSLB_PERCENT_MEM    |
| --exclude-node          | CSLB_EXCLUDE_NODES  |
| --exclude-vmid          | CSLB_EXCLUDE_VMIDS  |
| --exclude-type          | CSLB_EXCLUDE_TYPES  |
| --include-node          | CSLB_INCLUDE_NODES  |
| --include-vmid          | CSLB_INCLUDE_VMIDS  |
| --include-type          | CSLB_INCLUDE_TYPES  |

---

# Known Issues

- ~~pve-cslb tries to avoid moving the same workload multiple times, but an edge-case exists in which lightly loadeds
  clusters with few workloads per node may see more migrations than strictly necessary. Adding more workloads to the
  cluster will generally cease this behavior.~~

---

# Dependencies

| Module    | Purpose            | Linky                                  |
|-----------|--------------------|----------------------------------------|
| proxmoxer | Proxmox API        | https://github.com/proxmoxer/proxmoxer |
| requests  | API backend        | https://github.com/psf/requests        |
| paramiko  | API backend        | https://github.com/paramiko/paramiko   |
| loguru    | Pretty logging     | https://github.com/Delgan/loguru       |
| pyyaml    | YAML configuration | https://github.com/yaml/pyyaml         |

---

# Development

Add the development modules if you like:

```shell
$ rye sync  # <-- without '--no-dev'!
```

---

# Contributors

| [![padthaitofuhot](https://github.com/padthaitofuhot.png?size=100)](https://github.com/padthaitofuhot) |
|--------------------------------------------------------------------------------------------------------|
| [padthaitofuhot](https://github.com/padthaitofuhot)                                                    |
