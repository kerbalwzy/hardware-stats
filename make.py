import os
import shutil
import PyInstaller.__main__
import psutil
import platform

onWindows: bool = platform.system() == "Windows"

if onWindows:
    AppName = "hardware-stats.exe"
else:
    AppName = "hardware-stats"

# 清理正在运行的进程，避免程序占用文件
for proc in psutil.process_iter(["pid", "name"]):
    if proc.info["name"] == AppName:
        try:
            pid = proc.info["pid"]
            process = psutil.Process(pid)
            process.terminate()
            process.wait()  # 等待进程终止
            print(f"Killed process with PID: {pid}")
        except psutil.NoSuchProcess:
            print(f"Process with PID {pid} does not exist.")
        except psutil.AccessDenied:
            print(f"Access denied to terminate process with PID {pid}.")

# 运行 PyInstaller 编译
if os.path.exists("./dist"):
    shutil.rmtree("./dist")

PyInstaller.__main__.run(
    [
        "main.py",
        "--onefile",
        "--noconsole" if onWindows else "--nowindowed",
    ]
)

os.makedirs("./dist/external/LibreHardwareMonitor", exist_ok=True)

if onWindows:
    shutil.move("./dist/main.exe", f"./dist/{AppName}")
else:
    shutil.move("./dist/main", f"./dist/{AppName}")

shutil.copy(
    "./external/LibreHardwareMonitor/HidSharp.dll",
    "./dist/external/LibreHardwareMonitor/HidSharp.dll",
)
shutil.copy(
    "./external/LibreHardwareMonitor/LibreHardwareMonitorLib.dll",
    "./dist/external/LibreHardwareMonitor/LibreHardwareMonitorLib.dll",
)
