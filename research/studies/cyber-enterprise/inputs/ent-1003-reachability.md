# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | mailClient:execution, kerberoast:credentialAccess |
| appServer:lateralMovement | OR | ssoLogin:authenticate |
| backupHost:lateralMovement | OR | dbLogin:authenticate |
| browserStore:credentialAccess | OR | exposedApi:initialAccess |
| ciRunner:exploitPublicApp | OR | supplychain:initialAccess |
| codeRepo:collection | OR | backupHost:lateralMovement, secretsManager:privilegeEscalation, jumpHost:lateralMovement |
| containerHost:exploitPublicApp | OR | wifiGuest:initialAccess |
| crownData:exfiltrate | OR | mailArchive:collection, vaultRead:collection, dbReplica:collection, codeRepo:collection |
| dbLogin:authenticate | AND | containerHost:exploitPublicApp, memoryDump:credentialAccess |
| dbReplica:collection | OR | appServer:lateralMovement, domainAdmin:privilegeEscalation |
| dmzWeb:exploitPublicApp | OR | supplychain:initialAccess, internet:initialAccess, vpnGateway:initialAccess |
| domainAdmin:privilegeEscalation | AND | dbLogin:authenticate, jumpHost:lateralMovement |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | browserStore:credentialAccess |
| hypervisor:privilegeEscalation | AND | fileServer:lateralMovement, appServer:lateralMovement |
| internet:initialAccess | OR | — (entry) |
| jumpHost:lateralMovement | OR | apiToken:authenticate, vpnSession:authenticate, memoryDump:credentialAccess |
| kerberoast:credentialAccess | OR | ciRunner:exploitPublicApp |
| localAdmin:privilegeEscalation | AND | dbLogin:authenticate, apiToken:authenticate |
| mailArchive:collection | OR | secretsManager:privilegeEscalation, jumpHost:lateralMovement, serviceAccount:privilegeEscalation |
| mailClient:execution | OR | phishing:initialAccess |
| memoryDump:credentialAccess | OR | mailClient:execution, vpnGateway:initialAccess, supplychain:initialAccess |
| monitoringHost:lateralMovement | OR | dbLogin:authenticate, vpnSession:authenticate, browserStore:credentialAccess |
| phishing:initialAccess | OR | — (entry) |
| rdpLogin:authenticate | AND | containerHost:exploitPublicApp, mailClient:execution |
| secretsManager:privilegeEscalation | AND | backupHost:lateralMovement, ssoLogin:authenticate |
| serviceAccount:privilegeEscalation | AND | jumpHost:lateralMovement, fileServer:lateralMovement |
| shareMount:collection | OR | appServer:lateralMovement, domainAdmin:privilegeEscalation, backupHost:lateralMovement |
| sshKey:credentialAccess | OR | workstation:execution |
| ssoLogin:authenticate | AND | memoryDump:credentialAccess, mailClient:execution |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | mailClient:execution |
| vaultRead:collection | OR | backupHost:lateralMovement |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | dmzWeb:exploitPublicApp, workstation:execution |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:execution | OR | internet:initialAccess, vpnGateway:initialAccess, supplychain:initialAccess |

## Deployed defences
The defender has blocked these steps (they can no longer be used): jumpHost:lateralMovement, memoryDump:credentialAccess.

## Question
With those defences in place, is the target still reachable?
