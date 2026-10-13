# Enterprise attack model

The attacker starts at the perimeter (`reach_dmz` is true) and wins when `exfiltrated` becomes true. Each technique can be used only when its **requires** condition holds; using it makes its **achieves** variables true. A deployed defence makes its constant true and so blocks the techniques that require it to be false.

**State variables** (all start false except reach_dmz): reach_dmz, reach_internal, exfiltrated, foothold_web, admin_web, foothold_proxy, admin_proxy, foothold_workstation, admin_workstation, foothold_appserver, admin_appserver, foothold_dc, admin_dc, foothold_db, admin_db, foothold_fileserver, admin_fileserver, stolen_user, stolen_admin, stolen_dbadmin

**Deployed defences**: none

**Techniques**:
- `exploit_web` — requires (reach_dmz AND NOT patched_web); achieves foothold_web
- `exploit_proxy` — requires (reach_dmz AND NOT patched_proxy); achieves foothold_proxy
- `phish_workstation` — requires (always available); achieves foothold_workstation, stolen_user
- `escalate_workstation` — requires (foothold_workstation AND NOT patched_workstation); achieves admin_workstation
- `steal_user_cred` — requires ((((((foothold_web OR foothold_proxy) OR foothold_workstation) OR foothold_appserver) OR foothold_dc) OR foothold_db) OR foothold_fileserver); achieves stolen_user
- `pivot_internal` — requires (((((((foothold_web OR foothold_proxy) OR foothold_workstation) OR foothold_appserver) OR foothold_dc) OR foothold_db) OR foothold_fileserver) AND (NOT segmented OR (admin_appserver OR admin_workstation))); achieves reach_internal
- `auth_appserver` — requires (reach_internal AND stolen_user AND (NOT mfa_user OR foothold_workstation)); achieves foothold_appserver
- `escalate_appserver` — requires (foothold_appserver AND (stolen_admin OR NOT patched_appserver)); achieves admin_appserver
- `auth_dc` — requires (reach_internal AND stolen_admin AND NOT mfa_admin); achieves foothold_dc
- `kerberoast_dc` — requires (reach_internal AND foothold_appserver); achieves stolen_admin
- `escalate_dc` — requires (foothold_dc AND stolen_admin); achieves admin_dc
- `dump_dbadmin_dc` — requires admin_dc; achieves stolen_dbadmin
- `auth_db` — requires (reach_internal AND stolen_dbadmin AND (NOT mfa_dbadmin OR admin_dc)); achieves foothold_db
- `escalate_db` — requires (foothold_db AND (admin_dc OR stolen_dbadmin)); achieves admin_db
- `exfiltrate_db` — requires admin_db; achieves exfiltrated
- `auth_fileserver` — requires (reach_internal AND stolen_dbadmin AND (NOT mfa_dbadmin OR admin_dc)); achieves foothold_fileserver
- `escalate_fileserver` — requires (foothold_fileserver AND (admin_dc OR stolen_dbadmin)); achieves admin_fileserver
- `exfiltrate_fileserver` — requires admin_fileserver; achieves exfiltrated

## Current state
These variables are currently true: foothold_web. All other state variables are false and no defences are deployed.

## Question
Is the technique `auth_appserver` applicable right now?
