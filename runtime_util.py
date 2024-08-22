# coding:utf-8

import ctypes
import os
import socket
import psutil
import win32api
import win32con
import sys
import winreg as reg
from log import logger

def set_always_runas_admin():
    # 获取程序名称
    executable = os.path.abspath(sys.argv[0])
    # 注册表路径
    reg_path = r"Software\\Microsoft\Windows NT\\CurrentVersion\AppCompatFlags\\Layers"
    try:
        # 打开注册表路径
        reg_key = reg.OpenKey(reg.HKEY_CURRENT_USER, reg_path, 0, reg.KEY_SET_VALUE)
        # 设置程序的注册表值，标记为管理员权限
        reg.SetValueEx(reg_key, executable, 0, reg.REG_SZ, "~ RUNASADMIN")
        # 关闭注册表
        reg.CloseKey(reg_key)
        
        logger.info(f"Successfully set always run as administrator.")
    except Exception as e:
        logger.error(f"Successfully set always run as administrator: {e}")

def is_runas_admin():
    """检查当前进程是否以管理员身份运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def is_runas_executable():
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

# 必须以管理员身份启动
def require_runas_admin():
    if not is_runas_executable():
        return
    if not is_runas_admin():
        # 如果是已编译的可执行文件，修改注册表实现总是以管理员身份运行
        set_always_runas_admin()
        # 显示弹窗提示用户以管理员身份重新启动
        show_message_box("请以管理员权限启动当前程序\nPlease start the current program with administrator privileges")
        try:
            sys.exit(0)
        except:
            os._exit(0)
# 必须以唯一进程启动
def require_runas_unique():
    if not is_runas_executable():
        return
    # 在启动前先杀死同名称的进程
    current_pid = os.getpid()
    executable = os.path.abspath(sys.argv[0])
    program_name = os.path.basename(executable)
    logger.info(f'Current PID: {current_pid}\t Program Name: {program_name}')
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == program_name and proc.info['pid'] != current_pid:
            try:
                pid = proc.info['pid']
                process = psutil.Process(pid)
                process.terminate()
                process.wait()  # 等待进程终止
                logger.info(f"Killed process with PID: {pid}")
            except psutil.NoSuchProcess:
                logger.error(f"Process with PID {pid} does not exist.")
            except psutil.AccessDenied:
                logger.error(f"Access denied to terminate process with PID {pid}.")
    

