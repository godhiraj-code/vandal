# Run from demo/agent_loop with the project's Python environment activated.
# Rendering takes about 45 to 60 seconds of video, depending on machine speed.
Output demo.mp4
Output demo.gif
Set Width 1600
Set Height 900
Set FontSize 38
Set TypingSpeed 25ms
Set Padding 40
Set Theme "Catppuccin Mocha"
Env PS1 "$ "
Hide
Type "clear"
Enter
Show
Type "# Does this checkout test catch broken UI?"
Enter
Sleep 2s
Type "python run_demo.py"
Enter
Wait+Screen@180s /Reports and logs:/
Sleep 3s
Hide
Type "clear"
Enter
Show
Type "diff -u test_weak.py test_fixed.py"
Enter
Sleep 8s
