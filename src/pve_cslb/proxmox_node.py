#  Copyright (C) 2025 Travis Wichert
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

from proxmoxer import ProxmoxAPI


class ProxmoxNode:
    """Model for a Proxmox node"""

    def __init__(self, host: str, user: str, password: str):
        """Initialize the Proxmox node with API connection details."""
        self.proxmox = ProxmoxAPI(host, user=user, password=password)

    def get_rrd_data(self, node_name: str, timeframe: str = "hour", cf: str = "AVERAGE"):
        """Fetch RRD data for a specified node."""
        return self.proxmox.nodes(node_name).rrddata().get(timeframe=timeframe, cf=cf)

    def get_tasks_log(self, node_name: str, upid: str):
        """Retrieve logs for a specific task UPID."""
        return self.proxmox.nodes(node_name).tasks(upid).log().get()

    def get_network_usage(self, node_name: str):
        """Calculate the total network usage for the node by summing input and output traffic."""
        net_in = net_out = 0
        for workload in self.proxmox.nodes(node_name).netstat.get():
            net_in += int(workload.get("in", 0))
            net_out += int(workload.get("out", 0))
        return net_in + net_out
