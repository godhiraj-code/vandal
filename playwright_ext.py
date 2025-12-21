from .core import VandalEngine, MutationResult
import uuid
import json
import os
from typing import List, Optional

class Vandal:
    """Playwright Wrapper for Vandal UI Mutation Testing."""
    
    def __init__(self, page):
        self.page = page
        self.mutants: List[MutationResult] = []
        self._active_mutant: Optional[MutationResult] = None
        self._init_scripts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._active_mutant:
            if exc_type is not None:
                self._active_mutant.killed = True
                self._active_mutant.details = f"Test failed with: {exc_val}"
            else:
                self._active_mutant.killed = False
                self._active_mutant.details = "Test passed despite mutation (Mutant Survived!)"
            
            self.mutants.append(self._active_mutant)
            self._active_mutant = None

    async def apply_mutation(self, mutation_type: str, selector: str, persistent: bool = True):
        """Applies a mutation. If persistent=True, it survives navigation."""
        script_template = VandalEngine.get_script(mutation_type)
        if not script_template:
            raise ValueError(f"Unknown mutation type: {mutation_type}")
        
        # Persistence logic: Deep Mutation Monitoring
        observer_script = f"""
            (() => {{
                const mutationType = '{mutation_type}';
                const selector = '{selector}';
                const mutationScript = {script_template};
                
                const apply = () => {{
                    try {{
                        mutationScript(selector);
                    }} catch (e) {{}}
                }};

                const startObserver = () => {{
                    const target = document.documentElement || document;
                    if (!target) {{
                        setTimeout(startObserver, 10);
                        return;
                    }}
                    const mainObserver = new MutationObserver(apply);
                    mainObserver.observe(target, {{ childList: true, subtree: true }});
                    apply();
                }};

                startObserver();
                const originalAttachShadow = Element.prototype.attachShadow;
                Element.prototype.attachShadow = function() {{
                    const shadowRoot = originalAttachShadow.apply(this, arguments);
                    const shadowObserver = new MutationObserver(apply);
                    shadowObserver.observe(shadowRoot, {{ childList: true, subtree: true }});
                    setTimeout(apply, 0); 
                    return shadowRoot;
                }};
            }})();
        """
        
        if persistent:
            await self.page.add_init_script(observer_script)
            self._init_scripts.append(observer_script)
        
        # Apply immediately to current page
        count = await self.page.evaluate(script_template, selector)
        
        self._active_mutant = MutationResult(
            id=str(uuid.uuid4())[:8],
            type=mutation_type,
            selector=selector
        )
        
        if count == 0:
            print(f"Warning: No elements found for selector '{selector}' on current page.")
        else:
            print(f"Applied '{mutation_type}' to {count} element(s).")

    async def revert_mutation(self, mutation_type: str, selector: str):
        """Reverts a specific mutation."""
        script = VandalEngine.get_revert_script(mutation_type)
        if not script:
            print(f"No revert script for {mutation_type}")
            return
        
        await self.page.evaluate(script, selector)
        print(f"Reverted '{mutation_type}' on '{selector}'.")

    async def revert_all(self):
        """Reverts all mutations applied in this session (experimental)."""
        # Note: This only works if elements are still on page. 
        # For init scripts, we can't easily 'remove' them from the page object once added,
        # but we can reload the page without them if we had a way to clear them.
        # Playwright doesn't have a 'remove_init_script' yet.
        for m in self.mutants:
            await self.revert_mutation(m.type, m.selector)

    def save_report(self, file_path: str = "vandal_report.json"):
        """Saves results to JSON and HTML."""
        data = [
            {
                "id": m.id, "type": m.type, "selector": m.selector,
                "killed": m.killed, "details": m.details
            }
            for m in self.mutants
        ]
        # Save JSON
        json_path = file_path if file_path.endswith(".json") else file_path + ".json"
        with open(json_path, "w") as f:
            json.dump(data, f, indent=4)
        
        # Save HTML
        html_path = json_path.replace(".json", ".html")
        html_content = self._generate_html_report(data)
        with open(html_path, "w") as f:
            f.write(html_content)
            
        print(f"Reports saved to {json_path} and {html_path}")

    def _generate_html_report(self, data):
        rows = "".join([
            f"""<tr class="{'killed' if m['killed'] else 'survived'}">
                <td>{m['id']}</td><td>{m['type']}</td><td><code>{m['selector']}</code></td>
                <td>{'💀 KILLED' if m['killed'] else '🧟 SURVIVED'}</td><td>{m['details']}</td>
            </tr>""" for m in data
        ])
        return f"""
        <html>
        <head>
            <title>Vandal Mutation Report</title>
            <style>
                body {{ font-family: sans-serif; margin: 40px; background: #f4f4f9; }}
                table {{ width: 100%; border-collapse: collapse; background: white; }}
                th, td {{ padding: 12px; border: 1px solid #ddd; text-align: left; }}
                th {{ background: #007bff; color: white; }}
                .killed {{ background: #d4edda; }}
                .survived {{ background: #f8d7da; }}
                code {{ background: #eee; padding: 2px 4px; }}
            </style>
        </head>
        <body>
            <h1>Vandal Mutation Report</h1>
            <table>
                <tr><th>ID</th><th>Type</th><th>Selector</th><th>Status</th><th>Details</th></tr>
                {rows}
            </table>
        </body>
        </html>
        """

    def report(self):
        """Prints a summary of the mutation test results."""
        print("\n--- Vandal Mutation Report ---")
        for m in self.mutants:
            status = "💀 KILLED" if m.killed else "🧟 SURVIVED"
            print(f"[{status}] {m.type} on '{m.selector}'")
            if not m.killed:
                print(f"   Potential Gap: {m.details}")
        print("------------------------------\n")
