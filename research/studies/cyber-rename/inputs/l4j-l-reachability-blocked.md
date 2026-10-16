# Delivery routing model: sorting line v1.4

The delivery succeeds when `delivery_completed` becomes true. Each action can be used only when its **requires** condition holds; using it makes its **achieves** variables true. An applied safeguard makes its switch true and so blocks the actions that require it to be false.

**State variables** (all start false): order_received, template_expanded, carrier_contacted, manifest_returned, package_loaded, delivery_completed

**Configuration switches**: template_processing=false, remote_ordering=true, carrier_directory=true, outbound_permitted=true, order_validated=false, external_loader_trusted=false, local_plugin=true

**Applied safeguards**: switch_off_template_processing

**Actions**:
- `submit_order` — requires NOT order_validated; achieves order_received
- `expand_template` — requires (order_received AND template_processing AND carrier_directory); achieves template_expanded
- `contact_carrier` — requires (template_expanded AND remote_ordering AND outbound_permitted); achieves carrier_contacted
- `return_manifest` — requires carrier_contacted; achieves manifest_returned
- `load_package_external` — requires (manifest_returned AND external_loader_trusted); achieves package_loaded
- `load_package_local` — requires (manifest_returned AND local_plugin); achieves package_loaded
- `complete_delivery` — requires package_loaded; achieves delivery_completed

## Question
With the safeguards above applied, can the delivery still be completed?
