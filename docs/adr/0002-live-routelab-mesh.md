# ADR 0002. Show live RouteLab state in the Observatory

## Decision

The Observatory's live mesh reads the same RouteLab WebSocket state as the routing simulator. Both views share the same simulation session. They use the same next-hop tracing function and link state. The Observatory sends link changes through RouteLab's existing event endpoint.

The live mesh shows a forwarding path between the first and last routers in the current topology. The tunnel demo retains its own replay clock and event source. The live mesh does not carry tunnel socket traffic.
