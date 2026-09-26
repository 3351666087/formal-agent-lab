export * from "./generated.ts";
export * from "./meta.ts";

import type { AssignEffect, ForallEffect, WhenEffect } from "./generated.ts";

/** Discriminated union of IR effects (the generator inlines it, so it is named here). */
export type Effect = AssignEffect | WhenEffect | ForallEffect;
