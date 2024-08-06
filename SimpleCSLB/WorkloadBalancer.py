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
from requests.exceptions import ConnectionError

from .Config import Config
from .MigrationSpec import MigrationSpec

logger.disable("WorkloadBalancer")


class WorkloadBalancer:

    conf = None
    proxmox = None

    def __init__(self, conf: Config) -> None:
        self.conf = conf
        logger.info(
            f"Connecting to Proxmox API {self.conf.proxmox_node}:{self.conf.proxmox_port}..."
        )
        try:
            self.pve = ProxmoxAPI(
                host=self.conf.proxmox_node,
                port=self.conf.proxmox_port,
                user=self.conf.proxmox_user,
                password=self.conf.proxmox_pass,
            )
        except (ResourceException, ConnectionError) as e:
            logger.error(e)
            exit(1)

    def get_node_state(self, node_name: str, node_status: dict) -> (int, int, float):
        cpu_mhz = float(node_status["cpuinfo"]["mhz"])
        cpu_cores = float(node_status["cpuinfo"]["cores"])
        cpu_load = mean(list(map(float, node_status["loadavg"])))
        cpu_total = cpu_mhz * cpu_cores
        cpu_used = cpu_mhz * cpu_load
        cpu_free = cpu_total - cpu_used
        logger.debug(
            f"Node {node_name}: cpu_mhz: {cpu_mhz}, cores: {cpu_cores}, load: {round(cpu_load, 2)}"
        )

        w_cpu = self.conf.percent_cpu * (cpu_total / cpu_free) * 100
        logger.debug(
            f"Node {node_name}: cpu_total: {round(cpu_total, 2)}, cpu_free: {round(cpu_free, 2)}, w_cpu {round(w_cpu, 2)}"
        )

        mem_total = int(node_status["memory"]["total"])
        mem_used = int(node_status["memory"]["used"])
        mem_free = int(node_status["memory"]["free"])
        mem_ksm = int(node_status["ksm"]["shared"])
        mem_free_no_ksm = mem_total - (mem_used + mem_ksm)
        logger.debug(
            f"Node {node_name}: mem_free: {mem_free}, mem_ksm: {mem_ksm}, mem_total: {mem_total}"
        )

        w_mem = self.conf.percent_mem * (mem_total / mem_free_no_ksm) * 100
        logger.debug(
            f"Node {node_name}: mem_total: {mem_total}, mem_free_no_ksm: {mem_free_no_ksm}, w_mem {round(w_mem, 2)}"
        )
        weight = round(w_cpu + w_mem)

        logger.info(f"Node {node_name}: weight: {weight}")
        return weight, mem_free, cpu_free

    def get_node_workloads(self, node: dict) -> dict:
        workloads = {}

        if "qemu" not in self.conf.exclude_types:
            try:
                workloads_from_node = self.pve.nodes(node["node"]).qemu.get()
            except (ResourceException, ConnectionError) as e:
                logger.error(e)
                exit(1)

            for workload in workloads_from_node:
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
            logger.debug(f"Ignoring QEMU workloads per configuration")

        del workloads_from_node

        if "lxc" not in self.conf.exclude_types:
            try:
                workloads_from_node = self.pve.nodes(node["node"]).lxc.get()
            except (ResourceException, ConnectionError) as e:
                logger.error(e)
                exit(1)

            for workload in workloads_from_node:
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
            logger.debug(f"Ignoring LXC workloads per configuration")

        del workloads_from_node

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
        w_cpu = self.conf.percent_cpu * (cpu_used / cpu_max) * 100

        mem_max = float(workload["maxmem"])
        mem_used = float(workload["mem"])
        w_mem = self.conf.percent_mem * (mem_used / mem_max) * 100

        weight = round(w_cpu + w_mem)

        logger.debug(
            f"Node {node_name}: workload {workload_kind}/{vmid} '{workload_name}': weight: {weight}, mem_used: {round(mem_used)}, cpu_used: {round(cpu_used, 2)}"
        )

        return weight, mem_used, cpu_used

    def get_migration_candidates(self) -> list:
        node_states = {}

        for node in self.pve.nodes.get():
            node_name = node["node"]
            if node_name in self.conf.exclude_nodes:
                logger.info(f"Node {node['node']}: ignoring per configuration")
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
                        f"Proposing workload migration: '{workload['name']}' ({workload['kind']}/{vmid}) from node {source_name} to node {destination_name}..."
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
                        f"Could not find a destination node with enough free resources for workload '{workload['name']}' ({workload['kind']}/{vmid}) on node {source_name}"
                    )

        return migration_proposals

    def do_migration(self, spec: MigrationSpec) -> (bool, str):
        logger.info(
            f"Migrating workload '{spec.name}' ({spec.kind}/{spec.vmid}) from node {spec.source} to node {spec.destination}..."
        )

        try:
            match spec.kind:
                case "lxc":
                    job = (
                        self.pve.nodes(spec.source)
                        .lxc(spec.vmid)
                        .migrate.post(target=spec.destination, online=0)
                    )
                case "qemu":
                    job = (
                        self.pve.nodes(spec.source)
                        .qemu(spec.vmid)
                        .migrate.post(target=spec.destination, online=1)
                    )
                case _:
                    raise TypeError(f"Unknown workload type: {spec.kind}")
        except ResourceException as e:
            logger.error(f"Migration failed, {spec.kind} is locked: {e}")
            return False, None
        except ConnectionError as e:
            logger.error(f"Migration failed, connection error: {e}")
            return False, None

        logger.debug(f"Migration jobspec: {job}")
        return True, job
