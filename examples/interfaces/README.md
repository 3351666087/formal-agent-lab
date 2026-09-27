# 接口示例（P1-042）

每个稳定接口一个可直接运行的示例（均只调用项目自带的纯数据模拟器与本地组件）：

| 接口 | 示例 |
|---|---|
| `ModelFrontend.compile` | [model_frontend.py](model_frontend.py) |
| `Verifier.check` | [verifier.py](verifier.py) |
| `Environment.reset/observe/step/snapshot/restore/close` | [environment.py](environment.py) |
| `Planner.propose` | [planner.py](planner.py) |
| `Evaluator.score` | [evaluator.py](evaluator.py) |
| `ArtifactStore.put/get` | [artifact_store.py](artifact_store.py) |

```bash
uv run --frozen python examples/interfaces/verifier.py
```

`tests/examples/test_interface_examples.py` 运行全部示例。
