# coding:utf-8
# hareware-stats.py: Write hardware status data in a loop to a local YAML format file for other programs to read and use
import argparse
import atexit
import os
import gc
import shutil
import signal
import sys
import time
import tempfile
import platform
import ruamel.yaml

from runtime_util import require_runas_admin, require_runas_unique
from log import logger

TEMP_DIR = tempfile.TemporaryDirectory()


def safe_exit(signum=None, frame=None):
    logger.info(f"Received signal {signum}, cleaning up...")
    TEMP_DIR.cleanup()
    try:
        sys.exit(0)
    except:
        os._exit(0)


# 注册退出时要执行的清理函数
atexit.register(safe_exit)
# 捕获终止信号
signal.signal(signal.SIGTERM, safe_exit)
signal.signal(signal.SIGINT, safe_exit)  # Ctrl+C

require_runas_unique()

if platform.system() == "Windows":  # Windows-specific
    require_runas_admin()
    from sensors_librehardwaremonitor import Cpu, Gpu, Memory, Disk, Net
else:
    from sensors_python import Cpu, Gpu, Memory, Disk, Net


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
    logger.info("start get stats...")
    temp_path = os.path.join(TEMP_DIR.name, "temp-hardware-stats")
    loop_count = 0
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
        loop_count += 1
        # 每万次手动进行一次垃圾回收
        if loop_count % 10000 == 0:
            gc.collect()
        else:
            time.sleep(args.interval)

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        logger.error(e)
