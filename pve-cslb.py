#!/usr/bin/env python3

#  Copyright (C) 2024 Travis Wichert
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

from argparse import ArgumentParser
from sys import exit, stdout

from loguru import logger

from SimpleCSLB.Config import Config, ConfigurationError
from SimpleCSLB.WorkloadBalancer import WorkloadBalancer

TITLE = "pve-cslb"
COPYRIGHT = """
Copyright (C) 2024 Travis Wichert <padthaitofuhot@users.noreply.github.com>
"""
VERSION = "0.1.0-alpha"
DESCRIPTION = """
A workload balancing engine for ProxmoxPVE.  Identifies nodes with imbalanced loads and migrates workloads around to even things out.
"""


def main():
    parser = ArgumentParser(
        prog="pve-cslb",
        description=f"{TITLE} {VERSION} - {DESCRIPTION}",
        epilog=COPYRIGHT,
    )
    parser.add_argument(
        "-c",
        "--config-file",
        metavar="FILE",
        default=None,
        help=f"YAML configuration file (default: %(default)s)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Increase verbosity (default: %(default)s)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        default=False,
        help="Only output errors (default: %(default)s)",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        default=False,
        help="Perform read-only analysis; no write actions. (default: %(default)s)",
    )
    parser.add_argument(
        "--proxmox-host",
        metavar="HOST",
        help="Proxmox host",
    )
    parser.add_argument(
        "--proxmox-port",
        metavar="PORT",
        type=int,
        default=8006,
        help="Proxmox port (default: %(default)s)",
    )
    parser.add_argument(
        "--proxmox-user",
        metavar="USER",
        default="root@pam",
        help="Proxmox user (default: %(default)s)",
    )
    parser.add_argument(
        "--proxmox-pass",
        metavar="PASS",
        help="Proxmox password",
    )
    parser.add_argument(
        "-m",
        "--max-migrations",
        metavar="NUM",
        type=int,
        default=5,
        help="Max simultaneous migrations to start (default: %(default)s)",
    )
    parser.add_argument(
        "--percent-cpu",
        metavar="%",
        type=float,
        default=0.3,
        help="Percent priority of CPU rule (p-cpu and p-mem must equal 1.0; default: %(default)s)",
    )
    parser.add_argument(
        "--percent-mem",
        metavar="%",
        type=float,
        default=0.7,
        help="Percent priority of MEM rule (p-cpu and p-mem must equal 1.0; default: %(default)s)",
    )
    parser.add_argument(
        "--exclude-node",
        action="append",
        help="Exclude a node (can be specified multiple times)",
    )
    parser.add_argument(
        "--exclude-vmid",
        action="append",
        help="Exclude a VMID (can be specified multiple times)",
    )
    parser.add_argument(
        "--exclude-type",
        action="append",
        help="Exclude a workload type ('lxc' or 'qemu'; can be specified multiple times)",
    )
    parser.add_argument(
        "--include-node",
        action="append",
        help="Include a previously excluded node (can be specified multiple times)",
    )
    parser.add_argument(
        "--include-vmid",
        action="append",
        help="Include a previously excluded VMID (can be specified multiple times)",
    )
    parser.add_argument(
        "--include-type",
        action="append",
        help="Include a previously excluded workload type (must be 'lxc' or 'qemu'; can be specified multiple times)",
    )
    args = parser.parse_args()

    log_level = "INFO"
    if args.verbose:
        log_level = "DEBUG"
    if args.quiet:
        log_level = "ERROR"
    config = {
        "handlers": [
            {
                "sink": stdout,
                "colorize": True,
                "format": "<green>{time:YYYY-MM-DD HH:mm:ss}</green> <level>{message}</level>",
                "level": log_level,
            }
        ],
    }
    logger.configure(**config)
    logger.enable("WorkloadBalancer")
    logger.enable("Config")

    try:
        lb_config = Config(vars(args))
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        exit(1)

    my_simple_cslb = WorkloadBalancer(lb_config)
    migration_candidates = my_simple_cslb.get_migration_candidates()
    if len(migration_candidates) < 1:
        logger.info("No migration candidates found.")
        exit(0)
    if not args.dry_run:
        for migration_candidate in migration_candidates:
            success, jobspec = my_simple_cslb.do_migration(migration_candidate)
    else:
        logger.info("Dry run; no migrations started.")


if __name__ == "__main__":
    exit(main())
