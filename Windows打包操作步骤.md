# Windows 打包操作步骤

## 一、明天你只需要做这几步

1. 打开 Windows 电脑。
2. 安装 Python 3.10 或 3.11。
3. 下载 GitHub 仓库最新版代码。
4. 解压项目代码。
5. 先双击：

```text
check_windows_packaging_ready.bat
```

6. 检查通过后，再双击：

```text
package_windows_release.bat
```

7. 等窗口提示完成后，把这个文件发给用户：

```text
release\windows\物业管理收费系统-v2.0-windows.zip
```

用户收到后只需要：

```text
解压 zip → 双击 PropertyFeeSystem.exe → admin / admin123 登录
```

## 二、安装 Python

打开官网：

```text
https://www.python.org/downloads/windows/
```

下载 Python 3.10 或 3.11。

安装时一定勾选：

```text
Add python.exe to PATH
```

如果忘记勾选，后面的脚本可能会提示找不到 Python。

## 三、下载项目代码

进入 GitHub 仓库页面，下载最新版代码，或者用 Git 克隆。

如果不熟悉 Git，直接用 GitHub 页面里的：

```text
Code → Download ZIP
```

下载后解压。

## 四、先运行打包前检查

进入解压后的项目文件夹，双击：

```text
check_windows_packaging_ready.bat
```

它会检查：

- Python 是否可用。
- pip 是否可用。
- Windows 打包脚本是否存在。
- 打包配置是否存在。
- 用户说明文档是否存在。
- 清空本机试用数据脚本是否存在。
- Windows 打包配置是否没有夹带本机 `property.db`。

如果检查失败，把窗口里的内容发回来。

## 五、生成 Windows 试用包

检查通过后，双击：

```text
package_windows_release.bat
```

这个脚本会自动完成：

- 安装 Python 依赖。
- 打包 `PropertyFeeSystem.exe`。
- 整理 Windows 试用交付目录。
- 生成 zip 压缩包。
- 检查 zip 里没有 `.env`、`property.db`、`*.db`、`backups/`、缓存和日志。

完成后会看到：

```text
release\windows\物业管理收费系统-v2.0-windows.zip
```

## 六、发给用户哪个文件

只发这个 zip：

```text
release\windows\物业管理收费系统-v2.0-windows.zip
```

不要发项目源码文件夹，也不要单独发 `dist`。

## 七、用户怎么打开

告诉用户：

1. 解压 zip。
2. 打开解压后的文件夹。
3. 双击：

```text
PropertyFeeSystem\PropertyFeeSystem.exe
```

4. 浏览器自动打开后登录：

```text
用户名：admin
密码：admin123
```

如果 Windows 安全提示拦截，点：

```text
更多信息 → 仍要运行
```

## 八、如果用户看到旧测试数据

说明那台 Windows 电脑之前运行过系统，旧数据在：

```text
%APPDATA%\PropertyFeeSystem
```

让用户先关闭程序，再双击：

```text
清空本机试用数据.bat
```

脚本会先备份旧数据到桌面，再清空本机试用数据。

## 九、常见失败处理

| 问题 | 处理 |
|---|---|
| 提示找不到 Python | 重新安装 Python，并勾选 `Add python.exe to PATH` |
| 打包时依赖安装失败 | 检查 Windows 是否能联网，重新运行脚本 |
| 打包完成但没有 zip | 看窗口报错，通常是 PowerShell 或权限问题 |
| 双击 exe 没反应 | 运行 `diagnose_windows.bat`，把输出发回来 |
| 用户看到旧数据 | 运行 `清空本机试用数据.bat` |

## 十、明天验收标准

Windows 电脑上至少确认：

- `package_windows_release.bat` 能跑完。
- 生成 `release\windows\物业管理收费系统-v2.0-windows.zip`。
- 解压 zip 后能双击打开 `PropertyFeeSystem.exe`。
- 能登录后台首页。
- 能打开：
  - 账单管理
  - 电子票据
  - 对账报表
  - 业主端登录页
