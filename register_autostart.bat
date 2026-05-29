schtasks /Create /TN "D2SlideOS" /TR "wscript.exe C:\Users\I605232\projects\Aiden_AI\start_silent.vbs" /SC ONLOGON /RL HIGHEST /F
echo 注册成功！下次开机登录后 D2SlideOS 自动在后台启动。
pause