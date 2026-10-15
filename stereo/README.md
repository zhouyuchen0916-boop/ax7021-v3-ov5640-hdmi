# AN5642 双目标定

当前板上程序保持运行，无需重新综合。采集脚本通过 JTAG 暂停 ARM，停止两路写 VDMA，分别读取两路上一张完整的 1280x720 帧，然后恢复 VDMA 和 ARM。每次采集会让 HDMI 画面暂停约 20-30 秒，完成后自动恢复。

## 1. 准备棋盘格

推荐使用 **9 列 x 6 行内角点**、单格边长 **25 mm** 的平面棋盘格。打印时必须保持 100% 比例并用直尺测量实际格长；如果不是 25 mm，运行标定时传入实际值。

工程已生成可直接打印的 `output/pdf/an5642_checkerboard_9x6_25mm_a4_landscape.pdf`。打印设置选择 A4 横向、实际大小或 100%，关闭“适合页面/缩放页面”。打印后把纸平整贴到硬质平板上，并确认单格实测为 25 mm。

需要重新生成 PDF 时运行：

```powershell
D:\Python\python.exe .\stereo\generate_checkerboard_pdf.py
```

## 2. 采集图片对

板卡电源、JTAG、UART 和 HDMI 保持连接，当前双路程序保持运行。在项目根目录执行：

```powershell
.\stereo\capture_pair.bat
```

成功后生成同名文件：

```text
stereo/pairs/left/pair_YYYYMMDD_HHMMSS.png
stereo/pairs/right/pair_YYYYMMDD_HHMMSS.png
```

采集至少 20 对，棋盘格需覆盖画面中央、四角、近处、远处和不同倾角。每一对中两只镜头都必须看到完整棋盘格，且画面不能模糊。相邻采集之间先移动棋盘格，再执行一次脚本。

也可以运行交互式连续采集程序。它会从现有编号继续，检查左右两边是否都识别到 54 个角点，并在达到 20 对时结束：

```powershell
powershell -ExecutionPolicy Bypass -File .\stereo\collect_calibration_pairs.ps1 -Target 20
```

每次摆好棋盘格后按回车。无效图片会移动到 `stereo/pairs/rejected`，不会进入正式标定；按 `Q` 后回车可随时退出，下次运行会从现有有效编号继续。

## 3. 标定

默认参数是 9x6 内角点、25 mm 格长：

```powershell
D:\Python\python.exe .\stereo\calibrate_stereo.py
```

若实际格长为 20 mm：

```powershell
D:\Python\python.exe .\stereo\calibrate_stereo.py --square-mm 20
```

成功输出：

```text
stereo/output/stereo_calibration.json
stereo/output/stereo_calibration.npz
stereo/output/detections/*_left.jpg
stereo/output/detections/*_right.jpg
```

`baseline_mm` 应与模组实际镜头间距同量级，`stereo_rms` 越小越好。正式测距前还要用校正图检查同一特征点是否位于近似相同的水平行。

## 4. 生成板端参数并编译

把标定结果转换为裸机程序使用的 C 常量：

```powershell
D:\Python\python.exe .\stereo\generate_runtime_params.py `
  --calibration .\stereo\output\stereo_calibration.json `
  --output .\Vitis\auto_create_vitis\src\an5642_single\stereo_calibration_params.h
```

然后编译并通过 JTAG 下载：

```powershell
cd .\Vitis\manual_build
.\build.bat
cd ..
.\run_jtag.bat
```

串口输出中的 `source=stereo` 表示左右人脸已经配对并使用标定后的视差测距；`source=fallback` 表示本次没有得到可信双目配对，暂时使用人脸框高度估算。板端对双目结果执行连续 3 次确认、5 点中值和单目尺度合理性检查，以抑制检测框中心抖动。

## 5. 本次标定结果

- 有效棋盘格图像对：20
- 左相机重投影 RMS：0.6083 px
- 右相机重投影 RMS：0.5892 px
- 双目标定 RMS：0.6420 px
- 计算基线：40.239 mm
- 校正后纵向误差：平均绝对值 0.257 px，RMS 0.385 px，95% 分位 0.844 px

硬件串口已出现 `source=stereo`，证明双路采集、双路人脸检测、标定点校正和视差换算链路已经连通。距离是基于两路人脸框中心的近似值，最终精度仍应在 0.5 m、1.0 m、1.5 m 等已知距离处用直尺或卷尺复核。
