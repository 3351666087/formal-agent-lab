# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | sshKey:credentialAccess, ciRunner:exploitPublicApp |
| backupHost:lateralMovement | OR | tokenCache:credentialAccess, kerberoast:credentialAccess, browserStore:credentialAccess |
| browserStore:credentialAccess | OR | iotDevice:execution, exposedApi:initialAccess |
| ciRunner:exploitPublicApp | OR | wifiGuest:initialAccess |
| codeRepo:collection | OR | secretsManager:privilegeEscalation |
| configSecret:credentialAccess | OR | ciRunner:exploitPublicApp, iotDevice:execution |
| crownData:exfiltrate | OR | dbReplica:collection, mailArchive:collection, shareMount:collection, codeRepo:collection |
| dbLogin:authenticate | AND | sshKey:credentialAccess, ciRunner:exploitPublicApp |
| dbReplica:collection | OR | jumpHost:lateralMovement, backupHost:lateralMovement, printServer:lateralMovement |
| dmzWeb:execution | OR | wifiGuest:initialAccess |
| domainAdmin:privilegeEscalation | AND | jumpHost:lateralMovement, backupHost:lateralMovement |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | configSecret:credentialAccess, sshKey:credentialAccess, vpnSession:authenticate |
| hypervisor:privilegeEscalation | AND | ssoLogin:authenticate, printServer:lateralMovement |
| internet:initialAccess | OR | — (entry) |
| iotDevice:execution | OR | internet:initialAccess, vpnGateway:initialAccess, exposedApi:initialAccess |
| jumpHost:lateralMovement | OR | kerberoast:credentialAccess |
| kerberoast:credentialAccess | OR | wifiGuest:initialAccess, workstation:exploitPublicApp, ciRunner:exploitPublicApp |
| localAdmin:privilegeEscalation | AND | jumpHost:lateralMovement, monitoringHost:lateralMovement |
| mailArchive:collection | OR | jumpHost:lateralMovement |
| mailClient:execution | OR | supplychain:initialAccess, phishing:initialAccess, internet:initialAccess |
| monitoringHost:lateralMovement | OR | ssoLogin:authenticate |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | dbLogin:authenticate |
| rdpLogin:authenticate | AND | ciRunner:exploitPublicApp, dmzWeb:execution |
| secretsManager:privilegeEscalation | AND | printServer:lateralMovement, fileServer:lateralMovement |
| serviceAccount:privilegeEscalation | AND | ssoLogin:authenticate, backupHost:lateralMovement |
| shareMount:collection | OR | secretsManager:privilegeEscalation, localAdmin:privilegeEscalation, backupHost:lateralMovement |
| sshKey:credentialAccess | OR | wifiGuest:initialAccess, phishing:initialAccess |
| ssoLogin:authenticate | AND | sshKey:credentialAccess, iotDevice:execution |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | internet:initialAccess |
| vaultRead:collection | OR | domainAdmin:privilegeEscalation, secretsManager:privilegeEscalation |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | dmzWeb:execution, sshKey:credentialAccess |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:exploitPublicApp | OR | phishing:initialAccess, wifiGuest:initialAccess |

## Attacker constraint
The attacker has only ONE foothold available: `vpnGateway:initialAccess`. The other footholds cannot be used.

## Question
From that single foothold alone, can the attacker reach the target?
