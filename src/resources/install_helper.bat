@echo off
REM Windows文件替换助手脚本
REM 用于在程序退出后替换可执行文件

setlocal enabledelayedexpansion

if "%~3"=="" (
    echo 错误: 参数不足
    echo 用法: install_helper.bat ^<当前exe路径^> ^<新exe路径^> ^<备份路径^>
    echo 实际参数: %1 %2 %3
    pause
    exit /b 1
)

set CURRENT_EXE=%~1
set NEW_EXE=%~2
set BACKUP_EXE=%~3

echo ========================================
echo        DG-LAB-VRCOSC 更新安装程序
echo ========================================
echo.
echo 即将开始安装更新，请确认以下信息：
echo.
echo 当前程序: %CURRENT_EXE%
echo 新程序: %NEW_EXE%
echo 备份位置: %BACKUP_EXE%
echo.
echo 注意：安装过程中程序将会自动退出，然后替换文件
echo 此过程需要几秒钟时间，请耐心等待
echo.
set /p confirm="是否继续安装？(Y/N): "
if /i not "%confirm%"=="Y" (
    echo 安装已取消
    pause
    exit /b 0
)

echo.
echo 开始安装更新...

REM 等待程序完全退出
echo 等待程序退出...
echo 正在检测程序进程...
:wait_loop
tasklist /FI "IMAGENAME eq %~nx1" 2>NUL | find /I "%~nx1" >NUL
if not errorlevel 1 (
    echo 程序仍在运行，继续等待...
    timeout /t 1 /nobreak >NUL
    goto wait_loop
)

echo 程序已退出，等待3秒确保完全退出...
timeout /t 3 /nobreak >NUL
echo 开始替换文件...

REM 创建备份
if exist "%CURRENT_EXE%" (
    echo 正在创建备份文件...
    copy "%CURRENT_EXE%" "%BACKUP_EXE%" >NUL 2>&1
    if errorlevel 1 (
        echo 错误: 无法创建备份
        echo.
        echo 安装失败！请检查文件权限。
        pause
        exit /b 1
    )
    echo 备份创建成功
)

REM 替换文件
if exist "%NEW_EXE%" (
    echo 正在替换程序文件...
    move "%NEW_EXE%" "%CURRENT_EXE%" >NUL 2>&1
    if errorlevel 1 (
        echo 错误: 无法替换程序文件
        REM 尝试恢复备份
        if exist "%BACKUP_EXE%" (
            copy "%BACKUP_EXE%" "%CURRENT_EXE%" >NUL 2>&1
            echo 已恢复备份文件
        )
        echo.
        echo 安装失败！请检查文件权限或手动安装。
        pause
        exit /b 1
    )
    echo 程序文件替换成功
) else (
    echo 错误: 新程序文件不存在
    echo.
    echo 安装失败！新程序文件丢失。
    pause
    exit /b 1
)

echo 文件替换完成！

REM 不自动启动新程序，让用户手动启动
echo 新程序已准备就绪，请手动启动: %CURRENT_EXE%

REM 清理临时文件
if exist "%NEW_EXE%" del "%NEW_EXE%" >NUL 2>&1

echo.
echo ========================================
echo        更新安装成功！
echo ========================================
echo.
echo 程序已成功更新，请手动启动新版本程序。
echo 程序路径: %CURRENT_EXE%
echo 备份文件保存在: %BACKUP_EXE%
echo.
echo 如果遇到问题，可以使用备份文件恢复。
echo 安装过程已完成，您可以关闭此窗口。
echo.
pause
exit /b 0
