# 学生建筑绘图作业自动分析器

把学生提交的平面、剖面、立面、总平面或节点图交给视觉模型分析，自动生成：

- 无黑色控制台的 Windows 图形界面；
- 天津大学建筑学院与智绘小屋品牌界面；
- 启动时自动检测 OpenAI 网络，并识别系统代理和常见本机代理端口；
- 带红框/蓝框和编号的标注图；
- 图纸下方逐条对应问题、可见依据和修改建议的检查完毕长图；
- 可继续编辑的 `analysis.json`；
- 教师可阅读的 Markdown 与 HTML 报告；
- 可选的同类型本地参考案例推荐；
- 批处理汇总页 `index.html`。

红色表示可由图面直接核验的绘图错误，蓝色表示表达质量不足。完整边界见 [rubric.md](rubric.md)。

## 安装

```powershell
cd C:\Users\Administrator\Documents\战术战略讨论\student_drawing_analyzer
python -m pip install -r requirements.txt
```

`Pillow` 用于读图和画标注。处理 PDF 时还需要 `PyMuPDF`；当前 `requirements.txt` 已一并列出。

## 设置 API 密钥

EXE 版本在窗口右上角点击“密钥设置”，只需配置一次。程序使用 Windows DPAPI 按当前 Windows 用户加密，保存到 `%LOCALAPPDATA%\StudentDrawingAnalyzer\openai_api_key.bin`。其他 Windows 用户或把该文件复制到其他电脑后无法直接解密；清除密钥也在同一设置窗口完成。

源码版本也可以只使用当前 PowerShell 会话的环境变量：

```powershell
$env:OPENAI_API_KEY = "你的密钥"
```

密钥不会写入报告、源码或 EXE。学生图纸会作为图像输入发送到 OpenAI API；涉及未公开作业时，请先确认学校的数据使用要求。

## 使用

双击 `学生绘图作业分析器.exe` 会直接打开图形界面，不再出现黑色控制台。点击“选择图纸”后，程序自动分析并在右侧显示检查结果。也可以把单张图片直接拖到 EXE 图标上启动。

窗口右上角会显示网络状态。VPN 已开启系统代理时，程序会自动使用该代理；当前机器已验证可自动识别 LetsVPN 的 `127.0.0.1:10818`。如果显示“VPN 未连接”，连接 VPN 后点击“重新检测”，无需重启程序。

完成后，程序会在原图旁生成 `原文件名_检查完毕.png`。该图片上方是标框图，下方按 `R/B` 编号列出问题、可见依据和修改建议；同时保留完整的 JSON、Markdown 和 HTML 报告。

新版对每张图执行“问题识别 + 位置精修”两步视觉分析。第二步只收紧问题框，不新增或改写问题；如果精修框比原框更大，程序会拒绝采用。每张图因此会比旧版多一次 API 请求。

图形界面右上角提供一次性的“密钥设置”。已经在本机保存过密钥时，不需要再次输入。

批量图片、PDF 和命令行参数仍可通过源码脚本 `analyze_drawings.py` 使用。

也可以在 PowerShell 中使用完整参数：

分析单张图：

```powershell
python analyze_drawings.py .\作业\学生01.png
```

批量分析目录（递归查找图片和 PDF）：

```powershell
python analyze_drawings.py .\作业 -o .\批改结果
```

接入此前下载的案例库：

```powershell
python analyze_drawings.py .\作业 `
  --manifest C:\path\to\arch_drawings\output\manifest.jsonl `
  --max-references 3
```

模型默认是 `gpt-5.2`，可用 `--model` 或环境变量 `OPENAI_MODEL` 修改：

```powershell
python analyze_drawings.py .\作业\学生01.png --model gpt-5.2
```

需要手动指定代理时：

```powershell
python analyze_drawings.py .\作业\学生01.png --proxy http://127.0.0.1:7890
```

PDF 默认逐页分析。可用 `--pdf-dpi 220` 提高清晰度，也可用 `--max-pdf-pages 10` 限制每份 PDF 页数。

## 人工复核后重新出图

第一次分析后，可以直接修改输出目录中的 `analysis.json`，再用本地模式重新生成标注和报告，不会再次调用 API：

```powershell
python analyze_drawings.py .\作业\学生01.png `
  --analysis-json .\批改结果\学生01\analysis.json `
  -o .\复核结果
```

也可以先用仓库自带的 `example_analysis.json` 验证本地出图链路：

```powershell
python analyze_drawings.py .\任意测试图片.png `
  --analysis-json .\example_analysis.json `
  -o .\本地验证结果
```

## 输出目录

每张图或每个 PDF 页面都有独立子目录：

```text
批改结果/
  index.html
  学生01/
    source.png
    annotated.png
    checked.png
    analysis.json
    report.md
    report.html
```

脚本保留原图副本，所有坐标使用相对于原图的 `0-1000` 归一化坐标。自动分析存在误判可能，特别是低清晰度扫描件、手写尺寸和缺少上下文的局部图；正式评分前应由教师复核。

## 测试

```powershell
python -m unittest discover -s tests -v
python -m py_compile analyze_drawings.py
```
