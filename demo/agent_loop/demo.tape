# Run from demo/agent_loop with the project's Python environment activated.
# A 60-second social-video target, not a guarantee on every machine.
Output demo.mp4
Output demo.gif
Set Width 1600
Set Height 1000
Set FontSize 30
Set Padding 24
Set TypingSpeed 35ms
Set Theme "Catppuccin Mocha"
Type "python run_demo.py"
Enter
# Wait for the real final result; never cut off a slower measurement at 60s.
Wait+Screen@180s /Reports and logs:/
Sleep 6s
