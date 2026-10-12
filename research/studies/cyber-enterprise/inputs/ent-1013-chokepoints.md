# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | browserStore:credentialAccess, dmzWeb:execution |
| backupHost:lateralMovement | OR | sshKey:credentialAccess, dbLogin:authenticate |
| browserStore:credentialAccess | OR | internet:initialAccess |
| ciRunner:exploitPublicApp | OR | exposedApi:initialAccess |
| codeRepo:collection | OR | fileServer:lateralMovement |
| containerHost:execution | OR | supplychain:initialAccess, internet:initialAccess |
| crownData:exfiltrate | OR | vaultRead:collection, mailArchive:collection, codeRepo:collection, shareMount:collection |
| dbLogin:authenticate | AND | dmzWeb:execution, tokenCache:credentialAccess |
| dbReplica:collection | OR | fileServer:lateralMovement, hypervisor:privilegeEscalation |
| dmzWeb:execution | OR | wifiGuest:initialAccess, exposedApi:initialAccess, phishing:initialAccess |
| domainAdmin:privilegeEscalation | AND | rdpLogin:authenticate, jumpHost:lateralMovement |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | sshKey:credentialAccess, rdpLogin:authenticate, ssoLogin:authenticate |
| hypervisor:privilegeEscalation | AND | dbLogin:authenticate, ssoLogin:authenticate |
| internet:initialAccess | OR | — (entry) |
| iotDevice:execution | OR | phishing:initialAccess, exposedApi:initialAccess, vpnGateway:initialAccess |
| jumpHost:lateralMovement | OR | dbLogin:authenticate |
| kerberoast:credentialAccess | OR | wifiGuest:initialAccess |
| localAdmin:privilegeEscalation | AND | dbLogin:authenticate, vpnSession:authenticate |
| mailArchive:collection | OR | fileServer:lateralMovement, jumpHost:lateralMovement |
| memoryDump:credentialAccess | OR | supplychain:initialAccess, vpnGateway:initialAccess |
| monitoringHost:lateralMovement | OR | memoryDump:credentialAccess, dbLogin:authenticate |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | rdpLogin:authenticate, memoryDump:credentialAccess |
| rdpLogin:authenticate | AND | containerHost:execution, tokenCache:credentialAccess |
| secretsManager:privilegeEscalation | AND | dbLogin:authenticate, ssoLogin:authenticate |
| serviceAccount:privilegeEscalation | AND | jumpHost:lateralMovement, fileServer:lateralMovement |
| shareMount:collection | OR | jumpHost:lateralMovement |
| sshKey:credentialAccess | OR | iotDevice:execution, containerHost:execution, dmzWeb:execution |
| ssoLogin:authenticate | AND | memoryDump:credentialAccess, dmzWeb:execution |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | vpnGateway:initialAccess |
| vaultRead:collection | OR | serviceAccount:privilegeEscalation, secretsManager:privilegeEscalation, printServer:lateralMovement |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | containerHost:execution, iotDevice:execution |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:exploitPublicApp | OR | wifiGuest:initialAccess, vpnGateway:initialAccess, supplychain:initialAccess |

## Question
A single point of failure is one step that, if the defender blocks it on its own, makes the target unreachable. How many of the steps (excluding footholds and the target) are single points of failure?
