# Windows 服务器无黑框运行说明

## 目标

服务器电脑上不再长期打开黑框窗口。系统仍然在后台运行，员工继续通过浏览器访问：

```text
http://服务器内网IP:5001
```

这套方案用于 Windows 服务器，不是 macOS .app。

## 推荐方式

使用 Windows 任务计划程序安装一个后台任务：

- 任务名：`PropertyFeeSystemServer`
- 启动方式：服务器开机自动启动
- 运行账号：`SYSTEM`
- 监听地址：`0.0.0.0:5001`
- 数据目录：`D:\PropertyFeeSystemData`
- 日志文件：`D:\PropertyFeeSystemData\logs\server_task.log`
- 运行效果：不会显示黑框

## 安装步骤

1. 把 Windows 交付包解压到服务器电脑，例如：

```text
D:\PropertyFeeSystemRelease
```

2. 进入解压后的目录。
3. 找到：

```text
install_windows_background_task.bat
```

4. 右键选择：

```text
以管理员身份运行
```

5. 安装完成后，让员工电脑打开：

```text
http://服务器内网IP:5001
```

## 查看是否正常运行

右键以管理员身份运行：

```text
status_windows_background_task.bat
```

它会检查任务是否存在，并访问：

```text
http://127.0.0.1:5001/
```

## 停止后台运行

如果需要取消开机自启，右键以管理员身份运行：

```text
uninstall_windows_background_task.bat
```

这个脚本只删除后台任务，不会删除业务数据。

## 数据和备份位置

正式服务器数据统一放在：

```text
D:\PropertyFeeSystemData
```

其中：

```text
D:\PropertyFeeSystemData\database\property.db
D:\PropertyFeeSystemData\backups
D:\PropertyFeeSystemData\logs
```

不要把这个目录随便删除。

## 注意事项

- 服务器程序必须运行，区别只是后台运行，不显示黑框。
- 如果员工电脑打不开，先检查服务器 IP、Windows 防火墙和 5001 端口。
- 如果换服务器，先备份 `D:\PropertyFeeSystemData`。
- 如果只双击 `PropertyFeeSystem.exe`，那是普通桌面模式；正式服务器建议使用本说明里的后台任务模式。
