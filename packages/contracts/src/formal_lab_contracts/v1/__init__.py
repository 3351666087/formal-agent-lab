"""Frozen formal-lab-contracts/v1.

This sub-package is the exact phase-1 contract source. It exists so that `contracts/v1/` keeps being generated
byte-identically, v1 JSON can be validated as v1, and v1 replay bundles stay readable. Live code speaks v2
(`formal_lab_contracts`); `formal_lab_contracts.compat` upgrades v1 objects to v2. Never edit these modules.
"""

from .common import CONTRACT_VERSION

__all__ = ["CONTRACT_VERSION"]
