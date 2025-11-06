# UDP-Plus

UDP-Plus is a lightweight overlay protocol and Python toolkit that brings reliable, chunked messaging to raw UDP.

Designed for embedded systems, low-latency services, and peer-to-peer utilities, UDP-Plus provides a pragmatic layer on top of UDP that
adds chunking, per-chunk acknowledgements, and simple delivery guarantees while keeping the API small and fully asynchronous.

Key features
- Overlay protocol on UDP: adds reliability primitives without replacing UDP's connectionless model.
- Transparent chunking: automatically fragments and reassembles large payloads to avoid MTU issues.
- Per-chunk ACKs and configurable retries: improves delivery probability on lossy networks while remaining lightweight.
- Async producer/consumer buckets: separate send and receive queues (send_bucket, recv_bucket) for clean concurrency patterns.
- Minimal, extensible API: small surface area to embed into existing asyncio applications or services.

Technical summary
UDP-Plus implements an application-level protocol that encodes control and data fields into compact CSV-based packets. Each message is assigned
an operation id and split into fixed-size chunks. Receivers acknowledge each chunk; senders retry missing chunks up to a configurable number
of attempts. The implementation exposes two non-blocking queues for integration: a send queue for outgoing packets and a receive queue for
consumed messages, enabling event-driven or batch-processing consumption models.

Who should use it
- Projects that need better-than-best-effort delivery but cannot or do not want to use TCP.
- Systems requiring predictable, small-footprint async messaging over UDP (IoT devices, game servers, telemetry collectors).

Extensibility and integration
The codebase was designed to be easy to extend: add authentication, encryption, or a stronger retransmission/backoff strategy by
wrapping the packet-generation and send/confirm logic. The queues make it straightforward to integrate with worker pools or priority schedulers.

License
Specify a license in the repository to make reuse and contribution terms explicit.

Quick API
 - `put_message(ip: str, port: int, message: str)`
	 - Enqueue a message to be sent to the target (non-blocking, async).

 - `get_message()` -> `(sender_ip: str, message: str)`
	 - Await a received message from the receive bucket (async).
