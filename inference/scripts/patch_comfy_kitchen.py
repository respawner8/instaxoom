"""
Patches comfy_kitchen type annotations for PyTorch 2.5 compatibility
"""
import os
import glob

def patch_file(path):
    if not os.path.exists(path):
        return
    with open(path, "r") as f:
        lines = f.readlines()
    
    new_lines = []
    future_inserted = False
    typing_inserted = False

    for line in lines:
        if line.startswith("from __future__"):
            new_lines.append(line)
            if not typing_inserted:
                new_lines.append("from typing import List, Optional, Sequence, Union\n")
                typing_inserted = True
        else:
            new_lines.append(line)

    if not typing_inserted:
        new_lines.insert(0, "from typing import List, Optional, Sequence, Union\n")

    code = "".join(new_lines)
    code = code.replace("list[int]", "List[int]")
    code = code.replace("list[bool]", "List[bool]")
    code = code.replace("float | None", "Optional[float]")
    code = code.replace("torch.Tensor | None", "Optional[torch.Tensor]")
    
    with open(path, "w") as f:
        f.write(code)
    print(f"Patched: {path}")

site_packages = glob.glob("/usr/local/lib/python*/dist-packages/comfy_kitchen/backends/eager/*.py")
for p in site_packages:
    patch_file(p)

try:
    import comfy_kitchen
    print("SUCCESS: comfy_kitchen imported successfully!")
except Exception as e:
    import traceback
    traceback.print_exc()
