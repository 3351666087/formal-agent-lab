# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | containerHost:execution, tokenCache:credentialAccess |
| appServer:lateralMovement | OR | dbLogin:authenticate |
| backupHost:lateralMovement | OR | browserStore:credentialAccess, tokenCache:credentialAccess |
| browserStore:credentialAccess | OR | workstation:exploitPublicApp, dmzWeb:execution |
| ciRunner:execution | OR | phishing:initialAccess |
| codeRepo:collection | OR | monitoringHost:lateralMovement, appServer:lateralMovement |
| configSecret:credentialAccess | OR | iotDevice:exploitPublicApp |
| containerHost:execution | OR | supplychain:initialAccess, internet:initialAccess, exposedApi:initialAccess |
| crownData:exfiltrate | OR | vaultRead:collection, shareMount:collection, dbReplica:collection, mailArchive:collection |
| dbLogin:authenticate | AND | iotDevice:exploitPublicApp, tokenCache:credentialAccess |
| dbReplica:collection | OR | fileServer:lateralMovement, jumpHost:lateralMovement, serviceAccount:privilegeEscalation |
| dmzWeb:execution | OR | exposedApi:initialAccess, wifiGuest:initialAccess |
| domainAdmin:privilegeEscalation | AND | fileServer:lateralMovement, ssoLogin:authenticate |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | configSecret:credentialAccess |
| hypervisor:privilegeEscalation | AND | dbLogin:authenticate, ssoLogin:authenticate |
| internet:initialAccess | OR | — (entry) |
| iotDevice:exploitPublicApp | OR | wifiGuest:initialAccess, internet:initialAccess |
| jumpHost:lateralMovement | OR | ssoLogin:authenticate, browserStore:credentialAccess |
| localAdmin:privilegeEscalation | AND | ssoLogin:authenticate, backupHost:lateralMovement |
| mailArchive:collection | OR | hypervisor:privilegeEscalation, jumpHost:lateralMovement |
| memoryDump:credentialAccess | OR | wifiGuest:initialAccess, workstation:exploitPublicApp, exposedApi:initialAccess |
| monitoringHost:lateralMovement | OR | tokenCache:credentialAccess, configSecret:credentialAccess |
| phishing:initialAccess | OR | — (entry) |
| rdpLogin:authenticate | AND | browserStore:credentialAccess, iotDevice:exploitPublicApp |
| secretsManager:privilegeEscalation | AND | ssoLogin:authenticate, dbLogin:authenticate |
| serviceAccount:privilegeEscalation | AND | rdpLogin:authenticate, fileServer:lateralMovement |
| shareMount:collection | OR | jumpHost:lateralMovement |
| sshKey:credentialAccess | OR | phishing:initialAccess, ciRunner:execution, dmzWeb:execution |
| ssoLogin:authenticate | AND | sshKey:credentialAccess, browserStore:credentialAccess |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | iotDevice:exploitPublicApp |
| vaultRead:collection | OR | serviceAccount:privilegeEscalation, jumpHost:lateralMovement |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | sshKey:credentialAccess, tokenCache:credentialAccess |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:exploitPublicApp | OR | wifiGuest:initialAccess, supplychain:initialAccess, exposedApi:initialAccess |

## Question
A single point of failure is one step that, if the defender blocks it on its own, makes the target unreachable. How many of the steps (excluding footholds and the target) are single points of failure?
