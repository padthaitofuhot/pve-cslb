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
import re
from os import environ
from re import compile

from loguru import logger
from yaml import safe_load

logger.disable("Config")

pluralize_re_match = compile(r"^(include|exclude)_(node|type|vmid)$")


class ConfigurationError(Exception):
    """Custom exception for invalid configuration"""


class Config:

    args: dict
    config_file: str
    dry_run: bool
    verbose: bool
    quiet: bool
    no_color: bool
    exclude_nodes: list
    exclude_vmids: list
    exclude_types: list
    percent_cpu: float
    percent_mem: float
    max_migrations: int
    proxmox_user: str
    proxmox_pass: str
    proxmox_node: str
    proxmox_port: int

    def __init__(self, args: dict):

        self.dry_run = False
        self.verbose = False
        self.quiet = False
        self.no_color = False
        self.exclude_nodes = []
        self.exclude_vmids = []
        self.exclude_types = []
        self.percent_cpu = 0.4
        self.percent_mem = 0.6
        self.max_migrations = 5
        self.proxmox_user = "root@pam"
        self.proxmox_pass = ""
        self.proxmox_node = "localhost"
        self.proxmox_port = 8006

        if args:
            self.args = args
            # First read from config file
            if "config_file" in args.keys() and args["config_file"]:
                logger.debug(f"CLI: Configured config_file = {args['config_file']}")
                try:
                    logger.debug(
                        f"Reading YAML configuration from {args['config_file']}"
                    )
                    with open(args["config_file"], "r") as stream:
                        config = safe_load(stream)
                        for k, v in config.items():
                            setattr(self, k, v)
                            logger.debug(
                                f"YML: Configured {k} = {'*****' if k == 'proxmox_pass' else v}"
                            )
                except FileNotFoundError:
                    raise ConfigurationError("Config file not found")

            # Second override from environment variables
            for var in [
                "PROXMOX_NODE",
                "PROXMOX_PORT",
                "PROXMOX_USER",
                "PROXMOX_PASS",
                "PERCENT_CPU",
                "PERCENT_MEM",
                "MAX_MIGRATIONS",
                "VERBOSE",
                "QUIET",
                "DRY_RUN",
                "NO_COLOR",
            ]:
                if environ.get(f"CSLB_{var}"):
                    setattr(self, var.lower(), environ.get(f"CSLB_{var}"))
                    logger.debug(
                        f"ENV: Configured {var.lower()} = {'*****' if var == 'PROXMOX_PASS' else environ.get(f'CSLB_{var}')} (from CSLB_{var})"
                    )

            # Then override with CLI args
            for k, v in args.items():
                if v is not None:
                    match k:
                        case "exclude_node":
                            self.exclude_nodes += v
                        case "exclude_vmid":
                            self.exclude_vmids += v
                        case "exclude_type":
                            self.exclude_types += v
                        case "include_node":
                            for x in self.exclude_nodes:
                                if x in v:
                                    self.exclude_nodes.remove(x)
                        case "include_vmid":
                            for x in self.exclude_vmids:
                                if x in v:
                                    self.exclude_vmids.remove(x)
                        case "include_type":
                            for x in self.exclude_types:
                                if x in v:
                                    self.exclude_types.remove(x)
                        case "config_file":
                            continue
                        case _:
                            setattr(self, k, v)

                    logger.debug(
                        f"CLI: Configured {k + 's' if re.match(pluralize_re_match, k) else k} = {'*****' if k == 'proxmox_pass' else v}"
                    )
        else:
            raise ConfigurationError("Cannot continue, not fully configured.")

        # Resolve proportions so they always sum to 1
        if self.percent_cpu + self.percent_mem > 1:
            if self.percent_cpu > self.percent_mem:
                if self.percent_cpu > 1:
                    self.percent_cpu = 1
                self.percent_mem = 1 - self.percent_cpu
            if self.percent_cpu < self.percent_mem:
                if self.percent_mem > 1:
                    self.percent_mem = 1
                self.percent_cpu = 1 - self.percent_mem
            if self.percent_cpu == self.percent_mem:
                self.percent_cpu = 0.5
                self.percent_mem = 0.5
        if self.percent_cpu + self.percent_mem < 1:
            if self.percent_cpu > self.percent_mem:
                self.percent_cpu = 1 - self.percent_mem
            if self.percent_mem > self.percent_cpu:
                self.percent_mem = 1 - self.percent_cpu
            if self.percent_cpu == self.percent_mem:
                self.percent_cpu = 0.5
                self.percent_mem = 0.5

    def __dict__(self) -> dict:
        return {
            "args": self.args,
            "config_file": self.config_file,
            "dry_run": self.dry_run,
            "verbose": self.verbose,
            "quiet": self.quiet,
            "exclude_nodes": self.exclude_nodes,
            "exclude_vmids": self.exclude_vmids,
            "exclude_types": self.exclude_types,
            "percent_cpu": self.percent_cpu,
            "percent_mem": self.percent_mem,
            "max_migrations": self.max_migrations,
            "proxmox_user": self.proxmox_user,
            "proxmox_pass": self.proxmox_pass,
            "proxmox_node": self.proxmox_node,
            "proxmox_port": self.proxmox_port,
        }
