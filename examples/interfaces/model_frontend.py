"""ModelFrontend.compile: source text → type-checked, digested ModelPackage."""

from formal_lab_contracts import ModelSource
from formal_lab_model.frontend import IRJsonFrontend
from formal_lab_model.samples import lamp

frontend = IRJsonFrontend()
package = frontend.compile(ModelSource(format="fal-ir-json/v1", text=lamp().model_dump_json()), package_id="lamp",
                           version=1)
print(package.package_id, package.version, package.semantic_profile, package.digest)
assert package.digest.value and package.ir.name == "lamp-counter"
