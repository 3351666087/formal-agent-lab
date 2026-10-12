# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | sshKey:credentialAccess, ciRunner:exploitPublicApp |
| appServer:lateralMovement | OR | dbLogin:authenticate, rdpLogin:authenticate, configSecret:credentialAccess |
| backupHost:lateralMovement | OR | sshKey:credentialAccess |
| browserStore:credentialAccess | OR | wifiGuest:initialAccess, ciRunner:exploitPublicApp |
| ciRunner:exploitPublicApp | OR | internet:initialAccess, vpnGateway:initialAccess |
| codeRepo:collection | OR | fileServer:lateralMovement, secretsManager:privilegeEscalation |
| configSecret:credentialAccess | OR | containerHost:exploitPublicApp |
| containerHost:exploitPublicApp | OR | supplychain:initialAccess, wifiGuest:initialAccess |
| crownData:exfiltrate | OR | vaultRead:collection, mailArchive:collection, dbReplica:collection, shareMount:collection |
| dbLogin:authenticate | AND | dmzWeb:exploitPublicApp, kerberoast:credentialAccess |
| dbReplica:collection | OR | monitoringHost:lateralMovement |
| dmzWeb:exploitPublicApp | OR | exposedApi:initialAccess, internet:initialAccess |
| domainAdmin:privilegeEscalation | AND | fileServer:lateralMovement, ssoLogin:authenticate |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | ssoLogin:authenticate |
| hypervisor:privilegeEscalation | AND | printServer:lateralMovement, rdpLogin:authenticate |
| internet:initialAccess | OR | — (entry) |
| iotDevice:exploitPublicApp | OR | exposedApi:initialAccess, supplychain:initialAccess |
| kerberoast:credentialAccess | OR | wifiGuest:initialAccess, internet:initialAccess, iotDevice:exploitPublicApp |
| localAdmin:privilegeEscalation | AND | vpnSession:authenticate, appServer:lateralMovement |
| mailArchive:collection | OR | printServer:lateralMovement |
| mailClient:execution | OR | vpnGateway:initialAccess |
| memoryDump:credentialAccess | OR | iotDevice:exploitPublicApp |
| monitoringHost:lateralMovement | OR | rdpLogin:authenticate |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | memoryDump:credentialAccess |
| rdpLogin:authenticate | AND | memoryDump:credentialAccess, iotDevice:exploitPublicApp |
| secretsManager:privilegeEscalation | AND | apiToken:authenticate, vpnSession:authenticate |
| serviceAccount:privilegeEscalation | AND | printServer:lateralMovement, appServer:lateralMovement |
| shareMount:collection | OR | serviceAccount:privilegeEscalation, secretsManager:privilegeEscalation |
| sshKey:credentialAccess | OR | mailClient:execution |
| ssoLogin:authenticate | AND | mailClient:execution, browserStore:credentialAccess |
| supplychain:initialAccess | OR | — (entry) |
| vaultRead:collection | OR | serviceAccount:privilegeEscalation, printServer:lateralMovement, appServer:lateralMovement |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | memoryDump:credentialAccess, browserStore:credentialAccess |
| wifiGuest:initialAccess | OR | — (entry) |

## Question
A single point of failure is one step that, if the defender blocks it on its own, makes the target unreachable. How many of the steps (excluding footholds and the target) are single points of failure?
