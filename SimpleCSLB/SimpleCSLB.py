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

from math import sqrt
from statistics import mean

from loguru import logger
from proxmoxer import ProxmoxAPI
from yaml import safe_load


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
    p_cpu = 0.2
    p_mem = 0.8
    proxmox_user = None
    proxmox_pass = None
    proxmox_host = None
    proxmox_port = None

    def __init__(self, args: dict):
        if args:
            # First read from config file
            if args["config_file"]:
                with open(args["config_file"], "r") as stream:
                    config = safe_load(stream)
                    for k, v in config.items():
                        setattr(self, k, v)
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
            raise ConfigurationError(
                "Missing required configuration.  Try using --help."
            )


class MigrationSpec:
    source = None
    destination = None
    name = None
    vmid = None
    kind = None

    def __init__(self, source: str, destination: str, name: str, vmid: int, kind: str):
        self.source = source
        self.destination = destination
        self.name = name
        self.vmid = vmid
        self.kind = kind


class LoadBalancer:

    conf = None
    proxmox = None

    def __init__(self, args: dict) -> None:
        logger.debug("Reading config...")
        self.conf = Config(args)
        logger.debug("Connecting to Proxmox API...")
        self.pve = ProxmoxAPI(
            host=self.conf.proxmox_host,
            port=self.conf.proxmox_port,
            user=self.conf.proxmox_user,
            password=self.conf.proxmox_pass,
        )

    def get_migration_candidates(self) -> list:
        logger.info("Looking for migration candidates...")

        for kind in self.conf.exclude_types:
            logger.info(f"Ignoring workloads of type {kind} per configuration")

        node_states = {}

        for node in self.pve.nodes.get():
            if node["node"] in self.conf.exclude_nodes:
                logger.info(f"Ignoring node {node['node']} per configuration")
                continue

            node_status = self.pve.nodes(node["node"]).status.get()

            w_cpu = (
                self.conf.p_cpu
                * float(node_status["cpuinfo"]["mhz"])
                * node_status["cpuinfo"]["sockets"]
                * node_status["cpuinfo"]["cores"]
                * float(node_status["loadavg"][1])
            )

            w_mem = (
                self.conf.p_mem
                * (node_status["memory"]["used"] + node_status["ksm"]["shared"])
                * node_status["memory"]["total"]
            )

            weight = sqrt(w_cpu + w_mem)

            node_states[node["node"]] = {
                "weight": weight,
                "memfree": node_status["memory"]["free"],
            }

            workloads = {}

            if "qemu" not in self.conf.exclude_types:
                for workload in self.pve.nodes(node["node"]).qemu.get():
                    if workload["status"] != "running":
                        continue
                    if workload["vmid"] in self.conf.exclude_vmids:
                        logger.debug(
                            f"Ignoring workload VMID {workload['vmid']} per configuration"
                        )
                        continue

                    workload.update({"kind": "qemu"})
                    vmid = workload["vmid"]
                    del workload["vmid"]
                    workloads.update({vmid: workload})

            if "lxc" not in self.conf.exclude_types:
                for workload in self.pve.nodes(node["node"]).lxc.get():
                    if workload["status"] != "running":
                        continue
                    if workload["vmid"] in self.conf.exclude_vmids:
                        logger.debug(
                            f"Ignoring workload VMID {workload['vmid']} per configuration"
                        )
                        continue
                    workload.update({"kind": "lxc"})
                    vmid = workload["vmid"]
                    del workload["vmid"]
                    workloads.update({vmid: workload})

            for vmid, workload in workloads.items():
                w_cpu = self.conf.p_cpu * workload["cpus"] * float(workload["cpu"])
                w_mem = self.conf.p_mem * workload["mem"] * workload["maxmem"]
                workloads[vmid].update({"weight": sqrt(w_cpu + w_mem)})

            node_states[node["node"]].update(
                {"workload_count": len(workloads), "workloads": workloads}
            )

        weights = [n["weight"] for n in node_states.values()]
        w_mean = mean(weights)

        loads = [n["workload_count"] for n in node_states.values()]
        l_mean = mean(loads)

        candidates = {"source": {}, "destination": {}}
        source_count = 0
        destination_count = 0

        for node, state in node_states.items():
            if state["weight"] < w_mean * 0.9:
                candidates["destination"].update({node: state})
                destination_count += 1
                logger.debug(
                    f"Found destination candidate: {node} (weight: {state['weight']}, workload_count: {state['workload_count']})"
                )
            if state["weight"] > w_mean * 1.1 and state["workload_count"] > l_mean:
                candidates["source"].update({node: state})
                source_count += 1
                logger.debug(
                    f"Found source candidate: {node} (weight: {state['weight']}, workload_count: {state['workload_count']})"
                )

        migration_proposals = []

        while source_count > 0 and destination_count > 0:

            source_name, source_workloads = sorted(
                candidates["source"].items(), key=lambda x: x[1]["weight"], reverse=True
            )[0]
            vmid, workload = sorted(
                candidates["source"][source_name]["workloads"].items(),
                key=lambda x: x[1]["weight"],
                reverse=True,
            )[0]
            del candidates["source"][source_name]
            source_count -= 1

            # Find a destination candidate with enough free memory for the source workload
            for destination_name, destination_workloads in sorted(
                candidates["destination"].items(),
                key=lambda x: x[1]["weight"],
                reverse=False,
            ):
                if node_states[destination_name]["memfree"] > workload["maxmem"]:
                    del candidates["destination"][destination_name]
                    destination_count -= 1
                    logger.info(
                        f"Proposing workload migration: '{workload['name']}' ({workload['kind']} VMID {vmid}) from node {source_name} to node {destination_name}..."
                    )
                    migration_proposals.append(
                        MigrationSpec(
                            source_name,
                            destination_name,
                            workload["name"],
                            vmid,
                            workload["kind"],
                        )
                    )
                    break
                else:
                    logger.info(
                        f"Could not find a destination node with enough free memory for workload '{workload['name']}' ({workload['kind']} VMID {vmid}) on node {source_name}"
                    )

        if len(migration_proposals) < 1:
            logger.debug("No migration candidates found")

        return migration_proposals

    def do_migration(self, spec: MigrationSpec) -> str:
        logger.info(
            f"Migrating workload '{spec.name}' ({spec.kind} VMID {spec.vmid}) from node {spec.source} to node {spec.destination}..."
        )

        match spec.kind:
            case "lxc":
                job = (
                    self.pve.nodes(spec.source)
                    .lxc(spec.vmid)
                    .migrate.post(target=spec.destination, online=1)
                )
            case "qemu":
                job = (
                    self.pve.nodes(spec.source)
                    .qemu(spec.vmid)
                    .migrate.post(target=spec.destination, online=1)
                )
            case _:
                raise TypeError(f"Unknown workload type: {spec.kind}")

        logger.debug(f"Migration jobspec: {job}")
        return job
