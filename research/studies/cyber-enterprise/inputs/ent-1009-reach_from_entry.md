# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | dmzWeb:execution, tokenCache:credentialAccess |
| appServer:lateralMovement | OR | browserStore:credentialAccess, dbLogin:authenticate, vpnSession:authenticate |
| backupHost:lateralMovement | OR | apiToken:authenticate, ssoLogin:authenticate |
| browserStore:credentialAccess | OR | workstation:exploitPublicApp, iotDevice:execution, phishing:initialAccess |
| ciRunner:exploitPublicApp | OR | exposedApi:initialAccess |
| codeRepo:collection | OR | domainAdmin:privilegeEscalation, appServer:lateralMovement, hypervisor:privilegeEscalation |
| configSecret:credentialAccess | OR | containerHost:execution, wifiGuest:initialAccess |
| containerHost:execution | OR | wifiGuest:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess |
| crownData:exfiltrate | OR | shareMount:collection, vaultRead:collection, dbReplica:collection, codeRepo:collection |
| dbLogin:authenticate | AND | browserStore:credentialAccess, workstation:exploitPublicApp |
| dbReplica:collection | OR | domainAdmin:privilegeEscalation |
| dmzWeb:execution | OR | vpnGateway:initialAccess |
| domainAdmin:privilegeEscalation | AND | fileServer:lateralMovement, dbLogin:authenticate |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | configSecret:credentialAccess |
| hypervisor:privilegeEscalation | AND | printServer:lateralMovement, jumpHost:lateralMovement |
| internet:initialAccess | OR | — (entry) |
| iotDevice:execution | OR | supplychain:initialAccess |
| jumpHost:lateralMovement | OR | sshKey:credentialAccess, tokenCache:credentialAccess, ssoLogin:authenticate |
| localAdmin:privilegeEscalation | AND | backupHost:lateralMovement, vpnSession:authenticate |
| mailArchive:collection | OR | jumpHost:lateralMovement, serviceAccount:privilegeEscalation, fileServer:lateralMovement |
| memoryDump:credentialAccess | OR | workstation:exploitPublicApp, supplychain:initialAccess, containerHost:execution |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | tokenCache:credentialAccess |
| rdpLogin:authenticate | AND | containerHost:execution, memoryDump:credentialAccess |
| secretsManager:privilegeEscalation | AND | jumpHost:lateralMovement, backupHost:lateralMovement |
| serviceAccount:privilegeEscalation | AND | fileServer:lateralMovement, backupHost:lateralMovement |
| shareMount:collection | OR | backupHost:lateralMovement, serviceAccount:privilegeEscalation, printServer:lateralMovement |
| sshKey:credentialAccess | OR | exposedApi:initialAccess |
| ssoLogin:authenticate | AND | iotDevice:execution, memoryDump:credentialAccess |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | iotDevice:execution, vpnGateway:initialAccess, workstation:exploitPublicApp |
| vaultRead:collection | OR | secretsManager:privilegeEscalation |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | containerHost:execution, browserStore:credentialAccess |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:exploitPublicApp | OR | internet:initialAccess |

## Attacker constraint
The attacker has only ONE foothold available: `wifiGuest:initialAccess`. The other footholds cannot be used.

## Question
From that single foothold alone, can the attacker reach the target?
