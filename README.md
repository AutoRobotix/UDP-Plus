# UDP-Plus

**UDP-Plus** is a lightweight **overlay protocol** and **Python toolkit** that adds reliable, chunked messaging on top of raw UDP.

Designed for **embedded systems**, **low-latency services**, and **peer-to-peer applications**, it introduces minimal reliability mechanisms—such as chunking and acknowledgements—while preserving UDP’s connectionless model and asynchronous efficiency.

---

## ⚙️ Overview

**UDP-Plus** provides a pragmatic reliability layer for UDP communication.
It delivers guaranteed-order, chunked message transmission with retry logic and async integration, making it ideal for distributed or resource-constrained environments.

### Key Features

* **Overlay protocol on UDP:** Adds reliability primitives while keeping UDP’s stateless, connectionless semantics.
* **Transparent chunking:** Automatically fragments and reassembles large payloads, avoiding MTU fragmentation issues.
* **Per-chunk ACKs and configurable retries:** Increases delivery probability over lossy networks while remaining lightweight.
* **Async API for sending and receiving:** Direct methods for sending (`put_message`) and receiving (`get_message`) messages asynchronously.
* **Minimal, extensible API:** Compact surface area for seamless embedding into existing `asyncio` applications or services.

---

## 🧩 Technical Summary

UDP-Plus defines an **application-level protocol** that encodes control and data fields into compact, CSV-formatted packets.

Each message is assigned a unique **operation ID** and split into fixed-size **chunks**.
Receivers acknowledge each chunk; senders automatically retry unconfirmed chunks up to a configurable limit.

The library provides direct async methods:

* **`put_message`** for sending messages
* **`get_message`** for receiving messages

This design enables **event-driven** and **batch-processing** messaging models, suitable for everything from embedded devices to high-volume async pipelines.

---

## 🎯 Intended Use Cases

Use **UDP-Plus** when you need:

* **Better-than-best-effort delivery** without switching to TCP.
* **Deterministic, small-footprint async messaging** for IoT, gaming, or telemetry.
* **Custom UDP extensions** with minimal integration overhead.

---

## 🔧 Extensibility & Integration

The codebase is designed for **easy extension and customization**.
You can enhance the protocol by:

* Adding **authentication** or **encryption** layers
* Implementing a **stronger retransmission/backoff strategy**
* Wrapping the **packet generation**, **send**, or **confirm** logic

The modular queue system makes it straightforward to integrate UDP-Plus into worker pools, schedulers, or message routers.

---

## 🧰 Quick API Reference

```python
await put_message(ip: str, port: int, message: str)
```

Enqueue a message to be sent to the target (non-blocking, async).

```python
sender_ip, message = await get_message()
```

Await and retrieve a received message from the receive bucket.

---

**UDP-Plus**
Reliable messaging over UDP — simplified.

> A pragmatic bridge between UDP’s speed and TCP’s reliability.

