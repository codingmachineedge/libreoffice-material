# Notification service architecture checkpoint

Status: implemented and source-validated; native CppUnit and runtime UI proof are
not yet recorded for this checkpoint.

This checkpoint puts an asynchronous boundary between UI code and the existing
synchronous, durable `NotificationStore`. It does not implement notification
cards, a manager window, dialog routing, or producer migrations.

## Ownership and ordering

`SfxApplication::GetNotificationCenter()` lazily creates one profile service.
The service starts one serialized worker, and that worker constructs, calls, and
destroys its `NotificationStore`. UI code receives no store reference. Every
accepted request gets a monotonic request ID; every completed request gets a
monotonic snapshot generation. A FIFO queue therefore defines mutation and
completion order without per-record worker races.

The injectable repository factory exists for focused tests. Production uses the
fixed profile repository and a VCL completion queue. The queue coalesces worker
results into one user event, preserves FIFO delivery, and can cancel undelivered
callbacks during application teardown.

## Immutable result boundary

Each completion carries a `shared_ptr<const NotificationCenterSnapshot>`. The
snapshot owns const health, error, head, preferences, record, and history values
captured under one store lock. Consumers can retain a generation safely but
cannot mutate service state or race a later request.

A failed compare-and-swap remains a failed mutation. Before returning it, the
worker explicitly refreshes the store so the accompanying snapshot identifies
the winning head and current records instead of presenting stale state.

## Shutdown contract

Shutdown is idempotent. The profile facade first closes and clears its VCL
completion queue, then stops worker admission, drains all already-accepted
requests, joins the worker, and releases the service. Closing delivery before
the join also prevents a draining worker from posting into a UI loop that is
already tearing down. Accepted mutations remain durable even when their UI
callback is cancelled. A request attempted after admission closes returns ID
zero.

The application resets the lazy service near the start of `SfxApplication`
destruction, while the VCL event queue still exists. The store itself is reset
inside the worker function, not in the application thread.

## Configuration and privacy

`NotificationConfiguration` is a typed adapter over the generated
`officecfg::Office::UI::NotificationCenter` accessors. It reads and writes all
display and history fields as one normalized configuration batch. The profile
service persists preference updates on its worker; the repository test factory
does not write the user profile.

The service does not add a second persistence format or relax the store's
privacy policy. `MetadataOnly` remains the default, untrusted callers still
must use it, and only the store's audited safe-display path can retain title or
body text. The service forwards one draft to one store call and exposes only the
redacted record returned by the durable snapshot. The repository remains local,
bare, hook-free, remote-free, and unencrypted as documented in the storage
contract.

## Atomic bulk behavior and coverage

Each bulk service request passes the complete validated ID vector to exactly one
store method. The service never loops into one commit per selected row. The
focused CppUnit additions cover:

- FIFO request IDs, snapshot generations, and record growth;
- draining accepted mutations and rejecting post-shutdown admission;
- deterministic compare-and-swap conflict refresh;
- three selected deletions producing exactly one additional Git commit; and
- metadata-only display text remaining absent from returned snapshots.

The existing notification target now wires 18 CppUnit cases. The fail-closed
source validator and its 18 mutation tests cover the new worker, snapshot,
configuration, lifetime, conflict, bulk, shutdown, and privacy markers. Until
the native target is compiled and run from this exact source, those CppUnit
cases are registered coverage, not runtime evidence.

## Next checkpoint

The visible stack and manager should consume only retained immutable snapshots
and submit service requests. Dialog conversion remains an explicit routing
decision: prompts that collect input, confirm destructive actions, handle
credentials, or enforce security keep their modal semantics even when their
Windows surface uses the bottom-right notification-form profile.
