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

logger.disable("Config")


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
    _percent_cpu: float
    _percent_mem: float
    max_migrations: int
    proxmox_user: str
    proxmox_pass: str
    proxmox_node: str
    proxmox_port: int

    def __init__(self):
        self.config_file = ""
        self.dry_run = False
        self.verbose = False
        self.quiet = False
        self.no_color = False
        self.exclude_nodes = []
        self.exclude_vmids = []
        self.exclude_types = []
        self._percent_cpu = 0.4
        self._percent_mem = 0.6
        self.max_migrations = 5
        self.proxmox_user = "root@pam"
        self.proxmox_pass = ""
        self.proxmox_node = "localhost"
        self.proxmox_port = 8006

    @property
    def percent_cpu(self) -> float:
        return self._percent_cpu

    @percent_cpu.setter
    def percent_cpu(self, percent_cpu: float = 0.4):
        self._percent_cpu = percent_cpu
        self.balance_resource_weights()

    @property
    def percent_mem(self) -> float:
        return self._percent_mem

    @percent_mem.setter
    def percent_mem(self, percent_mem: float = 0.6):
        self._percent_mem = percent_mem
        self.balance_resource_weights()

    def __dict__(self) -> dict:
        return {
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

    def balance_resource_weights(self):
        # Resolve proportions so they always sum to 1
        if self._percent_cpu + self._percent_mem > 1:
            if self._percent_cpu > self._percent_mem:
                if self._percent_cpu > 1:
                    self._percent_cpu = 1
                self._percent_mem = 1 - self._percent_cpu
            if self._percent_cpu < self._percent_mem:
                if self._percent_mem > 1:
                    self._percent_mem = 1
                self._percent_cpu = 1 - self._percent_mem
            if self._percent_cpu == self._percent_mem:
                self._percent_cpu = 0.5
                self._percent_mem = 0.5
        if self._percent_cpu + self._percent_mem < 1:
            if self._percent_cpu > self._percent_mem:
                self._percent_cpu = 1 - self._percent_mem
            if self._percent_mem > self._percent_cpu:
                self._percent_mem = 1 - self._percent_cpu
            if self._percent_cpu == self._percent_mem:
                self._percent_cpu = 0.5
                self._percent_mem = 0.5
