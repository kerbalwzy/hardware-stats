import os
import shutil

# 运行 Nuitka 编译
shutil.rmtree("./dist")
os.system("nuitka \
          --standalone \
          --onefile \
          --windows-console-mode=disable \
          main.py")
os.makedirs("./dist/external/LibreHardwareMonitor", exist_ok=True)
shutil.move("./main.exe", "./dist/hardware-stats.exe")
shutil.copy("./external/LibreHardwareMonitor/HidSharp.dll", "./dist/external/LibreHardwareMonitor/HidSharp.dll")
shutil.copy("./external/LibreHardwareMonitor/LibreHardwareMonitorLib.dll", "./dist/external/LibreHardwareMonitor/LibreHardwareMonitorLib.dll")
