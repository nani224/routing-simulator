# ADR 0003. Use user-authored topologies in the simulation session

## Decision

The topology builder saves one editable definition in browser storage. The definition includes router IDs, autonomous systems, and link parameters. The frontend submits that definition through the existing simulation and comparison APIs. Reset restores the saved link parameters. The Observatory reads the resulting live session, and its synthetic tunnel replay still has its own data source.

Route probes are simulated packets. The backend router looks up the next hop and transmits through the link emulator at each hop. The browser renders the packet events it receives. Probe traffic is counted separately from routing control traffic in metrics.
