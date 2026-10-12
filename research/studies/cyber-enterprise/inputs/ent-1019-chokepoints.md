# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | workstation:execution, sshKey:credentialAccess |
| backupHost:lateralMovement | OR | vpnSession:authenticate, apiToken:authenticate, kerberoast:credentialAccess |
| browserStore:credentialAccess | OR | internet:initialAccess, phishing:initialAccess, mailClient:exploitPublicApp |
| ciRunner:exploitPublicApp | OR | internet:initialAccess |
| codeRepo:collection | OR | printServer:lateralMovement, domainAdmin:privilegeEscalation |
| configSecret:credentialAccess | OR | iotDevice:exploitPublicApp |
| containerHost:exploitPublicApp | OR | vpnGateway:initialAccess, supplychain:initialAccess |
| crownData:exfiltrate | OR | vaultRead:collection, codeRepo:collection, dbReplica:collection, mailArchive:collection |
| dbLogin:authenticate | AND | workstation:execution, mailClient:exploitPublicApp |
| dbReplica:collection | OR | serviceAccount:privilegeEscalation |
| domainAdmin:privilegeEscalation | AND | vpnSession:authenticate, dbLogin:authenticate |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | rdpLogin:authenticate |
| hypervisor:privilegeEscalation | AND | rdpLogin:authenticate, vpnSession:authenticate |
| internet:initialAccess | OR | — (entry) |
| iotDevice:exploitPublicApp | OR | vpnGateway:initialAccess, phishing:initialAccess, internet:initialAccess |
| jumpHost:lateralMovement | OR | sshKey:credentialAccess, configSecret:credentialAccess |
| kerberoast:credentialAccess | OR | mailClient:exploitPublicApp |
| localAdmin:privilegeEscalation | AND | ssoLogin:authenticate, printServer:lateralMovement |
| mailArchive:collection | OR | monitoringHost:lateralMovement, fileServer:lateralMovement, localAdmin:privilegeEscalation |
| mailClient:exploitPublicApp | OR | vpnGateway:initialAccess |
| monitoringHost:lateralMovement | OR | apiToken:authenticate, vpnSession:authenticate, tokenCache:credentialAccess |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | sshKey:credentialAccess, vpnSession:authenticate, apiToken:authenticate |
| rdpLogin:authenticate | AND | browserStore:credentialAccess, ciRunner:exploitPublicApp |
| secretsManager:privilegeEscalation | AND | jumpHost:lateralMovement, vpnSession:authenticate |
| serviceAccount:privilegeEscalation | AND | vpnSession:authenticate, backupHost:lateralMovement |
| shareMount:collection | OR | backupHost:lateralMovement, domainAdmin:privilegeEscalation, hypervisor:privilegeEscalation |
| sshKey:credentialAccess | OR | vpnGateway:initialAccess, containerHost:exploitPublicApp, internet:initialAccess |
| ssoLogin:authenticate | AND | mailClient:exploitPublicApp, iotDevice:exploitPublicApp |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | exposedApi:initialAccess, mailClient:exploitPublicApp, containerHost:exploitPublicApp |
| vaultRead:collection | OR | hypervisor:privilegeEscalation |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | browserStore:credentialAccess, mailClient:exploitPublicApp |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:execution | OR | phishing:initialAccess, vpnGateway:initialAccess |

## Question
A single point of failure is one step that, if the defender blocks it on its own, makes the target unreachable. How many of the steps (excluding footholds and the target) are single points of failure?
