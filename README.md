# pve-cslb
A Central Scheduler Load Balancer (CSLB) for PromoxVE (PVE)

Identifies nodes with resource surpluses and deficits (presently only CPU and memory) and migrates workloads around to balance things out.  Takes inspiration from, and expands upon, ideas in [this oft-cited paper](https://research.ijcaonline.org/volume46/number6/pxc3879263.pdf) from 2012.

# Installing

# Using
The defaults are reasonable.  Config file is optional.  Command line arguments are optional unless you want to use a config file.  Follows 12-factor conventions and configurable from environment variables ("CSLB_" namespace).

API endpoint and credentials with read and migrate permissions are required.

## CLI
```
$ ./pve-cslb.py --exclude-node firefly -v --help
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
  -d, --dry-run         Perform read-only analysis; no write actions. (default: false)
      --no-color        Disable ANSI color in output (default: false)
  --proxmox-node NODE   Proxmox node (default: localhost)
  --proxmox-port PORT   Proxmox port (default: 8006)
  --proxmox-user USER   Proxmox user (default: root@pam)
  --proxmox-pass PASS   Proxmox password (no default)
  -m NUM, --max-migrations NUM
                        Max simultaneous migrations to start (default: 5)
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

## Available Env Vars
| Env Vars            |
|---------------------|
| CSLB_PROXMOX_NODE   |
| CSLB_PROXMOX_PORT   |
| CSLB_PROXMOX_USER   |
| CSLB_PROXMOX_PASS   |
| CSLB_PERCENT_CPU    |
| CLSB_PERCENT_MEM    |
| CLSB_MAX_MIGRATIONS |
| CSLB_DRY_RUN        |

# Known Issues
pve-cslb tries to avoid moving the same workload multiple times, but an edge-case exists in which lightly loaded clusters with few workloads and many nodes may see more migrations than strictly necessary.  Adding more workloads to the cluster will generally cease this behavior.

# Contributors
 [![padthaitofuhot](https://github.com/padthaitofuhot.png?size=100)](https://github.com/padthaitofuhot)
 | ---------------------------------------------------------------------------------------- |
 [padthaitofuhot](https://github.com/padthaitofuhot)
