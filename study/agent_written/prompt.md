Write a Python pytest suite using the synchronous Playwright API for this web application.

Application: $app_name
Local base URL: $app_url
Reviewed application facts and user workflows:
$task_facts

Exercise the listed workflows through the browser and assert their user-visible outcomes, including relevant validation and state changes. Use the supplied pytest-playwright page fixture, accessible locators where practical, and deterministic waits. Keep tests independent and reset application state using only the supplied local reset procedure. Do not replace application behavior with mocks or change application code.

Write all suite files beneath suite/. You may read the supplied application source and local documentation and use the approved local shell and browser tools. Do not access external hosts, install dependencies, read credentials, or change the environment. Use only the supplied Python dependencies and Chromium. Do not use skips, xfails, test-order dependencies, arbitrary sleeps, or retries to conceal failures. Report incomplete workflows and any inability to produce a passing suite.

You have at most 30 assistant turns and 1800 seconds from the first request, including tool time. Stop at the first limit. Return the suite and a concise account of covered workflows and known limitations.
