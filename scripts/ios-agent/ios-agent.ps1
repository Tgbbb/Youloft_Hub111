# TestHub iOS Agent — 一键启动 / 常驻看护 / 注册心跳
#
# 依赖：go-ios（ios.exe）+ wintun（放 System32）+ 已安装的 WDA
# 用法：
#   .\ios-agent.ps1 -Mode start     # 一键：起隧道/WDA/转发 + 注册到 TestHub
#   .\ios-agent.ps1 -Mode watch     # 常驻：健康检查 + 自愈 + 心跳（推荐挂计划任务）
#   .\ios-agent.ps1 -Mode stop      # 停止并在 TestHub 标记离线
#   .\ios-agent.ps1 -Mode start -DryRun   # 只打印将要执行的命令，不真正执行
[CmdletBinding()]
param(
    [ValidateSet('start', 'watch', 'stop')]
    [string]$Mode = 'start',
    [string]$ConfigPath = '',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
# $PSScriptRoot 在 param 默认值里可能为空（-File 调用），这里运行时再解析
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
if (-not $ScriptDir) { $ScriptDir = (Get-Location).Path }
if (-not $ConfigPath) { $ConfigPath = Join-Path $ScriptDir 'agent.config.json' }
$StatePath = Join-Path $ScriptDir 'agent.state.json'
$LogPath   = Join-Path $ScriptDir 'agent.log'

function Write-Log {
    param([string]$Message, [string]$Level = 'INFO')
    $line = "[{0}] [{1}] {2}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $Level, $Message
    Write-Host $line
    if (-not $DryRun) {
        try { Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8 } catch { }
    }
}

function Test-Admin {
    try {
        $p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
        return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch { return $false }
}

function Read-Config {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "配置文件不存在：$Path（可复制 agent.config.example.json 为 agent.config.json）"
    }
    return (Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Load-State {
    if (Test-Path -LiteralPath $StatePath) {
        try { return (Get-Content -LiteralPath $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json) } catch { return $null }
    }
    return $null
}

function Save-State {
    param($State)
    if ($DryRun) { return }
    ($State | ConvertTo-Json -Depth 6) | Set-Content -LiteralPath $StatePath -Encoding UTF8
}

function Invoke-Ios {
    param([string]$Exe, [string[]]$Arguments, [switch]$AsText)
    if ($DryRun) { Write-Log ("[dry] {0} {1}" -f $Exe, ($Arguments -join ' ')); return '' }
    # go-ios 会把 WARN 写到 stderr；$ErrorActionPreference='Stop' 下会把原生 stderr
    # 当成终止性错误，所以这里局部降级为 Continue，把 stderr 当普通输出合并回来。
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $Exe @Arguments 2>&1
        return (($out | Out-String).Trim())
    } finally {
        $ErrorActionPreference = $prev
    }
}

# 原生命令（netsh 等）统一走这里，避免它们写 stderr 时把脚本打断
function Invoke-Native {
    param([string]$Command, [string[]]$Arguments)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($Arguments) { return (& $Command @Arguments 2>&1) }
        return (& $Command 2>&1)
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Start-IosBackground {
    param([string]$Exe, [string[]]$Arguments, [string]$Tag = 'bg')
    if ($DryRun) {
        Write-Log ("[dry] (bg) {0} {1}" -f $Exe, ($Arguments -join ' '))
        return 0
    }
    $outLog = Join-Path $ScriptDir ("agent.$Tag.out.log")
    $errLog = Join-Path $ScriptDir ("agent.$Tag.err.log")
    try {
        $p = Start-Process -FilePath $Exe -ArgumentList $Arguments -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput $outLog -RedirectStandardError $errLog
        Write-Log ("已后台启动 (PID {0}, 日志: agent.{1}.err.log): {2}" -f $p.Id, $Tag, ($Arguments -join ' '))
        return $p.Id
    } catch {
        Write-Log ("后台启动失败: {0}（命令: {1} {2}）" -f $_.Exception.Message, $Exe, ($Arguments -join ' ')) 'ERROR'
        return 0
    }
}

function Test-Alive {
    param([int]$ProcessId)
    if (-not $ProcessId) { return $false }
    return [bool](Get-Process -Id $ProcessId -ErrorAction SilentlyContinue)
}

function Stop-Alive {
    param([int]$ProcessId)
    if ($ProcessId -and (Test-Alive $ProcessId)) {
        if ($DryRun) { Write-Log ("[dry] stop pid {0}" -f $ProcessId); return }
        try { Stop-Process -Id $ProcessId -Force -ErrorAction Stop; Write-Log ("已结束进程 {0}" -f $ProcessId) } catch { }
    }
}

function Get-Udid {
    param($Config)
    if ($Config.device_udid) { return [string]$Config.device_udid }
    if ($DryRun) { return 'DRYRUN-UDID' }
    $raw = Invoke-Ios -Exe $Config.ios_tool_path -Arguments @('list')
    if (-not $raw) { return '' }
    $udids = @()
    foreach ($line in ($raw -split "`r?`n")) {
        if (-not $line.Trim()) { continue }
        try {
            $j = $line | ConvertFrom-Json
            if ($j.deviceList) { $udids += $j.deviceList }
        } catch { }
    }
    if ($udids.Count -eq 0) { throw '未发现 iOS 设备（检查数据线/信任/驱动是否正常）' }
    if ($udids.Count -gt 1) { throw ("发现多台设备，请在配置里指定 device_udid：{0}" -f ($udids -join ', ')) }
    return [string]$udids[0]
}

function Get-IosVersion {
    param($Config, [string]$Udid)
    try {
        $raw = Invoke-Ios -Exe $Config.ios_tool_path -Arguments @('--udid=' + $Udid, 'info')
        if ($raw -and ($raw -match '"ProductVersion"\s*:\s*"([^"]+)"')) { return $Matches[1] }
    } catch { }
    return ''
}

function Get-InstalledWdaBundleId {
    param($Config, [string]$Udid)
    try {
        $raw = Invoke-Ios -Exe $Config.ios_tool_path -Arguments @('--udid=' + $Udid, 'apps')
        if (-not $raw) { return '' }
        $m = [regex]::Matches($raw, '"CFBundleIdentifier":"([A-Za-z0-9_.\-]*WebDriverAgentRunner[A-Za-z0-9_.\-]*)"')
        if ($m.Count -gt 0) { return $m[0].Groups[1].Value }
    } catch { }
    return ''
}

# go-ios 的日志行也是 JSON（含 level/msg），这里只挑真正的数据条目
function Get-GoIosJsonEntries {
    param([string]$Output)
    $entries = @()
    if (-not $Output) { return $entries }
    foreach ($line in ($Output -split "`r?`n")) {
        $t = $line.Trim()
        if (-not ($t.StartsWith('[') -or $t.StartsWith('{'))) { continue }
        try { $obj = $t | ConvertFrom-Json } catch { continue }
        foreach ($item in @($obj)) {
            if ($null -eq $item -or $item -isnot [pscustomobject]) { continue }
            $names = $item.PSObject.Properties.Name
            if ($names -contains 'level' -or $names -contains 'msg') { continue }  # go-ios 日志行
            $entries += $item
        }
    }
    return $entries
}

function Test-TunnelUp {
    param([string]$Output, [string]$Udid)
    foreach ($e in (Get-GoIosJsonEntries -Output $Output)) {
        if (($e.PSObject.Properties.Name -contains 'rsdPort') -and ($e.udid -eq $Udid)) { return $true }
    }
    return $false
}

function Test-PortListening {
    param([int]$Port)
    try {
        $c = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction Stop
        if ($c) { return $true }
    } catch { }
    # 退回 TCP 连接探测（不依赖 netstat，也不受 stderr 影响）
    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $iar = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne(600)) { $client.EndConnect($iar); return $true }
        return $false
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Test-Wda {
    param([int]$Port)
    try {
        $r = Invoke-WebRequest -Uri ("http://127.0.0.1:{0}/status" -f $Port) -TimeoutSec 5 -UseBasicParsing
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

function Get-LanIp {
    param([string]$TesthubBaseUrl)
    try {
        $hostName = ([Uri]$TesthubBaseUrl).Host
        $route = Find-NetRoute -RemoteIPAddress $hostName -ErrorAction Stop | Select-Object -First 1
        if ($route -and $route.IPAddress -and $route.IPAddress -ne '127.0.0.1') { return $route.IPAddress }
    } catch { }
    $candidates = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
        Select-Object -First 1
    if ($candidates) { return $candidates.IPAddress }
    return ''
}

function Ensure-PortShare {
    param([int]$Port)
    $admin = Test-Admin
    if (-not $admin) {
        Write-Log '未以管理员运行：跳过局域网端口暴露（端口转发/防火墙未配置）。' 'WARN'
        Write-Log ("如需他机访问，请用管理员执行： netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport={0} connectaddress=127.0.0.1 connectport={0}" -f $Port) 'WARN'
        Write-Log ("并放行入站： netsh advfirewall firewall add rule name=TestHub-iOS-Agent-{0} dir=in action=allow protocol=TCP localport={0}" -f $Port) 'WARN'
        return $false
    }
    if ($DryRun) {
        Write-Log ("[dry] netsh interface portproxy add v4tov4 listenaddress=0.0.0.0 listenport={0} connectaddress=127.0.0.1 connectport={0}" -f $Port)
        return $true
    }
    $ruleName = "TestHub-iOS-Agent-$Port"
    Invoke-Native -Command 'netsh' -Arguments @('interface', 'portproxy', 'delete', 'v4tov4',
        'listenaddress=0.0.0.0', "listenport=$Port") | Out-Null
    Invoke-Native -Command 'netsh' -Arguments @('interface', 'portproxy', 'add', 'v4tov4',
        'listenaddress=0.0.0.0', "listenport=$Port", 'connectaddress=127.0.0.1', "connectport=$Port") | Out-Null
    Invoke-Native -Command 'netsh' -Arguments @('advfirewall', 'firewall', 'delete', 'rule',
        "name=$ruleName") | Out-Null
    Invoke-Native -Command 'netsh' -Arguments @('advfirewall', 'firewall', 'add', 'rule',
        "name=$ruleName", 'dir=in', 'action=allow', 'protocol=TCP', "localport=$Port") | Out-Null
    Write-Log ("已暴露端口 {0} 到局域网" -f $Port)
    return $true
}

function Remove-PortShare {
    param([int]$Port)
    if ($DryRun) { Write-Log ("[dry] remove portproxy/firewall for {0}" -f $Port); return }
    if (-not (Test-Admin)) { Write-Log '非管理员运行：跳过清理端口代理/防火墙规则。' 'WARN'; return }
    Invoke-Native -Command 'netsh' -Arguments @('interface', 'portproxy', 'delete', 'v4tov4',
        'listenaddress=0.0.0.0', "listenport=$Port") | Out-Null
    Invoke-Native -Command 'netsh' -Arguments @('advfirewall', 'firewall', 'delete', 'rule',
        "name=TestHub-iOS-Agent-$Port") | Out-Null
}

function Send-Report {
    param($Config, [string]$Udid, [string]$WdaHost, [string]$IosVersion, [string]$Status = 'online')
    $payload = @{
        device_id   = $Udid
        platform    = 'ios'
        name        = if ($Config.device_name) { [string]$Config.device_name } else { "iPhone ({0}...)" -f $Udid.Substring(0, [Math]::Min(8, $Udid.Length)) }
        wda_host    = $WdaHost
        ios_version = $IosVersion
        agent_host  = if ($Config.machine_name) { [string]$Config.machine_name } else { $env:COMPUTERNAME }
        status      = $Status
    } | ConvertTo-Json -Compress
    if ($DryRun) { Write-Log ("[dry] POST agent_report {0}" -f $payload); return $true }
    try {
        $r = Invoke-RestMethod -Method Post -Uri ($Config.testhub_base_url.TrimEnd('/') + '/ui-automation/midscene/devices/agent_report/') `
            -Headers @{ Authorization = ('Token ' + $Config.agent_token) } -ContentType 'application/json' -Body $payload -TimeoutSec 10
        Write-Log ("已上报：device={0} status={1} wda={2}" -f $r.device_id, $r.status, $WdaHost)
        return $true
    } catch {
        Write-Log ("上报失败：{0}" -f $_.Exception.Message) 'WARN'
        return $false
    }
}

function Send-Release {
    param($Config, [string]$Udid)
    $payload = @{ device_id = $Udid } | ConvertTo-Json -Compress
    if ($DryRun) { Write-Log ("[dry] POST agent_release {0}" -f $payload); return }
    try {
        Invoke-RestMethod -Method Post -Uri ($Config.testhub_base_url.TrimEnd('/') + '/ui-automation/midscene/devices/agent_release/') `
            -Headers @{ Authorization = ('Token ' + $Config.agent_token) } -ContentType 'application/json' -Body $payload -TimeoutSec 10 | Out-Null
        Write-Log '已在 TestHub 标记离线'
    } catch { Write-Log ("下线上报失败：{0}" -f $_.Exception.Message) 'WARN' }
}

# ------------------------- 主流程 -------------------------

function Invoke-EnsureOnce {
    param($Config, [string]$Udid, $State)

    $exe  = [string]$Config.ios_tool_path
    $port = [int]$Config.forward_port
    $tgt  = [int]$Config.wda_target_port

    # 1) 隧道（runwda 依赖它；注意 tunnel ls 的日志行里也可能出现 UDID，必须按数据结构判断）
    if ($DryRun) {
        Write-Log '[dry] 检查/启动隧道'
    } else {
        $tunnels = Invoke-Ios -Exe $exe -Arguments @('tunnel', 'ls')
        if (Test-TunnelUp -Output $tunnels -Udid $Udid) {
            Write-Log '隧道已在运行'
        } else {
            Write-Log '隧道未就绪，启动隧道 (ios tunnel start)'
            if (-not (Test-Alive ([int]$State.tunnel_pid))) {
                $State.tunnel_pid = Start-IosBackground -Exe $exe -Arguments @('tunnel', 'start') -Tag 'tunnel'
            }
            $deadline = (Get-Date).AddSeconds(30)
            $up = $false
            while ((Get-Date) -lt $deadline) {
                Start-Sleep -Seconds 2
                if (Test-TunnelUp -Output (Invoke-Ios -Exe $exe -Arguments @('tunnel', 'ls')) -Udid $Udid) { $up = $true; break }
            }
            if ($up) { Write-Log '隧道已就绪' } else { Write-Log '隧道 30s 内未就绪：后续 runwda 可能失败，可重跑或手动 ios tunnel start' 'WARN' }
        }
    }

    # 2) 开发者映像（幂等，go-ios 会自己判断是否已挂载）
    Write-Log '挂载开发者映像 (ios image auto)'
    Invoke-Ios -Exe $exe -Arguments @('--udid=' + $Udid, 'image', 'auto') | Out-Null

    # 3) WDA（假定已自行安装）
    #   签名可能变化 → 以设备上实际安装的 WDA 包名为准，避免 runwda 失败
    $bundleId = [string]$Config.wda_bundle_id
    $testRunnerId = [string]$Config.wda_testrunner_bundle_id
    if (-not $DryRun) {
        $installed = Get-InstalledWdaBundleId -Config $Config -Udid $Udid
        if ($installed -and ($installed -ne $bundleId -or $installed -ne $testRunnerId)) {
            Write-Log ("检测到设备上 WDA 实际包名为 {0}（配置里是 {1}），本次改用实际包名" -f $installed, $bundleId) 'WARN'
            $bundleId = $installed
            $testRunnerId = $installed
        }
    }
    if (-not (Test-Wda -Port $port) -and -not (Test-Alive $State.wda_pid)) {
        Write-Log '启动 WDA (ios runwda)'
        $State.wda_pid = Start-IosBackground -Exe $exe -Arguments @(
            '--udid=' + $Udid, 'runwda',
            '--bundleid=' + $bundleId,
            '--testrunnerbundleid=' + $testRunnerId,
            '--xctestconfig=' + [string]$Config.wda_xctest_config
        ) -Tag 'wda'
    }

    # 4) 端口转发
    if (-not (Test-PortListening -Port $port) -and -not (Test-Alive $State.forward_pid)) {
        Write-Log ("建立端口转发 (ios forward {0} {1})" -f $port, $tgt)
        $State.forward_pid = Start-IosBackground -Exe $exe -Arguments @('--udid=' + $Udid, 'forward', "$port", "$tgt") -Tag 'forward'
    }

    # 5) 等待 WDA 就绪
    if (-not $DryRun) {
        $deadline = (Get-Date).AddSeconds(60)
        while ((Get-Date) -lt $deadline) {
            if (Test-Wda -Port $port) { break }
            Start-Sleep -Seconds 2
        }
    }
    return $State
}

function Invoke-Agent {
    $Config = Read-Config -Path $ConfigPath
    $warn = @()
    foreach ($key in @('testhub_base_url', 'agent_token', 'ios_tool_path', 'wda_bundle_id', 'wda_testrunner_bundle_id', 'wda_xctest_config')) {
        if (-not $Config.$key) { $warn += $key }
    }
    if ($warn.Count -gt 0) { throw ("配置缺少必填项：{0}（见 agent.config.example.json）" -f ($warn -join ', ')) }
    # 相对路径按脚本目录解析（整包拷给同事时可直接写 tools\go-ios-win\ios.exe）
    if ($Config.ios_tool_path -and -not [System.IO.Path]::IsPathRooted([string]$Config.ios_tool_path)) {
        $Config.ios_tool_path = Join-Path $ScriptDir ([string]$Config.ios_tool_path)
    }
    if (-not (Test-Path -LiteralPath ([string]$Config.ios_tool_path))) { throw ("找不到 go-ios：{0}" -f $Config.ios_tool_path) }

    # 避免系统代理拦截本机/局域网 HTTP（WDA 探测、TestHub 上报）
    if (-not $Config.use_proxy) {
        try { [System.Net.WebRequest]::DefaultWebProxy = $null } catch { }
    }

    $State = Load-State
    if (-not $State) { $State = [pscustomobject]@{ tunnel_pid = 0; wda_pid = 0; forward_pid = 0; udid = '' } }

    # ---- stop 模式 ----
    if ($Mode -eq 'stop') {
        Write-Log '停止 agent：结束后台进程 + 清理端口暴露 + 上报离线'
        Stop-Alive ([int]$State.wda_pid)
        Stop-Alive ([int]$State.forward_pid)
        Stop-Alive ([int]$State.tunnel_pid)
        if ($Config.share_on_lan -and $State.udid) { Remove-PortShare -Port ([int]$Config.forward_port) }
        if ($State.udid) { Send-Release -Config $Config -Udid ([string]$State.udid) }
        Save-State ([pscustomobject]@{ tunnel_pid = 0; wda_pid = 0; forward_pid = 0; udid = '' })
        return
    }

    # ---- start / watch ----
    $Udid = Get-Udid -Config $Config
    if (-not $Udid) { throw '未能解析设备 UDID' }
    $State.udid = $Udid
    Write-Log ("目标设备 UDID = {0}" -f $Udid)

    $State = Invoke-EnsureOnce -Config $Config -Udid $Udid -State $State
    Save-State $State

    $wdaHost = '127.0.0.1:' + [string]$Config.forward_port
    if ($Config.share_on_lan) {
        if (Ensure-PortShare -Port ([int]$Config.forward_port)) {
            $lanIp = Get-LanIp -TesthubBaseUrl ([string]$Config.testhub_base_url)
            if ($lanIp) { $wdaHost = ('{0}:{1}' -f $lanIp, [string]$Config.forward_port) }
        }
    }

    $iosVersion = Get-IosVersion -Config $Config -Udid $Udid
    $wdaOk = if ($DryRun) { $true } else { Test-Wda -Port ([int]$Config.forward_port) }
    if (-not $wdaOk) {
        Write-Log 'WDA 未就绪（/status 不通）：本次按 offline 上报，看护模式会继续重试' 'WARN'
    }
    Send-Report -Config $Config -Udid $Udid -WdaHost $wdaHost -IosVersion $iosVersion `
        -Status $(if ($wdaOk) { 'online' } else { 'offline' }) | Out-Null

    if ($Mode -eq 'start') {
        Write-Log ("一键启动完成。WDA = {0}（状态: {1}）" -f $wdaHost, $(if ($wdaOk) { '在线' } else { '未就绪' }))
        return
    }

    # ---- watch：健康检查 + 自愈 + 心跳 ----
    $interval = [int]($Config.heartbeat_seconds); if ($interval -le 0) { $interval = 30 }
    Write-Log ("进入看护循环，每 {0}s 心跳一次（Ctrl+C 退出）" -f $interval)
    while ($true) {
        Start-Sleep -Seconds $interval
        try {
            if (-not (Test-Wda -Port ([int]$Config.forward_port))) {
                Write-Log 'WDA 不可达，尝试自愈重启' 'WARN'
                Stop-Alive ([int]$State.wda_pid); $State.wda_pid = 0
                if (-not (Test-PortListening -Port ([int]$Config.forward_port))) {
                    Stop-Alive ([int]$State.forward_pid); $State.forward_pid = 0
                }
                $State = Invoke-EnsureOnce -Config $Config -Udid $Udid -State $State
                Save-State $State
            }
            $wdaNow = Test-Wda -Port ([int]$Config.forward_port)
            Send-Report -Config $Config -Udid $Udid -WdaHost $wdaHost -IosVersion $iosVersion `
                -Status $(if ($wdaNow) { 'online' } else { 'offline' }) | Out-Null
        } catch {
            Write-Log ("看护循环异常：{0}" -f $_.Exception.Message) 'WARN'
        }
    }
}

Invoke-Agent
