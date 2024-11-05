import sys
import os

def get_executable_location():
    # sys.executable 返回的是当前可执行文件的完整路径
    if getattr(sys, 'frozen', False):
        # 如果程序已打包
        return os.path.dirname(sys.executable)
    else:
        # 如果是直接运行 .py 脚本
        return os.path.dirname(os.path.abspath(__file__))

EXEC_PATH = get_executable_location()
LOG_PATH = os.path.join(EXEC_PATH, "log.txt")
LOGGER_NAME = "HardwareStats"
STATE_PATH = os.path.join(EXEC_PATH, "hardware-stats.yaml")