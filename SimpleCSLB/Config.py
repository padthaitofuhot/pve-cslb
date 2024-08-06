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
from os import environ

from loguru import logger
from yaml import safe_load

logger.disable("Config")


class ConfigurationError(Exception):
    """Custom exception for invalid configuration"""


class Config:

    args: dict
    config_file: str
    dry_run: bool
    verbose: bool
    exclude_nodes: list
    exclude_vmids: list
    exclude_types: list
    percent_cpu: float
    percent_mem: float
    proxmox_user: str
    proxmox_pass: str
    proxmox_node: str
    proxmox_port: int

    def __init__(self, args: dict):

        self.proxmox_user = "root@pam"
        self.proxmox_pass = ""
        self.proxmox_node = "localhost"
        self.proxmox_port = 8006
        self.exclude_nodes = []
        self.exclude_vmids = []
        self.exclude_types = []
        self.percent_cpu = 0.4
        self.percent_mem = 0.6
        self.max_migrations = 5
        self.dry_run = False
        self.verbose = False
        self.quiet = False

        if args:
            self.args = args
            # First read from config file
            if "config_file" in args.keys() and args["config_file"]:
                try:
                    logger.debug(f"Reading configuration from {args['config_file']}")
                    with open(args["config_file"], "r") as stream:
                        config = safe_load(stream)
                        for k, v in config.items():
                            setattr(self, k, v)
                            logger.debug(f"FILE: Configured {k}")
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
            ]:
                if environ.get(f"CSLB_{var}"):
                    setattr(self, var.lower(), environ.get(f"CSLB_{var}"))
                    logger.debug(f"ENV: Configured {var.lower()} (from CSLB_{var})")

            # Then override with CLI args
            for k, v in args.items():
                if v is not None:
                    match k:
                        case "exclude_node":
                            self.exclude_nodes += v
                            logger.debug(f"ARGS: Excluding nodes: {', '.join(v)}")
                        case "exclude_vmid":
                            self.exclude_vmids += v
                            logger.debug(f"ARGS: Excluding VMIDs: {', '.join(v)}")
                        case "exclude_type":
                            self.exclude_types += v
                            logger.debug(f"ARGS: Excluding types: {', '.join(v)}")
                        case "include_node":
                            for x in self.exclude_nodes:
                                if x in v:
                                    self.exclude_nodes.remove(x)
                                    logger.debug(
                                        f"ARGS: Including nodes: {', '.join(v)}"
                                    )
                        case "include_vmid":
                            for x in self.exclude_vmids:
                                if x in v:
                                    self.exclude_vmids.remove(x)
                                    logger.debug(
                                        f"ARGS: Including VMIDs: {', '.join(v)}"
                                    )
                        case "include_type":
                            for x in self.exclude_types:
                                if x in v:
                                    self.exclude_types.remove(x)
                                    logger.debug(
                                        f"ARGS: Including types: {', '.join(v)}"
                                    )
                        case _:
                            setattr(self, k, v)
                            logger.debug(f"ARGS: Configured {k} = {v}")
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
            "exclude_nodes": self.exclude_nodes,
            "exclude_vmids": self.exclude_vmids,
            "exclude_types": self.exclude_types,
            "p_cpu": self.percent_cpu,
            "p_mem": self.percent_mem,
            "proxmox_user": self.proxmox_user,
            "proxmox_pass": self.proxmox_pass,
            "proxmox_node": self.proxmox_node,
            "proxmox_port": self.proxmox_port,
        }
