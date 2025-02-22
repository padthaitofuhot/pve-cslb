#!/usr/Scripts/env python3
"""Basic runner for pve-cslb"""

# pve-cslb - a central scheduling load balancer for Proxmox PVE
# Copyright (C) 2024-2025  Travis Wichert
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
from os import environ
from re import compile
from re import match as re_match
from sys import exit, stdout

from loguru import logger
from yaml import safe_load

from pve_cslb.config import Config, ConfigurationError
from pve_cslb.workload_balancer import WorkloadBalancer

__version__ = "1.4.0"
__title__ = "pve-cslb"
__copyright__ = """
Copyright (C) 2024-2025 Travis Wichert <travis@padthaitofuhot.com>
"""
__description__ = """
A workload balancing engine for ProxmoxPVE.  Identifies nodes with imbalanced loads and migrates workloads around to even things out.
"""

re_pluralize = compile(r"^(include|exclude)_(node|type|vmid)$")
re_include = compile(r"^include_.*$")
re_exclude = compile(r"^exclude.*$")


@logger.catch(level="ERROR")
def main():
    #
    # Configuration
    #

    parser = ArgumentParser(
        prog="pve-cslb",
        description=f"{__title__} {__version__} - {__description__}",
        epilog=__copyright__,
    )
    parser.add_argument(
        "-c",
        "--config-file",
        metavar="FILE",
        help="YAML configuration file (default: /etc/pve-cslb.yml)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Increase verbosity (default: false)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Only output errors (default: false)",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color in output (default: false)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform read-only analysis; no write actions (default: false)",
    )
    parser.add_argument(
        "--proxmox-scheme",
        metavar="SCHEME",
        type=str,
        help="Proxmox API connection method (https [default], ssh, local)",
    )
    parser.add_argument(
        "--proxmox-node",
        metavar="NODE",
        type=str,
        help="Proxmox node (default: localhost)",
    )
    parser.add_argument(
        "--proxmox-port",
        metavar="PORT",
        type=int,
        help="Proxmox port (default: 8006)",
    )
    parser.add_argument(
        "--proxmox-user",
        metavar="USER",
        type=str,
        help="Proxmox user (default: root@pam)",
    )
    parser.add_argument(
        "--proxmox-pass",
        metavar="PASS",
        type=str,
        help="Proxmox password (no default)",
    )
    parser.add_argument(
        "--max-migrations",
        metavar="NUM",
        type=int,
        help="Max simultaneous migrations to start (default: 5)",
    )
    parser.add_argument(
        "--tolerance",
        metavar="%",
        type=float,
        help="Max workload disparity tolerance (default: 0.2)",
    )
    parser.add_argument(
        "--percent-cpu",
        metavar="%",
        type=float,
        help="Percent priority of CPU rule (p-cpu and p-mem must equal 1.0; default: 0.4)",
    )
    parser.add_argument(
        "--percent-mem",
        metavar="%",
        type=float,
        help="Percent priority of MEM rule (p-cpu and p-mem must equal 1.0; default: 0.6)",
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
    args = vars(parser.parse_args())

    log_level = "INFO"
    if args["verbose"]:
        log_level = "DEBUG"
    if args["quiet"]:
        log_level = "ERROR"

    logging_config = {
        "handlers": [
            {
                "sink": stdout,
                "colorize": not args["no_color"],
                "format": "<green>{time:YYYY-MM-DD HH:mm:ss}</green> <level>{message}</level>",
                "level": log_level,
                # "enqueue": True,
            }
        ],
    }
    logger.configure(**logging_config)
    logger.enable("WorkloadBalancer")
    logger.enable("Config")

    if not args:
        raise ConfigurationError("Cannot continue, not fully configured.")

    lb_config = Config()
    setattr(lb_config, "config_file", args["config_file"])

    # First read from config file
    if "config_file" in args.keys() and args["config_file"]:
        logger.debug(f"CLI: Configured config_file = {args['config_file']}")
        try:
            with open(args["config_file"], "r") as stream:
                config = safe_load(stream)
                for k, v in config.items():
                    setattr(lb_config, k, v)
                    logger.debug(
                        f"YML: Configured {k} = {'*****' if k == 'proxmox_pass' else v}"
                    )
        except FileNotFoundError:
            raise ConfigurationError("Config file not found")

    # Next configure from CLI and ENV
    # CLI-only vars
    for var in [
        "verbose",
        "quiet",
        "no_color",
    ]:
        if var in args.keys():
            if args[var] is not None:
                setattr(lb_config, var, args[var])
                logger.debug(f"CLI: Configured {var} = {args[var]}")

    # Scalars
    for var in [
        "proxmox_node",
        "proxmox_scheme",
        "proxmox_port",
        "proxmox_user",
        "proxmox_pass",
        "tolerance",
        "percent_cpu",
        "percent_mem",
        "max_migrations",
        "dry_run",
    ]:
        if environ.get(f"CSLB_{var.upper()}"):
            setattr(lb_config, var, environ.get(f"CSLB_{var.upper()}"))
            logger.debug(
                f"ENV: Configured {var} = {'*****' if var == 'proxmox_pass' else environ.get(f'CSLB_{var.upper()}')} (from CSLB_{var.upper()})"
            )

        if var in args.keys():
            if args[var] is not None:
                setattr(lb_config, var, args[var])
                logger.debug(
                    f"CLI: Configured {var + 's' if re_match(re_pluralize, var) else var} = {'*****' if var == 'proxmox_pass' else args[var]}"
                )

    # Lists
    for var in [
        "exclude_node",
        "exclude_vmid",
        "exclude_type",
        "include_node",
        "include_vmid",
        "include_type",
    ]:
        var_s = var + "s"
        ex_var_s = var_s.replace("include", "exclude")

        if environ.get(f"CSLB_{var_s.upper()}"):
            if re_match(re_exclude, var):
                env_list = environ.get(f"CSLB_{var_s.upper()}").split(" ")
                cnf_list = getattr(lb_config, var_s)
                new_list = cnf_list + env_list
                setattr(lb_config, var_s, new_list)
                logger.debug(
                    f"ENV: Configured {var_s}: added {env_list} (from CSLB_{var_s.upper()})"
                )
                del env_list
                del cnf_list
                del new_list

            if re_match(re_include, var):
                env_list = environ.get(f"CSLB_{var_s.upper()}").split(" ")
                cnf_list = getattr(lb_config, ex_var_s)
                new_list = []
                for item in cnf_list:
                    if item in env_list:
                        continue
                    new_list.append(item)
                setattr(lb_config, ex_var_s, new_list)
                logger.debug(
                    f"ENV: Configured {ex_var_s}: removed {env_list} (from CSLB_{var_s.upper()})"
                )
                del env_list
                del cnf_list
                del new_list

        if var in args.keys() and args[var] is not None:
            if re_match(re_exclude, var):
                cnf_list = getattr(lb_config, var_s)
                for item in args[var]:
                    if item not in cnf_list:
                        new_list = cnf_list + [item]
                        setattr(lb_config, var_s, new_list)
                        logger.debug(f"CLI: Configured {var_s}: added {item}")
                del cnf_list

            if re_match(re_include, var):
                cnf_list = getattr(lb_config, ex_var_s)
                for item in args[var]:
                    if item in cnf_list:
                        cnf_list.remove(item)
                        setattr(lb_config, ex_var_s, cnf_list)
                        logger.debug(f"CLI: Configured {ex_var_s}: removed {item}")
                del cnf_list

    #
    # Main
    #

    my_cslb = WorkloadBalancer(lb_config)
    migration_candidates = my_cslb.get_migration_candidates()

    if len(migration_candidates) < 1:
        logger.success("No migration candidate(s) found.")
        exit(0)

    if not lb_config.dry_run:
        migrations = list()
        for migration_candidate in migration_candidates:
            success, jobspec = my_cslb.do_migration(migration_candidate)
            migrations.append(jobspec)
        logger.success("Migration job(s) submitted")

        exit(0)
    else:
        logger.success("Dry run; no migration(s) started.")
        exit(0)


if __name__ == "__main__":
    exit(main())
