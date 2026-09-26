// TypeScript-side contract test: the generated bundle schema accepts/rejects the same shared fixtures
// the Python contract tests use (tests/contracts/fixtures), and generated metadata matches DIGEST.json.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "../../..");
const readJson = async (p) => JSON.parse(await readFile(p, "utf8"));

const bundle = await readJson(path.join(root, "contracts/v1/bundle.schema.json"));
const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);
ajv.addSchema(bundle, "bundle");
const validatorFor = (type) => ajv.getSchema(`bundle#/$defs/${type}`);

async function fixtures(sub) {
  const dir = path.join(root, "tests/contracts/fixtures", sub);
  const names = (await readdir(dir)).filter((n) => n.endsWith(".json")).sort();
  return Promise.all(names.map(async (n) => [n.replace(/\.json$/, ""), await readJson(path.join(dir, n))]));
}

for (const [name, instance] of await fixtures("valid")) {
  test(`valid fixture ${name} accepted`, () => {
    const validate = validatorFor(name.split(".")[0]);
    assert.ok(validate, `no schema for ${name}`);
    assert.ok(validate(instance), JSON.stringify(validate.errors, null, 2));
  });
}

for (const [name, fixture] of await fixtures("invalid")) {
  test(`invalid fixture ${name} rejected (${fixture.reason})`, () => {
    const validate = validatorFor(fixture.object);
    assert.equal(validate(fixture.instance), false);
  });
}

test("generated meta.ts matches DIGEST.json", async () => {
  const digest = await readJson(path.join(root, "contracts/v1/DIGEST.json"));
  const meta = await readFile(path.join(here, "../src/meta.ts"), "utf8");
  assert.match(meta, new RegExp(`CONTRACT_DIGEST = "${digest.digest}"`));
  assert.match(meta, /CONTRACT_VERSION = "formal-lab-contracts\/v1"/);
});
