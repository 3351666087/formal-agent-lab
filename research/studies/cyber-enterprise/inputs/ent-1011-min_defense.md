# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | configSecret:credentialAccess, memoryDump:credentialAccess |
| backupHost:lateralMovement | OR | configSecret:credentialAccess, apiToken:authenticate, rdpLogin:authenticate |
| browserStore:credentialAccess | OR | workstation:execution, containerHost:exploitPublicApp, supplychain:initialAccess |
| codeRepo:collection | OR | serviceAccount:privilegeEscalation, monitoringHost:lateralMovement, backupHost:lateralMovement |
| configSecret:credentialAccess | OR | internet:initialAccess, workstation:execution |
| containerHost:exploitPublicApp | OR | wifiGuest:initialAccess, phishing:initialAccess |
| crownData:exfiltrate | OR | dbReplica:collection, codeRepo:collection, shareMount:collection, vaultRead:collection |
| dbLogin:authenticate | AND | workstation:execution, browserStore:credentialAccess |
| dbReplica:collection | OR | domainAdmin:privilegeEscalation |
| dmzWeb:execution | OR | exposedApi:initialAccess |
| domainAdmin:privilegeEscalation | AND | backupHost:lateralMovement, ssoLogin:authenticate |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | dbLogin:authenticate, memoryDump:credentialAccess |
| hypervisor:privilegeEscalation | AND | apiToken:authenticate, dbLogin:authenticate |
| internet:initialAccess | OR | — (entry) |
| iotDevice:exploitPublicApp | OR | vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess |
| jumpHost:lateralMovement | OR | browserStore:credentialAccess, memoryDump:credentialAccess |
| kerberoast:credentialAccess | OR | workstation:execution, containerHost:exploitPublicApp, supplychain:initialAccess |
| localAdmin:privilegeEscalation | AND | dbLogin:authenticate, fileServer:lateralMovement |
| mailArchive:collection | OR | domainAdmin:privilegeEscalation |
| mailClient:execution | OR | phishing:initialAccess, vpnGateway:initialAccess, internet:initialAccess |
| memoryDump:credentialAccess | OR | phishing:initialAccess, exposedApi:initialAccess |
| monitoringHost:lateralMovement | OR | tokenCache:credentialAccess, ssoLogin:authenticate |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | ssoLogin:authenticate, memoryDump:credentialAccess |
| rdpLogin:authenticate | AND | memoryDump:credentialAccess, workstation:execution |
| secretsManager:privilegeEscalation | AND | dbLogin:authenticate, ssoLogin:authenticate |
| serviceAccount:privilegeEscalation | AND | rdpLogin:authenticate, apiToken:authenticate |
| shareMount:collection | OR | domainAdmin:privilegeEscalation, jumpHost:lateralMovement |
| ssoLogin:authenticate | AND | iotDevice:exploitPublicApp, browserStore:credentialAccess |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | iotDevice:exploitPublicApp, supplychain:initialAccess |
| vaultRead:collection | OR | fileServer:lateralMovement, secretsManager:privilegeEscalation, monitoringHost:lateralMovement |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | tokenCache:credentialAccess, iotDevice:exploitPublicApp |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:execution | OR | exposedApi:initialAccess, internet:initialAccess, wifiGuest:initialAccess |

## Question
A defender may block steps to stop the attacker. What is the smallest number of steps they must block so the target becomes unreachable? (Footholds and the target itself cannot be blocked.)
