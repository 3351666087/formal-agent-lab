# Fidelity to the source models, and documented deviations

Each attack model reproduces a published / standardised state machine. This file records,
per model, the authoritative source and every place our encoding departs from it, so the
modelling choices are auditable rather than asserted.

## A — TCP connection (RFC 793), KORG half-open attack

**Authoritative source.** The KORG TCP model, `demo/TCP/TCP.pml` in von Hippel et al.'s
AttackerSynthesis repository (the model the paper's TCP case study runs on), together with
`phi1.pml`. The PROMELA model has exactly the 11 RFC 793 states we use —
`CLOSED, LISTEN, SYN_SENT, SYN_RECEIVED, ESTABLISHED, FIN_WAIT_1, FIN_WAIT_2, CLOSE_WAIT,
CLOSING, LAST_ACK, TIME_WAIT` — and `phi1 = always(leftClosed implies !rightEstablished)`,
i.e. "no half-open connection". Its message alphabet is
`mtype = {SYN, FIN, ACK, ABORT, CLOSE, RST, OPEN}`.

**Edge provenance.** Every non-attack transition in `A_attack` corresponds to a branch of
`proctype TCP` in `TCP.pml` (active/passive open, the three-way handshake incl. simultaneous
open, the four-way teardown incl. simultaneous close via `CLOSING`, `TIME_WAIT`→`CLOSED`).

**Deviations (declared):**
1. *Single-automaton abstraction.* KORG models **two** `TCP` processes plus a network, and
   `phi1` is a predicate over the joint state (`leftClosed ∧ rightEstablished`). We model one
   peer's RFC 793 automaton and represent the half-open outcome as a dedicated `aborted`
   state. This is an abstraction of the joint half-open condition, not a second peer.
2. *`inject_rst`* is faithful: `RST` is in KORG's message alphabet and the synthesised
   attacker (the Daisy gadget) injects such messages.
3. *`inject_in_window_syn`* is an **addition** from RFC 5961 (an in-window SYN triggers a
   challenge-ACK / reset), included only to give the bad state a second independent
   mechanism. It is not in the KORG demo and is labelled as a separate mechanism.

## B — TLS 1.2 composite handshake (de Ruiter & Poll; SMACK / FREAK)

**Authoritative source.** de Ruiter & Poll, "Protocol State Fuzzing of TLS Implementations"
(USENIX Security 2015) — the happy-flow handshake of their Fig. 1 (ClientHello/ServerHello,
Certificate, [ServerKeyExchange], ServerHelloDone, ClientKeyExchange, ChangeCipherSpec,
Finished, then the server's ChangeCipherSpec+Finished, then ApplicationData); and Beurdouche
et al., "A Messy State of the Union" (IEEE S&P 2015), for FREAK.

**Edge provenance.** The happy-flow path and the RSA vs (EC)DHE split (the `ServerKeyExchange`
only in the DHE branch) follow TLS 1.2 (RFC 5246) and de Ruiter's learned machines.

**Deviations (declared):**
1. *FREAK* (`accept_export_grade_key`, `cert_received → weak_channel`) is a **stylised single
   edge**. The real FREAK is a server offering an export-grade RSA `ServerKeyExchange` in an
   RSA (non-export) suite and the client accepting it; we collapse that to one illegal edge
   into a weak-session state.
2. *Skip-auth* (`skip_cert_accept_data`, `hello_exchanged → weak_channel`) is a stylisation of
   the class of "accept a message / application data in a state that should not" bugs de
   Ruiter found; it is not one specific CVE.
3. We model TLS 1.2 (composite but still linear-ish), not the full multi-ciphersuite
   composite graph of SMACK, which is larger.

## C — WPA2 4-way + group-key handshakes (KRACK)

**Authoritative source.** Vanhoef & Piessens, "Key Reinstallation Attacks" (ACM CCS 2017),
Fig. 3 ("Supplicant 4-way handshake state machine as defined in the 802.11 standard
[1, Fig. 13-17]"): `PTK-INIT → PTK-START (Msg1) → PTK-NEGOTIATING (Msg3, MIC ok, not replayed;
install PTK, send Msg4) → PTK-DONE (unconditional; MLME-SETKEYS)`, with rekey edges on Msg1.
The paper states the same technique attacks the group-key handshake.

**Edge provenance.** The four PTK states and their edges are exactly Fig. 3. The group-key
handshake (`gtk_rekeying`, `gtk_done`) is the 802.11 two-message group-key handshake the paper
also targets.

**Deviations (declared):**
1. *Reinstallation as a distinct bad state.* In Fig. 3 the PTK reinstallation is the **back
   edge** `PTK-DONE → PTK-NEGOTIATING` taken on a replayed Msg3 (re-entering the install
   state). We instead route both the replayed-Msg3 (PTK) and replayed-group-Msg1 (GTK)
   reinstallations into a single dedicated `key_reinstalled` state, so the model has one bad
   state reachable by two independent mechanisms. The triggering conditions are unchanged; the
   target state is renamed/merged.

## What would raise fidelity further (not done here)

* Reuse KORG's PROMELA `P` directly and check our LTS against it by (bi)simulation in SPIN,
  rather than re-encoding the RFC 793 automaton by hand.
* Model TCP as the two-peer product so `phi1` is checked over the joint state verbatim.
* Use SMACK's full composite multi-ciphersuite machine and a specific FREAK CVE trace.
* Keep KRACK's reinstallation as the Fig. 3 back-edge instead of a merged bad state.
