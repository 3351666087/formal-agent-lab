# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | containerHost:execution, kerberoast:credentialAccess |
| appServer:lateralMovement | OR | dbLogin:authenticate, memoryDump:credentialAccess, tokenCache:credentialAccess |
| backupHost:lateralMovement | OR | vpnSession:authenticate, memoryDump:credentialAccess |
| browserStore:credentialAccess | OR | workstation:execution |
| ciRunner:exploitPublicApp | OR | wifiGuest:initialAccess, vpnGateway:initialAccess, supplychain:initialAccess |
| codeRepo:collection | OR | secretsManager:privilegeEscalation, fileServer:lateralMovement |
| configSecret:credentialAccess | OR | vpnGateway:initialAccess, ciRunner:exploitPublicApp |
| containerHost:execution | OR | phishing:initialAccess, supplychain:initialAccess |
| crownData:exfiltrate | OR | dbReplica:collection, vaultRead:collection, codeRepo:collection, mailArchive:collection |
| dbLogin:authenticate | AND | mailClient:execution, iotDevice:exploitPublicApp |
| dbReplica:collection | OR | secretsManager:privilegeEscalation, domainAdmin:privilegeEscalation, hypervisor:privilegeEscalation |
| domainAdmin:privilegeEscalation | AND | apiToken:authenticate, rdpLogin:authenticate |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | dbLogin:authenticate, tokenCache:credentialAccess |
| hypervisor:privilegeEscalation | AND | printServer:lateralMovement, monitoringHost:lateralMovement |
| internet:initialAccess | OR | — (entry) |
| iotDevice:exploitPublicApp | OR | exposedApi:initialAccess, phishing:initialAccess, supplychain:initialAccess |
| kerberoast:credentialAccess | OR | supplychain:initialAccess, exposedApi:initialAccess |
| localAdmin:privilegeEscalation | AND | backupHost:lateralMovement, ssoLogin:authenticate |
| mailArchive:collection | OR | domainAdmin:privilegeEscalation |
| mailClient:execution | OR | internet:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess |
| memoryDump:credentialAccess | OR | internet:initialAccess |
| monitoringHost:lateralMovement | OR | dbLogin:authenticate, configSecret:credentialAccess |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | dbLogin:authenticate, vpnSession:authenticate |
| rdpLogin:authenticate | AND | iotDevice:exploitPublicApp, workstation:execution |
| secretsManager:privilegeEscalation | AND | rdpLogin:authenticate, fileServer:lateralMovement |
| serviceAccount:privilegeEscalation | AND | appServer:lateralMovement, backupHost:lateralMovement |
| shareMount:collection | OR | secretsManager:privilegeEscalation, appServer:lateralMovement, localAdmin:privilegeEscalation |
| ssoLogin:authenticate | AND | workstation:execution, ciRunner:exploitPublicApp |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | supplychain:initialAccess, wifiGuest:initialAccess, containerHost:execution |
| vaultRead:collection | OR | secretsManager:privilegeEscalation |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | containerHost:execution, configSecret:credentialAccess |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:execution | OR | supplychain:initialAccess, exposedApi:initialAccess, internet:initialAccess |

## Question
A single point of failure is one step that, if the defender blocks it on its own, makes the target unreachable. How many of the steps (excluding footholds and the target) are single points of failure?
