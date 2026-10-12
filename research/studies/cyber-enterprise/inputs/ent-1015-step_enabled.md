# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | browserStore:credentialAccess, iotDevice:exploitPublicApp |
| appServer:lateralMovement | OR | memoryDump:credentialAccess, sshKey:credentialAccess, tokenCache:credentialAccess |
| backupHost:lateralMovement | OR | ssoLogin:authenticate |
| browserStore:credentialAccess | OR | vpnGateway:initialAccess, ciRunner:execution, exposedApi:initialAccess |
| ciRunner:execution | OR | wifiGuest:initialAccess, internet:initialAccess, phishing:initialAccess |
| codeRepo:collection | OR | appServer:lateralMovement |
| configSecret:credentialAccess | OR | ciRunner:execution, internet:initialAccess |
| containerHost:exploitPublicApp | OR | wifiGuest:initialAccess, internet:initialAccess, supplychain:initialAccess |
| crownData:exfiltrate | OR | dbReplica:collection, vaultRead:collection, shareMount:collection, codeRepo:collection |
| dbLogin:authenticate | AND | iotDevice:exploitPublicApp, memoryDump:credentialAccess |
| dbReplica:collection | OR | domainAdmin:privilegeEscalation, hypervisor:privilegeEscalation, fileServer:lateralMovement |
| dmzWeb:exploitPublicApp | OR | internet:initialAccess, vpnGateway:initialAccess |
| domainAdmin:privilegeEscalation | AND | ssoLogin:authenticate, rdpLogin:authenticate |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | dbLogin:authenticate |
| hypervisor:privilegeEscalation | AND | apiToken:authenticate, rdpLogin:authenticate |
| internet:initialAccess | OR | — (entry) |
| iotDevice:exploitPublicApp | OR | exposedApi:initialAccess, wifiGuest:initialAccess |
| jumpHost:lateralMovement | OR | rdpLogin:authenticate, vpnSession:authenticate |
| localAdmin:privilegeEscalation | AND | appServer:lateralMovement, jumpHost:lateralMovement |
| mailArchive:collection | OR | monitoringHost:lateralMovement |
| memoryDump:credentialAccess | OR | iotDevice:exploitPublicApp, containerHost:exploitPublicApp |
| monitoringHost:lateralMovement | OR | memoryDump:credentialAccess, ssoLogin:authenticate, rdpLogin:authenticate |
| phishing:initialAccess | OR | — (entry) |
| rdpLogin:authenticate | AND | tokenCache:credentialAccess, sshKey:credentialAccess |
| secretsManager:privilegeEscalation | AND | rdpLogin:authenticate, dbLogin:authenticate |
| serviceAccount:privilegeEscalation | AND | fileServer:lateralMovement, dbLogin:authenticate |
| shareMount:collection | OR | secretsManager:privilegeEscalation, appServer:lateralMovement, monitoringHost:lateralMovement |
| sshKey:credentialAccess | OR | iotDevice:exploitPublicApp, dmzWeb:exploitPublicApp |
| ssoLogin:authenticate | AND | sshKey:credentialAccess, containerHost:exploitPublicApp |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | wifiGuest:initialAccess, vpnGateway:initialAccess, exposedApi:initialAccess |
| vaultRead:collection | OR | secretsManager:privilegeEscalation, localAdmin:privilegeEscalation |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | memoryDump:credentialAccess, iotDevice:exploitPublicApp |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:exploitPublicApp | OR | vpnGateway:initialAccess |

## Current state
The attacker has already compromised: appServer:lateralMovement, jumpHost:lateralMovement.

## Question
Is the step `localAdmin:privilegeEscalation` (type AND) enabled to be taken next?
