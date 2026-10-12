# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | configSecret:credentialAccess, dmzWeb:exploitPublicApp |
| appServer:lateralMovement | OR | ssoLogin:authenticate, memoryDump:credentialAccess |
| backupHost:lateralMovement | OR | dbLogin:authenticate, browserStore:credentialAccess |
| browserStore:credentialAccess | OR | iotDevice:execution, dmzWeb:exploitPublicApp |
| ciRunner:execution | OR | wifiGuest:initialAccess, vpnGateway:initialAccess, internet:initialAccess |
| codeRepo:collection | OR | serviceAccount:privilegeEscalation |
| configSecret:credentialAccess | OR | dmzWeb:exploitPublicApp |
| crownData:exfiltrate | OR | vaultRead:collection, shareMount:collection, dbReplica:collection, codeRepo:collection |
| dbLogin:authenticate | AND | dmzWeb:exploitPublicApp, memoryDump:credentialAccess |
| dbReplica:collection | OR | serviceAccount:privilegeEscalation |
| dmzWeb:exploitPublicApp | OR | supplychain:initialAccess |
| domainAdmin:privilegeEscalation | AND | monitoringHost:lateralMovement, fileServer:lateralMovement |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | ssoLogin:authenticate |
| hypervisor:privilegeEscalation | AND | ssoLogin:authenticate, monitoringHost:lateralMovement |
| internet:initialAccess | OR | — (entry) |
| iotDevice:execution | OR | internet:initialAccess, exposedApi:initialAccess |
| kerberoast:credentialAccess | OR | wifiGuest:initialAccess |
| localAdmin:privilegeEscalation | AND | appServer:lateralMovement, rdpLogin:authenticate |
| mailArchive:collection | OR | fileServer:lateralMovement, printServer:lateralMovement |
| mailClient:exploitPublicApp | OR | supplychain:initialAccess, internet:initialAccess |
| memoryDump:credentialAccess | OR | vpnGateway:initialAccess |
| monitoringHost:lateralMovement | OR | kerberoast:credentialAccess, browserStore:credentialAccess, vpnSession:authenticate |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | tokenCache:credentialAccess, browserStore:credentialAccess |
| rdpLogin:authenticate | AND | configSecret:credentialAccess, browserStore:credentialAccess |
| secretsManager:privilegeEscalation | AND | monitoringHost:lateralMovement, fileServer:lateralMovement |
| serviceAccount:privilegeEscalation | AND | ssoLogin:authenticate, vpnSession:authenticate |
| shareMount:collection | OR | backupHost:lateralMovement |
| ssoLogin:authenticate | AND | ciRunner:execution, kerberoast:credentialAccess |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | phishing:initialAccess, ciRunner:execution |
| vaultRead:collection | OR | secretsManager:privilegeEscalation |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | workstation:exploitPublicApp, configSecret:credentialAccess |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:exploitPublicApp | OR | wifiGuest:initialAccess, vpnGateway:initialAccess |

## Question
A single point of failure is one step that, if the defender blocks it on its own, makes the target unreachable. How many of the steps (excluding footholds and the target) are single points of failure?
