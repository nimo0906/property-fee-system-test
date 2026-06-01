#语言
-沟通：中文
-代码，命令，变量名，日志：英文
-先解决用户问题，再追求流程完整度

#安全红线
-不硬编码密钥
-不提交‘.env’
-不在日志中泄露敏感信息
-修改公共API/数据结构/数据库 schema/删除文件：先征得确认
-默认直接执行日常开发动作，只对少数高风险动作做硬拦截

#工作流程
-命令报错 / 测试失败：必须明确报告，不掩盖
-声称“完成”前：先运行验证
-修 bug：优先先写失败测试再修复
-默认低摩擦执行，不把系统做成频繁确认工作流

#代码标准
-单文件不宜过大：Python/JS/TS ≦300行；Java/Go/Rust≦400行
-不写不必要的向后兼容代码
-不做不必要抽象
-Commit message:类型英文，描述中文
-每次commit 后立即 push

#用户偏好
-用户名：yuheng
-不确认的事情要确认
-模糊的事情要确认
-更看重：完成度，质量，效率，而不是形式化流程
-偏好中文沟通
-有明显匹配的skill时优先调用；无则直接执行

#质量
-先验证，在宣称完成
-优先沿用仓库已有tests/lint/typecheck
-对用户可见行为变化，必须说清楚

#Context 管理
-上下文接近上限时主动 compact
-完成一个完整功能模块后，是compact的好时机


#桌面 App 优先
- 后续优化和升级默认以桌面端 App 交付为目标，而不是只满足网页预览。
- 改动用户可见功能后，除普通 HTTP 页面验证外，还要考虑桌面启动器、打包资源、用户数据目录、备份目录和本地端口是否正常。
- macOS 交付入口：`build_macos_app.command` -> `dist/物业管理收费系统.app`。
- Windows 交付入口：`build_windows_exe.bat` -> `dist\PropertyFeeSystem\PropertyFeeSystem.exe`。
- 新增静态资源、模板、文档或依赖时，要同步检查 PyInstaller spec 是否纳入打包。
- 声称桌面端完成前，至少运行桌面相关测试；涉及打包资源时优先验证打包后的可执行入口能打开登录页。

#更新与发布强制规范
- 后续任何用户可见更新，必须同步 macOS、Windows 和 GitHub Release；不能只更新单端。
- Windows 包必须通过 Windows 环境或 GitHub Actions 产出，并和 macOS 包一起更新 `internal-latest`。
- 发布前必须运行 `py_compile`、`pytest`、`scripts/desktop_release_check.py`；更新器/打包相关变更还要跑对应专项测试。
- 更新器、安全边界、发布清单和 SHA256 校验要求见 `docs/release-update-policy.md`。
- 不提交真实 Excel、数据库、备份、缓存、构建目录、`.env`、日志或系统临时文件。
- 清理仓库时，缓存和构建产物可清；删除历史文档、发布目录或真实数据前必须先列清单确认。
- 代码体积严格控制，新增逻辑优先拆模块，避免继续放大已有大文件。
