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
from statistics import mean

from loguru import logger
from proxmoxer import ProxmoxAPI, ResourceException
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
            logger.debug("Reading config...")
            if args["config_file"]:
                try:
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

    def __init__(self, conf: Config) -> None:
        self.conf = conf
        logger.debug("Connecting to Proxmox API...")
        self.pve = ProxmoxAPI(
            host=self.conf.proxmox_host,
            port=self.conf.proxmox_port,
            user=self.conf.proxmox_user,
            password=self.conf.proxmox_pass,
        )

    def get_node_state(self, node_name: str, node_status: dict) -> (int, int, float):
        cpu_mhz = float(node_status["cpuinfo"]["mhz"])
        cpu_cores = float(node_status["cpuinfo"]["cores"])
        cpu_load = mean(list(map(float, node_status["loadavg"])))
        cpu_total = cpu_mhz * cpu_cores
        cpu_used = cpu_mhz * cpu_load
        cpu_free = cpu_total - cpu_used
        # logger.debug(
        #     f"{node_name}: cpu_mhz: {cpu_mhz}, cores: {cpu_cores}, load: {cpu_load}"
        # )

        w_cpu = self.conf.p_cpu * (cpu_total / cpu_free) * 100
        # logger.debug(
        #     f"{node_name}: cpu_total: {cpu_total}, cpu_free: {cpu_free}, w_cpu {w_cpu}"
        # )

        mem_total = int(node_status["memory"]["total"])
        mem_used = int(node_status["memory"]["used"])
        mem_free = int(node_status["memory"]["free"])
        mem_ksm = int(node_status["ksm"]["shared"])
        mem_free_no_ksm = mem_total - (mem_used + mem_ksm)
        # logger.debug(
        #     f"{node_name}: mem_free: {mem_free}, mem_ksm: {mem_ksm}, mem_total: {mem_total}"
        # )

        w_mem = self.conf.p_mem * (mem_total / mem_free_no_ksm) * 100
        # logger.debug(
        #     f"{node_name}: mem_total: {mem_total}, mem_free_no_ksm: {mem_free_no_ksm}, w_mem {w_mem}"
        # )
        weight = round(w_cpu + w_mem)

        logger.info(f"{node_name}: weight: {weight}")
        return weight, mem_free, cpu_free

    def get_node_workloads(self, node: dict) -> dict:
        workloads = {}

        if "qemu" not in self.conf.exclude_types:
            for workload in self.pve.nodes(node["node"]).qemu.get():
                vmid = str(workload["vmid"])
                if vmid in self.conf.exclude_vmids:
                    logger.debug(f"Ignoring VMID {vmid} per configuration")
                    continue
                if workload["status"] != "running":
                    continue
                workload.update({"kind": "qemu"})
                del workload["vmid"]
                workloads.update({vmid: workload})
        else:
            logger.debug(f"Ignoring QEMU workloads per configuration.")

        if "lxc" not in self.conf.exclude_types:
            for workload in self.pve.nodes(node["node"]).lxc.get():
                vmid = str(workload["vmid"])
                if vmid in self.conf.exclude_vmids:
                    logger.debug(f"Ignoring VMID {vmid} per configuration")
                    continue
                if workload["status"] != "running":
                    continue
                workload.update({"kind": "lxc"})
                del workload["vmid"]
                workloads.update({vmid: workload})
        else:
            logger.debug(f"Ignoring LXC workloads per configuration.")

        return workloads

    def get_workload_state(
        self, node_name: str, node_status: dict, vmid: int, workload: dict
    ) -> (int, int, float):
        workload_name = workload["name"]
        workload_kind = workload["kind"]

        cpu_cores = float(workload["cpus"])
        cpu_load = float(workload["cpu"])
        cpu_mhz = float(node_status["cpuinfo"]["mhz"])
        cpu_used = cpu_mhz * cpu_load
        cpu_max = cpu_mhz * cpu_cores
        # This prevents division by zero
        if cpu_used <= 0.001:
            cpu_used = 0.001
        w_cpu = self.conf.p_cpu * (cpu_used / cpu_max) * 100
        # logger.debug(
        #     f"cpu_load: {cpu_load}, cpu_used: {cpu_used}, cpu_max: {cpu_max}, w_cpu: {w_cpu}"
        # )

        mem_max = float(workload["maxmem"])
        mem_used = float(workload["mem"])
        w_mem = self.conf.p_mem * (mem_used / mem_max) * 100
        # logger.debug(f"mem_max: {mem_max}, mem_used: {mem_used}, w_mem: {w_mem}")

        weight = round(w_cpu + w_mem)

        logger.debug(
            f"{node_name} {workload_kind}/{vmid} '{workload_name}': weight: {weight}, mem_used: {mem_used}, cpu_used: {cpu_used}"
        )

        return weight, mem_used, cpu_used

    def get_migration_candidates(self) -> list:
        logger.info("Looking for migration candidates...")

        node_states = {}

        for node in self.pve.nodes.get():
            node_name = node["node"]
            if node_name in self.conf.exclude_nodes:
                logger.debug(f"Ignoring node {node['node']} per configuration")
                continue

            node_status = self.pve.nodes(node_name).status.get()
            weight, mem_free, cpu_free = self.get_node_state(node_name, node_status)

            node_states[node_name] = {
                "weight": weight,
                "mem_free": mem_free,
                "cpu_free": cpu_free,
            }

            workloads = self.get_node_workloads(node)
            for vmid, workload in workloads.items():
                weight, mem_used, cpu_max = self.get_workload_state(
                    node_name, node_status, vmid, workload
                )
                workloads[vmid].update(
                    {
                        "weight": weight,
                        "mem_used": mem_used,
                        "cpu_max": cpu_max,
                    }
                )

            node_states[node_name].update(
                {
                    "workload_count": len(workloads),
                    "workloads": workloads,
                }
            )

        w_mean = mean([n["weight"] for n in node_states.values()])
        l_mean = mean([n["workload_count"] for n in node_states.values()])

        candidates = {"source": {}, "destination": {}}
        source_count = 0
        destination_count = 0

        for node, state in node_states.items():
            if state["weight"] < w_mean:  # * 0.9:
                candidates["destination"].update({node: state})
                destination_count += 1
                logger.debug(
                    f"Found destination candidate: {node} (weight: {state['weight']}, workload_count: {state['workload_count']})"
                )
            if state["weight"] > w_mean and state["workload_count"] > l_mean:  # * 1.1
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
                # logger.debug(
                #     f"{node_states[destination_name]['mem_free']}, {node_states[destination_name]['cpu_free']} >? {workload['mem_used']}, {workload['cpu_max']}"
                # )
                if (
                    node_states[destination_name]["mem_free"] > workload["mem_used"]
                    and node_states[destination_name]["cpu_free"] > workload["cpu_max"]
                ):
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
                        f"Could not find a destination node with enough free resources for workload '{workload['name']}' ({workload['kind']} VMID {vmid}) on node {source_name}"
                    )

        if len(migration_proposals) < 1:
            logger.debug("No migration candidates found")

        return migration_proposals

    def do_migration(self, spec: MigrationSpec) -> (bool, str):
        logger.info(
            f"Migrating workload '{spec.name}' ({spec.kind} VMID {spec.vmid}) from node {spec.source} to node {spec.destination}..."
        )

        try:
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
        except ResourceException:
            logger.error(f"Migration failed, {spec.kind} is locked")
            return False, None

        logger.debug(f"Migration jobspec: {job}")
        return True, job
