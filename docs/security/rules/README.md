# Detection rules — Log4Shell (CVE-2021-44228) & Struts S2-045 (CVE-2017-5638)

Importable rules derived from [`../log4shell-struts-detection.md`](../log4shell-struts-detection.md) and mapped to the
formal models in `packages/domain-mal/cve_2021_44228.py` / `cve_2017_5638.py`. Defensive only.

## Sigma (`sigma/`)
Backend-agnostic. Convert to your SIEM with [sigma-cli / pySigma](https://github.com/SigmaHQ/sigma-cli), e.g.:
```bash
sigma convert -t splunk -p splunk_windows sigma/log4shell_jndi_lookup_cve_2021_44228.yml
sigma convert -t elasticsearch sigma/struts_s2_045_cve_2017_5638.yml
```
- `log4shell_jndi_lookup_cve_2021_44228.yml` — JNDI payload in HTTP request fields (logsource `webserver`; adjust the
  field names to your proxy/WAF schema).
- `log4shell_egress_ldap_rmi.yml` — outbound LDAP/RMI from the app tier (logsource `firewall`; **set `src_ip` to your
  real app subnets** before use).
- `struts_s2_045_cve_2017_5638.yml` — OGNL in `Content-Type`.

## Suricata (`suricata/local-log4shell-struts.rules`)
Private sid range `1000001+`, keywords valid on Suricata 5+. Deploy:
```bash
cp suricata/local-log4shell-struts.rules /etc/suricata/rules/
# add the file to rule-files: in suricata.yaml, then:
suricatasc -c reload-rules   # or restart
```

## Obfuscation note
The Log4Shell payload is heavily obfuscated in the wild (`${${lower:j}ndi:…}`, `${${::-j}…}`, base64, nesting). The
Sigma `keywords` list and the Suricata byte/pcre rules cover the common forms, but for high-recall matching normalise
the field first and apply the regex from the detection doc:
`(?i)\$\{[^}]{0,80}(jndi:|\$\{(lower|upper|env|sys|date|::-)[^}]*\})`
The **outbound LDAP/RMI** signal (sid 1000005 / the egress Sigma rule) is obfuscation-proof and the most reliable
confirmation.

## False positives
Security scanners and WAF self-tests will fire these; allowlist your scanners. The egress rule needs the app-tier
subnets scoped or it will match legitimate LDAP clients.
