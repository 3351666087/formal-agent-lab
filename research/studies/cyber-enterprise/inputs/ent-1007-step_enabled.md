# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | dmzWeb:execution, memoryDump:credentialAccess |
| backupHost:lateralMovement | OR | apiToken:authenticate |
| browserStore:credentialAccess | OR | ciRunner:execution, wifiGuest:initialAccess |
| ciRunner:execution | OR | exposedApi:initialAccess, wifiGuest:initialAccess |
| codeRepo:collection | OR | localAdmin:privilegeEscalation, monitoringHost:lateralMovement, printServer:lateralMovement |
| containerHost:exploitPublicApp | OR | exposedApi:initialAccess |
| crownData:exfiltrate | OR | shareMount:collection, dbReplica:collection, vaultRead:collection, codeRepo:collection |
| dbLogin:authenticate | AND | memoryDump:credentialAccess, sshKey:credentialAccess |
| dbReplica:collection | OR | serviceAccount:privilegeEscalation, fileServer:lateralMovement, backupHost:lateralMovement |
| dmzWeb:execution | OR | vpnGateway:initialAccess |
| domainAdmin:privilegeEscalation | AND | printServer:lateralMovement, jumpHost:lateralMovement |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | sshKey:credentialAccess, ssoLogin:authenticate, vpnSession:authenticate |
| hypervisor:privilegeEscalation | AND | dbLogin:authenticate, printServer:lateralMovement |
| internet:initialAccess | OR | — (entry) |
| iotDevice:exploitPublicApp | OR | phishing:initialAccess |
| jumpHost:lateralMovement | OR | browserStore:credentialAccess, kerberoast:credentialAccess |
| kerberoast:credentialAccess | OR | exposedApi:initialAccess, phishing:initialAccess |
| localAdmin:privilegeEscalation | AND | dbLogin:authenticate, rdpLogin:authenticate |
| mailArchive:collection | OR | hypervisor:privilegeEscalation, secretsManager:privilegeEscalation |
| memoryDump:credentialAccess | OR | workstation:exploitPublicApp, supplychain:initialAccess |
| monitoringHost:lateralMovement | OR | browserStore:credentialAccess, sshKey:credentialAccess |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | kerberoast:credentialAccess, memoryDump:credentialAccess |
| rdpLogin:authenticate | AND | dmzWeb:execution, containerHost:exploitPublicApp |
| secretsManager:privilegeEscalation | AND | dbLogin:authenticate, jumpHost:lateralMovement |
| serviceAccount:privilegeEscalation | AND | apiToken:authenticate, jumpHost:lateralMovement |
| shareMount:collection | OR | fileServer:lateralMovement, backupHost:lateralMovement, hypervisor:privilegeEscalation |
| sshKey:credentialAccess | OR | exposedApi:initialAccess |
| ssoLogin:authenticate | AND | iotDevice:exploitPublicApp, workstation:exploitPublicApp |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | supplychain:initialAccess, ciRunner:execution, containerHost:exploitPublicApp |
| vaultRead:collection | OR | localAdmin:privilegeEscalation, hypervisor:privilegeEscalation, secretsManager:privilegeEscalation |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | tokenCache:credentialAccess, ciRunner:execution |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:exploitPublicApp | OR | wifiGuest:initialAccess, phishing:initialAccess |

## Current state
The attacker has already compromised: dbLogin:authenticate.

## Question
Is the step `hypervisor:privilegeEscalation` (type AND) enabled to be taken next?
