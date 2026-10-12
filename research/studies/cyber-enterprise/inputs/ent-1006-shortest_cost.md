# Attack graph (formal AND/OR dependency model)

An attacker starts at the entry footholds. A step with type **OR** becomes reachable once **any** of its parent steps is reached; a step with type **AND** only once **all** of its parents are reached. The target is the crown objective.

- Entry footholds (always reachable to start): internet:initialAccess, phishing:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess, wifiGuest:initialAccess, exposedApi:initialAccess
- Target: crownData:exfiltrate

| step | type | parents |
|---|---|---|
| apiToken:authenticate | AND | ciRunner:execution, dmzWeb:execution |
| appServer:lateralMovement | OR | browserStore:credentialAccess |
| browserStore:credentialAccess | OR | internet:initialAccess |
| ciRunner:execution | OR | internet:initialAccess, vpnGateway:initialAccess |
| codeRepo:collection | OR | domainAdmin:privilegeEscalation, appServer:lateralMovement, localAdmin:privilegeEscalation |
| configSecret:credentialAccess | OR | supplychain:initialAccess, vpnGateway:initialAccess, dmzWeb:execution |
| containerHost:execution | OR | internet:initialAccess, wifiGuest:initialAccess |
| crownData:exfiltrate | OR | vaultRead:collection, dbReplica:collection, shareMount:collection, mailArchive:collection |
| dbLogin:authenticate | AND | tokenCache:credentialAccess, ciRunner:execution |
| dbReplica:collection | OR | hypervisor:privilegeEscalation, printServer:lateralMovement, serviceAccount:privilegeEscalation |
| dmzWeb:execution | OR | internet:initialAccess, vpnGateway:initialAccess |
| domainAdmin:privilegeEscalation | AND | rdpLogin:authenticate, jumpHost:lateralMovement |
| exposedApi:initialAccess | OR | — (entry) |
| fileServer:lateralMovement | OR | apiToken:authenticate, rdpLogin:authenticate, dbLogin:authenticate |
| hypervisor:privilegeEscalation | AND | monitoringHost:lateralMovement, appServer:lateralMovement |
| internet:initialAccess | OR | — (entry) |
| iotDevice:execution | OR | vpnGateway:initialAccess |
| jumpHost:lateralMovement | OR | kerberoast:credentialAccess |
| kerberoast:credentialAccess | OR | internet:initialAccess, supplychain:initialAccess, vpnGateway:initialAccess |
| localAdmin:privilegeEscalation | AND | ssoLogin:authenticate, vpnSession:authenticate |
| mailArchive:collection | OR | domainAdmin:privilegeEscalation, printServer:lateralMovement, fileServer:lateralMovement |
| memoryDump:credentialAccess | OR | supplychain:initialAccess, containerHost:execution |
| monitoringHost:lateralMovement | OR | tokenCache:credentialAccess, dbLogin:authenticate, vpnSession:authenticate |
| phishing:initialAccess | OR | — (entry) |
| printServer:lateralMovement | OR | configSecret:credentialAccess, ssoLogin:authenticate, apiToken:authenticate |
| rdpLogin:authenticate | AND | configSecret:credentialAccess, dmzWeb:execution |
| secretsManager:privilegeEscalation | AND | rdpLogin:authenticate, apiToken:authenticate |
| serviceAccount:privilegeEscalation | AND | apiToken:authenticate, appServer:lateralMovement |
| shareMount:collection | OR | secretsManager:privilegeEscalation |
| ssoLogin:authenticate | AND | containerHost:execution, tokenCache:credentialAccess |
| supplychain:initialAccess | OR | — (entry) |
| tokenCache:credentialAccess | OR | containerHost:execution, internet:initialAccess |
| vaultRead:collection | OR | jumpHost:lateralMovement, secretsManager:privilegeEscalation |
| vpnGateway:initialAccess | OR | — (entry) |
| vpnSession:authenticate | AND | kerberoast:credentialAccess, workstation:execution |
| wifiGuest:initialAccess | OR | — (entry) |
| workstation:execution | OR | wifiGuest:initialAccess, exposedApi:initialAccess, supplychain:initialAccess |

## Question
What is the minimum number of attack steps the attacker must take to reach the target? Count every step the attacker performs, **including the final step that compromises the target itself**.
