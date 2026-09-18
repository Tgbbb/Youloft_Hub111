# TestHub iOS Agent

把 `E:\iOS相关` 那套手工步骤（隧道 → 开发者映像 → runwda → 端口转发）封装成
**一键启动 + 常驻看护 + 自动注册/心跳**，让 iOS 设备自动出现在 TestHub 设备列表里。
WDA 由使用者**自行安装**（脚本只负责把它跑起来，不负责装）。

同一份脚本、两种用法：

| 场景 | share_on_lan | 注册的 WDA 地址 |
| --- | --- | --- |
| 设备插在 TestHub 服务器本机 | `false` | `127.0.0.1:9000` |
| 设备插在同事电脑（局域网访问） | `true` | `<同事电脑局域网IP>:9000` |

## 前置条件

1. **go-ios**：`E:\iOS相关\go-ios-win\ios.exe`（路径可在配置里改）。
2. **wintun**：把 `E:\iOS相关\wintun\bin\amd64\wintun.dll` 复制到 `C:\Windows\System32\`（隧道依赖）。
3. **Apple 驱动/iTunes**：保证 `ios list` 能看到设备；设备需已配对并在“信任此电脑”。
4. **开发者模式**：iOS 设备「设置 → 隐私与安全性 → 开发者模式」打开。
5. **WDA 已安装**：`E:\iOS相关\WDA(5).ipa`（用 `ios install` 安装，签名包名以实际为准）。
6. **服务账号 Token**：在 TestHub 服务器执行
   ```
   python manage.py drf_create_token <服务账号用户名>
   ```
   把输出的 token 填到配置的 `agent_token`。

## 配置

复制 `agent.config.example.json` 为 `agent.config.json`（与脚本同目录），按需修改：

- `testhub_base_url`：TestHub 的 API 根地址，如 `http://192.168.8.120:8000/api`
- `agent_token`：上一步生成的 Token
- `ios_tool_path`：go-ios 可执行文件路径
- `wda_bundle_id` / `wda_testrunner_bundle_id` / `wda_xctest_config`：WDA 的签名包名与测试配置，签名变了要同步改

  **签包名一般不用手动改**：脚本启动前会读设备上实际安装的 WDA 包名（`ios apps` 里匹配 `WebDriverAgentRunner`），与配置不一致时自动改用实际包名并在日志里提示。想手动确认可执行：
  ```powershell
  E:\iOS相关\go-ios-win\ios.exe apps --udid=<UDID> | Select-String WebDriverAgentRunner
  ```
- `forward_port`（默认 9000）/ `wda_target_port`（默认 8100）
- `share_on_lan`：同事电脑跑就设 `true`（会把 9000 暴露到局域网，需要管理员）
- `use_proxy`：默认 `false`，脚本会忽略系统代理直连本机/局域网（装了 clash 之类代理时保持 `false`）
- `heartbeat_seconds`：心跳间隔，默认 30
- `device_udid`：留空自动探测；插了多台设备时必须填

## 用法

```powershell
# 一键（推荐）：起隧道/WDA/转发 + 常驻看护 + 心跳（窗口开着设备就一直在线）
.\ios-agent.ps1 -Mode watch

# 跑一次就退出（仅注册一下，之后 2 分钟会因无心跳转离线）
.\ios-agent.ps1 -Mode start

# 双击等价写法
.\ios-agent.bat

# 停止：结束后台进程 + 清理端口暴露 + 在 TestHub 标记离线
.\ios-agent.ps1 -Mode stop

# 只打印将要执行的命令，不实际操作（用于核对）
.\ios-agent.ps1 -Mode start -DryRun
```

> 维护提示：`ios-agent.ps1` 必须保存为 **UTF-8 with BOM**。`.bat` 调的是 Windows PowerShell 5.1，
> 无 BOM 时它按 ANSI 解码，脚本里的中文会把语法读崩。编辑后如需修复 BOM：
> `$t=[IO.File]::ReadAllText($p);[IO.File]::WriteAllText($p,$t,(New-Object Text.UTF8Encoding($true)))`

### 挂成开机自启（看护模式）

**管理员** PowerShell 执行：

```powershell
schtasks /create /tn "TestHub iOS Agent" /sc onlogon /rl highest /f ^
  /tr "powershell.exe -NoProfile -ExecutionPolicy Bypass -File \"E:\TestHub\testhub_platform\scripts\ios-agent\ios-agent.ps1\" -Mode watch"
```

删除：`schtasks /delete /tn "TestHub iOS Agent" /f`

## 局域网暴露（同事电脑场景）

`share_on_lan=true` 时脚本会自动配置（需管理员）：

```powershell
netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport=9000 connectaddress=127.0.0.1 connectport=9000
netsh advfirewall firewall add rule name="TestHub-iOS-Agent-9000" dir=in action=allow protocol=TCP localport=9000
```

非管理员运行时脚本**不会失败**，只打印上面两条命令并降级为“仅本机可用”。

验证可达性（在 TestHub 服务器上执行）：

```powershell
Test-NetConnection <同事电脑IP> -Port 9000
curl http://<同事电脑IP>:9000/status
```

通了以后，TestHub 设备列表里会出现该设备（来源机器 = 同事电脑名），点“测通”应返回成功。

## 心跳与离线

- agent 每 `heartbeat_seconds`（默认 30s）上报一次 `/agent_report/`。
- TestHub 侧 Celery beat 每分钟跑 `mark_stale_midscene_devices`：`last_seen_at` 超过 120s 的 iOS 设备自动转 `offline`（`locked` 状态不动）。
- agent 正常停止时调用 `/agent_release/` 立即置离线。

## 常见问题

| 现象 | 排查 |
| --- | --- |
| `未发现 iOS 设备` | 换线/换口；`ios list` 是否能看到；iTunes 能否识别；设备是否点过“信任” |
| 隧道起不来 | `wintun.dll` 是否在 `System32`；`ios tunnel ls` 有无残留；重试 `ios tunnel stopagent` 再 start |
| WDA 起不来 | 开发者模式是否打开；检查 `ios image auto` 是否挂载成功；WDA 证书是否过期（需重签名重装）、`bundleid` 是否与签名一致 |
| 注册失败 401 | `agent_token` 是否正确；服务账号是否有效 |
| 同事机设备在 TestHub 点“测通”不通 | `netsh interface portproxy show v4tov4`；防火墙规则；两台机是否同网段/未被隔离 |
| 设备频繁离线 | agent 是否在跑；`schtasks /query /tn "TestHub iOS Agent"`；看 `agent.log` |

## 同事版整包（给同事的傻瓜包）

`E:\iOS相关\TestHub-iOS-Agent-同事版\` 是可直接分发的整包：

| 文件 | 说明 |
| --- | --- |
| `1-首次准备.bat` | 首次跑一次（自动提权）：把 wintun.dll 装到 `C:\Windows\System32` + 列出设备 |
| `ios-agent.bat` | 平时双击启动；因 `share_on_lan=true` 会自动请求管理员 |
| `ios-agent.ps1` | agent 本体 |
| `agent.config.json` | 已预填同事场景：`share_on_lan=true`、相对 go-ios 路径、token |
| `使用说明.txt` | 给同事看的傻瓜步骤 |
| `tools\go-ios-win\ios.exe`、`tools\wintun\wintun.dll` | 随包自带，免安装 |

同事只需：**双击 `1-首次准备.bat` → 双击 `ios-agent.bat`**。

要点：

- `ios_tool_path` 写的是相对路径 `tools\go-ios-win\ios.exe`，脚本按自身目录解析，所以整个文件夹放哪都行。
- 想让每个同事用独立账号（便于追溯设备归属），把 `agent.config.json` 的 `agent_token` 换成各自账号的 token 即可。
- 重建整包用本目录的 `ios-agent.ps1` / `ios-agent.bat` / `agent.config.colleague.example.json`；后者是同事场景模板（不含 token，可入库）。

## 验收清单

1. 本机 `-Mode start` → TestHub 设备列表出现该设备，「来源机器」为电脑名，「测通」成功。
2. 同事机 `share_on_lan=true` → 设备以 `同事IP:9000` 出现且「测通」成功。
3. `-Mode stop`（或直接关掉 agent）→ 1~2 分钟内设备转 `offline`。
4. 拔插设备或杀掉 WDA → `-Mode watch` 能自动恢复并继续心跳。
