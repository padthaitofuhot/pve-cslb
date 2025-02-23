"""config module
This module contains the Config class and helpers.
"""

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

from os import path

from loguru import logger

logger.disable("Config")


class ConfigurationError(Exception):
    pass
    """Exception for invalid configuration"""


class Config:
    """
    This class provides necessary config data for connecting to Proxmox and identifying
    and scheduling workload migrations.
    """

    # pylint: disable=R0902
    config_file: str | None = "/etc/pve-cslb.conf"
    dry_run: bool = False
    verbose: bool = False
    quiet: bool = False
    no_color: bool = False
    exclude_nodes: list = []
    exclude_vmids: list = []
    exclude_types: list = []
    _tolerance: float = 0.2
    _percent_cpu: float = 0.4
    _percent_mem: float = 0.6
    max_migrations: int = 5
    proxmox_node: str = "localhost"
    proxmox_scheme: str = "https"
    proxmox_port: int = 8006
    proxmox_user: str = "root@pam"
    proxmox_pass: str | None = None
    _proxmox_ssh_key_file: str | None = "~/.ssh/id_rsa"
    proxmox_no_verify_ssl: bool = False

    @property
    def tolerance(self) -> float:
        """Property getter for _tolerance"""
        return self._tolerance

    @tolerance.setter
    def tolerance(self, tolerance: float):
        """Property setter for _tolerance"""
        self._tolerance = float(tolerance)

    @property
    def percent_cpu(self) -> float:
        """Property getter for _percent_cpu"""
        return self._percent_cpu

    @percent_cpu.setter
    def percent_cpu(self, percent_cpu: float = 0.4):
        """Property setter for _percent_cpu"""
        self._percent_cpu = float(percent_cpu)
        self.balance_resource_weights()

    @property
    def percent_mem(self) -> float:
        """Property getter for _percent_mem"""
        return self._percent_mem

    @percent_mem.setter
    def percent_mem(self, percent_mem: float = 0.6):
        """Property setter for _percent_mem"""
        self._percent_mem = float(percent_mem)
        self.balance_resource_weights()

    @property
    def proxmox_ssh_key_file(self) -> str | None:
        """Property getter for _proxmox_ssh_key_file"""
        return self._proxmox_ssh_key_file

    @proxmox_ssh_key_file.setter
    def proxmox_ssh_key_file(self, ssh_key_file: str | None = None):
        """Property setter for _proxmox_ssh_key_file"""
        if ssh_key_file is None:
            self._proxmox_ssh_key_file = None
        elif path.isabs(ssh_key_file):
            self._proxmox_ssh_key_file = ssh_key_file
        else:
            self._proxmox_ssh_key_file = path.expanduser(ssh_key_file)

    def balance_resource_weights(self):
        """Ensures resource weighting proportions always sum to 1"""
        if self._percent_cpu + self._percent_mem > 1:
            if self._percent_cpu > self._percent_mem:
                self._percent_cpu = min(self._percent_cpu, 1)
                self._percent_mem = 1 - self._percent_cpu
            if self._percent_cpu < self._percent_mem:
                self._percent_mem = min(self._percent_mem, 1)
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
