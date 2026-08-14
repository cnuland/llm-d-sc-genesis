# Review of the Agentic ASDLC

The proposed asymmetric flow is a strong fit for llm-d-sc: frontier research/specification, a local implementation workhorse, independent review, deterministic state transitions, clean-room GitHub CI, prod-like OpenShift validation, and human merge authority.

The most important adaptation for this project is that **SPECIFIED -> TEST-DESIGNED must be a hard gate**. llm-d-sc sits in a latency-sensitive network path and is state/cache/concurrency sensitive. A patch can look correct while failing under overload, restart, cache loss, model revision changes, or real topology latency.

Before implementation, every feature spec must define:
- state ownership;
- failure behavior;
- overload/deadline behavior;
- security/privacy behavior;
- performance measurement plan;
- exact acceptance criteria;
- test IDs proving each criterion.

Performance cannot be postponed until the end, but it must be layered:
- normal CI proves algorithmic invariants;
- CI may retain non-blocking microbenchmark trends;
- repeatable OpenShift hardware profiles own hard topology/runtime latency gates.

Failure testing is first-class. Every meaningful feature must answer: missing model, corrupt model, full queue, expired deadline, caller cancellation, cache loss, process restart, partial signal failure, bad candidate revision, and overload recovery.

The dummy Praxis boundary belongs in the MVP. It prevents the Rust service from accidentally absorbing routing responsibilities while giving the implementation agent a real integration target early.

The model artifact also belongs in MVP validation. The runtime image and model image remain distinct, and the classifier is proven to load from a self-contained OCI artifact with external model-download egress disabled.

Bad worker prompt:

> Implement caching and make it fast.

Good worker prompt:

> Implement AC-006 / U-040. First write a test proving a cache hit performs zero tokenizer calls and zero runtime forwards. Show RED because the result cache does not exist. Implement the smallest cache path. Run affected tests and stop.

This preserves the original principle: automate evidence, not autonomy.
