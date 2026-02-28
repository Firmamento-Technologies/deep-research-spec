"""RLM Runtime — sandboxed REPL loop compatible with LangGraph async context.

Key design decisions:
  1. Thread isolation: run() spawns a daemon thread with its own event loop.
     This avoids 'cannot run nested event loop' errors in LangGraph.
  2. RestrictedPython sandbox: blocks filesystem, network, __import__.
  3. llm_query() is synchronous inside the REPL thread (asyncio.run is safe
     because the thread has its own fresh event loop).
  4. CostEntry emission is handled by budget_bridge.py, NOT here.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any, Callable

import anthropic
from RestrictedPython import compile_restricted, safe_builtins, safe_globals


@dataclass
class RLMResult:
    output: Any
    cost_usd: float
    subcalls: int
    iterations: int
    log: list[dict]
    method: str  # "repl_final" | "root_final" | "fallback"
    root_model: str = "claude-sonnet-4-5"
    sub_model: str = "claude-haiku-3-5"


@dataclass
class RLMRuntime:
    """Sandboxed REPL runtime implementing the RLM pattern (arxiv:2512.24601).

    Args:
        root_model:      Model for the root agent that writes/executes REPL code.
        sub_model:       Model for llm_query() sub-calls inside the REPL.
        max_subcalls:    Hard cap on llm_query() invocations per run.
        max_iterations:  Hard cap on root-model agentic loop iterations.
        cost_hard_limit: USD cap; run aborts if exceeded.
        timeout_seconds: Wall-clock timeout for the entire run().
    """

    root_model: str = "claude-sonnet-4-5"
    sub_model: str = "claude-haiku-3-5"
    max_subcalls: int = 20
    max_iterations: int = 12
    cost_hard_limit: float = 0.30
    timeout_seconds: int = 120

    # Internal state — reset on every run()
    _subcall_count: int = field(default=0, init=False, repr=False)
    _total_cost: float = field(default=0.0, init=False, repr=False)
    _log: list[dict] = field(default_factory=list, init=False, repr=False)
    _client: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._client = anthropic.AsyncAnthropic()

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    async def run(self, context: dict, task_instruction: str) -> RLMResult:
        """Execute an RLM task over the given context dict.

        Runs in a daemon thread with its own event loop so it is safe to
        await from an already-running async context (e.g. LangGraph nodes).

        Args:
            context:          Python-serializable dict loaded into the REPL.
            task_instruction: Natural-language task for the root agent.

        Returns:
            RLMResult with output, cost, subcall count, and execution log.
        """
        result_queue: Queue = Queue()

        def _thread_worker() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    self._run_async(context, task_instruction)
                )
                result_queue.put(("ok", result))
            except Exception as exc:  # noqa: BLE001
                result_queue.put(("error", exc))
            finally:
                loop.close()

        thread = threading.Thread(target=_thread_worker, daemon=True)
        thread.start()

        outer_loop = asyncio.get_event_loop()
        try:
            result_type, value = await outer_loop.run_in_executor(
                None,
                lambda: result_queue.get(timeout=self.timeout_seconds + 5),
            )
        except Empty:
            self._log_event("TIMEOUT", f"RLM did not complete within {self.timeout_seconds}s")
            return RLMResult(
                output=None,
                cost_usd=self._total_cost,
                subcalls=self._subcall_count,
                iterations=0,
                log=self._log,
                method="fallback",
                root_model=self.root_model,
                sub_model=self.sub_model,
            )

        if result_type == "error":
            raise value  # type: ignore[misc]
        return value  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Agentic loop
    # ------------------------------------------------------------------

    async def _run_async(self, context: dict, task_instruction: str) -> RLMResult:
        self._subcall_count = 0
        self._total_cost = 0.0
        self._log = []

        # Initialise REPL state with context variables
        repl_state: dict = {}
        context_init_code = self._serialize_context(context)
        try:
            exec(context_init_code, repl_state)  # noqa: S102
        except Exception as exc:  # noqa: BLE001
            self._log_event("CONTEXT_INIT_ERROR", str(exc))

        # Inject runtime helpers into REPL
        repl_state["llm_query"] = self._make_sync_llm_query()
        repl_state["llm_query_batched"] = self._make_sync_llm_query_batched()
        repl_state["final_answer"] = None

        system_prompt = self._build_system_prompt(task_instruction)
        messages: list[dict] = [
            {
                "role": "user",
                "content": (
                    "Context initialized in your REPL.\n\n"
                    f"Context variables available:\n```python\n{context_init_code[:2000]}\n```\n\n"
                    "Execute your task."
                ),
            }
        ]

        for iteration in range(self.max_iterations):
            if self._total_cost >= self.cost_hard_limit:
                self._log_event(
                    "BUDGET_EXCEEDED",
                    f"${self._total_cost:.4f} >= hard limit ${self.cost_hard_limit}",
                )
                break

            t0 = time.monotonic()
            root_text = await self._call_root(system_prompt, messages)
            latency_ms = int((time.monotonic() - t0) * 1000)
            self._log_event("ROOT_CALL", {"iter": iteration, "latency_ms": latency_ms})

            messages.append({"role": "assistant", "content": root_text})

            code_blocks = self._extract_repl_blocks(root_text)

            if not code_blocks:
                # Root model replied in prose — treat as final answer
                return RLMResult(
                    output=self._try_parse_json(root_text),
                    cost_usd=self._total_cost,
                    subcalls=self._subcall_count,
                    iterations=iteration + 1,
                    log=self._log,
                    method="root_final",
                    root_model=self.root_model,
                    sub_model=self.sub_model,
                )

            repl_outputs: list[str] = []
            for code in code_blocks:
                out = self._exec_code_sandboxed(code, repl_state)
                repl_outputs.append(out)

            combined = "\n---\n".join(repl_outputs)
            messages.append({"role": "user", "content": f"REPL output:\n{combined}"})

            if repl_state.get("final_answer") is not None:
                return RLMResult(
                    output=repl_state["final_answer"],
                    cost_usd=self._total_cost,
                    subcalls=self._subcall_count,
                    iterations=iteration + 1,
                    log=self._log,
                    method="repl_final",
                    root_model=self.root_model,
                    sub_model=self.sub_model,
                )

        # Exhausted iterations — return last assistant message
        last_assistant = next(
            (m["content"] for m in reversed(messages) if m["role"] == "assistant"),
            "",
        )
        return RLMResult(
            output=self._try_parse_json(last_assistant),
            cost_usd=self._total_cost,
            subcalls=self._subcall_count,
            iterations=self.max_iterations,
            log=self._log,
            method="fallback",
            root_model=self.root_model,
            sub_model=self.sub_model,
        )

    # ------------------------------------------------------------------
    # Sandboxed REPL execution
    # ------------------------------------------------------------------

    def _exec_code_sandboxed(self, code: str, state: dict) -> str:
        """Execute code in a RestrictedPython sandbox.

        Captures stdout. Updates ``state`` with new variables produced.
        Never raises — returns error text so the root model can self-correct.
        """
        import io
        from contextlib import redirect_stdout

        restricted_builtins = dict(safe_builtins)
        restricted_builtins.update(
            {
                "len": len,
                "range": range,
                "enumerate": enumerate,
                "zip": zip,
                "sorted": sorted,
                "filter": filter,
                "map": map,
                "list": list,
                "dict": dict,
                "str": str,
                "int": int,
                "float": float,
                "bool": bool,
                "max": max,
                "min": min,
                "sum": sum,
                "isinstance": isinstance,
                "print": print,
                "json": __import__("json"),
                "re": __import__("re"),
            }
        )

        safe_env = {**safe_globals, "__builtins__": restricted_builtins, **state}
        stdout_buf = io.StringIO()

        try:
            compiled = compile_restricted(code, "<rlm_repl>", "exec")
            with redirect_stdout(stdout_buf):
                exec(compiled, safe_env)  # noqa: S102

            # Propagate new variables back into shared state
            skip = set(safe_globals.keys()) | {"__builtins__"}
            for k, v in safe_env.items():
                if not k.startswith("_") and k not in skip:
                    state[k] = v

            output = stdout_buf.getvalue().strip()
            self._log_event("REPL_OK", {"output_len": len(output)})
            return output or "(no stdout)"

        except SyntaxError as exc:
            msg = f"SyntaxError: {exc}"
            self._log_event("REPL_SYNTAX_ERROR", msg)
            return msg
        except Exception as exc:  # noqa: BLE001
            msg = f"REPL Error [{type(exc).__name__}]: {exc}"
            self._log_event("REPL_RUNTIME_ERROR", msg)
            return msg

    # ------------------------------------------------------------------
    # Synchronous llm_query helpers (called from REPL thread)
    # ------------------------------------------------------------------

    def _make_sync_llm_query(self) -> Callable:
        """Return a sync llm_query(prompt, chunk='') for use inside REPL.

        Safe to call with asyncio.run() because the REPL runs in a thread
        that owns a fresh event loop (no nesting).
        """
        runtime = self

        def llm_query(prompt: str, context_chunk: str = "") -> str:
            if runtime._subcall_count >= runtime.max_subcalls:
                return "[SUBCALL_LIMIT_REACHED]"
            runtime._subcall_count += 1
            full_prompt = (
                f"{prompt}\n\nContext:\n{context_chunk}" if context_chunk else prompt
            )

            async def _call() -> str:
                t0 = time.monotonic()
                response = await runtime._client.messages.create(
                    model=runtime.sub_model,
                    max_tokens=1500,
                    temperature=0.1,
                    messages=[{"role": "user", "content": full_prompt}],
                )
                latency = int((time.monotonic() - t0) * 1000)
                text = response.content[0].text
                tokens_in = response.usage.input_tokens
                tokens_out = response.usage.output_tokens
                # claude-haiku-3-5 pricing: $0.80/1M in, $4.00/1M out
                cost = (tokens_in * 0.80 + tokens_out * 4.0) / 1_000_000
                runtime._total_cost += cost
                runtime._log_event(
                    "SUBCALL",
                    {
                        "n": runtime._subcall_count,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "cost_usd": round(cost, 6),
                        "latency_ms": latency,
                    },
                )
                return text

            return asyncio.run(_call())

        return llm_query

    def _make_sync_llm_query_batched(self) -> Callable:
        """Return a sync llm_query_batched(prompts, chunks) for parallel sub-calls."""
        runtime = self

        def llm_query_batched(
            prompts: list[str], chunks: list[str] | None = None
        ) -> list[str]:
            if chunks is None:
                chunks = [""] * len(prompts)

            async def _batch() -> list[str]:
                tasks = []
                for prompt, chunk in zip(prompts, chunks):
                    if runtime._subcall_count >= runtime.max_subcalls:
                        tasks.append(
                            asyncio.coroutine(lambda: "[SUBCALL_LIMIT_REACHED]")()
                        )
                    else:
                        runtime._subcall_count += 1
                        full = f"{prompt}\n\nContext:\n{chunk}" if chunk else prompt
                        tasks.append(
                            runtime._client.messages.create(
                                model=runtime.sub_model,
                                max_tokens=1000,
                                temperature=0.1,
                                messages=[{"role": "user", "content": full}],
                            )
                        )
                responses = await asyncio.gather(*tasks, return_exceptions=True)
                results: list[str] = []
                for r in responses:
                    if isinstance(r, Exception):
                        results.append(f"[ERROR: {r}]")
                    elif isinstance(r, str):
                        results.append(r)
                    else:
                        text = r.content[0].text
                        tokens_in = r.usage.input_tokens
                        tokens_out = r.usage.output_tokens
                        cost = (tokens_in * 0.80 + tokens_out * 4.0) / 1_000_000
                        runtime._total_cost += cost
                        results.append(text)
                return results

            return asyncio.run(_batch())

        return llm_query_batched

    # ------------------------------------------------------------------
    # Root model call
    # ------------------------------------------------------------------

    async def _call_root(self, system: str, messages: list[dict]) -> str:
        """Call root model and track cost in log."""
        t0 = time.monotonic()
        # claude-sonnet-4-5 pricing: $3.00/1M in, $15.00/1M out
        response = await self._client.messages.create(
            model=self.root_model,
            max_tokens=4096,
            temperature=0.2,
            system=system,
            messages=messages,
        )
        latency = int((time.monotonic() - t0) * 1000)
        text = response.content[0].text
        tokens_in = response.usage.input_tokens
        tokens_out = response.usage.output_tokens
        cost = (tokens_in * 3.0 + tokens_out * 15.0) / 1_000_000
        self._total_cost += cost
        self._log_event(
            "ROOT_TOKENS",
            {
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": round(cost, 6),
                "latency_ms": latency,
            },
        )
        return text

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _serialize_context(self, context: dict) -> str:
        """Serialize context dict to Python assignment statements."""
        lines: list[str] = []
        for k, v in context.items():
            if isinstance(v, str):
                escaped = v.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
                lines.append(f'{k} = """{escaped}"""')
            else:
                try:
                    lines.append(f"{k} = {json.dumps(v, ensure_ascii=False)}")
                except TypeError:
                    lines.append(f"{k} = {v!r}")
        return "\n".join(lines)

    def _extract_repl_blocks(self, text: str) -> list[str]:
        return re.findall(r"```repl\n(.*?)```", text, re.DOTALL)

    def _try_parse_json(self, text: str) -> Any:
        """Try to parse JSON from a code block or raw text; return str on failure."""
        match = re.search(r"```(?:json)?\n(.*?)```", text, re.DOTALL)
        raw = match.group(1) if match else text
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return text

    def _build_system_prompt(self, task: str) -> str:
        return f"""You are an AI agent operating a Python REPL to complete a research analysis task.
Context variables are pre-loaded in your REPL. Inspect, filter, and analyze them.

Use llm_query(prompt, context_chunk) to semantically analyze specific text chunks.
Use llm_query_batched(prompts, chunks) for parallel analysis of multiple chunks.

REPL syntax — wrap code in triple backticks with the 'repl' tag:
```repl
# your Python code here
result = llm_query("Summarize key claims", source_texts["0"])
print(result)
```

CONSTRAINTS:
- Maximum {self.max_subcalls} llm_query / llm_query_batched calls total
- Budget hard limit: ${self.cost_hard_limit:.2f} USD
- When task is complete: set  final_answer = <your result>  (dict or str)
- Do NOT set final_answer until you have gathered sufficient evidence

TASK: {task}"""

    def _log_event(self, event: str, detail: Any) -> None:
        self._log.append({"event": event, "detail": detail, "ts": time.monotonic()})


def get_rlm_runtime(
    root_model: str = "claude-sonnet-4-5",
    sub_model: str = "claude-haiku-3-5",
    max_subcalls: int = 20,
    cost_hard_limit: float = 0.25,
    timeout_seconds: int = 90,
) -> RLMRuntime:
    """Factory with conservative DRS-safe defaults."""
    return RLMRuntime(
        root_model=root_model,
        sub_model=sub_model,
        max_subcalls=max_subcalls,
        cost_hard_limit=cost_hard_limit,
        timeout_seconds=timeout_seconds,
    )
