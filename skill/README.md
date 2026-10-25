# Zynq 双路摄像头到 HDMI 联调清单

## 适用范围

面向 Zynq-7000、两路并行 DVP 摄像头、AXI VDMA、DDR 帧缓存及 HDMI 输出的裸机工程。这里的实例使用 AX7021 V3.0、AN5642、Vivado/Vitis 2023.1；具体引脚、时钟和寄存器地址不能直接套到其他板卡。它是从本项目的故障与修复中提炼的排查流程，并非适用于所有摄像头的自动配置工具。

## 使用方法

按下列顺序验证，每一步通过后再进入下一步。构建和下载命令见根目录 README.md。

1. JTAG 与串口：运行 Vitis/check_jtag.bat，确认目标列表含 Zynq/ARM；串口设置为 115200、8N1。目标列表为空时先核对板卡电源、启动开关、下载线与驱动，不要把串口口当 JTAG。
2. 两只传感器：下载后要求串口分别打印 OV5640 camera1 chip ID: 0x5640 和 OV5640 camera2 chip ID: 0x5640。若只识别一路，先检查该路电源、复位、SCCB/I²C 和 J16 排线，再检查视频像素流。
3. 帧缓存：要求两路 CAMERA*_FRAME_SYNC_READY 的 seen=0x7，清除启动期锁存后 VDMA 错误为 0x0。读帧必须选刚完成的缓冲区，避免在写入中的帧上推理；不要仅凭一个非零 DDR 地址判断视频已稳定。
4. 显示与预处理：遮挡任一镜头时仅对应的预览半幅变化；原始推理帧保持 1280×720。颜色通道和灰度缩小方式应与训练一致；本工程使用 BGR888、BT.601 加权灰度与 8×6 块均值。
5. 检测与双目测距：无脸场景观察 FACE[...] none；有人脸时核对框坐标和 source。source=stereo 只证明双目配对路径已执行，不能替代已知距离处的误差测试；source=fallback 表示当次回退为框高估计。
6. 时序与复现：重新生成比特流后检查 Vivado/reports/timing_summary.rpt、drc.rpt 和 cdc.rpt；确认版本、器件和脚本路径匹配，再按顺序重建 HLS、Vivado、Vitis。

## 本项目验证过的现象

- 早期画面与人脸框错位时，改为按真实 VDMA 帧边界读取上一张完整帧，并使预处理与训练一致；对应代码见 Vitis/auto_create_vitis/src/an5642_single/display_demo.c。
- 摄像头像素时钟跨到视频 AXI 时钟域时，使用异步 FIFO 处理数据；对应自定义接收 IP 见 Vivado/auto_create_project/my_ip/ov5640_ip/。
- 棋盘格图像必须在左右两路均识别出完整角点后才加入标定；采集与拒收流程见 stereo/collect_calibration_pairs.ps1 和 stereo/validate_pair.py。

## 失效条件

本清单不提供板级引脚自动迁移、未知摄像头寄存器配置、训练数据授权或测距精度保证。更换板卡、镜头、分辨率或时钟后，必须重新核对 XDC、采集时序、相机内参及双目基线。HLS 综合估算延迟也不是整机实测帧率。
