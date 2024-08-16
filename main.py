# coding:utf-8
# hareware-stats.py: Write hardware status data in a loop to a local YAML format file for other programs to read and use
import argparse
import os
import shutil
import sys
import time
import tempfile
import platform
import ruamel.yaml
import atexit
import signal
from runtime_util import require_run_as_admin, get_socket_lock
from log import logger

# Get socket
socket = get_socket_lock()


def safe_exit():
    """在进程退出时执行的清理函数"""
    socket.close()
    try:
        sys.exit(0)
    except:
        os._exit(0)


def handle_signal(signum, frame):
    """信号处理函数"""
    print(f"Received signal {signum}, cleaning up...")
    safe_exit()


# 注册退出时要执行的清理函数
atexit.register(safe_exit)
# 捕获终止信号
signal.signal(signal.SIGTERM, handle_signal)
signal.signal(signal.SIGINT, handle_signal)  # Ctrl+C

if platform.system() == "Windows":  # Windows-specific
    require_run_as_admin()
    from sensors_librehardwaremonitor import Cpu, Gpu, Memory, Disk, Net
else:
    from sensors_python import Cpu, Gpu, Memory, Disk, Net

import atexit
import signal


def run():
    parser = argparse.ArgumentParser(
        description="Write hardware status data in a loop to a local YAML format file for other programs to read and use"
    )
    parser.add_argument(
        "--interval", type=float, default=0.5, help="Write interval, unit second"
    )
    parser.add_argument(
        "--network", type=str, default="", help="The netword interface want to watch"
    )
    args = parser.parse_args()
    #
    logger.info("start get stats")
    temp_path = os.path.join(tempfile.gettempdir(), "temp-hardware-stats")
    while True:
        with open(temp_path, "w", encoding="utf-8") as tmp_file:
            # CPU
            cpuStats = {
                name: getattr(Cpu, name)()
                for name in [
                    "percentage",
                    "frequency",
                    "temperature",
                    "fan_rpm",
                ]
            }
            # GPU
            gpuStats = {
                name: getattr(Gpu, name)()
                for name in [
                    "stats",
                    "is_available",
                    "fan_rpm",
                ]
            }
            gpuStats["load"] = gpuStats["stats"][0]
            gpuStats["percentage"] = gpuStats["stats"][1]
            gpuStats["total"] = gpuStats["stats"][3]
            gpuStats["used"] = gpuStats["stats"][2]
            gpuStats["free"] = gpuStats["total"] - gpuStats["used"]
            gpuStats["temperature"] = gpuStats["stats"][4]
            del gpuStats["stats"]
            # Memory
            memStats = {
                name: getattr(Memory, name)()
                for name in [
                    "percentage",
                    "used",
                    "free",
                ]
            }
            memStats["total"] = memStats["used"] + memStats["free"]
            # Disk
            diskStats = {
                name: getattr(Disk, name)()
                for name in [
                    "percentage",
                    "used",
                    "free",
                ]
            }
            diskStats["total"] = diskStats["used"] + diskStats["free"]
            # Net
            _netStats = Net.stats(args.network, args.interval)
            netStats = {
                "upload_rate": _netStats[0],
                "uploaded": _netStats[1],
                "download_rate": _netStats[2],
                "downloaded": _netStats[3],
            }
            data = {
                "Cpu": cpuStats,
                "Gpu": gpuStats,
                "Memory": memStats,
                "Disk": diskStats,
                "Net": netStats,
            }
            # logger.info(data)
            ruamel.yaml.YAML().dump(data, tmp_file)
        shutil.move(temp_path, "./hardware-stats.yaml")
        # sleep interval
        time.sleep(args.interval)
        # break


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        logger.error(e)
