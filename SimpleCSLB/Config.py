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

from loguru import logger
from yaml import safe_load

logger.disable("Config")


class ConfigurationError(Exception):
    """Custom exception for invalid configuration"""


class Config:

    args = None
    config_file = None
    dry_run = False
    verbose = False
    exclude_nodes = []
    exclude_vmids = []
    exclude_types = []
    p_cpu = 0.5
    p_mem = 0.5
    proxmox_user = None
    proxmox_pass = None
    proxmox_host = None
    proxmox_port = None

    def __init__(self, args: dict):
        # Defaults are managed by argparse in caller
        if args:
            # First read from config file
            self.args = args
            if "config_file" in args.keys() and args["config_file"]:
                try:
                    logger.debug("Reading config...")
                    with open(args["config_file"], "r") as stream:
                        config = safe_load(stream)
                        for k, v in config.items():
                            setattr(self, k, v)
                except FileNotFoundError:
                    raise ConfigurationError("Config file not found")
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
                        case _:
                            setattr(self, k, v)
        else:
            raise ConfigurationError("Cannot continue, not fully configured.")

        # Resolve proportions so they always sum to 1
        if self.p_cpu + self.p_mem > 1:
            if self.p_cpu > self.p_mem:
                if self.p_cpu > 1:
                    self.p_cpu = 1
                self.p_mem = 1 - self.p_cpu
            if self.p_cpu < self.p_mem:
                if self.p_mem > 1:
                    self.p_mem = 1
                self.p_cpu = 1 - self.p_mem
            if self.p_cpu == self.p_mem:
                self.p_cpu = 0.5
                self.p_mem = 0.5
        if self.p_cpu + self.p_mem < 1:
            if self.p_cpu > self.p_mem:
                self.p_cpu = 1 - self.p_mem
            if self.p_mem > self.p_cpu:
                self.p_mem = 1 - self.p_cpu
            if self.p_cpu == self.p_mem:
                self.p_cpu = 0.5
                self.p_mem = 0.5

    def __dict__(self) -> dict:
        return {
            "args": self.args,
            "config_file": self.config_file,
            "dry_run": self.dry_run,
            "verbose": self.verbose,
            "exclude_nodes": self.exclude_nodes,
            "exclude_vmids": self.exclude_vmids,
            "exclude_types": self.exclude_types,
            "p_cpu": self.p_cpu,
            "p_mem": self.p_mem,
            "proxmox_user": self.proxmox_user,
            "proxmox_pass": self.proxmox_pass,
            "proxmox_host": self.proxmox_host,
            "proxmox_port": self.proxmox_port,
        }
