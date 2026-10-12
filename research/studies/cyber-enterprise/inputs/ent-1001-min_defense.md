# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | browserStore:credentialAccess, iotDevice:execution |
| appServer:lateralMovement | OR | memoryDump:credentialAccess, apiToken:authenticate, ssoLogin:authenticate |
| backupHost:lateralMovement | OR | ssoLogin:authenticate |
| browserStore:credentialAccess | OR | wifiGuest:initialAccess, exposedApi:initialAccess |
| ciRunner:execution | OR | vpnGateway:initialAccess |
| codeRepo:collection | OR | appServer:lateralMovement, serviceAccount:privilegeEscalation |
| configSecret:credentialAccess | OR | supplychain:initialAccess |
| containerHost:exploitPublicApp | OR | phishing:initialAccess, wifiGuest:initialAccess |
| crownData:exfiltrate | OR | vaultRead:collection, codeRepo:collection, shareMount:collection, dbReplica:collection |
| dbLogin:authenticate | AND | ciRunner:execution, sshKey:credentialAccess |
| dbReplica:collection | OR | appServer:lateralMovement, hypervisor:privilegeEscalation, printServer:lateralMovement |
| dmzWeb:exploitPublicApp | OR | phishing:initialAccess, internet:initialAccess, supplychain:initialAccess |
| domainAdmin:privilegeEscalation | AND | appServer:lateralMovement, ssoLogin:authenticate |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | dbLogin:authenticate, rdpLogin:authenticate |
| hypervisor:privilegeEscalation | AND | fileServer:lateralMovement, jumpHost:lateralMovement |
| internet:initialAccess | OR | — (entry) |
| iotDevice:execution | OR | internet:initialAccess, exposedApi:initialAccess |
| jumpHost:lateralMovement | OR | dbLogin:authenticate, configSecret:credentialAccess |
| localAdmin:privilegeEscalation | AND | vpnSession:authenticate, appServer:lateralMovement |
| mailArchive:collection | OR | hypervisor:privilegeEscalation, jumpHost:lateralMovement, backupHost:lateralMovement |
| memoryDump:credentialAccess | OR | wifiGuest:initialAccess, supplychain:initialAccess, exposedApi:initialAccess |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | apiToken:authenticate, memoryDump:credentialAccess, vpnSession:authenticate |
| rdpLogin:authenticate | AND | containerHost:exploitPublicApp, memoryDump:credentialAccess |
| secretsManager:privilegeEscalation | AND | jumpHost:lateralMovement, appServer:lateralMovement |
| serviceAccount:privilegeEscalation | AND | ssoLogin:authenticate, vpnSession:authenticate |
| shareMount:collection | OR | localAdmin:privilegeEscalation, jumpHost:lateralMovement |
| sshKey:credentialAccess | OR | exposedApi:initialAccess, dmzWeb:exploitPublicApp |
| ssoLogin:authenticate | AND | configSecret:credentialAccess, dmzWeb:exploitPublicApp |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | phishing:initialAccess, supplychain:initialAccess, iotDevice:execution |
| vaultRead:collection | OR | hypervisor:privilegeEscalation, appServer:lateralMovement, secretsManager:privilegeEscalation |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | sshKey:credentialAccess, iotDevice:execution |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:execution | OR | vpnGateway:initialAccess, phishing:initialAccess, internet:initialAccess |

## Question
A defender may block steps to stop the attacker. What is the smallest number of steps they must block so the target becomes unreachable? (Footholds and the target itself cannot be blocked.)
