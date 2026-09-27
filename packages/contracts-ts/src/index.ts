export * from "./generated.ts";
export * from "./meta.ts";
/** The frozen phase-1 contract, for reading v1 data. */
export * as V1 from "./generated.v1.ts";

import type { AssignEffect, ForallEffect, WhenEffect } from "./generated.ts";

/** Discriminated union of IR effects (the generator inlines it, so it is named here). */
export type Effect = AssignEffect | WhenEffect | ForallEffect;
