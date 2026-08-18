# Drei-Layer-Prozesskette

`layer1_entry.py` startet `layer2_process.py` als Subprozess, der wiederum
`layer3_finalize.py` startet. Jeder Layer ist ein eigener Prozess.
