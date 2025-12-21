from dataclasses import dataclass
from typing import Dict, Any, List
import json

@dataclass
class MutationResult:
    id: str
    type: str
    selector: str
    killed: bool = False
    details: str = ""

class VandalEngine:
    """Core logic for UI mutations injected via JavaScript."""
    
    # Helper for deep selection (Shadow DOM)
    DEEP_SELECT = """
        (root) => {
            const findElements = (currentRoot) => {
                let found = Array.from(currentRoot.querySelectorAll(selector));
                const shadowRoots = Array.from(currentRoot.querySelectorAll('*')).filter(el => el.shadowRoot);
                shadowRoots.forEach(el => {
                    found = found.concat(findElements(el.shadowRoot));
                });
                return found;
            };
            return findElements(root);
        }
    """

    MUTATIONS = {
        "stealth_disable": """
            (selector) => {
                const findElements = %DEEP_SELECT%;
                const elements = findElements(document);
                elements.forEach(el => {
                    if (el.getAttribute('data-vandalized')) return;
                    const originalPointerEvents = el.style.pointerEvents;
                    el.style.pointerEvents = 'none';
                    el.setAttribute('data-vandal-original-pointer', originalPointerEvents);
                    el.setAttribute('data-vandalized', 'stealth_disable');
                });
                return elements.length;
            }
        """,
        "ghost_element": """
            (selector) => {
                const findElements = %DEEP_SELECT%;
                const elements = findElements(document);
                elements.forEach(el => {
                    if (el.getAttribute('data-vandalized')) return;
                    const originalOpacity = el.style.opacity;
                    const originalPointerEvents = el.style.pointerEvents;
                    el.style.opacity = '0';
                    el.style.pointerEvents = 'none';
                    el.setAttribute('data-vandal-original-opacity', originalOpacity);
                    el.setAttribute('data-vandal-original-pointer', originalPointerEvents);
                    el.setAttribute('data-vandalized', 'ghost_element');
                });
                return elements.length;
            }
        """,
        "data_sabotage": """
            (selector) => {
                const findElements = %DEEP_SELECT%;
                const elements = findElements(document);
                elements.forEach(el => {
                    if (el.getAttribute('data-vandalized')) return;
                    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                        el.setAttribute('data-vandal-original-val', el.value);
                        el.value = 'VANDALIZED_DATA';
                    } else {
                        el.setAttribute('data-vandal-original-text', el.innerText);
                        el.innerText = 'VANDALIZED_TEXT';
                    }
                    el.setAttribute('data-vandalized', 'data_sabotage');
                });
                return elements.length;
            }
        """,
        "logic_sabotage": """
            (selector) => {
                const findElements = %DEEP_SELECT%;
                const elements = findElements(document);
                const blockHandler = (e) => {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    console.log('Vandal Blocked Click propagation');
                };
                elements.forEach(el => {
                    if (el.getAttribute('data-vandalized')) return;
                    el.addEventListener('click', blockHandler, true);
                    el.setAttribute('data-vandalized', 'logic_sabotage');
                    // We store a reference to the handler if possible, or just mark it
                });
                return elements.length;
            }
        """,
        "ui_shift": """
            (selector) => {
                const findElements = %DEEP_SELECT%;
                const elements = findElements(document);
                elements.forEach(el => {
                    if (el.getAttribute('data-vandalized')) return;
                    const originalTransform = el.style.transform;
                    el.style.transform = 'translate(100px, 100px)';
                    el.setAttribute('data-vandalized', 'ui_shift');
                });
                return elements.length;
            }
        """,
        "slow_load": """
            (selector) => {
                const findElements = %DEEP_SELECT%;
                const elements = findElements(document);
                elements.forEach(el => {
                    if (el.getAttribute('data-vandalized')) return;
                    const originalVisibility = el.style.visibility;
                    el.style.visibility = 'hidden';
                    setTimeout(() => {
                        el.style.visibility = originalVisibility;
                        el.removeAttribute('data-vandalized');
                    }, 5000);
                    el.setAttribute('data-vandalized', 'slow_load');
                });
                return elements.length;
            }
        """
    }

    REVERTS = {
        "stealth_disable": """
            (selector) => {
                const findElements = %DEEP_SELECT%;
                const elements = findElements(document);
                elements.forEach(el => {
                    if (el.getAttribute('data-vandalized') !== 'stealth_disable') return;
                    el.style.pointerEvents = el.getAttribute('data-vandal-original-pointer') || '';
                    el.removeAttribute('data-vandal-original-pointer');
                    el.removeAttribute('data-vandalized');
                });
            }
        """,
        "ghost_element": """
            (selector) => {
                const findElements = %DEEP_SELECT%;
                const elements = findElements(document);
                elements.forEach(el => {
                    if (el.getAttribute('data-vandalized') !== 'ghost_element') return;
                    el.style.opacity = el.getAttribute('data-vandal-original-opacity') || '';
                    el.style.pointerEvents = el.getAttribute('data-vandal-original-pointer') || '';
                    el.removeAttribute('data-vandal-original-opacity');
                    el.removeAttribute('data-vandal-original-pointer');
                    el.removeAttribute('data-vandalized');
                });
            }
        """,
        "data_sabotage": """
            (selector) => {
                const findElements = %DEEP_SELECT%;
                const elements = findElements(document);
                elements.forEach(el => {
                    if (el.getAttribute('data-vandalized') !== 'data_sabotage') return;
                    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                        el.value = el.getAttribute('data-vandal-original-val') || '';
                        el.removeAttribute('data-vandal-original-val');
                    } else {
                        el.innerText = el.getAttribute('data-vandal-original-text') || '';
                        el.removeAttribute('data-vandal-original-text');
                    }
                    el.removeAttribute('data-vandalized');
                });
            }
        """,
        "ui_shift": """
            (selector) => {
                const findElements = %DEEP_SELECT%;
                const elements = findElements(document);
                elements.forEach(el => {
                    if (el.getAttribute('data-vandalized') !== 'ui_shift') return;
                    el.style.transform = el.getAttribute('data-vandal-original-transform') || '';
                    el.removeAttribute('data-vandal-original-transform');
                    el.removeAttribute('data-vandalized');
                });
            }
        """
    }

    @staticmethod
    def get_script(mutation_type: str) -> str:
        script = VandalEngine.MUTATIONS.get(mutation_type, "")
        if script:
            return script.replace("%DEEP_SELECT%", VandalEngine.DEEP_SELECT)
        return ""

    @staticmethod
    def get_revert_script(mutation_type: str) -> str:
        script = VandalEngine.REVERTS.get(mutation_type, "")
        if script:
            return script.replace("%DEEP_SELECT%", VandalEngine.DEEP_SELECT)
        return ""

