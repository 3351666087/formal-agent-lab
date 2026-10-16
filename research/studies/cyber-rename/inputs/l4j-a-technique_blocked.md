# Attack chain model: CVE-2021-44228 (Log4Shell), Log4j 2.14.1

The attacker wins when `rce_achieved` becomes true. Each technique can be used only when its **requires** condition holds; using it makes its **achieves** variables true. A deployed mitigation makes its constant true and so blocks the techniques that require it to be false.

**State variables** (all start false): attacker_input_logged, jndi_lookup_triggered, attacker_endpoint_contacted, malicious_reference_returned, remote_class_loaded, rce_achieved

**Configuration constants**: message_lookups=true, jndi_enabled=true, jndi_class_present=true, egress_allowed=true, input_sanitized=false, trust_url_codebase=false, gadget_present=true

**Deployed mitigations**: none

**Techniques**:
- `inject_jndi_string` — requires NOT input_sanitized; achieves attacker_input_logged
- `trigger_jndi_lookup` — requires (attacker_input_logged AND message_lookups AND jndi_class_present); achieves jndi_lookup_triggered
- `resolve_to_attacker` — requires (jndi_lookup_triggered AND jndi_enabled AND egress_allowed); achieves attacker_endpoint_contacted
- `return_malicious_reference` — requires attacker_endpoint_contacted; achieves malicious_reference_returned
- `load_class_via_reference` — requires (malicious_reference_returned AND trust_url_codebase); achieves remote_class_loaded
- `load_class_via_gadget` — requires (malicious_reference_returned AND gadget_present); achieves remote_class_loaded
- `execute_payload` — requires remote_class_loaded; achieves rce_achieved

## Current state
These variables are currently true: . All other state variables are false and no mitigations are deployed.


## Question
Is the technique `resolve_to_attacker` applicable right now?
