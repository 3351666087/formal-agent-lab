# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | iotDevice:exploitPublicApp, kerberoast:credentialAccess |
| backupHost:lateralMovement | OR | configSecret:credentialAccess |
| ciRunner:execution | OR | wifiGuest:initialAccess, supplychain:initialAccess |
| codeRepo:collection | OR | jumpHost:lateralMovement, hypervisor:privilegeEscalation |
| configSecret:credentialAccess | OR | phishing:initialAccess |
| containerHost:execution | OR | wifiGuest:initialAccess, vpnGateway:initialAccess |
| crownData:exfiltrate | OR | codeRepo:collection, dbReplica:collection, mailArchive:collection, vaultRead:collection |
| dbLogin:authenticate | AND | sshKey:credentialAccess, mailClient:exploitPublicApp |
| dbReplica:collection | OR | monitoringHost:lateralMovement, hypervisor:privilegeEscalation, printServer:lateralMovement |
| domainAdmin:privilegeEscalation | AND | dbLogin:authenticate, vpnSession:authenticate |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | memoryDump:credentialAccess, tokenCache:credentialAccess |
| hypervisor:privilegeEscalation | AND | printServer:lateralMovement, jumpHost:lateralMovement |
| internet:initialAccess | OR | — (entry) |
| iotDevice:exploitPublicApp | OR | supplychain:initialAccess, phishing:initialAccess, wifiGuest:initialAccess |
| jumpHost:lateralMovement | OR | ssoLogin:authenticate, apiToken:authenticate |
| kerberoast:credentialAccess | OR | ciRunner:execution, exposedApi:initialAccess, vpnGateway:initialAccess |
| localAdmin:privilegeEscalation | AND | jumpHost:lateralMovement, apiToken:authenticate |
| mailArchive:collection | OR | backupHost:lateralMovement, secretsManager:privilegeEscalation, hypervisor:privilegeEscalation |
| mailClient:exploitPublicApp | OR | wifiGuest:initialAccess, vpnGateway:initialAccess |
| memoryDump:credentialAccess | OR | containerHost:execution, ciRunner:execution, mailClient:exploitPublicApp |
| monitoringHost:lateralMovement | OR | memoryDump:credentialAccess, apiToken:authenticate, vpnSession:authenticate |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | dbLogin:authenticate, ssoLogin:authenticate |
| rdpLogin:authenticate | AND | memoryDump:credentialAccess, iotDevice:exploitPublicApp |
| secretsManager:privilegeEscalation | AND | dbLogin:authenticate, apiToken:authenticate |
| serviceAccount:privilegeEscalation | AND | ssoLogin:authenticate, jumpHost:lateralMovement |
| shareMount:collection | OR | printServer:lateralMovement |
| sshKey:credentialAccess | OR | mailClient:exploitPublicApp, wifiGuest:initialAccess |
| ssoLogin:authenticate | AND | mailClient:exploitPublicApp, tokenCache:credentialAccess |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | supplychain:initialAccess, iotDevice:exploitPublicApp, phishing:initialAccess |
| vaultRead:collection | OR | printServer:lateralMovement |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | ciRunner:execution, kerberoast:credentialAccess |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:exploitPublicApp | OR | phishing:initialAccess, internet:initialAccess |

## Question
A single point of failure is one step that, if the defender blocks it on its own, makes the target unreachable. How many of the steps (excluding footholds and the target) are single points of failure?
