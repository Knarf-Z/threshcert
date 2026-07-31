#!/usr/bin/env python3
"""Run and certify the bounded-loop Halmos EVM-to-schema proof suite.

The 35 canonical four-member sets are concrete wrappers because Halmos 0.3.3
cannot use a symbolic index into a Solidity memory array. All seven credit
coordinates and all payment values remain symbolic. Withdrawal proofs cover
the pre-terminal fiber and the three terminal claimable equivalence classes
for every member. Two hostile-member proofs exercise reentrant callbacks into
all mutating entries before and after completion. A run is accepted only if
every expected proof reports PASS,
every summary has zero failures, and every proof has bounds: [].
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "contracts" / "OverlappingPoolEscrow.sol"
HARNESS = ROOT / "formal" / "OverlappingPoolEscrowBridge.t.sol"
CONFIG = ROOT / "foundry.toml"
DEFAULT_RESULTS = ROOT / "results"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
PASS = re.compile(
    r"\[PASS\]\s+(?P<name>check_[A-Za-z0-9_]+)\([^)]*\)\s+"
    r"\(paths:\s*(?P<paths>\d+),\s*time:\s*(?P<seconds>[0-9.]+)s,\s*"
    r"bounds:\s*\[\]\)"
)
SUMMARY = re.compile(
    r"Symbolic test result:\s*(?P<passed>\d+) passed;\s*(?P<failed>\d+) failed"
)
EDGE_CODES = tuple("".join(map(str, x)) for x in combinations(range(7), 4))
EDGE_GROUPS = (EDGE_CODES[:10], EDGE_CODES[10:20], EDGE_CODES[20:30], EDGE_CODES[30:])
WITHDRAW_GROUPS = ((0, 1), (2, 3), (4, 5), (6,))
TERMINAL_WITHDRAW_PREFIXES = (
    "Selected",
    "SelectedAfterPoolWithdraw",
    "Unselected",
)
AUXILIARY = (
    "check_EVMCompletedAcquireAlwaysReverts",
    "check_EVMConfigureSuccessClosure",
    "check_EVMExcessFundingReverts",
    "check_EVMEntryClosure",
    "check_EVMInvalidSetReverts",
    "check_EVMOversizeCreditReverts",
    "check_EVMReconfigureAlwaysReverts",
    "check_EVMUnauthorizedConfigure",
    "check_EVMWithdrawValueReverts",
)
HOSTILE_CALLBACK = (
    "check_EVMHostileCallbackPreTerminal",
    "check_EVMHostileCallbackTerminal",
)
ROLE_CONFLICT_SUFFIXES = (
    "Controller", "Member_0", "Member_1", "Member_2",
    "Member_3", "Member_4", "Member_5", "Member_6",
)
ROLE_CONFLICT_GROUPS = (
    ROLE_CONFLICT_SUFFIXES[:2], ROLE_CONFLICT_SUFFIXES[2:4],
    ROLE_CONFLICT_SUFFIXES[4:6], ROLE_CONFLICT_SUFFIXES[6:],
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_digest(path: Path) -> str:
    return digest(path.read_bytes())


def strip_metadata(bytecode: str) -> bytes:
    raw = bytes.fromhex(bytecode.removeprefix("0x"))
    if len(raw) < 2:
        raise RuntimeError("deployed bytecode too short")
    trailer = int.from_bytes(raw[-2:], "big") + 2
    if trailer > len(raw):
        raise RuntimeError("invalid Solidity metadata trailer")
    return raw[:-trailer]


def version(command: list[str]) -> str:
    result = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, check=True
    )
    return ANSI.sub("", result.stdout).strip()


def alternatives(items) -> str:
    return "(" + "|".join(map(str, items)) + ")"


def specs():
    jobs = []
    for index, group in enumerate(EDGE_GROUPS, 1):
        jobs.append({
            "tag": f"edge-{index}",
            "match": f"EVMEdge_{alternatives(group)}",
            "expected": tuple(f"check_EVMEdge_{code}" for code in group),
        })
    for index, group in enumerate(WITHDRAW_GROUPS, 1):
        jobs.append({
            "tag": f"withdraw-{index}",
            "match": f"EVMWithdrawProjectionNeutral_{alternatives(group)}",
            "expected": tuple(
                f"check_EVMWithdrawProjectionNeutral_{member}" for member in group
            ),
        })
    for prefix in TERMINAL_WITHDRAW_PREFIXES:
        for index, group in enumerate(WITHDRAW_GROUPS, 1):
            jobs.append({
                "tag": f"terminal-{prefix.lower()}-{index}",
                "match": (
                    f"EVMTerminalWithdraw{prefix}_{alternatives(group)}"
                ),
                "expected": tuple(
                    f"check_EVMTerminalWithdraw{prefix}_{member}"
                    for member in group
                ),
            })
    for index, group in enumerate(ROLE_CONFLICT_GROUPS, 1):
        jobs.append({
            "tag": f"role-conflict-{index}",
            "match": f"EVMRoleConflicted{alternatives(group)}",
            "expected": tuple(
                f"check_EVMRoleConflicted{suffix}" for suffix in group
            ),
        })
    jobs.append({
        "tag": "auxiliary",
        "match": (
            "EVM(CompletedAcquireAlwaysReverts|ConfigureSuccessClosure|"
            "ExcessFundingReverts|EntryClosure|HostileCallbackPreTerminal|"
            "HostileCallbackTerminal|InvalidSetReverts|OversizeCreditReverts|"
            "ReconfigureAlwaysReverts|UnauthorizedConfigure|"
            "WithdrawValueReverts)"
        ),
        "expected": AUXILIARY + HOSTILE_CALLBACK,
    })
    return jobs


def prepare(parent: Path, tag: str) -> Path:
    worker = parent / tag
    worker.mkdir()
    shutil.copy2(CONFIG, worker / "foundry.toml")
    shutil.copytree(ROOT / "contracts", worker / "contracts")
    shutil.copytree(ROOT / "formal", worker / "formal")
    return worker


def run_job(parent: Path, spec, solver: str, loop_bound: int):
    worker = prepare(parent, spec["tag"])
    command = [
        sys.executable, "-m", "halmos",
        "--forge-build-out", "halmos-out",
        "--contract", "OverlappingPoolEscrowBridgeProof",
        "--match-test", spec["match"],
        "--loop", str(loop_bound),
        "--solver", solver,
        "--solver-timeout-branching", "10000",
        "--solver-timeout-assertion", "120000",
        "--solver-threads", "2",
    ]
    environment = os.environ.copy()
    environment["FOUNDRY_OUT"] = "halmos-out"
    result = subprocess.run(
        command, cwd=worker, env=environment, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    output = ANSI.sub("", result.stdout).replace(str(parent), "<HALMOS_WORKDIR>")
    if result.returncode:
        raise RuntimeError(f"{spec['tag']} exited {result.returncode}\n{output}")
    lowered = output.lower()
    for forbidden in (
        "[fail]", "[error]", "counterexample", "loop unrolling bound",
        "paths were not fully explored"
    ):
        if forbidden in lowered:
            raise RuntimeError(f"{spec['tag']} contains {forbidden!r}")
    proofs = {
        match.group("name"): {
            "paths": int(match.group("paths")),
            "seconds": float(match.group("seconds")),
            "bounds": [],
        }
        for match in PASS.finditer(output)
    }
    expected = set(spec["expected"])
    if set(proofs) != expected:
        raise RuntimeError(
            f"{spec['tag']} names differ: expected={sorted(expected)}, actual={sorted(proofs)}"
        )
    summaries = list(SUMMARY.finditer(output))
    if len(summaries) != 1:
        raise RuntimeError(f"{spec['tag']} has {len(summaries)} summaries")
    if int(summaries[0].group("passed")) != len(expected) or int(
        summaries[0].group("failed")
    ) != 0:
        raise RuntimeError(f"{spec['tag']} has a non-passing summary")
    candidates = tuple((worker / "halmos-out").rglob("OverlappingPoolEscrow.json"))
    if len(candidates) != 1:
        raise RuntimeError(f"{spec['tag']} has {len(candidates)} contract artifacts")
    artifact = json.loads(candidates[0].read_text(encoding="utf-8"))
    deployed = artifact["deployedBytecode"]["object"]
    raw = bytes.fromhex(deployed.removeprefix("0x"))
    executable = strip_metadata(deployed)
    return {
        "tag": spec["tag"], "match": spec["match"],
        "expected": list(spec["expected"]), "proofs": proofs, "output": output,
        "runtimeBytecodeSha256": digest(raw),
        "runtimeExecutableSha256": digest(executable),
        "runtimeExecutableBytes": len(executable),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--loop", type=int, default=8)
    parser.add_argument("--solver", default="yices-2.6.4")
    parser.add_argument("--results-dir", type=Path, default=DEFAULT_RESULTS)
    args = parser.parse_args()
    if not 1 <= args.jobs <= 4:
        parser.error("--jobs must be between 1 and 4")
    if args.loop < 8:
        parser.error("--loop must be at least 8 for this harness")
    for required in (SOURCE, HARNESS, CONFIG):
        if not required.is_file():
            raise FileNotFoundError(required)

    job_specs = specs()
    by_tag = {}
    with tempfile.TemporaryDirectory(prefix="ope-halmos-") as temporary:
        parent = Path(temporary)
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = {
                executor.submit(run_job, parent, spec, args.solver, args.loop): spec["tag"]
                for spec in job_specs
            }
            for future in as_completed(futures):
                tag = futures[future]
                by_tag[tag] = future.result()
                print(f"HALMOS_JOB_{tag.upper().replace('-', '_')}=PASS")

    ordered = [by_tag[spec["tag"]] for spec in job_specs]
    proofs = {}
    full_hashes, executable_hashes, executable_sizes = set(), set(), set()
    log_parts = []
    for result in ordered:
        proofs.update(result["proofs"])
        full_hashes.add(result["runtimeBytecodeSha256"])
        executable_hashes.add(result["runtimeExecutableSha256"])
        executable_sizes.add(result["runtimeExecutableBytes"])
        log_parts.append(f"=== {result['tag']} ===\n{result['output'].rstrip()}\n")
    expected = {
        *(f"check_EVMEdge_{code}" for code in EDGE_CODES),
        *(f"check_EVMWithdrawProjectionNeutral_{i}" for i in range(7)),
        *(
            f"check_EVMTerminalWithdraw{prefix}_{i}"
            for prefix in TERMINAL_WITHDRAW_PREFIXES
            for i in range(7)
        ),
        *AUXILIARY,
        *(f"check_EVMRoleConflicted{x}" for x in ROLE_CONFLICT_SUFFIXES),
        *HOSTILE_CALLBACK,
    }
    if set(proofs) != expected:
        raise RuntimeError("aggregate proof-name closure failed")
    if len(full_hashes) != 1 or len(executable_hashes) != 1 or len(executable_sizes) != 1:
        raise RuntimeError("worker bytecode hashes differ")

    results = args.results_dir.resolve()
    results.mkdir(parents=True, exist_ok=True)
    log = "\n".join(log_parts).replace(str(ROOT), "<PROJECT_ROOT>")
    log_path = results / "halmos_evm_bridge.log"
    log_path.write_text(log, encoding="utf-8", newline="\n")
    certificate = {
        "schema": "overlapping-pool-halmos-bridge/v6",
        "status": "PASS",
        "claim": (
            "every admissible y has a verified configuration prefix, and "
            "T_OPE,postcfg^EVM <=_pi T_OPE^sch for the pinned Cancun runtime, "
            "including four share-right transfers to a symbolic role-separated payer, "
            "exact payer funding, and a concrete hostile mutating-reentry basis"
        ),
        "scope": {
            "evmRevision": "cancun",
            "deployment": (
                "exact non-proxy OverlappingPoolEscrow runtime; fixed controller; "
                "seven distinct nonzero members; symbolic external payer domain checked on every acquisition terminal; concrete hostile mutating-reentry basis checked"
            ),
            "coveredSuccessUniverse": (
                "successful configureCredits calls initialize the post-configuration roots; "
                "the refined LTS then covers all top-level acquireFour/withdraw calls; "
                "configure/acquire values range over uint256, withdraw is nonpayable, "
                "and reverting calls are projected stutters, not abstract edges"
            ),
            "projection": (
                "on the post-configuration LTS, pi=(credits,completed,terminalMask,"
                "deliveredShareMask,totalAcquisitionCallValue); configured is fixed true; "
                "acquirer and shareOwner are auxiliary caller/delivery invariants, while "
                "claimable balances and withdrawals are projection-neutral"
            ),
            "excluded": [
                "proxies, delegatecall, upgrades, CREATE/CREATE2, and selfdestruct",
                "gas exhaustion, chain reorganization, and non-Cancun revisions",
                "runtime-template mismatch or an uncertified deployment transaction",
                "off-contract beneficial ownership, cryptographic usability of each share right, member willingness, and production pass-through",
            ],
        },
        "tools": {
            "python": sys.version.split()[0], "platform": platform.platform(),
            "forge": version(["forge", "--version"]),
            "halmos": version([sys.executable, "-m", "halmos", "--version"]),
            "solver": version(["yices-smt2", "--version"]),
        },
        "trustedComputingBase": {
            "components": [
                "Solidity 0.8.28 compiler and Cancun code generation",
                "Foundry bytecode build used by Halmos",
                "Halmos 0.3.3 symbolic EVM semantics and path exploration",
                "Yices 2.6.4 SMT solving",
                "the harness assumptions and proof-obligation partition"
            ],
            "excludedEnvironment": [
                "out-of-gas behavior", "chain reorganization", "non-Cancun revisions"
            ]
        },        "parameters": {
            "halmosLoopBound": args.loop, "solver": args.solver,
            "parallelJobs": args.jobs, "solverTimeoutBranchingMs": 10000,
            "solverTimeoutAssertionMs": 120000, "solverThreadsPerJob": 2,
        },
        "inputs": {
            "contract": "contracts/OverlappingPoolEscrow.sol",
            "contractSha256": file_digest(SOURCE),
            "harness": "formal/OverlappingPoolEscrowBridge.t.sol",
            "harnessSha256": file_digest(HARNESS),
            "foundryConfig": "foundry.toml",
            "foundryConfigSha256": file_digest(CONFIG),
        },
        "compiledRuntime": {
            "foundryRuntimeBytecodeSha256": next(iter(full_hashes)),
            "foundryRuntimeExecutableSha256": next(iter(executable_hashes)),
            "foundryRuntimeExecutableBytes": next(iter(executable_sizes)),
        },
        "proofCounts": {
            "symbolicEdgeWrappers": len(EDGE_CODES),
            "symbolicPayerEdgeWrappers": len(EDGE_CODES),
            "preTerminalWithdrawWrappers": 7,
            "terminalWithdrawWrappers": 21,
            "auxiliaryObligations": len(AUXILIARY),
            "roleConflictObligations": len(ROLE_CONFLICT_SUFFIXES),
            "hostileCallbackObligations": len(HOSTILE_CALLBACK),
            "totalProofs": len(proofs), "failed": 0, "nonemptyBounds": 0,
        },
        "proofs": dict(sorted(proofs.items())),
        "transcript": {
            "path": "results/halmos_evm_bridge.log",
            "sha256": file_digest(log_path),
        },
    }
    certificate_path = results / "halmos_evm_bridge.json"
    certificate_path.write_text(
        json.dumps(certificate, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(f"HALMOS_EVM_EDGE_WRAPPERS={len(EDGE_CODES)}")
    print("HALMOS_EVM_PRETERMINAL_WITHDRAW_WRAPPERS=7")
    print("HALMOS_EVM_TERMINAL_WITHDRAW_WRAPPERS=21")
    print(f"HALMOS_EVM_HOSTILE_CALLBACK_OBLIGATIONS={len(HOSTILE_CALLBACK)}")
    print(f"HALMOS_EVM_TOTAL_PROOFS={len(proofs)}")
    print("HALMOS_EVM_NONEMPTY_BOUNDS=0")
    print("CONFIGURATION_PREFIX_TOTALITY=PASS")
    print("POSTCONFIGURATION_EVM_TO_SCHEMA_BRIDGE=PASS")
    print(f"HALMOS_CERTIFICATE={certificate_path}")


if __name__ == "__main__":
    main()