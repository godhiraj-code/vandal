"""Observe Playwright operations and Locator assertions while --vandal is active."""
import asyncio
import functools
import inspect
import json
import uuid
from contextvars import ContextVar

from .core import VandalEngine

# These are the public operations we observe. Locator selectors use Playwright's
# internal representation so get_by_role(), chaining and nth() can be replayed.
OPERATIONS = (
    "click", "dblclick", "fill", "check", "uncheck", "set_checked", "select_option",
    "press", "type", "hover", "tap", "focus", "dispatch_event", "input_value",
    "inner_text", "text_content", "all_text_contents", "all_inner_texts",
    "get_attribute", "is_visible", "is_enabled", "is_checked", "count", "wait_for",
    "wait_for_selector", "set_input_files",
)
FACTORIES = (
    "locator", "get_by_role", "get_by_text", "get_by_label", "get_by_placeholder",
    "get_by_test_id", "get_by_title", "get_by_alt_text", "filter", "nth",
)
def frame_parts(selector):
    """Split the final frame traversal from a Playwright selector.

    Quoted text and nested JSON selectors can contain the traversal spelling;
    only unquoted selector parts are frame boundaries.
    """
    parts, start, quote, escaped, index, depth = [], 0, None, False, 0, 0
    while index < len(selector):
        char = selector[index]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif quote:
            if char == quote:
                quote = None
        elif char in ("'", '"', "`"):
            quote = char
        elif char in "[({":
            depth += 1
        elif char in "])}":
            depth = max(0, depth - 1)
        elif depth == 0 and selector[index:index + 2] == ">>":
            parts.append(selector[start:index].strip())
            index += 1
            start = index + 1
        index += 1
    parts.append(selector[start:].strip())
    boundaries = [i for i, part in enumerate(parts)
                  if part == "internal:control=enter-frame"]
    if not boundaries:
        return "", selector
    boundary = boundaries[-1] + 1
    return " >> ".join(parts[:boundary]) + " >> ", " >> ".join(parts[boundary:])


class Instrumentation:
    def __init__(self, state):
        self.state = state
        self.originals = []
        self._busy = ContextVar("vandal_instrumentation_busy", default=False)
        self._seen_key = "__vandal_seen_" + uuid.uuid4().hex
        self._engine_name = "vandal_" + uuid.uuid4().hex
        self._binding_name = self._engine_name + "_receipt"
        self._registrations = {}
        self._bindings = {}

    @property
    def busy(self):
        return self._busy.get()

    @busy.setter
    def busy(self, value):
        self._busy.set(value)

    def record(self, selector, operation, kwargs):
        if selector and self.state.current is not None:
            events = self.state.current["targets"]
            entry = events.setdefault(selector, {"operations": [], "force": False})
            if operation not in entry["operations"]:
                entry["operations"].append(operation)
            entry["force"] |= bool(kwargs.get("force"))

    def selector(self, obj, args, kwargs):
        if hasattr(obj, "_impl_obj") and hasattr(obj._impl_obj, "_selector"):
            return obj._impl_obj._selector
        return args[0] if args and isinstance(args[0], str) else kwargs.get("selector")

    def mutation(self, obj, selector):
        worker = self.state.worker
        if not worker or worker.get("control") or self.state.phase != "call":
            return None
        target = worker["selector"]
        if hasattr(obj, "_impl_obj") and hasattr(obj._impl_obj, "_selector"):
            # A configured CSS target may be acted on through a role, text or
            # chained locator. Resolve it independently in the operation's frame.
            frame = next(frame for frame in obj.page.frames
                         if frame._impl_obj is obj._impl_obj._frame)
            prefix, _ = frame_parts(selector)
            target_prefix, _ = frame_parts(target)
            locator = frame.locator(target if target_prefix else prefix + target)
        else:
            locator = obj.locator(target)
        return locator, self.mutation_script()

    def mutation_script(self):
        worker = self.state.worker
        script = VandalEngine.MUTATIONS[worker["strategy"]].replace(
            "%DEEP_SELECT%", "(root) => fresh"
        )
        # Keep identity independently of strategy-owned DOM attributes. slow_load
        # removes its marker when it restores visibility, but must not run twice
        # on that node. A WeakSet still permits replacement nodes and navigation.
        expression = """elements => {
            const seen = globalThis[KEY] || (globalThis[KEY] = new WeakSet());
            const fresh = elements.filter(el => !seen.has(el)
                && (!el.hasAttribute('data-vandalized')
                    || el.getAttribute('data-vandalized') === STRATEGY));
            fresh.forEach(el => {
                // cloneNode copies attributes/styles but not event listeners
                // or restoration timers. A copied marker is not node identity.
                const copied = el.getAttribute('data-vandalized') === STRATEGY;
                if (STRATEGY === 'slow_load') {
                    if (copied && el.hasAttribute(VISIBILITY))
                        el.style.visibility = el.getAttribute(VISIBILITY);
                    el.setAttribute(VISIBILITY, el.style.visibility);
                }
                if (copied) el.removeAttribute('data-vandalized');
            });
            const apply = SCRIPT;
            apply(null);
            const changed = fresh.filter(el => el.getAttribute('data-vandalized') === STRATEGY);
            changed.forEach(el => seen.add(el));
            return changed.length;
        }""".replace("SCRIPT", script).replace("KEY", json.dumps(self._seen_key)).replace(
            "STRATEGY", json.dumps(worker["strategy"])
        ).replace(
            "VISIBILITY", json.dumps("data-vandal-visibility-" + self._engine_name)
        )
        return expression

    async def register_engine(self, selectors):
        if selectors not in self._registrations:
            self._registrations[selectors] = [asyncio.Lock(), False]
        registration = self._registrations[selectors]
        async with registration[0]:
            if registration[1]:
                return
            # This branch contributes no matches. It only mutates the roots that
            # Playwright resolved, on every native query/retry, before resolving
            # the original operation. Both branches use Playwright's own engines.
            script = """({
                queryAll(root) {
                    try {
                        const changed = (MUTATE)([root]);
                        if (changed) globalThis[BINDING](changed, null).catch(() => {});
                    } catch (error) {
                        globalThis[BINDING](0, String(error)).catch(() => {});
                    }
                    return [];
                }
            })""".replace("MUTATE", self.mutation_script()).replace(
                "BINDING", json.dumps(self._binding_name)
            )
            await selectors.register(self._engine_name, script=script)
            registration[1] = True

    def wrap_start(self, original):
        # Playwright snapshots custom selector engines when a document's
        # injected script is first created. Register before any browser/page
        # exists, including pages loaded by fixtures and persistent contexts.
        if inspect.iscoroutinefunction(original):
            @functools.wraps(original)
            async def asynchronous(manager, *args, **kwargs):
                playwright = await original(manager, *args, **kwargs)
                if self.state.worker and not self.state.worker.get("control"):
                    await self.register_engine(playwright._impl_obj.selectors)
                return playwright
            return asynchronous

        @functools.wraps(original)
        def synchronous(manager, *args, **kwargs):
            playwright = original(manager, *args, **kwargs)
            if self.state.worker and not self.state.worker.get("control"):
                playwright._sync(self.register_engine(playwright._impl_obj.selectors))
            return playwright
        return synchronous

    def retry_selector(self, selector):
        prefix, operation = frame_parts(selector)
        target_prefix, target = frame_parts(self.state.worker["selector"])
        if target_prefix and target_prefix != prefix:
            # The existing independent injection can address another frame, but
            # Playwright disallows crossing frames inside an internal:or branch.
            return selector
        return (prefix + target + " >> " + self._engine_name
                + "=apply >> internal:or=" + json.dumps(operation))

    async def register_receipts(self, context):
        if context not in self._bindings:
            self._bindings[context] = [asyncio.Lock(), False]
        registration = self._bindings[context]
        async with registration[0]:
            if registration[1]:
                return

            def receipt(source, changed, error):
                # The binding event is emitted when mutation runs, before an
                # action can navigate or detach its frame. Record on the host;
                # neither the old document nor a later evaluation is needed.
                if type(changed) is not int or changed not in (0, 1):
                    self.state.injection_errors.append("Invalid mutation receipt")
                    return
                self.state.applied += changed
                if error is not None:
                    self.state.injection_errors.append(str(error))

            await context.expose_binding(self._binding_name, receipt)
            registration[1] = True

    def wrap_native(self, original):
        @functools.wraps(original)
        async def native(frame, selector, *args, **kwargs):
            worker = self.state.worker
            if (self.busy or not selector or self.state.current is None
                    or not worker or worker.get("control") or self.state.phase != "call"):
                return await original(frame, selector, *args, **kwargs)
            try:
                selectors = frame._page._browser_context._browser._browser_type._playwright.selectors
                await self.register_engine(selectors)
                await self.register_receipts(frame._page._browser_context)
                replacement = self.retry_selector(selector)
            except Exception as exc:
                self.state.injection_errors.append(str(exc))
                return await original(frame, selector, *args, **kwargs)
            try:
                return await original(frame, replacement, *args, **kwargs)
            finally:
                # Binding callbacks are dispatched as tasks by Playwright.
                # Events from the query precede its operation response; let
                # those already queued callbacks record before classification.
                await asyncio.sleep(0)
        return native

    def wrap(self, original, name, factory=False):
        if inspect.iscoroutinefunction(original):
            @functools.wraps(original)
            async def asynchronous(obj, *args, **kwargs):
                if self.busy or self.state.current is None:
                    return await original(obj, *args, **kwargs)
                selector = self.selector(obj, args, kwargs) if name not in ("goto", "set_content") else None
                if selector:
                    self.record(selector, name, kwargs)
                self.busy = True
                try:
                    mutation = self.mutation(obj, selector)
                    if mutation and name not in ("goto", "set_content"):
                        # Read the counter after awaiting: another task may have
                        # confirmed an injection while this evaluation ran.
                        changed = await mutation[0].evaluate_all(mutation[1])
                        self.state.applied += changed
                except Exception as exc:
                    self.state.injection_errors.append(str(exc))
                finally:
                    self.busy = False
                result = await original(obj, *args, **kwargs)
                if name in ("goto", "set_content"):
                    self.busy = True
                    try:
                        mutation = self.mutation(obj, selector)
                        if mutation:
                            changed = await mutation[0].evaluate_all(mutation[1])
                            self.state.applied += changed
                    except Exception as exc:
                        self.state.injection_errors.append(str(exc))
                    finally:
                        self.busy = False
                return result
            return asynchronous

        @functools.wraps(original)
        def synchronous(obj, *args, **kwargs):
            if self.busy or self.state.current is None:
                return original(obj, *args, **kwargs)
            if factory:
                result = original(obj, *args, **kwargs)
                self.record(self.selector(result, (), {}), name, kwargs)
                return result
            selector = self.selector(obj, args, kwargs) if name not in ("goto", "set_content") else None
            if selector:
                self.record(selector, name, kwargs)
            self.busy = True
            try:
                mutation = self.mutation(obj, selector)
                if mutation and name not in ("goto", "set_content"):
                    self.state.applied += mutation[0].evaluate_all(mutation[1])
            except Exception as exc:
                self.state.injection_errors.append(str(exc))
            finally:
                self.busy = False
            result = original(obj, *args, **kwargs)
            if name in ("goto", "set_content"):
                self.busy = True
                try:
                    mutation = self.mutation(obj, selector)
                    if mutation:
                        self.state.applied += mutation[0].evaluate_all(mutation[1])
                except Exception as exc:
                    self.state.injection_errors.append(str(exc))
                finally:
                    self.busy = False
            return result
        return synchronous

    def wrap_expect(self, original):
        # Both public APIs route Locator assertions through this async method.
        # Wrapping only public Locator methods misses expect(locator), including
        # locators created in fixtures and never otherwise used in the test.
        @functools.wraps(original)
        async def expectation(obj, expression, options, *args, **kwargs):
            if self.busy or self.state.current is None:
                return await original(obj, expression, options, *args, **kwargs)
            self.record(obj._selector, "expect:" + expression, {})
            return await original(obj, expression, options, *args, **kwargs)
        return expectation

    def install(self):
        from playwright import async_api, sync_api
        from playwright._impl._frame import Frame as ImplFrame
        from playwright._impl._locator import Locator as ImplLocator
        from playwright.sync_api._context_manager import PlaywrightContextManager as SyncManager
        from playwright.async_api._context_manager import PlaywrightContextManager as AsyncManager
        for cls, name in ((SyncManager, "__enter__"), (AsyncManager, "__aenter__")):
            original = getattr(cls, name)
            self.originals.append((cls, name, original))
            setattr(cls, name, self.wrap_start(original))
        for api in (sync_api, async_api):
            for cls in (api.Page, api.Frame, api.Locator):
                for name in OPERATIONS + FACTORIES + ("goto", "set_content"):
                    original = getattr(cls, name, None)
                    if original is not None:
                        self.originals.append((cls, name, original))
                        setattr(cls, name, self.wrap(original, name, name in FACTORIES))
        original = ImplLocator._expect
        self.originals.append((ImplLocator, "_expect", original))
        ImplLocator._expect = self.wrap_expect(original)
        for name in set(OPERATIONS) | {"_click", "_expect", "_query_count", "eval_on_selector_all"}:
            original = getattr(ImplFrame, name, None)
            if original is not None:
                self.originals.append((ImplFrame, name, original))
                setattr(ImplFrame, name, self.wrap_native(original))

    def restore(self):
        for cls, name, original in reversed(self.originals):
            setattr(cls, name, original)
        self.originals.clear()
