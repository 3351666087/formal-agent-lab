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

const ajv = new Ajv2020({ strict: false, allErrors: true });
addFormats(ajv);
for (const version of ["v1", "v2"]) {
  ajv.addSchema(await readJson(path.join(root, `contracts/${version}/bundle.schema.json`)), `bundle-${version}`);
}
const validatorFor = (version, type) => ajv.getSchema(`bundle-${version}#/$defs/${type}`);

async function fixtures(version, sub) {
  const dir = path.join(root, "tests/contracts/fixtures", version, sub);
  const names = (await readdir(dir)).filter((n) => n.endsWith(".json")).sort();
  return Promise.all(names.map(async (n) => [n.replace(/\.json$/, ""), await readJson(path.join(dir, n))]));
}

for (const version of ["v1", "v2"]) {
  for (const [name, instance] of await fixtures(version, "valid")) {
    test(`${version} valid fixture ${name} accepted`, () => {
      const validate = validatorFor(version, name.split(".")[0]);
      assert.ok(validate, `no ${version} schema for ${name}`);
      assert.ok(validate(instance), JSON.stringify(validate.errors, null, 2));
    });
  }
  for (const [name, fixture] of await fixtures(version, "invalid")) {
    test(`${version} invalid fixture ${name} rejected (${fixture.reason})`, () => {
      const validate = validatorFor(version, fixture.object);
      assert.equal(validate(fixture.instance), false);
    });
  }
}

test("generated meta.ts matches DIGEST.json of v2 and v1", async () => {
  const meta = await readFile(path.join(here, "../src/meta.ts"), "utf8");
  const digest = await readJson(path.join(root, "contracts/v2/DIGEST.json"));
  const digestV1 = await readJson(path.join(root, "contracts/v1/DIGEST.json"));
  assert.match(meta, new RegExp(`CONTRACT_DIGEST = "${digest.digest}"`));
  assert.match(meta, new RegExp(`CONTRACT_DIGEST_V1 = "${digestV1.digest}"`));
  assert.match(meta, /CONTRACT_VERSION = "formal-lab-contracts\/v2"/);
});
