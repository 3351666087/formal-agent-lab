# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | configSecret:credentialAccess, ciRunner:exploitPublicApp |
| backupHost:lateralMovement | OR | kerberoast:credentialAccess |
| browserStore:credentialAccess | OR | ciRunner:exploitPublicApp, supplychain:initialAccess, dmzWeb:exploitPublicApp |
| ciRunner:exploitPublicApp | OR | phishing:initialAccess, internet:initialAccess, exposedApi:initialAccess |
| codeRepo:collection | OR | jumpHost:lateralMovement, printServer:lateralMovement, localAdmin:privilegeEscalation |
| configSecret:credentialAccess | OR | containerHost:execution |
| containerHost:execution | OR | vpnGateway:initialAccess, supplychain:initialAccess |
| crownData:exfiltrate | OR | vaultRead:collection, codeRepo:collection, shareMount:collection, dbReplica:collection |
| dbLogin:authenticate | AND | browserStore:credentialAccess, configSecret:credentialAccess |
| dbReplica:collection | OR | serviceAccount:privilegeEscalation, domainAdmin:privilegeEscalation, monitoringHost:lateralMovement |
| dmzWeb:exploitPublicApp | OR | vpnGateway:initialAccess |
| domainAdmin:privilegeEscalation | AND | dbLogin:authenticate, apiToken:authenticate |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | kerberoast:credentialAccess, rdpLogin:authenticate, configSecret:credentialAccess |
| hypervisor:privilegeEscalation | AND | rdpLogin:authenticate, apiToken:authenticate |
| internet:initialAccess | OR | — (entry) |
| jumpHost:lateralMovement | OR | sshKey:credentialAccess |
| kerberoast:credentialAccess | OR | workstation:execution, ciRunner:exploitPublicApp, mailClient:execution |
| localAdmin:privilegeEscalation | AND | fileServer:lateralMovement, monitoringHost:lateralMovement |
| mailArchive:collection | OR | secretsManager:privilegeEscalation, jumpHost:lateralMovement |
| mailClient:execution | OR | supplychain:initialAccess, wifiGuest:initialAccess |
| memoryDump:credentialAccess | OR | internet:initialAccess, supplychain:initialAccess |
| monitoringHost:lateralMovement | OR | rdpLogin:authenticate |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | configSecret:credentialAccess, ssoLogin:authenticate |
| rdpLogin:authenticate | AND | mailClient:execution, browserStore:credentialAccess |
| secretsManager:privilegeEscalation | AND | jumpHost:lateralMovement, ssoLogin:authenticate |
| serviceAccount:privilegeEscalation | AND | vpnSession:authenticate, jumpHost:lateralMovement |
| shareMount:collection | OR | backupHost:lateralMovement |
| sshKey:credentialAccess | OR | phishing:initialAccess, exposedApi:initialAccess, supplychain:initialAccess |
| ssoLogin:authenticate | AND | containerHost:execution, configSecret:credentialAccess |
| supplychain:initialAccess | OR | — (entry) |
| vaultRead:collection | OR | domainAdmin:privilegeEscalation, serviceAccount:privilegeEscalation |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | dmzWeb:exploitPublicApp, ciRunner:exploitPublicApp |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:execution | OR | supplychain:initialAccess, wifiGuest:initialAccess, vpnGateway:initialAccess |

## Question
What is the minimum number of attack steps the attacker must take to reach the target? Count every step the attacker performs, **including the final step that compromises the target itself**.
