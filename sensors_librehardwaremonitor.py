# coding:utf-8
import ctypes
import os
import sys
from statistics import mean
from typing import Tuple

import clr  # type: ignore # Clr is from pythonnet package. Do not install clr package
import psutil
from win32api import * # type: ignore

import sensors as sensors
from log import logger
from consts import EXEC_PATH
# Import LibreHardwareMonitor dll to Python
lhm_dll = EXEC_PATH + "\\external\\LibreHardwareMonitor\\LibreHardwareMonitorLib.dll"
# noinspection PyUnresolvedReferences
clr.AddReference(lhm_dll)
# noinspection PyUnresolvedReferences
clr.AddReference(EXEC_PATH + "\\external\\LibreHardwareMonitor\\HidSharp.dll")
# noinspection PyUnresolvedReferences
from LibreHardwareMonitor import Hardware  # type: ignore

File_information = GetFileVersionInfo(lhm_dll, "\\")

ms_file_version = File_information["FileVersionMS"]
ls_file_version = File_information["FileVersionLS"]

logger.debug(
    "Found LibreHardwareMonitorLib %s"
    % ".".join(
        [
            str(HIWORD(ms_file_version)),
            str(LOWORD(ms_file_version)),
            str(HIWORD(ls_file_version)),
            str(LOWORD(ls_file_version)),
        ]
    )
)

if ctypes.windll.shell32.IsUserAnAdmin() == 0:
    logger.error("Program is not running as administrator.")
    try:
        sys.exit(0)
    except:
        os._exit(0)

handle = Hardware.Computer()
handle.IsCpuEnabled = True
handle.IsGpuEnabled = True
handle.IsMemoryEnabled = True
handle.IsMotherboardEnabled = True  # For CPU Fan Speed
handle.IsControllerEnabled = True  # For CPU Fan Speed
handle.IsNetworkEnabled = True
handle.IsStorageEnabled = True
handle.IsPsuEnabled = False
handle.Open()
for hardware in handle.Hardware:
    if hardware.HardwareType == Hardware.HardwareType.Cpu:
        logger.info("Found CPU: %s" % hardware.Name)
    elif hardware.HardwareType == Hardware.HardwareType.Memory:
        logger.info("Found Memory: %s" % hardware.Name)
    elif hardware.HardwareType == Hardware.HardwareType.GpuNvidia:
        logger.info("Found Nvidia GPU: %s" % hardware.Name)
    elif hardware.HardwareType == Hardware.HardwareType.GpuAmd:
        logger.info("Found AMD GPU: %s" % hardware.Name)
    elif hardware.HardwareType == Hardware.HardwareType.GpuIntel:
        logger.info("Found Intel GPU: %s" % hardware.Name)
    elif hardware.HardwareType == Hardware.HardwareType.Storage:
        logger.info("Found Storage: %s" % hardware.Name)
    elif hardware.HardwareType == Hardware.HardwareType.Network:
        logger.info("Found Network interface: %s" % hardware.Name)


def get_hw_and_update(
    hwtype: Hardware.HardwareType, name: str = None
) -> Hardware.Hardware:
    for hardware in handle.Hardware:
        if hardware.HardwareType == hwtype:
            if (name and hardware.Name == name) or name is None:
                hardware.Update()
                return hardware
    return None


def get_gpu_name() -> str:
    # Determine which GPU to use, in case there are multiple : try to avoid using discrete GPU for stats
    hw_gpus = []
    for hardware in handle.Hardware:
        if (
            hardware.HardwareType == Hardware.HardwareType.GpuNvidia
            or hardware.HardwareType == Hardware.HardwareType.GpuAmd
            or hardware.HardwareType == Hardware.HardwareType.GpuIntel
        ):
            hw_gpus.append(hardware)

    if len(hw_gpus) == 0:
        # No supported GPU found on the system
        logger.warning("No supported GPU found")
        return ""
    elif len(hw_gpus) == 1:
        # Found one supported GPU
        logger.debug("Found one supported GPU: %s" % hw_gpus[0].Name)
        return str(hw_gpus[0].Name)
    else:
        # Found multiple GPUs, try to determine which one to use
        amd_gpus = 0
        intel_gpus = 0
        nvidia_gpus = 0

        gpu_to_use = ""

        # Count GPUs by manufacturer
        for gpu in hw_gpus:
            if gpu.HardwareType == Hardware.HardwareType.GpuAmd:
                amd_gpus += 1
            elif gpu.HardwareType == Hardware.HardwareType.GpuIntel:
                intel_gpus += 1
            elif gpu.HardwareType == Hardware.HardwareType.GpuNvidia:
                nvidia_gpus += 1

        logger.warning(
            "Found %d GPUs on your system (%d AMD / %d Nvidia / %d Intel). Auto identify which GPU to use."
            % (len(hw_gpus), amd_gpus, nvidia_gpus, intel_gpus)
        )

        if nvidia_gpus >= 1:
            # One (or more) Nvidia GPU: use first available for stats
            gpu_to_use = get_hw_and_update(Hardware.HardwareType.GpuNvidia).Name
        elif amd_gpus == 1:
            # No Nvidia GPU, only one AMD GPU: use it
            gpu_to_use = get_hw_and_update(Hardware.HardwareType.GpuAmd).Name
        elif amd_gpus > 1:
            # No Nvidia GPU, several AMD GPUs found: try to use the real GPU but not the APU integrated in CPU
            for gpu in hw_gpus:
                if gpu.HardwareType == Hardware.HardwareType.GpuAmd:
                    for sensor in gpu.Sensors:
                        if sensor.SensorType == Hardware.SensorType.Load and str(
                            sensor.Name
                        ).startswith("GPU Core"):
                            # Found load sensor for this GPU: assume it is main GPU and use it for stats
                            gpu_to_use = gpu.Name
        else:
            # No AMD or Nvidia GPU: there are several Intel GPUs, use first available for stats
            gpu_to_use = get_hw_and_update(Hardware.HardwareType.GpuIntel).Name

        if gpu_to_use:
            logger.debug("This GPU will be used for stats: %s" % gpu_to_use)
        else:
            logger.warning("No supported GPU found (no GPU with load sensor)")

        return gpu_to_use


def get_net_interface_and_update(if_name: str = "") -> Hardware.Hardware:
    for hardware in handle.Hardware:
        if hardware.HardwareType == Hardware.HardwareType.Network:
            if not if_name:  # 默认返回第一个网卡
                hardware.Update()
                return hardware
            else:  # 返回指定名称的网卡
                if hardware.Name == if_name:
                    hardware.Update()
                    return hardware
    #
    logger.warning(
        "Network interface '%s' not found. Check names in config.yaml." % if_name
    )
    return None


class Cpu(sensors.Cpu):
    @staticmethod
    def percentage() -> float:
        cpu = get_hw_and_update(Hardware.HardwareType.Cpu)
        for sensor in cpu.Sensors:
            if (
                sensor.SensorType == Hardware.SensorType.Load
                and str(sensor.Name).startswith("CPU Total")
                and sensor.Value is not None
            ):
                return float(sensor.Value)

        logger.error("CPU load cannot be read")
        return -1

    @staticmethod
    def frequency() -> float:
        frequencies = []
        cpu = get_hw_and_update(Hardware.HardwareType.Cpu)
        try:
            for sensor in cpu.Sensors:
                if sensor.SensorType == Hardware.SensorType.Clock:
                    # Keep only real core clocks, ignore effective core clocks
                    if (
                        "Core #" in str(sensor.Name)
                        and "Effective" not in str(sensor.Name)
                        and sensor.Value is not None
                    ):
                        frequencies.append(float(sensor.Value))
            if frequencies:
                # Take mean of all core clock as "CPU clock" (as it is done in Windows Task Manager Performance tab)
                return mean(frequencies) / 1000
        except:
            pass

        # Frequencies reading is not supported on this CPU
        return -1

    @staticmethod
    def temperature() -> float:
        cpu = get_hw_and_update(Hardware.HardwareType.Cpu)
        try:
            # By default, the average temperature of all CPU cores will be used
            for sensor in cpu.Sensors:
                if (
                    sensor.SensorType == Hardware.SensorType.Temperature
                    and str(sensor.Name).startswith("Core Average")
                    and sensor.Value is not None
                ):
                    return float(sensor.Value)
            # If not available, the max core temperature will be used
            for sensor in cpu.Sensors:
                if (
                    sensor.SensorType == Hardware.SensorType.Temperature
                    and str(sensor.Name).startswith("Core Max")
                    and sensor.Value is not None
                ):
                    return float(sensor.Value)
            # If not available, the CPU Package temperature (usually same as max core temperature) will be used
            for sensor in cpu.Sensors:
                if (
                    sensor.SensorType == Hardware.SensorType.Temperature
                    and str(sensor.Name).startswith("CPU Package")
                    and sensor.Value is not None
                ):
                    return float(sensor.Value)
            # Otherwise any sensor named "Core..." will be used
            for sensor in cpu.Sensors:
                if (
                    sensor.SensorType == Hardware.SensorType.Temperature
                    and str(sensor.Name).startswith("Core")
                    and sensor.Value is not None
                ):
                    return float(sensor.Value)
        except:
            pass

        return -1

    @staticmethod
    def fan_rpm() -> float:
        mb = get_hw_and_update(Hardware.HardwareType.Motherboard)
        try:
            for sh in mb.SubHardware:
                sh.Update()
                for sensor in sh.Sensors:
                    if (
                        sensor.SensorType == Hardware.SensorType.Fan
                        and "#2" in str(sensor.Name)
                        and sensor.Value is not None
                    ):  # Is Motherboard #2 Fan always the CPU Fan ?
                        return float(sensor.Value)
        except:
            pass

        # No Fan Speed sensor for this CPU model
        return -1


class Gpu(sensors.Gpu):
    # GPU to use is detected once, and its name is saved for future sensors readings
    gpu_name = ""

    # Latest FPS value is backed up in case next reading returns no value
    prev_fps = 0

    # Get GPU to use for sensors, and update it
    @classmethod
    def get_gpu_to_use(cls):
        gpu_to_use = get_hw_and_update(Hardware.HardwareType.GpuAmd, cls.gpu_name)
        if gpu_to_use is None:
            gpu_to_use = get_hw_and_update(
                Hardware.HardwareType.GpuNvidia, cls.gpu_name
            )
        if gpu_to_use is None:
            gpu_to_use = get_hw_and_update(Hardware.HardwareType.GpuIntel, cls.gpu_name)

        return gpu_to_use

    @classmethod
    def stats(
        cls,
    ) -> Tuple[
        float, float, float, float, float
    ]:  # load (%) / used mem (%) / used mem (Mb) / total mem (Mb) / temp (°C)
        gpu_to_use = cls.get_gpu_to_use()
        if gpu_to_use is None:
            # GPU not supported
            return -1, -1, -1, -1, -1

        load = 0
        used_mem = 0
        total_mem = 0
        temp = 0
        for sensor in gpu_to_use.Sensors:
            if (
                sensor.SensorType == Hardware.SensorType.Load
                and str(sensor.Name).startswith("GPU Core")
                and sensor.Value is not None
            ):
                load = float(sensor.Value)
            elif (
                sensor.SensorType == Hardware.SensorType.Load
                and str(sensor.Name).startswith("D3D 3D")
                and load == 0
                and sensor.Value is not None
            ):
                # Only use D3D usage if global "GPU Core" sensor is not available, because it is less
                # precise and does not cover the entire GPU: https://www.hwinfo.com/forum/threads/what-is-d3d-usage.759/
                load = float(sensor.Value)
            elif (
                sensor.SensorType == Hardware.SensorType.SmallData
                and str(sensor.Name).startswith("GPU Memory Used")
                and sensor.Value is not None
            ):
                used_mem = float(sensor.Value)
            elif (
                sensor.SensorType == Hardware.SensorType.SmallData
                and str(sensor.Name).startswith("D3D")
                and str(sensor.Name).endswith("Memory Used")
                and used_mem == 0
                and sensor.Value is not None
            ):
                # Only use D3D memory usage if global "GPU Memory Used" sensor is not available, because it is less
                # precise and does not cover the entire GPU: https://www.hwinfo.com/forum/threads/what-is-d3d-usage.759/
                used_mem = float(sensor.Value)
            elif (
                sensor.SensorType == Hardware.SensorType.SmallData
                and str(sensor.Name).startswith("GPU Memory Total")
                and sensor.Value is not None
            ):
                total_mem = float(sensor.Value)
            elif (
                sensor.SensorType == Hardware.SensorType.Temperature
                and str(sensor.Name).startswith("GPU Core")
                and sensor.Value is not None
            ):
                temp = float(sensor.Value)

        return load, (used_mem / total_mem * 100.0), used_mem, total_mem, temp

    @classmethod
    def fps(cls) -> int:
        gpu_to_use = cls.get_gpu_to_use()
        if gpu_to_use is None:
            # GPU not supported
            return -1

        try:
            for sensor in gpu_to_use.Sensors:
                if (
                    sensor.SensorType == Hardware.SensorType.Factor
                    and "FPS" in str(sensor.Name)
                    and sensor.Value is not None
                ):
                    # If a reading returns a value <= 0, returns old value instead
                    if int(sensor.Value) > 0:
                        cls.prev_fps = int(sensor.Value)
                    return cls.prev_fps
        except:
            pass

        # No FPS sensor for this GPU model
        return -1

    @classmethod
    def fan_rpm(cls) -> float:
        gpu_to_use = cls.get_gpu_to_use()
        if gpu_to_use is None:
            # GPU not supported
            return -1
        try:
            for sensor in gpu_to_use.Sensors:
                if (
                    sensor.SensorType == Hardware.SensorType.Fan
                    and sensor.Value is not None
                ):
                    return float(sensor.Value)
        except:
            pass

        # No Fan Speed sensor for this GPU model
        return -1

    @classmethod
    def frequency(cls) -> float:
        gpu_to_use = cls.get_gpu_to_use()
        if gpu_to_use is None:
            # GPU not supported
            return -1

        try:
            for sensor in gpu_to_use.Sensors:
                if sensor.SensorType == Hardware.SensorType.Clock:
                    # Keep only real core clocks, ignore effective core clocks
                    if (
                        "Core" in str(sensor.Name)
                        and "Effective" not in str(sensor.Name)
                        and sensor.Value is not None
                    ):
                        return float(sensor.Value) / 1000
        except:
            pass

        # No Frequency sensor for this GPU model
        return -1

    @classmethod
    def is_available(cls) -> bool:
        cls.gpu_name = get_gpu_name()
        return bool(cls.gpu_name)


class Memory(sensors.Memory):

    @staticmethod
    def percentage() -> float:
        memory = get_hw_and_update(Hardware.HardwareType.Memory)
        for sensor in memory.Sensors:
            if (
                sensor.SensorType == Hardware.SensorType.Load
                and str(sensor.Name).startswith("Memory")
                and sensor.Value is not None
            ):
                return float(sensor.Value)

        return -1

    @staticmethod
    def used() -> int:  # In bytes
        memory = get_hw_and_update(Hardware.HardwareType.Memory)
        for sensor in memory.Sensors:
            if (
                sensor.SensorType == Hardware.SensorType.Data
                and str(sensor.Name).startswith("Memory Used")
                and sensor.Value is not None
            ):
                return int(sensor.Value * 1000000000.0)

        return -1

    @staticmethod
    def free() -> int:  # In bytes
        memory = get_hw_and_update(Hardware.HardwareType.Memory)
        for sensor in memory.Sensors:
            if (
                sensor.SensorType == Hardware.SensorType.Data
                and str(sensor.Name).startswith("Memory Available")
                and sensor.Value is not None
            ):
                return int(sensor.Value * 1000000000.0)

        return -1


# NOTE: all disk data are fetched from psutil Python library, because LHM does not have it.
# This is because LHM is a hardware-oriented library, whereas used/free/total space is for partitions, not disks
class Disk(sensors.Disk):
    @staticmethod
    def percentage() -> float:
        return psutil.disk_usage("/").percent

    @staticmethod
    def used() -> int:  # In bytes
        used = 0
        for part in psutil.disk_partitions():
            used += psutil.disk_usage(part.mountpoint).used
        return used

    @staticmethod
    def free() -> int:  # In bytes
        free = 0
        for part in psutil.disk_partitions():
            free += psutil.disk_usage(part.mountpoint).free
        return free


class Net(sensors.Net):
    @staticmethod
    def stats(
        if_name="", interval=1
    ) -> Tuple[
        int, int, int, int
    ]:  # up rate (B/s), uploaded (B), dl rate (B/s), downloaded (B)

        upload_rate = 0
        uploaded = 0
        download_rate = 0
        downloaded = 0

        net_if = get_net_interface_and_update(if_name)
        if net_if is not None:
            for sensor in net_if.Sensors:
                if (
                    sensor.SensorType == Hardware.SensorType.Data
                    and str(sensor.Name).startswith("Data Uploaded")
                    and sensor.Value is not None
                ):
                    uploaded = int(sensor.Value * 1000000000.0)
                elif (
                    sensor.SensorType == Hardware.SensorType.Data
                    and str(sensor.Name).startswith("Data Downloaded")
                    and sensor.Value is not None
                ):
                    downloaded = int(sensor.Value * 1000000000.0)
                elif (
                    sensor.SensorType == Hardware.SensorType.Throughput
                    and str(sensor.Name).startswith("Upload Speed")
                    and sensor.Value is not None
                ):
                    upload_rate = int(sensor.Value)
                elif (
                    sensor.SensorType == Hardware.SensorType.Throughput
                    and str(sensor.Name).startswith("Download Speed")
                    and sensor.Value is not None
                ):
                    download_rate = int(sensor.Value)

            return upload_rate, uploaded, download_rate, downloaded
        return -1, -1, -1, -1
