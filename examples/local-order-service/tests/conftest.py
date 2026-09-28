"""The order service runs on loopback: the tests' own HTTP calls never go through a proxy from the environment
(the adapter, probe and lifecycle manager bypass it themselves — formal_lab_example_orders.net)."""

import os

for _key in ("NO_PROXY", "no_proxy"):
    os.environ[_key] = ",".join(x for x in (os.environ.get(_key), "127.0.0.1,localhost,::1") if x)
