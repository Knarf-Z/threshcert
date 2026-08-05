# 主机1：Paid Threshold Response 正证书实验（v2）

独立实验，不覆盖 `threshcert` 现有代码。v1 结果保留在 `legacy/host1_result.v1.json`，不被覆盖。

## v2 相对 v1 的改动

v1 的 `evidence.py` 直接用闭式公式当作 certificate：

```python
certificate = uniform_certificate(prices, threshold) if all_pass else 0
```

于是 coalition `{4,5,6,7}` 的实际净支出是 22，报告里却写 10。这是循环论证。v2 拆成四个由**不同代码路径**得到的量：

| 量 | 来源 |
| --- | --- |
| `theory_cover` | 闭式公式，只读声明的 floors，不看任何执行 |
| `execution_floor(h)` | 该次执行的 allocation witness：`Σ_{i∈Q_c(h)} (D_i − R_i − F_i)` |
| `catalog_certificate` | 对 840 条 route 的 ledger-derived floor 取最小值 |
| `observed_minimum` | 实际运行结果的最小净支出 |

三者都等于 10，但没有任何一条是抄另一条。`{4,5,6,7}` 现在如实报告 `execution_floor = 22`。

其余改动：

- `Q_c(h)` 由 `aggregation_witness` 从记录中读出（绑定 operator id、partial hash、order、buyer、resource、epoch、responder bitmap），不再由 evaluator 自行挑选；
- (C2) 成为 `allocation_witness`，检查 debit_id 全局唯一、refund/funding id 不重复分配、逐成员 `D_i − R_i − F_i ≥ p_i`、总额 `≤ O(h)`；
- 每个 gate 有四种状态 `PASS / FAIL_COUNTEREXAMPLE / FAIL_CLOSED_MISSING_EVIDENCE / NOT_APPLICABLE`，整体判定 `CERTIFIED / REFUTED / UNKNOWN`；
- B3 在没有 named-buyer 可用交付时是 `NOT_APPLICABLE` 而不是失败；B4 只管退款/补贴/外部资金的枚举与扣除，不再夹带金额恒等式；`early_release` 保持 `paid_response` 路由只破坏时序；`bypass` 用零 required debit 因而只破坏 B5；
- `coverage_declared` 布尔参数删除，改为 `route_coverage_evidence` 证据对象，三种状态 `PROVED / REFUTED / UNKNOWN`；
- (C1)、(C3) 作为独立 proof object 落盘；
- 结果拆成 `canonical_result.v2.json`（确定性内容）与 `run_metadata.v2.json`（平台、PID、耗时）。

## 运行

```powershell
Set-Location "<解压目录>"
Set-ExecutionPolicy -Scope Process Bypass
.\powershell\Setup-Host1.ps1
.\powershell\Run-Host1-Experiment.ps1
```

期望输出：

```text
THEORY_COVER=10
CATALOG_CERTIFICATE=10
OBSERVED_MINIMUM=10
ROUTES_ENUMERATED=840
ALL_ROUTE_FLOORS_LEDGER_DERIVED=true
MINIMIZING_ROUTES=24
EXPENSIVE_COALITION_4567_EXECUTION_FLOOR=22
BASELINE_STATUS=CERTIFIED
MULTIPROCESS_WORKERS=4
HOST1_EXPERIMENT=PASS
RESULT_VERIFICATION=PASS
```

## 消融矩阵

目标是干净对角线：每个消融只让它针对的那道门给出 `FAIL_COUNTEREXAMPLE`。

| Ablation | B1 | B2 | B3 | B4 | B5 |
| --- | --- | --- | --- | --- | --- |
| Baseline | PASS | PASS | PASS | PASS | PASS |
| Wrong buyer | FAIL_CE | PASS | N/A | PASS | PASS |
| Sponsor funded | PASS | FAIL_CE | PASS | PASS | PASS |
| Early release | PASS | PASS | FAIL_CE | PASS | PASS |
| Reimbursement | PASS | PASS | PASS | FAIL_CE | PASS |
| Bypass route | PASS | PASS | PASS | PASS | FAIL_CE |

`N/A` 是语义正确的：wrong-buyer 下不存在 named-buyer 可用交付，原子性无所约束。

## 论文里能写和不能写

见 `PAPER_CLAIMS.md`。要点：可以写真实 4-of-7 threshold ElGamal、可验证 partial proof、840 条 route 的 ledger-derived certificate、干净消融对角线、UNKNOWN 与 REFUTED 的区分；**不能**写 deployment-wide 闭合、硬件强制 non-exportability、七个独立经济运营者、真实贿赂价格。
