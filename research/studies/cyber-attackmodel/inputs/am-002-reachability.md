# Enterprise attack model

The attacker starts at the perimeter (`reach_dmz` is true) and wins when `exfiltrated` becomes true. Each technique can be used only when its **requires** condition holds; using it makes its **achieves** variables true. A deployed defence makes its constant true and so blocks the techniques that require it to be false.

**State variables** (all start false except reach_dmz): reach_dmz, reach_internal, exfiltrated, foothold_web, admin_web, foothold_proxy, admin_proxy, foothold_vpn, admin_vpn, foothold_workstation, admin_workstation, foothold_laptop, admin_laptop, foothold_appserver, admin_appserver, foothold_apiserver, admin_apiserver, foothold_ciserver, admin_ciserver, foothold_dc, admin_dc, foothold_adfs, admin_adfs, foothold_db, admin_db, foothold_fileserver, admin_fileserver, foothold_backup, admin_backup, stolen_user, stolen_admin, stolen_dbadmin

**Deployed defences**: mfa:admin

**Techniques**:
- `exploit_web` — requires (reach_dmz AND NOT patched_web); achieves foothold_web
- `exploit_proxy` — requires (reach_dmz AND NOT patched_proxy); achieves foothold_proxy
- `exploit_vpn` — requires (reach_dmz AND NOT patched_vpn); achieves foothold_vpn
- `phish_workstation` — requires (always available); achieves foothold_workstation, stolen_user
- `escalate_workstation` — requires (foothold_workstation AND NOT patched_workstation); achieves admin_workstation
- `phish_laptop` — requires (always available); achieves foothold_laptop, stolen_user
- `escalate_laptop` — requires (foothold_laptop AND NOT patched_laptop); achieves admin_laptop
- `steal_user_cred` — requires ((((((((((((foothold_web OR foothold_proxy) OR foothold_vpn) OR foothold_workstation) OR foothold_laptop) OR foothold_appserver) OR foothold_apiserver) OR foothold_ciserver) OR foothold_dc) OR foothold_adfs) OR foothold_db) OR foothold_fileserver) OR foothold_backup); achieves stolen_user
- `pivot_internal` — requires (((((((((((((foothold_web OR foothold_proxy) OR foothold_vpn) OR foothold_workstation) OR foothold_laptop) OR foothold_appserver) OR foothold_apiserver) OR foothold_ciserver) OR foothold_dc) OR foothold_adfs) OR foothold_db) OR foothold_fileserver) OR foothold_backup) AND (NOT segmented OR ((((admin_appserver OR admin_apiserver) OR admin_ciserver) OR admin_workstation) OR admin_laptop))); achieves reach_internal
- `auth_appserver` — requires (reach_internal AND stolen_user AND (NOT mfa_user OR (foothold_workstation OR foothold_laptop))); achieves foothold_appserver
- `escalate_appserver` — requires (foothold_appserver AND (stolen_admin OR NOT patched_appserver)); achieves admin_appserver
- `auth_apiserver` — requires (reach_internal AND stolen_user AND (NOT mfa_user OR (foothold_workstation OR foothold_laptop))); achieves foothold_apiserver
- `escalate_apiserver` — requires (foothold_apiserver AND (stolen_admin OR NOT patched_apiserver)); achieves admin_apiserver
- `auth_ciserver` — requires (reach_internal AND stolen_user AND (NOT mfa_user OR (foothold_workstation OR foothold_laptop))); achieves foothold_ciserver
- `escalate_ciserver` — requires (foothold_ciserver AND (stolen_admin OR NOT patched_ciserver)); achieves admin_ciserver
- `leak_secrets_ciserver` — requires admin_ciserver; achieves stolen_dbadmin
- `auth_dc` — requires (reach_internal AND stolen_admin AND NOT mfa_admin); achieves foothold_dc
- `kerberoast_dc` — requires (reach_internal AND ((foothold_appserver OR foothold_apiserver) OR foothold_ciserver)); achieves stolen_admin
- `escalate_dc` — requires (foothold_dc AND stolen_admin); achieves admin_dc
- `dump_dbadmin_dc` — requires admin_dc; achieves stolen_dbadmin
- `auth_adfs` — requires (reach_internal AND stolen_admin AND NOT mfa_admin); achieves foothold_adfs
- `kerberoast_adfs` — requires (reach_internal AND ((foothold_appserver OR foothold_apiserver) OR foothold_ciserver)); achieves stolen_admin
- `escalate_adfs` — requires (foothold_adfs AND stolen_admin); achieves admin_adfs
- `dump_dbadmin_adfs` — requires admin_adfs; achieves stolen_dbadmin
- `auth_db` — requires (reach_internal AND stolen_dbadmin AND (NOT mfa_dbadmin OR (admin_dc OR admin_adfs))); achieves foothold_db
- `escalate_db` — requires (foothold_db AND ((admin_dc OR admin_adfs) OR stolen_dbadmin)); achieves admin_db
- `exfiltrate_db` — requires admin_db; achieves exfiltrated
- `auth_fileserver` — requires (reach_internal AND stolen_dbadmin AND (NOT mfa_dbadmin OR (admin_dc OR admin_adfs))); achieves foothold_fileserver
- `escalate_fileserver` — requires (foothold_fileserver AND ((admin_dc OR admin_adfs) OR stolen_dbadmin)); achieves admin_fileserver
- `exfiltrate_fileserver` — requires admin_fileserver; achieves exfiltrated
- `auth_backup` — requires (reach_internal AND stolen_dbadmin AND (NOT mfa_dbadmin OR (admin_dc OR admin_adfs))); achieves foothold_backup
- `escalate_backup` — requires (foothold_backup AND ((admin_dc OR admin_adfs) OR stolen_dbadmin)); achieves admin_backup
- `exfiltrate_backup` — requires admin_backup; achieves exfiltrated

## Question
With the deployed defences above in place, can the attacker still reach data exfiltration?
