# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | workstation:execution, tokenCache:credentialAccess |
| appServer:lateralMovement | OR | apiToken:authenticate |
| backupHost:lateralMovement | OR | browserStore:credentialAccess, kerberoast:credentialAccess, apiToken:authenticate |
| browserStore:credentialAccess | OR | workstation:execution |
| ciRunner:execution | OR | vpnGateway:initialAccess |
| codeRepo:collection | OR | hypervisor:privilegeEscalation, printServer:lateralMovement, backupHost:lateralMovement |
| configSecret:credentialAccess | OR | workstation:execution, dmzWeb:execution |
| crownData:exfiltrate | OR | vaultRead:collection, dbReplica:collection, codeRepo:collection, shareMount:collection |
| dbLogin:authenticate | AND | browserStore:credentialAccess, tokenCache:credentialAccess |
| dbReplica:collection | OR | jumpHost:lateralMovement, secretsManager:privilegeEscalation |
| dmzWeb:execution | OR | vpnGateway:initialAccess, wifiGuest:initialAccess |
| domainAdmin:privilegeEscalation | AND | ssoLogin:authenticate, apiToken:authenticate |
| exposedApi:initialAccess | OR | — (entry) |
| hypervisor:privilegeEscalation | AND | ssoLogin:authenticate, dbLogin:authenticate |
| internet:initialAccess | OR | — (entry) |
| iotDevice:exploitPublicApp | OR | internet:initialAccess, phishing:initialAccess, vpnGateway:initialAccess |
| jumpHost:lateralMovement | OR | dbLogin:authenticate |
| kerberoast:credentialAccess | OR | wifiGuest:initialAccess, vpnGateway:initialAccess |
| localAdmin:privilegeEscalation | AND | appServer:lateralMovement, apiToken:authenticate |
| mailArchive:collection | OR | domainAdmin:privilegeEscalation, appServer:lateralMovement, backupHost:lateralMovement |
| mailClient:execution | OR | vpnGateway:initialAccess, wifiGuest:initialAccess, phishing:initialAccess |
| memoryDump:credentialAccess | OR | ciRunner:execution, supplychain:initialAccess |
| monitoringHost:lateralMovement | OR | kerberoast:credentialAccess |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | rdpLogin:authenticate, dbLogin:authenticate |
| rdpLogin:authenticate | AND | tokenCache:credentialAccess, memoryDump:credentialAccess |
| secretsManager:privilegeEscalation | AND | printServer:lateralMovement, backupHost:lateralMovement |
| serviceAccount:privilegeEscalation | AND | ssoLogin:authenticate, backupHost:lateralMovement |
| shareMount:collection | OR | printServer:lateralMovement |
| ssoLogin:authenticate | AND | browserStore:credentialAccess, configSecret:credentialAccess |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | mailClient:execution |
| vaultRead:collection | OR | printServer:lateralMovement, serviceAccount:privilegeEscalation, secretsManager:privilegeEscalation |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | tokenCache:credentialAccess, dmzWeb:execution |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:execution | OR | wifiGuest:initialAccess, supplychain:initialAccess |

## Deployed defences
The defender has blocked these steps (they can no longer be used): apiToken:authenticate, rdpLogin:authenticate.

## Question
With those defences in place, is the target still reachable?
