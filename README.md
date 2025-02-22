# pve-cslb

A Central Scheduler Load Balancer (CSLB) for ProxmoxVE (PVE)

Identifies nodes with resource surpluses and deficits (presently only CPU and memory) and migrates workloads around to
balance things out. Takes inspiration from, and expands upon, ideas
in [this oft-cited paper](https://research.ijcaonline.org/volume46/number6/pxc3879263.pdf) from 2012.

---

# Installation

## From Repo

1. Clone the repo
2. Run `bash scripts/setup-dev-environment.sh`
3. Done.

---

# Using

## Requirements

1. A valid Proxmox API endpoint
2. Credentials with read and migrate permissions
3. An environment capable of running the script

## Configuration

The defaults are reasonable. Config file is optional. Command line arguments are optional unless you want to use a
config file (to tell the script where to find it).

The default runner follows 12-factor conventions and is configurable from environment variables ("CSLB_" namespace; see
below).

## CLI Runner

```
$ rye run pve-cslb --exclude-node firefly -v --help
usage: pve-cslb [-h] [-c FILE] [-v] [-q] [-d] [--proxmox-node NODE] [--proxmox-port PORT]
                [--proxmox-user USER] [--proxmox-pass PASS] [-m NUM] [--percent-cpu %]
                [--percent-mem %] [--exclude-node EXCLUDE_NODE]
                [--exclude-vmid EXCLUDE_VMID] [--exclude-type EXCLUDE_TYPE]
                [--include-node INCLUDE_NODE] [--include-vmid INCLUDE_VMID]
                [--include-type INCLUDE_TYPE]

options:
  -h, --help            show this help message and exit
  -c FILE, --config-file FILE
                        YAML configuration file (default: none)
  -v, --verbose         Increase verbosity (default: false)
  -q, --quiet           Only output errors (default: false)
  -d, --dry-run         Perform read-only analysis; no write actions (default: false)
      --no-color        Disable ANSI color in output (default: false)
  --proxmox-backend BACKEND
                        Proxmox API connection method (default: https)
  --proxmox-node NODE   Proxmox node (default: localhost)
  --proxmox-port PORT   Proxmox port (default: 8006)
  --proxmox-user USER   Proxmox user (default: root@pam)
  --proxmox-pass PASS   Proxmox password (no default)
  -m NUM, --max-migrations NUM
                        Max simultaneous migrations to start (default: 5)
  --tolerance %         Max load disparity tolerance (default: 0.2)
  --percent-cpu %       Percent priority of CPU rule (p-cpu and p-mem must equal 1.0;
                        default: 0.4)
  --percent-mem %       Percent priority of MEM rule (p-cpu and p-mem must equal 1.0;
                        default: 0.6)
  --exclude-node EXCLUDE_NODE
                        Exclude a node (can be specified multiple times)
  --exclude-vmid EXCLUDE_VMID
                        Exclude a VMID (can be specified multiple times)
  --exclude-type EXCLUDE_TYPE
                        Exclude a workload type ('lxc' or 'qemu'; can be specified multiple
                        times)
  --include-node INCLUDE_NODE
                        Include a previously excluded node (can be specified multiple times)
  --include-vmid INCLUDE_VMID
                        Include a previously excluded VMID (can be specified multiple times)
  --include-type INCLUDE_TYPE
                        Include a previously excluded workload type (must be 'lxc' or
                        'qemu'; can be specified multiple times)

Copyright (C) 2024 Travis Wichert <padthaitofuhot@users.noreply.github.com>
```

## Available environment variables in the default runner

| Env Vars             |
|----------------------|
| CSLB_PROXMOX_BACKEND |
| CSLB_PROXMOX_NODE    |
| CSLB_PROXMOX_PORT    |
| CSLB_PROXMOX_USER    |
| CSLB_PROXMOX_PASS    |
| CSLB_TOLERANCE       |
| CSLB_PERCENT_CPU     |
| CLSB_PERCENT_MEM     |
| CLSB_MAX_MIGRATIONS  |
| CSLB_DRY_RUN         |

---

# Known Issues

- ~~pve-cslb tries to avoid moving the same workload multiple times, but an edge-case exists in which lightly loaded
  clusters with few workloads per node may see more migrations than strictly necessary. Adding more workloads to the
  cluster will generally cease this behavior.~~

---

# Dependencies

| Module    | Purpose            | Linky                                  |
|-----------|--------------------|----------------------------------------|
| proxmoxer | Proxmox API        | https://github.com/proxmoxer/proxmoxer
| requests  | API backend        | https://github.com/psf/requests        |
| paramiko  | API backend        | https://github.com/paramiko/paramiko   |
| loguru    | Pretty logging     | https://github.com/Delgan/loguru       |
| pyyaml    | YAML configuration | https://github.com/yaml/pyyaml         |

---

# Contributors

| [![padthaitofuhot](https://github.com/padthaitofuhot.png?size=100)](https://github.com/padthaitofuhot) |
|--------------------------------------------------------------------------------------------------------|
| [padthaitofuhot](https://github.com/padthaitofuhot)                                                    |
