"""
This file provides a wrapper class for connecting to the Proxmox API, supporting
the available Proxmoxer backends: HTTPS, SSH, and local
"""

# pve-cslb - a configurable central scheduling load balancer for Proxmox PVE
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


import os.path

from loguru import logger
from proxmoxer import ProxmoxAPI, ResourceException, AuthenticationError

from .config import Config

logger.disable("ProxmoxConnection")


class ProxmoxConnection(ProxmoxAPI):
    """Proxmox API wrapper to support different backends."""

    config: Config = None
    proxmox_api: ProxmoxAPI = None

    def __init__(self, config: Config, **kwargs):
        """Initialize the Proxmox API wrapper with connection details."""
        self.config = config

        kwargs = {}
        match config.proxmox_scheme:
            case "https":
                kwargs = {
                    "backend": "https",
                    "host": config.proxmox_node,
                    "port": config.proxmox_port,
                    "user": config.proxmox_user,
                    "password": config.proxmox_pass,
                    "verify_ssl": not config.proxmox_no_verify_ssl
                }
            case "ssh":
                if config.proxmox_ssh_key_file is not None and not os.path.exists(
                        os.path.expanduser(config.proxmox_ssh_key_file)):
                    raise FileNotFoundError(
                        f"SSH key file {config.proxmox_ssh_key_file} does not exist."
                    )
                kwargs = {
                    "backend": "ssh_paramiko",
                    "host": config.proxmox_node,
                    "port": config.proxmox_port,
                    "user": config.proxmox_user,
                    "password": config.proxmox_pass,
                    "private_key_file": config.proxmox_ssh_key_file,
                }
            case "local":
                kwargs = {
                    "backend": "local",
                }

        logger.info(
            f"Using Proxmox API via {self.config.proxmox_scheme}://{self.config.proxmox_node}"
        )
        try:
            super().__init__(**kwargs)
            logger.debug("Proxmox API connection established.")
        except (ResourceException, ConnectionError, AuthenticationError) as exception:
            logger.error(exception)
            raise
        except (FileNotFoundError, PermissionError) as exception:
            logger.error(exception)
            raise
        except Exception as exception:
            logger.error(exception)
            raise
