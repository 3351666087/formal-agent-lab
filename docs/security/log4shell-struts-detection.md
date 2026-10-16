# Detection & mitigation — Log4Shell (CVE-2021-44228) and Struts S2-045 (CVE-2017-5638)

Defensive companion to the formal models in `packages/domain-mal/cve_2021_44228.py` and
`packages/domain-mal/cve_2017_5638.py`. It gives detection signatures for each attack stage and the fixes that cut
the chain — the blue-team side of the two attack/defence models. No exploit code here.

The formal models prove *where* to cut: the Log4Shell chain is six sequential links and **any one control breaks it**;
the Struts/Equifax chain is multi-stage and the **minimum two controls** (both branches of one stage) stop exfiltration.
Detection should target the earliest links you can see.

## 1. Log4Shell (CVE-2021-44228)

### Inbound — the JNDI-lookup trigger (model stage `attacker_input_logged` → `jndi_lookup_triggered`)
Any attacker-controllable value that gets logged can carry the payload: HTTP headers (`User-Agent`, `X-Api-Version`,
`Referer`, `X-Forwarded-For`), the URI/query, form fields, usernames, TLS SNI, etc.

- Core regex (case-insensitive), covering the obfuscations seen in the wild:
  `(?i)\$\{[^}]*(jndi|j\$\{|\$\{lower:j|\$\{upper:j|\$\{::-j)[^}]*\}`
- Simpler high-recall prefilter: the literal substring `${jndi:` and the schemes `ldap:`, `ldaps:`, `rmi:`, `dns:`,
  `nis:`, `iiop:`, `corba:`, `nds:` following it.
- Common obfuscations to normalise before matching: `${${lower:j}ndi:…}`, `${${::-j}${::-n}${::-d}${::-i}:…}`,
  `${base64:…}`, nested `${…}`.

### Egress — the call-out (model stage `attacker_endpoint_contacted`)
This is the strongest post-trigger signal and hard for an attacker to hide:
- Any application/JVM node making **outbound LDAP (389/636), RMI (1099, or ephemeral), or unexpected DNS** to a
  non-allowlisted host, especially right after a request.
- Egress-filter deny logs for those ports from app subnets.

### Host — code execution (model stage `remote_class_loaded` → `rce_achieved`)
- A Java process spawning child processes it never normally does: `java → sh|bash|cmd|powershell|curl|wget|nc`.
- New/unexpected classloaders pulling from a remote `http(s)://` codebase.

### Sigma-style sketch
```yaml
title: Log4Shell JNDI lookup in a logged field
logsource: { category: application }
detection:
  sel_payload:
    message|re: '(?i)\$\{[^}]*(jndi|\$\{lower:j|\$\{::-j)[^}]*\}'
  sel_egress:        # correlate within ~60s on the same host
    dest_port: [389, 636, 1099]
    direction: outbound
  condition: sel_payload or sel_egress
```

### Fix / controls (each cuts a model link)
- **Upgrade Log4j to ≥ 2.17.1** — removes message-lookup patterns and disables JNDI (cuts `trigger_jndi_lookup` and
  `resolve_to_attacker`). This is the real fix.
- Interim without upgrade: `-Dlog4j2.formatMsgNoLookups=true` (2.10+); delete the `JndiLookup` class from
  `log4j-core`; **block outbound LDAP/RMI** at the egress firewall; WAF-filter the payload; set
  `com.sun.jndi.ldap.object.trustURLCodebase=false` (default on modern JDKs).
- Verify a deployment is fixed, not just claimed: check the actual `log4j-core-*.jar` version on the classpath and
  the JDK build (pre-8u191 JDKs leave `trustURLCodebase` on, making the naive remote-class path exploitable).

## 2. Apache Struts S2-045 (CVE-2017-5638)

### Inbound — the OGNL-in-Content-Type trigger (model stage `foothold`)
The payload rides in the `Content-Type` (sometimes `Content-Disposition` / `Content-Length`) header, not the body.

- Match on `Content-Type` values that are **not** a valid multipart type **and** contain OGNL markers:
  `%{` or `${`, together with any of `(#_memberAccess`, `#context`, `@java.lang.Runtime@`, `@java.lang.ProcessBuilder@`,
  `ognl`, `#cmd=`, `multipart/form-data` immediately followed by `%{`.
- Regex sketch: `(?i)content-type:.*(%\{|\$\{).*(#_?memberaccess|runtime|processbuilder|#cmd)`

### Response / host
- Attacker PoCs commonly echo command output back in a **response header** — flag unusual response headers carrying
  command-like output.
- Tomcat/Struts worker spawning `sh|bash|cmd|powershell` — the RCE landing.

### Fix / controls (model controls)
- **Upgrade struts2-core to ≥ 2.5.10.1 (2.5 line) or ≥ 2.3.32 (2.3 line)** — the Jakarta Multipart parser no longer
  OGNL-evaluates error messages (`patch_struts`).
- Defence-in-depth per the Equifax lessons the model encodes: a WAF rule on the Content-Type (`waf`); **network
  segmentation** so a web-tier RCE cannot reach the databases (`segmentation`); credential vaulting (`credential_vaulting`);
  **egress filtering** on the DB tier (`exfiltration` cut); and working traffic monitoring (Equifax's lapsed cert is
  the modelled detection gap).
- Verify: check the actual `struts2-core-*.jar` version; 2.3.5–2.3.31 and 2.5–2.5.10 are vulnerable.

## How this ties back to the models
Each signature above maps to a technique/stage in the Z3-grounded models, and each fix maps to a defence constant the
model shows will cut the chain. The model answers "which single control is enough" (Log4Shell: any one of six;
Struts: two, both branches of one stage); detection tells you where to watch while you deploy them.
