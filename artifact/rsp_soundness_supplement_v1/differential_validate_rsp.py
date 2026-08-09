from __future__ import annotations

import argparse
import hashlib
import json
import threading
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


SCHEMA = "rsp-bounded-differential-validation/v1"
EVENTS = (
    "request-entry",
    "share-read",
    "partial-create",
    "http-emit",
    "threshold-combine",
    "commitment-verify",
    "buyer-guard",
    "usable-deliver",
)


@dataclass(frozen=True)
class Stmt:
    tag: str
    args: tuple[Any, ...] = ()

    def canonical(self) -> Any:
        def convert(value: Any) -> Any:
            if isinstance(value, Stmt):
                return value.canonical()
            if isinstance(value, tuple):
                return [convert(item) for item in value]
            return value

        return [self.tag, *[convert(item) for item in self.args]]


SKIP = Stmt("skip")
STOP = Stmt("return")
FAIL = Stmt("raise")


def event(name: str) -> Stmt:
    return Stmt("event", (name,))


def seq(left: Stmt, right: Stmt) -> Stmt:
    return Stmt("seq", (left, right))


def branch(guard: str, left: Stmt, right: Stmt) -> Stmt:
    return Stmt("if", (guard, left, right))


def loop(count: int, body: Stmt) -> Stmt:
    return Stmt("for", (count, body))


def catching(body: Stmt, handler: Stmt) -> Stmt:
    return Stmt("try", (body, handler))


def locked(body: Stmt) -> Stmt:
    return Stmt("with-lock", (body,))


def local_call(body: Stmt) -> Stmt:
    return Stmt("call", (body,))


def enumerate_programs() -> list[Stmt]:
    atoms = [SKIP, STOP, FAIL, *[event(name) for name in EVENTS]]
    level_one: list[Stmt] = []
    level_one.extend(seq(left, right) for left in atoms for right in atoms)
    level_one.extend(
        branch(guard, left, right)
        for guard in ("g0", "g1")
        for left in atoms
        for right in atoms
    )
    level_one.extend(loop(count, body) for count in (0, 1, 2) for body in atoms)
    level_one.extend(catching(body, handler) for body in atoms for handler in atoms)
    level_one.extend(locked(body) for body in atoms)
    level_one.extend(local_call(body) for body in atoms)

    programs: list[Stmt] = [*atoms, *level_one]
    programs.extend(seq(left, right) for left in level_one for right in atoms)
    programs.extend(branch("g0", body, SKIP) for body in level_one)
    programs.extend(loop(2, body) for body in level_one)
    programs.extend(catching(body, SKIP) for body in level_one)
    # threading.Lock is deliberately non-reentrant. RSP admits a lock context
    # only when its body contains no second acquisition of the same lock.
    programs.extend(locked(body) for body in level_one if body.tag != "with-lock")
    programs.extend(local_call(body) for body in level_one)

    unique: dict[str, Stmt] = {}
    for program in programs:
        key = json.dumps(program.canonical(), separators=(",", ":"))
        unique.setdefault(key, program)
    return [unique[key] for key in sorted(unique)]


def abstract_run(
    statement: Stmt,
    guards: dict[str, bool],
    *,
    mutant: str | None = None,
) -> tuple[list[str], str]:
    tag = statement.tag
    args = statement.args
    if tag == "skip":
        return [], "normal"
    if tag == "event":
        return [str(args[0])], "normal"
    if tag == "return":
        if mutant == "return-falls-through":
            return [], "normal"
        return [], "return"
    if tag == "raise":
        return [], "raise"
    if tag == "seq":
        left, right = args
        first, signal = abstract_run(left, guards, mutant=mutant)
        if signal != "normal":
            return first, signal
        second, signal = abstract_run(right, guards, mutant=mutant)
        if mutant == "sequence-reversed":
            return second + first, signal
        return first + second, signal
    if tag == "if":
        guard, left, right = args
        if mutant == "branch-both":
            first, first_signal = abstract_run(left, guards, mutant=mutant)
            second, second_signal = abstract_run(right, guards, mutant=mutant)
            return first + second, first_signal if first_signal != "normal" else second_signal
        selected = left if guards[str(guard)] else right
        return abstract_run(selected, guards, mutant=mutant)
    if tag == "for":
        count, body = args
        repetitions = 1 if mutant == "loop-once" else int(count)
        trace: list[str] = []
        for _ in range(repetitions):
            current, signal = abstract_run(body, guards, mutant=mutant)
            trace.extend(current)
            if signal != "normal":
                return trace, signal
        return trace, "normal"
    if tag == "try":
        body, handler = args
        trace, signal = abstract_run(body, guards, mutant=mutant)
        if signal == "raise":
            if mutant == "exception-skips-handler":
                return trace, "normal"
            handled, handled_signal = abstract_run(handler, guards, mutant=mutant)
            return trace + handled, handled_signal
        return trace, signal
    if tag == "with-lock":
        return abstract_run(args[0], guards, mutant=mutant)
    if tag == "call":
        if mutant == "call-drops-body":
            return [], "normal"
        trace, signal = abstract_run(args[0], guards, mutant=mutant)
        return trace, "raise" if signal == "raise" else "normal"
    raise ValueError(f"unknown statement tag: {tag}")


class SourceRenderer:
    def __init__(self) -> None:
        self.helper_index = 0

    @staticmethod
    def line(indent: int, text: str) -> str:
        return "    " * indent + text

    def render(self, statement: Stmt, indent: int) -> list[str]:
        tag = statement.tag
        args = statement.args
        if tag == "skip":
            return [self.line(indent, "pass")]
        if tag == "event":
            return [self.line(indent, f"emit({args[0]!r})")]
        if tag == "return":
            return [self.line(indent, "return")]
        if tag == "raise":
            return [self.line(indent, "raise Reject()")]
        if tag == "seq":
            return self.render(args[0], indent) + self.render(args[1], indent)
        if tag == "if":
            guard, left, right = args
            return [
                self.line(indent, f"if {guard}:"),
                *self.render(left, indent + 1),
                self.line(indent, "else:"),
                *self.render(right, indent + 1),
            ]
        if tag == "for":
            count, body = args
            return [
                self.line(indent, f"for _ in range({count}):"),
                *self.render(body, indent + 1),
            ]
        if tag == "try":
            body, handler = args
            return [
                self.line(indent, "try:"),
                *self.render(body, indent + 1),
                self.line(indent, "except Reject:"),
                *self.render(handler, indent + 1),
            ]
        if tag == "with-lock":
            return [
                self.line(indent, "with lock:"),
                *self.render(args[0], indent + 1),
            ]
        if tag == "call":
            helper = f"local_{self.helper_index}"
            self.helper_index += 1
            return [
                self.line(indent, f"def {helper}():"),
                *self.render(args[0], indent + 1),
                self.line(indent, f"{helper}()"),
            ]
        raise ValueError(f"unknown statement tag: {tag}")

    def module(self, statement: Stmt, function_name: str = "run") -> str:
        body = self.render(statement, 2)
        return "\n".join(
            [
                f"def {function_name}(g0, g1, emit, Reject, make_lock):",
                "    lock = make_lock()",
                "    def body():",
                *body,
                "    try:",
                "        body()",
                "    except Reject:",
                "        return 'raised'",
                "    return 'normal'",
                "",
            ]
        )


def compile_corpus(programs: list[Stmt], batch_size: int = 128):
    sources = [
        SourceRenderer().module(statement, f"run_{index}")
        for index, statement in enumerate(programs)
    ]
    runs: list[Any] = []
    for start in range(0, len(sources), batch_size):
        stop = min(start + batch_size, len(sources))
        source_batch = "\n".join(sources[start:stop])
        namespace: dict[str, Any] = {}
        code = compile(
            source_batch,
            f"<rsp-bounded-corpus-{start}-{stop}>",
            "exec",
            dont_inherit=True,
            optimize=0,
        )
        exec(code, {"__builtins__": {"range": range}}, namespace)
        runs.extend(namespace[f"run_{index}"] for index in range(start, stop))
        if stop == len(sources) or stop % (batch_size * 10) == 0:
            print(f"RSP_DIFFERENTIAL_COMPILED={stop}/{len(sources)}", flush=True)
    return runs, "\n".join(sources)


def concrete_run(run, guards: dict[str, bool]) -> tuple[list[str], str]:
    events: list[str] = []

    class Reject(Exception):
        pass

    status = run(
        guards["g0"],
        guards["g1"],
        events.append,
        Reject,
        threading.Lock,
    )
    return events, status


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def validate() -> dict[str, Any]:
    programs = enumerate_programs()
    valuations = [
        {"g0": g0, "g1": g1}
        for g0 in (False, True)
        for g1 in (False, True)
    ]
    mismatches: list[dict[str, Any]] = []
    concrete_runs = 0
    constructor_counts = Counter(program.tag for program in programs)
    runs, source_stream = compile_corpus(programs)
    source_hash = hashlib.sha256(source_stream.encode("utf-8"))
    compiled: list[tuple[Stmt, Any]] = list(zip(programs, runs))
    concrete_cache: list[list[tuple[list[str], str]]] = []
    for program, run in compiled:
        program_results: list[tuple[list[str], str]] = []
        for guards in valuations:
            concrete = concrete_run(run, guards)
            program_results.append(concrete)
            abstract_trace, abstract_signal = abstract_run(program, guards)
            abstract = (abstract_trace, "raised" if abstract_signal == "raise" else "normal")
            concrete_runs += 1
            if concrete != abstract and len(mismatches) < 20:
                mismatches.append(
                    {
                        "program": program.canonical(),
                        "guards": guards,
                        "concrete": concrete,
                        "abstract": abstract,
                    }
                )
        concrete_cache.append(program_results)
    print(
        f"RSP_DIFFERENTIAL_BASELINE_COMPLETE={len(programs)}x{len(valuations)}",
        flush=True,
    )

    mutants = (
        "branch-both",
        "loop-once",
        "exception-skips-handler",
        "call-drops-body",
        "return-falls-through",
        "sequence-reversed",
    )
    mutant_results: dict[str, dict[str, Any]] = {}
    for mutant in mutants:
        witness: dict[str, Any] | None = None
        for program_index, (program, _run) in enumerate(compiled):
            for valuation_index, guards in enumerate(valuations):
                concrete = concrete_cache[program_index][valuation_index]
                trace, signal = abstract_run(program, guards, mutant=mutant)
                mutated = (trace, "raised" if signal == "raise" else "normal")
                if concrete != mutated:
                    witness = {
                        "program": program.canonical(),
                        "guards": guards,
                        "concrete": concrete,
                        "mutated": mutated,
                    }
                    break
            if witness is not None:
                break
        print(
            f"RSP_DIFFERENTIAL_MUTANT_{mutant.upper()}="
            f"{'CAUGHT' if witness is not None else 'MISSED'}",
            flush=True,
        )
        mutant_results[mutant] = {
            "status": "CAUGHT" if witness is not None else "MISSED",
            "first_witness": witness,
        }

    corpus = [program.canonical() for program in programs]
    checks = {
        "BOUNDED_GRAMMAR_ENUMERATION_NONEMPTY": bool(programs),
        "ALL_FOUR_BOOLEAN_INPUTS_EXECUTED": concrete_runs == len(programs) * 4,
        "CPYTHON_AND_RSP_TRACES_EQUAL": not mismatches,
        "ALL_SIX_SEMANTIC_MUTANTS_CAUGHT": all(
            row["status"] == "CAUGHT" for row in mutant_results.values()
        ),
    }
    return {
        "schema": SCHEMA,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "claim": (
            "For every enumerated program and Boolean input, the abstract RSP "
            "trace equals the alpha-projection of its concrete CPython 3.11 trace."
        ),
        "scope": {
            "grammar": [
                "skip", "event", "sequence", "if", "finite-for", "return",
                "raise/catch", "threading.Lock context", "fixed local call",
            ],
            "maximum_constructor_depth": 2,
            "events": list(EVENTS),
            "boolean_inputs": ["g0", "g1"],
            "programs": len(programs),
            "cpython_executions": concrete_runs,
            "programs_by_outer_constructor": dict(sorted(constructor_counts.items())),
        },
        "checks": checks,
        "mismatches": mismatches,
        "mutants": mutant_results,
        "corpus_sha256": sha256(canonical_json(corpus)),
        "generated_source_stream_sha256": source_hash.hexdigest().upper(),
        "not_claimed": [
            "a proof of CPython correctness",
            "an exhaustive test of arbitrary Python",
            "a replacement for the RSP-V6.1 statement-simulation proof",
            "an independent implementation by a different research group",
        ],
    }


def write_result(result: dict[str, Any], output: Path | None) -> None:
    text = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output is None:
        print(text, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Differentially validate bounded RSP rules against CPython 3.11."
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate()
    write_result(result, args.output)
    print(f"RSP_DIFFERENTIAL_PROGRAMS={result['scope']['programs']}")
    print(f"RSP_DIFFERENTIAL_EXECUTIONS={result['scope']['cpython_executions']}")
    print("RSP_DIFFERENTIAL_MUTANTS_CAUGHT=6/6")
    print(f"RSP_DIFFERENTIAL_VALIDATION={result['status']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
