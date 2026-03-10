# Overleaves Windows 打包脚本
# 用法：在项目根目录执行 .\build.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Write-Host "===== Overleaves Windows 打包脚本 =====" -ForegroundColor Cyan

# 1. 检查依赖
Write-Host "`n[1/3] 检查并安装依赖..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Error "依赖安装失败，请检查 requirements.txt"
    exit 1
}

# 2. 清理旧的构建产物
Write-Host "[2/3] 清理旧构建产物..." -ForegroundColor Yellow
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }

# 3. 执行 PyInstaller 打包
Write-Host "[3/3] 执行 PyInstaller 打包..." -ForegroundColor Yellow
pyinstaller overleaves.spec --noconfirm

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller 打包失败"
    exit 1
}

# 完成
if (Test-Path "dist\overleaves.exe") {
    $size = [math]::Round((Get-Item "dist\overleaves.exe").Length / 1MB, 1)
    Write-Host "`n===== 打包成功！=====" -ForegroundColor Green
    Write-Host "输出文件：dist\overleaves.exe（${size} MB）" -ForegroundColor Green
} else {
    Write-Error "未找到 dist\overleaves.exe，打包可能失败"
    exit 1
}
