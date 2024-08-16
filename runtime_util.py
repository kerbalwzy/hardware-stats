# coding:utf-8
# runas_admin.py: 用于在windows平台上自动以管理员身份重启软件

import ctypes
import os
import socket
import win32api
import win32con
import sys
import winreg as reg
from log import logger

def set_program_as_admin():
    # 获取程序名称
    executable = os.path.abspath(sys.argv[0])
    program_name = os.path.basename(executable)
    
    # 注册表路径
    reg_path = r"Software\Microsoft\Windows NT\CurrentVersion\AppCompatFlags\Layers"
    
    try:
        # 打开注册表路径
        reg_key = reg.OpenKey(reg.HKEY_CURRENT_USER, reg_path, 0, reg.KEY_SET_VALUE)
        
        # 设置程序的注册表值，标记为管理员权限
        reg.SetValueEx(reg_key, executable, 0, reg.REG_SZ, "~ RUNASADMIN")
        
        # 关闭注册表
        reg.CloseKey(reg_key)
        
        logger.info(f"Successfully set '{program_name}' to always run as administrator.")
    
    except Exception as e:
        logger.error(f"Failed to set registry key: {e}")

def is_admin():
    """检查当前进程是否以管理员身份运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def is_running_as_executable():
    """检查当前进程是否是以已编译的可执行文件运行"""
        # 获取启动路径
    start_path = sys.argv[0]
    # 检查扩展名
    if start_path.lower().endswith('.exe'):
        return True
    elif start_path.lower().endswith('.py'):
        return False
    else:
        return os.path.isfile(start_path) and start_path.lower().endswith('.exe')

def show_message_box(message):
    """显示消息框"""
    win32api.MessageBox(0, message, "", win32con.MB_OK | win32con.MB_ICONINFORMATION)

def require_run_as_admin():
    """以管理员身份重新启动当前进程"""
    if not is_admin() and is_running_as_executable():
        # 如果是已编译的可执行文件，修改注册表以管理员身份运行
        set_program_as_admin()
        # 显示弹窗提示用户以管理员身份重新启动
        show_message_box("请以管理员权限启动当前程序\nPlease start the current program with administrator privileges")
        try:
            sys.exit(0)
        except:
            os._exit(0)
    else:
        logger.info("Is running as admin")

def get_socket_lock():
    """通过绑定端口实现进程单例"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # 绑定到本地指定端口
        sock.bind(("127.0.0.1", 61994))
        return sock
    except socket.error:
        # 如果无法绑定端口，说明另一个实例正在运行
        logger.error("Another instance of this program is already running.")
        sys.exit("Another instance of this program is already running.")

