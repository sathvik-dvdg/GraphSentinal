# Mininet Monitor Subsystem

## System Boundary & Architecture

The `mininet_monitor` module is an autonomous background monitoring component of the GraphSentinel backend (`backend/app/mininet_monitor/`).

### Decoupling & Independence
- **Backend Monitor (`backend/app/mininet_monitor/`)**: Runs in-process within the FastAPI application lifecycle. It periodically executes `ovs-ofctl dump-flows <switch>` (defaulting to switch `s1`) via subprocess/WSL and streams parsed OpenFlow flow records to the GraphSAGE ML inference pipeline.
- **Mininet Lab Topology (`mininet/topologies/`)**: A standalone Python Mininet topology script for running SDN lab simulations.

### Inter-Module Relationship
The monitor does **not** import or depend on Python modules inside `mininet/topologies/`. The two subsystems are fully decoupled: `mininet/` provisions the virtual network topology, while `backend/app/mininet_monitor/` passively reads OpenFlow flow tables directly from Open vSwitch.
