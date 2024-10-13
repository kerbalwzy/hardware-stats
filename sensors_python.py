# coding:utf-8
import platform
import sys
from collections import namedtuple
from enum import IntEnum, auto
from typing import Tuple

# Nvidia GPU
import GPUtil

# CPU & disk sensors
import psutil

import sensors as sensors
from log import logger

# AMD GPU on Linux
try:
    import pyamdgpuinfo  # type: ignore
except:
    pyamdgpuinfo = None

# AMD GPU on Windows
try:
    import pyadl # type: ignore
except:
    pyadl = None

PNIC_BEFORE = {}


class GpuType(IntEnum):
    UNSUPPORTED = auto()
    AMD = auto()
    NVIDIA = auto()


DETECTED_GPU = GpuType.UNSUPPORTED


# Function inspired of psutil/psutil/_pslinux.py:sensors_fans()
# Adapted to also get fan speed percentage instead of raw value
def sensors_fans():
    """Return hardware fans info (for CPU and other peripherals) as a
    dict including hardware label and current speed.

    Implementation notes:
    - /sys/class/hwmon looks like the most recent interface to
      retrieve this info, and this implementation relies on it
      only (old distros will probably use something else)
    - lm-sensors on Ubuntu 16.04 relies on /sys/class/hwmon
    """
    from psutil._common import bcat, cat
    import collections, glob, os

    ret = collections.defaultdict(list)
    basenames = glob.glob("/sys/class/hwmon/hwmon*/fan*_*")
    if not basenames:
        # CentOS has an intermediate /device directory:
        # https://github.com/giampaolo/psutil/issues/971
        basenames = glob.glob("/sys/class/hwmon/hwmon*/device/fan*_*")

    basenames = sorted(set([x.split("_")[0] for x in basenames]))
    for base in basenames:
        try:
            current_rpm = int(bcat(base + "_input"))
            try:
                max_rpm = int(bcat(base + "_max"))
            except:
                max_rpm = 1500  # Approximated: max fan speed is 1500 RPM
            try:
                min_rpm = int(bcat(base + "_min"))
            except:
                min_rpm = 0  # Approximated: min fan speed is 0 RPM
            percent = int((current_rpm - min_rpm) / (max_rpm - min_rpm) * 100)
        except (IOError, OSError) as err:
            continue
        unit_name = cat(os.path.join(os.path.dirname(base), "name")).strip()
        label = cat(base + "_label", fallback=os.path.basename(base)).strip()

        custom_sfan = namedtuple("sfan", ["label", "current", "percent"])
        ret[unit_name].append(custom_sfan(label, current_rpm, percent))

    return dict(ret)


def is_cpu_fan(label: str) -> bool:
    return ("cpu" in label.lower()) or ("proc" in label.lower())


class Cpu(sensors.Cpu):
    @staticmethod
    def percentage() -> float:
        try:
            return psutil.cpu_percent()
        except:
            return -1

    @staticmethod
    def frequency() -> float:
        try:
            return psutil.cpu_freq().current / 1000
        except:
            return -1

    @staticmethod
    def load() -> Tuple[float, float, float]:  # 1 / 5 / 15min avg (%):
        try:
            return psutil.getloadavg()
        except:
            return -1, -1, -1

    @staticmethod
    def temperature() -> float:
        cpu_temp = -1
        try:
            sensors_temps = psutil.sensors_temperatures()
            if "coretemp" in sensors_temps:
                # Intel CPU
                cpu_temp = sensors_temps["coretemp"][0].current
            elif "k10temp" in sensors_temps:
                # AMD CPU
                cpu_temp = sensors_temps["k10temp"][0].current
            elif "cpu_thermal" in sensors_temps:
                # ARM CPU
                cpu_temp = sensors_temps["cpu_thermal"][0].current
            elif "zenpower" in sensors_temps:
                # AMD CPU with zenpower (k10temp is in blacklist)
                cpu_temp = sensors_temps["zenpower"][0].current
        except:
            # psutil.sensors_temperatures not available on Windows / MacOS
            pass
        return cpu_temp

    @staticmethod
    def fan_rpm(fan_name: str = None) -> float:
        try:
            fans = sensors_fans()
            if fans:
                for name, entries in fans.items():
                    for entry in entries:
                        if fan_name is not None and fan_name == "%s/%s" % (
                            name,
                            entry.label,
                        ):
                            # Manually selected fan
                            return entry.current
                        elif is_cpu_fan(entry.label) or is_cpu_fan(name):
                            # Auto-detected fan
                            return entry.current
        except:
            pass

        return -1


class Gpu(sensors.Gpu):
    @staticmethod
    def stats() -> (
        Tuple[float, float, float, float, float]
    ):  # load (%) / used mem (%) / used mem (Mb) / total mem (Mb) / temp (°C)
        global DETECTED_GPU
        if DETECTED_GPU == GpuType.AMD:
            return GpuAmd.stats()
        elif DETECTED_GPU == GpuType.NVIDIA:
            return GpuNvidia.stats()
        else:
            return -1, -1, -1, -1, -1

    @staticmethod
    def fps() -> int:
        global DETECTED_GPU
        if DETECTED_GPU == GpuType.AMD:
            return GpuAmd.fps()
        elif DETECTED_GPU == GpuType.NVIDIA:
            return GpuNvidia.fps()
        else:
            return -1

    @staticmethod
    def fan_rpm() -> float:
        global DETECTED_GPU
        if DETECTED_GPU == GpuType.AMD:
            return GpuAmd.fan_rpm()
        elif DETECTED_GPU == GpuType.NVIDIA:
            return GpuNvidia.fan_rpm()
        else:
            return -1

    @staticmethod
    def frequency() -> float:
        global DETECTED_GPU
        if DETECTED_GPU == GpuType.AMD:
            return GpuAmd.frequency()
        elif DETECTED_GPU == GpuType.NVIDIA:
            return GpuNvidia.frequency()
        else:
            return -1

    @staticmethod
    def is_available() -> bool:
        global DETECTED_GPU
        if GpuAmd.is_available():
            # logger.info("Detected AMD GPU(s)")
            DETECTED_GPU = GpuType.AMD
        elif GpuNvidia.is_available():
            # logger.info("Detected Nvidia GPU(s)")
            DETECTED_GPU = GpuType.NVIDIA
        else:
            # logger.warning("No supported GPU found")
            DETECTED_GPU = GpuType.UNSUPPORTED
            
        return DETECTED_GPU != GpuType.UNSUPPORTED


class GpuNvidia(sensors.Gpu):
    @staticmethod
    def stats() -> (
        Tuple[float, float, float, float, float]
    ):  # load (%) / used mem (%) / used mem (Mb) / total mem (Mb) / temp (°C)
        # Unlike other sensors, Nvidia GPU with GPUtil pulls in all the stats at once
        nvidia_gpus = GPUtil.getGPUs()

        try:
            memory_used_all = [item.memoryUsed for item in nvidia_gpus]
            memory_used_mb = sum(memory_used_all) / len(memory_used_all)
        except:
            memory_used_mb = -1

        try:
            memory_total_all = [item.memoryTotal for item in nvidia_gpus]
            memory_total_mb = sum(memory_total_all) / len(memory_total_all)
        except:
            memory_total_mb = -1

        try:
            memory_percentage = (memory_used_mb / memory_total_mb) * 100
        except:
            memory_percentage = -1

        try:
            load_all = [item.load for item in nvidia_gpus]
            load = (sum(load_all) / len(load_all)) * 100
        except:
            load = -1

        try:
            temperature_all = [item.temperature for item in nvidia_gpus]
            temperature = sum(temperature_all) / len(temperature_all)
        except:
            temperature = -1

        return load, memory_percentage, memory_used_mb, memory_total_mb, temperature

    @staticmethod
    def fps() -> int:
        # Not supported by Python libraries
        return -1

    @staticmethod
    def fan_rpm() -> float:
        try:
            fans = sensors_fans()
            if fans:
                for name, entries in fans.items():
                    for entry in entries:
                        if "gpu" in (entry.label.lower() or name.lower()):
                            return entry.current
        except:
            pass

        return -1

    @staticmethod
    def frequency() -> float:
        # Not supported by Python libraries
        return -1

    @staticmethod
    def is_available() -> bool:
        try:
            return len(GPUtil.getGPUs()) > 0
        except:
            return False


class GpuAmd(sensors.Gpu):
    @staticmethod
    def stats() -> (
        Tuple[float, float, float, float, float]
    ):  # load (%) / used mem (%) / used mem (Mb) / total mem (Mb) / temp (°C)
        if pyamdgpuinfo:
            # Unlike other sensors, AMD GPU with pyamdgpuinfo pulls in all the stats at once
            pyamdgpuinfo.detect_gpus()
            amd_gpu = pyamdgpuinfo.get_gpu(0)

            try:
                memory_used_bytes = amd_gpu.query_vram_usage()
                memory_used = memory_used_bytes / 1024 / 1024
            except:
                memory_used_bytes = -1
                memory_used = -1

            try:
                memory_total_bytes = amd_gpu.memory_info["vram_size"]
                memory_total = memory_total_bytes / 1024 / 1024
            except:
                memory_total_bytes = -1
                memory_total = -1

            try:
                memory_percentage = (memory_used_bytes / memory_total_bytes) * 100
            except:
                memory_percentage = -1

            try:
                load = amd_gpu.query_load() * 100
            except:
                load = -1

            try:
                temperature = amd_gpu.query_temperature()
            except:
                temperature = -1

            return load, memory_percentage, memory_used, memory_total, temperature
        elif pyadl:
            amd_gpu = pyadl.ADLManager.getInstance().getDevices()[0]

            try:
                load = amd_gpu.getCurrentUsage()
            except:
                load = -1

            try:
                temperature = amd_gpu.getCurrentTemperature()
            except:
                temperature = -1

            # GPU memory data not supported by pyadl
            return load, -1, -1, -1, temperature

    @staticmethod
    def fps() -> int:
        # Not supported by Python libraries
        return -1

    @staticmethod
    def fan_rpm() -> float:
        try:
            # Try with psutil fans
            fans = sensors_fans()
            if fans:
                for name, entries in fans.items():
                    for entry in entries:
                        if "gpu" in (entry.label.lower() or name.lower()):
                            return entry.current

            # Try with pyadl if psutil did not find GPU fan
            if pyadl:
                return (
                    pyadl.ADLManager.getInstance()
                    .getDevices()[0]
                    .getCurrentFanSpeed(pyadl.ADL_DEVICE_FAN_SPEED_TYPE_RPM)
                )
        except:
            pass

        return -1

    @staticmethod
    def frequency() -> float:
        if pyamdgpuinfo:
            pyamdgpuinfo.detect_gpus()
            return pyamdgpuinfo.get_gpu(0).query_sclk() / 1000000
        elif pyadl:
            return (
                pyadl.ADLManager.getInstance().getDevices()[0].getCurrentEngineClock()
            )
        else:
            return -1

    @staticmethod
    def is_available() -> bool:
        try:
            if pyamdgpuinfo and pyamdgpuinfo.detect_gpus() > 0:
                return True
            elif pyadl and len(pyadl.ADLManager.getInstance().getDevices()) > 0:
                return True
            else:
                return False
        except:
            return False


class Memory(sensors.Memory):

    @staticmethod
    def percentage() -> float:
        try:
            return psutil.virtual_memory().percent
        except:
            return -1

    @staticmethod
    def used() -> int:  # In bytes
        try:
            # Do not use psutil.virtual_memory().used: from https://psutil.readthedocs.io/en/latest/#memory
            # "It is calculated differently depending on the platform and designed for informational purposes only"
            return psutil.virtual_memory().total - psutil.virtual_memory().available
        except:
            return -1

    @staticmethod
    def free() -> int:  # In bytes
        try:
            # Do not use psutil.virtual_memory().free: from https://psutil.readthedocs.io/en/latest/#memory
            # "note that this doesn’t reflect the actual memory available (use available instead)."
            return psutil.virtual_memory().available
        except:
            return -1


class Disk(sensors.Disk):
    @staticmethod
    def percentage() -> float:
        try:
            return psutil.disk_usage("/").percent
        except:
            return -1

    @staticmethod
    def used() -> int:  # In bytes
        try:
            return psutil.disk_usage("/").used
        except:
            return -1

    @staticmethod
    def free() -> int:  # In bytes
        try:
            return psutil.disk_usage("/").free
        except:
            return -1


class Net(sensors.Net):
    @staticmethod
    def stats(
        if_name="", interval=1
    ) -> Tuple[
        int, int, int, int
    ]:  # up rate (B/s), uploaded (B), dl rate (B/s), downloaded (B)
        global PNIC_BEFORE
        # Get current counters
        pnic_after = psutil.net_io_counters(pernic=True)

        upload_rate = 0
        uploaded = 0
        download_rate = 0
        downloaded = 0
        if not if_name and len(pnic_after) > 0:
            if_name = list(pnic_after.keys())[0]
        if if_name in pnic_after:
            try:
                upload_rate = (
                    pnic_after[if_name].bytes_sent
                    - PNIC_BEFORE[if_name].bytes_sent
                ) / interval
                uploaded = pnic_after[if_name].bytes_sent
                download_rate = (
                    pnic_after[if_name].bytes_recv
                    - PNIC_BEFORE[if_name].bytes_recv
                ) / interval
                downloaded = pnic_after[if_name].bytes_recv
            except:
                # Interface might not be in PNIC_BEFORE for now
                pass
            PNIC_BEFORE.update({if_name: pnic_after[if_name]})
            return upload_rate, uploaded, download_rate, downloaded
        # 
        logger.warning(
            "Network interface '%s' not found. Check names in config.yaml."
            % if_name
        )
        return -1, -1, -1, -1
            
