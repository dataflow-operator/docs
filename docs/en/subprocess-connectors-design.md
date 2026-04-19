# Design notes: subprocess connectors

This page records high-level design choices for the optional **subprocess** connector mode (separate binaries, **stdin/stdout**, **JSON Lines**). The normative wire format, commands, and examples are defined in [Connector Protocol (stdin/stdout)](connector-protocol.md).

## Goals

- Allow shipping connector implementations as separate binaries from the processor core.
- Keep a single clear protocol between the processor loop and each connector process.

## Transformers

Transformers are intended to stay small and stateless. **In-process** transformers avoid per-message IPC overhead and are the default path. Running transformers as subprocesses is theoretically supported for maximum extensibility, but each message pays serialization and process-boundary cost.

## When subprocess mode applies

Subprocess connectors are used when `DATAFLOW_USE_SUBPROCESS_CONNECTORS=1` and a matching `dataflow-connector-<type>` binary is discovered (see the protocol page for search order and handshake).

## Historical note

Longer internal drafts of this design were consolidated into `connector-protocol.md` and the operator implementation. Earlier standalone planning documents were removed to avoid contradicting the published protocol.
