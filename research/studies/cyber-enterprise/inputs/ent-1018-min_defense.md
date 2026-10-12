# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | sshKey:credentialAccess, kerberoast:credentialAccess |
| appServer:lateralMovement | OR | configSecret:credentialAccess, vpnSession:authenticate |
| backupHost:lateralMovement | OR | configSecret:credentialAccess, kerberoast:credentialAccess |
| browserStore:credentialAccess | OR | workstation:execution, phishing:initialAccess, mailClient:execution |
| ciRunner:execution | OR | wifiGuest:initialAccess, internet:initialAccess, supplychain:initialAccess |
| codeRepo:collection | OR | jumpHost:lateralMovement, backupHost:lateralMovement |
| configSecret:credentialAccess | OR | exposedApi:initialAccess, mailClient:execution, wifiGuest:initialAccess |
| containerHost:exploitPublicApp | OR | phishing:initialAccess, exposedApi:initialAccess, vpnGateway:initialAccess |
| crownData:exfiltrate | OR | dbReplica:collection, codeRepo:collection, shareMount:collection, mailArchive:collection |
| dbLogin:authenticate | AND | workstation:execution, configSecret:credentialAccess |
| dbReplica:collection | OR | domainAdmin:privilegeEscalation, monitoringHost:lateralMovement |
| domainAdmin:privilegeEscalation | AND | ssoLogin:authenticate, fileServer:lateralMovement |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | browserStore:credentialAccess, apiToken:authenticate, vpnSession:authenticate |
| hypervisor:privilegeEscalation | AND | rdpLogin:authenticate, monitoringHost:lateralMovement |
| internet:initialAccess | OR | — (entry) |
| iotDevice:execution | OR | exposedApi:initialAccess, wifiGuest:initialAccess, vpnGateway:initialAccess |
| jumpHost:lateralMovement | OR | vpnSession:authenticate, sshKey:credentialAccess, configSecret:credentialAccess |
| kerberoast:credentialAccess | OR | wifiGuest:initialAccess, supplychain:initialAccess, phishing:initialAccess |
| localAdmin:privilegeEscalation | AND | jumpHost:lateralMovement, ssoLogin:authenticate |
| mailArchive:collection | OR | monitoringHost:lateralMovement, fileServer:lateralMovement, domainAdmin:privilegeEscalation |
| mailClient:execution | OR | wifiGuest:initialAccess, phishing:initialAccess, exposedApi:initialAccess |
| memoryDump:credentialAccess | OR | iotDevice:execution, ciRunner:execution, containerHost:exploitPublicApp |
| monitoringHost:lateralMovement | OR | vpnSession:authenticate, ssoLogin:authenticate |
| phishing:initialAccess | OR | — (entry) |
| rdpLogin:authenticate | AND | containerHost:exploitPublicApp, memoryDump:credentialAccess |
| secretsManager:privilegeEscalation | AND | vpnSession:authenticate, monitoringHost:lateralMovement |
| serviceAccount:privilegeEscalation | AND | dbLogin:authenticate, monitoringHost:lateralMovement |
| shareMount:collection | OR | jumpHost:lateralMovement, serviceAccount:privilegeEscalation, localAdmin:privilegeEscalation |
| sshKey:credentialAccess | OR | wifiGuest:initialAccess |
| ssoLogin:authenticate | AND | workstation:execution, ciRunner:execution |
| supplychain:initialAccess | OR | — (entry) |
| vaultRead:collection | OR | jumpHost:lateralMovement, serviceAccount:privilegeEscalation, secretsManager:privilegeEscalation |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | workstation:execution, containerHost:exploitPublicApp |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:execution | OR | internet:initialAccess, vpnGateway:initialAccess |

## Question
A defender may block steps to stop the attacker. What is the smallest number of steps they must block so the target becomes unreachable? (Footholds and the target itself cannot be blocked.)
