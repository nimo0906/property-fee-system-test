# 明天 Windows 打包从这里开始

## 一句话目标

明天在 Windows 电脑上，从 GitHub 下载最新版代码，然后生成这个文件发给用户：

```text
release\windows\物业管理收费系统-v2.0-windows.zip
```

普通用户收到后只需要：

```text
解压 zip → 双击 PropertyFeeSystem.exe → admin / admin123 登录
```

## 1. 先确认下载的是最新版

GitHub 仓库：

```text
https://github.com/nimo0906/property-fee-system-test
```

进入仓库后，下载最新版代码：

```text
Code → Download ZIP
```

下载后解压到 Windows 电脑，例如：

```text
D:\property-fee-system-test
```

## 2. Windows 电脑先装 Python

安装 Python 3.10 或 3.11。

下载地址：

```text
https://www.python.org/downloads/windows/
```

安装时必须勾选：

```text
Add python.exe to PATH
```

## 3. 打包前先双击检查

进入项目文件夹，先双击：

```text
check_windows_packaging_ready.bat
```

如果看到检查通过，再继续下一步。

如果出现 `FAIL`，先不要打包，把窗口内容发回来。

## 4. 一键生成 Windows 试用包

双击：

```text
package_windows_release.bat
```

等待它自动完成。

成功后会生成：

```text
release\windows\物业管理收费系统-v2.0-windows.zip
```

## 5. 发给用户哪个文件

只发这个 zip：

```text
release\windows\物业管理收费系统-v2.0-windows.zip
```

不要发源码目录，不要发 `property.db`，不要发 `.env`。

## 6. 用户打开方式

告诉用户：

1. 解压 zip。
2. 打开解压后的文件夹。
3. 双击：

```text
PropertyFeeSystem\PropertyFeeSystem.exe
```

4. 登录：

```text
用户名：admin
密码：admin123
```

如果 Windows 安全提示拦截，点击：

```text
更多信息 → 仍要运行
```

## 7. 明天要验收哪些页面

生成 Windows 包后，在 Windows 电脑上至少打开这些页面：

- 后台首页 `/`
- 业主端登录 `/owner-portal/login`
- 支付订单 `/payment_orders`
- 电子票据 `/invoice_requests`
- 对账报表 `/reports`

## 8. 相关文件说明

| 文件 | 用途 |
|---|---|
| `check_windows_packaging_ready.bat` | 打包前检查环境和文件是否齐全 |
| `package_windows_release.bat` | 一键生成 Windows 试用 zip |
| `Windows打包操作步骤.md` | 更详细的 Windows 打包说明 |
| `Windows客户试用说明.md` | 可发给客户看的 Windows 试用说明 |
| `Windows用户发送文案.md` | zip 生成后可直接复制给用户的微信/邮件文案 |
| `清空本机试用数据.bat` | 备份并清空 Windows 本机旧试用数据 |
| `diagnose_windows.bat` | Windows 启动异常时诊断 |

## 9. 当前仓库状态

本仓库已经准备好明天 Windows 打包使用：

- Windows 打包脚本已准备。
- Windows 打包前检查脚本已准备。
- Windows 客户说明已准备。
- Windows 清空本机试用数据脚本已准备。
- Windows 打包配置已去掉本机 `property.db`，不会把本机测试数据库打进包。
- `.env` 不会提交。


## 真实数据提醒

从录入真实房间、业主、账单、收款开始，请先阅读 `真实数据试运行保护方案.md` 和 `真实数据导入前验收清单.md`。清空本机试用数据脚本只适合演示/试用环境，不适合已经录入真实业务数据的电脑。
