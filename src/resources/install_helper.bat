@echo off
REM Windows�ļ��滻���ֽű�
REM �����ڳ����˳����滻��ִ���ļ�

setlocal enabledelayedexpansion

if "%~3"=="" (
    echo ����: ��������
    echo �÷�: install_helper.bat ^<��ǰexe·��^> ^<��exe·��^> ^<����·��^>
    echo ʵ�ʲ���: %1 %2 %3
    pause
    exit /b 1
)

set CURRENT_EXE=%~1
set NEW_EXE=%~2
set BACKUP_EXE=%~3

echo ========================================
echo        DG-LAB-VRCOSC ���°�װ����
echo ========================================
echo.
echo ������ʼ��װ���£���ȷ��������Ϣ��
echo.
echo ��ǰ����: %CURRENT_EXE%
echo �³���: %NEW_EXE%
echo ����λ��: %BACKUP_EXE%
echo.
echo ע�⣺��װ�����г��򽫻��Զ��˳���Ȼ���滻�ļ�
echo �˹�����Ҫ������ʱ�䣬�����ĵȴ�
echo.
set /p confirm="�Ƿ������װ��(Y/N): "
if /i not "%confirm%"=="Y" (
    echo ��װ��ȡ��
    pause
    exit /b 0
)

echo.
echo ��ʼ��װ����...

REM �ȴ�������ȫ�˳�
echo �ȴ������˳�...
echo ���ڼ��������...
:wait_loop
tasklist /FI "IMAGENAME eq %~nx1" 2>NUL | find /I "%~nx1" >NUL
if not errorlevel 1 (
    echo �����������У������ȴ�...
    timeout /t 1 /nobreak >NUL
    goto wait_loop
)

echo �������˳����ȴ�3��ȷ����ȫ�˳�...
timeout /t 3 /nobreak >NUL
echo ��ʼ�滻�ļ�...

REM ��������
if exist "%CURRENT_EXE%" (
    echo ���ڴ��������ļ�...
    copy "%CURRENT_EXE%" "%BACKUP_EXE%" >NUL 2>&1
    if errorlevel 1 (
        echo ����: �޷���������
        echo.
        echo ��װʧ�ܣ������ļ�Ȩ�ޡ�
        pause
        exit /b 1
    )
    echo ���ݴ����ɹ�
)

REM �滻�ļ�
if exist "%NEW_EXE%" (
    echo �����滻�����ļ�...
    move "%NEW_EXE%" "%CURRENT_EXE%" >NUL 2>&1
    if errorlevel 1 (
        echo ����: �޷��滻�����ļ�
        REM ���Իָ�����
        if exist "%BACKUP_EXE%" (
            copy "%BACKUP_EXE%" "%CURRENT_EXE%" >NUL 2>&1
            echo �ѻָ������ļ�
        )
        echo.
        echo ��װʧ�ܣ������ļ�Ȩ�޻��ֶ���װ��
        pause
        exit /b 1
    )
    echo �����ļ��滻�ɹ�
) else (
    echo ����: �³����ļ�������
    echo.
    echo ��װʧ�ܣ��³����ļ���ʧ��
    pause
    exit /b 1
)

echo �ļ��滻��ɣ�

REM ���Զ������³������û��ֶ�����
echo �³�����׼�����������ֶ�����: %CURRENT_EXE%

REM ������ʱ�ļ�
if exist "%NEW_EXE%" del "%NEW_EXE%" >NUL 2>&1

echo.
echo ========================================
echo        ���°�װ�ɹ���
echo ========================================
echo.
echo �����ѳɹ����£����ֶ������°汾����
echo ����·��: %CURRENT_EXE%
echo �����ļ�������: %BACKUP_EXE%
echo.
echo ����������⣬����ʹ�ñ����ļ��ָ���
echo ��װ��������ɣ������Թرմ˴��ڡ�
echo.
pause
exit /b 0
