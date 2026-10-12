# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | kerberoast:credentialAccess, ciRunner:exploitPublicApp |
| backupHost:lateralMovement | OR | ssoLogin:authenticate, browserStore:credentialAccess |
| browserStore:credentialAccess | OR | wifiGuest:initialAccess, vpnGateway:initialAccess, mailClient:exploitPublicApp |
| ciRunner:exploitPublicApp | OR | internet:initialAccess, supplychain:initialAccess, exposedApi:initialAccess |
| codeRepo:collection | OR | monitoringHost:lateralMovement, jumpHost:lateralMovement |
| configSecret:credentialAccess | OR | vpnGateway:initialAccess, ciRunner:exploitPublicApp |
| containerHost:execution | OR | exposedApi:initialAccess, supplychain:initialAccess, internet:initialAccess |
| crownData:exfiltrate | OR | codeRepo:collection, dbReplica:collection, shareMount:collection, vaultRead:collection |
| dbLogin:authenticate | AND | mailClient:exploitPublicApp, configSecret:credentialAccess |
| dbReplica:collection | OR | localAdmin:privilegeEscalation, serviceAccount:privilegeEscalation |
| domainAdmin:privilegeEscalation | AND | jumpHost:lateralMovement, rdpLogin:authenticate |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | tokenCache:credentialAccess |
| hypervisor:privilegeEscalation | AND | ssoLogin:authenticate, printServer:lateralMovement |
| internet:initialAccess | OR | — (entry) |
| iotDevice:exploitPublicApp | OR | supplychain:initialAccess, internet:initialAccess |
| jumpHost:lateralMovement | OR | dbLogin:authenticate |
| kerberoast:credentialAccess | OR | phishing:initialAccess |
| localAdmin:privilegeEscalation | AND | monitoringHost:lateralMovement, backupHost:lateralMovement |
| mailArchive:collection | OR | secretsManager:privilegeEscalation, serviceAccount:privilegeEscalation |
| mailClient:exploitPublicApp | OR | exposedApi:initialAccess, phishing:initialAccess |
| monitoringHost:lateralMovement | OR | configSecret:credentialAccess, ssoLogin:authenticate, dbLogin:authenticate |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | ssoLogin:authenticate, kerberoast:credentialAccess, tokenCache:credentialAccess |
| rdpLogin:authenticate | AND | kerberoast:credentialAccess, tokenCache:credentialAccess |
| secretsManager:privilegeEscalation | AND | vpnSession:authenticate, ssoLogin:authenticate |
| serviceAccount:privilegeEscalation | AND | fileServer:lateralMovement, monitoringHost:lateralMovement |
| shareMount:collection | OR | secretsManager:privilegeEscalation |
| sshKey:credentialAccess | OR | containerHost:execution, internet:initialAccess, workstation:exploitPublicApp |
| ssoLogin:authenticate | AND | ciRunner:exploitPublicApp, tokenCache:credentialAccess |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | iotDevice:exploitPublicApp, workstation:exploitPublicApp, supplychain:initialAccess |
| vaultRead:collection | OR | jumpHost:lateralMovement |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | mailClient:exploitPublicApp, browserStore:credentialAccess |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:exploitPublicApp | OR | phishing:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess |

## Question
A single point of failure is one step that, if the defender blocks it on its own, makes the target unreachable. How many of the steps (excluding footholds and the target) are single points of failure?
