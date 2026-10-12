# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | dmzWeb:exploitPublicApp, tokenCache:credentialAccess |
| backupHost:lateralMovement | OR | kerberoast:credentialAccess |
| browserStore:credentialAccess | OR | internet:initialAccess, iotDevice:execution, phishing:initialAccess |
| codeRepo:collection | OR | fileServer:lateralMovement, localAdmin:privilegeEscalation, hypervisor:privilegeEscalation |
| configSecret:credentialAccess | OR | vpnGateway:initialAccess |
| containerHost:execution | OR | wifiGuest:initialAccess, supplychain:initialAccess, phishing:initialAccess |
| crownData:exfiltrate | OR | codeRepo:collection, mailArchive:collection, shareMount:collection, dbReplica:collection |
| dbLogin:authenticate | AND | iotDevice:execution, sshKey:credentialAccess |
| dbReplica:collection | OR | monitoringHost:lateralMovement, hypervisor:privilegeEscalation |
| dmzWeb:exploitPublicApp | OR | exposedApi:initialAccess, supplychain:initialAccess |
| domainAdmin:privilegeEscalation | AND | rdpLogin:authenticate, apiToken:authenticate |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | vpnSession:authenticate, browserStore:credentialAccess |
| hypervisor:privilegeEscalation | AND | backupHost:lateralMovement, rdpLogin:authenticate |
| internet:initialAccess | OR | — (entry) |
| iotDevice:execution | OR | supplychain:initialAccess, vpnGateway:initialAccess, phishing:initialAccess |
| jumpHost:lateralMovement | OR | tokenCache:credentialAccess |
| kerberoast:credentialAccess | OR | vpnGateway:initialAccess |
| localAdmin:privilegeEscalation | AND | ssoLogin:authenticate, dbLogin:authenticate |
| mailArchive:collection | OR | printServer:lateralMovement |
| mailClient:execution | OR | exposedApi:initialAccess, supplychain:initialAccess, internet:initialAccess |
| monitoringHost:lateralMovement | OR | vpnSession:authenticate |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | tokenCache:credentialAccess, vpnSession:authenticate, apiToken:authenticate |
| rdpLogin:authenticate | AND | dmzWeb:exploitPublicApp, mailClient:execution |
| secretsManager:privilegeEscalation | AND | monitoringHost:lateralMovement, rdpLogin:authenticate |
| serviceAccount:privilegeEscalation | AND | monitoringHost:lateralMovement, ssoLogin:authenticate |
| shareMount:collection | OR | serviceAccount:privilegeEscalation, secretsManager:privilegeEscalation |
| sshKey:credentialAccess | OR | exposedApi:initialAccess |
| ssoLogin:authenticate | AND | dmzWeb:exploitPublicApp, tokenCache:credentialAccess |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | containerHost:execution |
| vaultRead:collection | OR | fileServer:lateralMovement |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | sshKey:credentialAccess, mailClient:execution |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:exploitPublicApp | OR | wifiGuest:initialAccess, exposedApi:initialAccess, supplychain:initialAccess |

## Question
A single point of failure is one step that, if the defender blocks it on its own, makes the target unreachable. How many of the steps (excluding footholds and the target) are single points of failure?
