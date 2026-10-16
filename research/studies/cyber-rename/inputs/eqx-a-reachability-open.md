# Multi-stage intrusion model: Struts CVE-2017-5638 and the 2017 Equifax breach

The breach advances through six ordered stages; the attacker wins when `exfiltrated` becomes true. Each technique crosses one stage and can be used only when the previous stage is reached and none of its blocking controls is deployed.

**Stages in order**: foothold -> recon -> creds -> lateral -> db_access -> exfiltrated (goal: exfiltrated)

**Controls** (each deployed control blocks the techniques listed against it):
- credential_vaulting: steal_config_credentials
- db_access_control: query_pii_database
- dns_monitoring: exfiltrate_over_dns
- edr: dump_process_memory
- email_filtering: spearphish_employee
- network_segmentation: smb_lateral_movement
- patch_struts: exploit_struts_cve_2017_5638
- proxy_tls_inspection: exfiltrate_over_https
- replica_isolation: read_database_replica
- security_awareness: spearphish_employee
- vpn_mfa: vpn_pivot
- waf: exploit_struts_cve_2017_5638

**Deployed controls**: email_filtering, security_awareness

**Techniques**:
- `exploit_struts_cve_2017_5638` — crosses foothold (after start); blocked by patch_struts, waf
- `spearphish_employee` — crosses foothold (after start); blocked by email_filtering, security_awareness
- `internal_reconnaissance` — crosses recon (after foothold); blocked by (nothing)
- `steal_config_credentials` — crosses creds (after recon); blocked by credential_vaulting
- `dump_process_memory` — crosses creds (after recon); blocked by edr
- `smb_lateral_movement` — crosses lateral (after creds); blocked by network_segmentation
- `vpn_pivot` — crosses lateral (after creds); blocked by vpn_mfa
- `query_pii_database` — crosses db_access (after lateral); blocked by db_access_control
- `read_database_replica` — crosses db_access (after lateral); blocked by replica_isolation
- `exfiltrate_over_dns` — crosses exfiltrated (after db_access); blocked by dns_monitoring
- `exfiltrate_over_https` — crosses exfiltrated (after db_access); blocked by proxy_tls_inspection

## Question
With the deployed controls above in place, can the attacker still reach data exfiltration?
