# coding:utf-8
from abc import ABC, abstractmethod
from typing import Tuple


class Cpu(ABC):
    @staticmethod
    @abstractmethod
    def percentage() -> float:

        pass

    @staticmethod
    @abstractmethod
    def frequency() -> float:
        pass

    @staticmethod
    @abstractmethod
    def temperature() -> float:
        pass

    @staticmethod
    @abstractmethod
    def fan_rpm() -> float:
        pass


class Gpu(ABC):
    @staticmethod
    @abstractmethod
    def stats() -> Tuple[
        float, float, float, float, float]:  # load (%) / used mem (%) / used mem (Mb) / total mem (Mb) / temp (°C)
        pass

    @staticmethod
    @abstractmethod
    def fps() -> int:
        pass

    @staticmethod
    @abstractmethod
    def fan_rpm() -> float:
        pass

    @staticmethod
    @abstractmethod
    def frequency() -> float:
        pass

    @staticmethod
    @abstractmethod
    def is_available() -> bool:
        pass


class Memory(ABC):
    @staticmethod
    @abstractmethod
    def swap_percent() -> float:
        pass

    @staticmethod
    @abstractmethod
    def virtual_percent() -> float:
        pass

    @staticmethod
    @abstractmethod
    def virtual_used() -> int:  # In bytes
        pass

    @staticmethod
    @abstractmethod
    def virtual_free() -> int:  # In bytes
        pass


class Disk(ABC):
    @staticmethod
    @abstractmethod
    def disk_usage_percent() -> float:
        pass

    @staticmethod
    @abstractmethod
    def disk_used() -> int:  # In bytes
        pass

    @staticmethod
    @abstractmethod
    def disk_free() -> int:  # In bytes
        pass


class Net(ABC):
    @staticmethod
    @abstractmethod
    def stats(if_name="", interval=1) -> Tuple[
        int, int, int, int]:  # up rate (B/s), uploaded (B), dl rate (B/s), downloaded (B)
        pass

