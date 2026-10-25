# AX7021 V3.0 + AN5642 双目人脸检测与测距工程

本工程使用 Vivado/Vitis 2023.1，目标器件为 AX7021 V3.0 上的 `xc7z020clg484-2`。当前工程包含 AN5642 两路 OV5640 采集、各自独立的 DDR 三帧缓存、并排 HDMI 预览、TinyFace INT8 HLS 加速核、最多 3 个人脸框及双目测距的 Zynq 裸机程序。

`main` 为当前双目版本；较早的单路版本可由历史提交 `e19c8d6` 找回，第二镜头单独显示版本保留在 `codex/camera2-bringup`。

## 当前人脸检测路线

当前可综合、可下载的实现采用 `training/outputs/tiny_face_field_v2_neg4x.pt` 导出的 **TinyFace INT8 HLS 加速核**。该模型从随机权值开始训练，使用 FDDB YOLO 数据和现场采集的 120 张人脸图、74 张无人背景图；背景负样本在训练时按 4 倍采样，未使用旧检查点继续训练。加速核输入为 160×120 灰度 UINT8，输出为 15×20×5 的 INT32 检测张量；权值和量化参数已经保存在 `hls/src/tiny_face_params.h`，构建后编译进 PL 端 ROM。训练数据和 `.pt` 检查点未提交到 Git，现有仓库可从参数头文件重建硬件，但不能仅凭仓库逐样本重跑当时的训练。两路摄像头分别写入 DDR；PS 从各路已完成帧执行 BGR888/BT.601 灰度和 8×6 块均值预处理，再运行 HLS 推理、匹配人脸并通过 AXI GPIO 更新视频叠加框。

`third_party/lpyolo/` 保留了 LPYOLO 4W4A 的 PC 端参考推理实验及模型来源说明；原始 ONNX 权值应从上游取得，未用于当前 AX7021 比特流。仓库中的 BIT、XSA 和 ELF 对应 TinyFace HLS 路线，二者不能混用。

## 当前数据通路

`AN5642 两路 OV5640 -> 两套 DVP 接收与异步 FIFO -> 两路 VDMA S2MM -> DDR 左/右独立三帧缓存 -> PS 合成并排预览 -> 第三路 VDMA MM2S -> 目标框叠加 -> HDMI OUT`

两路原始帧均为 1280×720、RGB888。HDMI 输出为 1280×720：两路预览各等比例缩小到 640×360，左右并排且上下留黑边；缩小仅影响预览，推理和标定使用原始帧。具体连接见 `docs/stereo_architecture.md`。

PL 端的 AXI4-Stream 多目标框和字符叠加模块最多显示 3 张人脸。PS 对两路原始帧分别推理，匹配同一张脸后依据双目标定参数估计距离；串口 `source=stereo` 表示双目结果，`source=fallback` 表示匹配不可靠时改用框高估算。绿框旁显示 `PEOPLE x.xM`。已完成 20 对棋盘格的离线标定及板端链路验证；绝对测距误差仍需在已知距离处实测，不应把串口距离值视为已验证精度。

## 关键文件

- Vivado 工程：`Vivado/ov5640_single/ov5640_single.xpr`
- 完整重建入口：`Vivado/auto_create_project/create_project.bat`
- 工程创建脚本：`Vivado/auto_create_project/create_project.tcl`
- PS/PL 配置：`Vivado/auto_create_project/ps_config.tcl`、`pl_config.tcl`
- 板卡约束：`Vivado/auto_create_project/src/constraints/`
- OV5640 自定义 IP：`Vivado/auto_create_project/my_ip/ov5640_ip/`
- 比特流：`Vivado/design_1_wrapper.bit`
- 含比特流的硬件平台：`Vitis/design_1_wrapper.xsa`
- Vitis/BSP/应用一键构建：`Vitis/build_all.bat`
- 裸机应用 ELF：`Vitis/manual_build/an5642_single.elf`
- JTAG 识别检查：`Vitis/check_jtag.bat`
- BIT 和 ELF 下载运行：`Vitis/run_jtag.bat`
- 框叠加 RTL 自检仿真：`Vivado/auto_create_project/run_bbox_overlay_sim.bat`
- DDR 完整帧采集：`Vitis/capture_frame.bat`
- TinyFace HLS 源码、测试平台和已打包 IP：`hls/`
- 训练、评估和 INT8 校准工具：`training/`
- 双目标定与图像对采集：`stereo/README.md`
- 板端双目标定常量：`Vitis/auto_create_vitis/src/an5642_single/stereo_calibration_params.h`
- 双路架构：`docs/stereo_architecture.md`
- LPYOLO 模型与 PC 端参考实验：`third_party/lpyolo/`
- 人脸检测加速器结构：`docs/face_detector_architecture.md`
- 验证报告：`Vivado/reports/`

## 参赛资料与目录对照

本仓库保留了 Vivado/Vitis 工程原有目录，以免改名后破坏 Block Design、脚本或 Windows 工具路径。与选题指南的推荐结构对应如下：

| 指南目录 | 本仓库位置 |
| --- | --- |
| src/ | Vivado/auto_create_project/src/、hls/src/、Vitis/auto_create_vitis/src/ |
| sim/ | hls/tb/、Vivado/auto_create_project/run_bbox_overlay_sim.bat |
| build/ | hls/build_hls.bat、Vivado/auto_create_project/、Vitis/build_all.bat、Vivado/reports/ |
| board/ | Vivado/design_1_wrapper.bit、Vitis/design_1_wrapper.xsa、Vitis/manual_build/an5642_single.elf、Vitis/run_jtag.bat |
| data/ | hls/tb/test_vector.h；现场人脸图像与棋盘格原始图像对未公开 |
| skill/ | skill/README.md |
| report/ | report/README.md |

当前项目路径继承了部分 Vivado/Vitis 和厂商资料的大小写命名，尚未完全满足指南对仓库文件名小写的要求；直接批量重命名会使现有工程引用失效。参赛审阅应以本表和构建步骤定位文件。根目录 MIT 许可仅覆盖本项目原创部分；第三方文件和历史模型的来源见 THIRD_PARTY_NOTICES.md。

## 从头生成 Vivado 工程

构建脚本目前按 Windows 上 `D:\Xilinx\Vivado\2023.1` 和 `D:\Xilinx\Vitis\2023.1` 编写。如果安装在其他位置，先修改相关 `.bat` 中的工具路径。以下命令从仓库根目录开始执行；源码本身无需放在原作者的用户目录。

在 Windows 命令提示符或 PowerShell 中执行：

```powershell
git clone https://github.com/zhouyuchen0916-boop/ax7021-v3-ov5640-hdmi.git
cd .\ax7021-v3-ov5640-hdmi
.\hls\build_hls.bat all

Push-Location .\Vivado\auto_create_project
.\create_project.bat
Pop-Location
```

第一条命令使用仓库中已提交的 INT8 参数头文件运行 C 仿真、HLS 综合并打包 `tiny_face_accel` IP，不需要下载训练检查点。随后 Vivado 脚本会创建 Block Design、综合、实现、生成比特流、生成验证报告，并导出包含比特流的 XSA。HLS 成功标志为 `HLS_CSIM_MISMATCHES=0`，Vivado 成功标志为日志中的 `BUILD_OK`。

只修改约束且已有工程时，可执行：

```powershell
.\Vivado\auto_create_project\rebuild_constraints.bat
```

成功标志为 `REBUILD_OK`。

## 构建裸机程序

回到仓库根目录后，在 PowerShell 中执行：

```powershell
.\Vitis\build_all.bat
```

首次执行会从 XSA 创建 Vitis standalone 平台并编译 BSP，通常需要几分钟；随后使用 Vitis 2023.1 自带的 `arm-none-eabi-gcc` 构建应用。若重新生成了 XSA，先执行 `Vitis/auto_create_vitis/update_platform.bat` 更新现有平台，再执行 `Vitis/build_all.bat`。也可以删除生成目录 `Vitis/design_1_wrapper` 后直接运行 `build_all.bat` 完整重建。应用源码位于 `Vitis/auto_create_vitis/src/an5642_single`，可只执行 `Vitis/manual_build/build.bat` 快速重编应用。

裸 JTAG 启动不会执行 FSBL，因此应用在 `main()` 开始处调用 `XTime_SetTime(0)` 启动 SCU 全局定时器；否则 standalone 的 `usleep()` 会一直等待。三帧 1280×720 RGB888 缓存放在链接脚本的 `.noinit` 区，并在其上方预留启动栈保护区，避免 C 运行库清零 BSS 时覆盖 Cortex-A9 异常栈。

脚本临时使用 `P:`/`Q:` 映射工程根目录，以缩短 Xilinx 工具路径；源文件和输出仍保存在本工程目录中。运行前应确保这两个盘符未被其他设备占用。

## 实板连接与运行

断电连接以下设备：

1. AN5642 双目 OV5640 模组接 AX7021 V3.0 的 `J16`，当前工程同时使用两路镜头。
2. 板卡 `HDMI OUT` 接显示器，或接 USB HDMI 采集卡后再接电脑。普通笔记本 HDMI 口通常只能输出，不能直接作为 HDMI 输入。
3. 板卡 UART 接电脑，串口终端设置为 `115200、8N1、无流控`。
4. 板卡 JTAG 接电脑，接入电源并开机。

先检查 JTAG：

```powershell
.\Vitis\check_jtag.bat
```

输出的 `JTAG_TARGETS_BEGIN` 与 `JTAG_TARGETS_END` 之间应出现 Zynq 和 ARM Cortex-A9 目标。然后保持串口终端打开，执行：

```powershell
.\Vitis\run_jtag.bat
```

程序依次下载 `Vivado/design_1_wrapper.bit` 和 `Vitis/manual_build/an5642_single.elf`。正常串口输出应包含：

```text
AX7021 AN5642 dual-camera capture demo start
PS I2C0 camera1/HDMI ready at 40 kHz
PS I2C1 camera2 ready at 40 kHz
BBOX overlay: 3 faces, calibrated stereo distance labels enabled
OV5640 camera1 chip ID: 0x5640
OV5640 camera2 chip ID: 0x5640
VDMA errors after clear: camera1=0x0 camera2=0x0
CAMERA1_FRAME_SYNC_READY: seen=0x7 current=f0 errors=0x0
CAMERA2_FRAME_SYNC_READY: seen=0x7 current=f0 errors=0x0
DUAL CAPTURE RUNNING: camera1 + camera2 -> independent DDR rings
STEREO PREVIEW: camera1 left | camera2 right, 640x360 each, aspect ratio preserved
FACE0[f1]: (...) score=... distance=... source=stereo
```

两路都读到 `OV5640 ... chip ID: 0x5640`，才能确认两只摄像头的供电、复位和 SCCB/I²C 通信已建立；HDMI 预览左右均有实时画面，才能确认双路采集和显示链路。`source=stereo` 证明程序采用双目配对计算了距离，但测距精度仍需对照卷尺实测。

## 历史单路构建验证

以下记录属于 2026-10-12 的单路多人检测基线，不代表当前双路版本的资源、时序或文件哈希。当前双路设计应以 `Vivado/reports/` 中最新报告以及本分支的 BIT、XSA、ELF 为准。

- 实现和比特流生成：成功，0 Error
- 框叠加 RTL 自检仿真：通过，输出 `BBOX_SIM_PASS`
- HLS C 仿真：1500 个输出全部匹配，最大误差 0
- HLS 综合：估算延迟 4247755 周期，100 MHz 下约 42.48 ms
- 时序：WNS `+0.407 ns`，TNS `0 ns`，WHS `+0.030 ns`，THS `0 ns`
- 布线：0 条失败网络，0 条未布线网络
- CDC：摄像头像素数据由 XPM 异步 FIFO 跨域；报告中的 1 条 `CDC-6` 位于 VTC，2 条 `CDC-15` 位于 AXI Clock Converter 内部
- 资源：14106 LUT、19898 FF、57 RAMB36、12 RAMB18、39 DSP
- BIT SHA-256：`C55B6CF1149CB2DB7559A45F339ED11AF100A49353B54A0201EBBE2BF16169C3`
- XSA SHA-256：`72970C56F92C3B80B8D7834D51AF5C767B48EA8B80CC845BAD45F20FF1EE09D7`
- Vitis standalone BSP：成功构建，stdin/stdout 均为 `ps7_uart_1`
- 裸机应用：成功构建，0 编译错误、0 编译警告；ELF32 ARM hard-float，入口地址 `0x00100000`
- ELF 代码/数据/BSS 统计：64896 B / 2676 B / 8479680 B；三帧缓存位于 `.noinit`
- ELF SHA-256：`7F1E072B2DEC87E824C1C10C5574FF92D507E6144A0C677044710056DD131F89`
- 实采帧预处理对比：旧单点等权灰度与训练输入 MAE 为 `0.021849`；BGR BT.601 加权灰度加 8×6 块均值后为 `0.002575`
- 2026-10-11 实板帧同步验证：摄像头桥稳定等待结束后清除一次启动期 `0x810` 锁存，随后三帧自检为 `seen=0x7`、`errors=0x0`；推理循环按真实帧边界依次出现 `writing=f1/f0/f2`，始终读取刚完成的上一帧。连续四次同一人脸检测框约为 `(274–277,49–52)-(683–686,381–384)`，置信度为 `0.931–0.938`。

## 仓库内容与提交范围

仓库保留可复用的 RTL、AXI 外设配置、板卡约束、自定义 OV5640 IP、Vivado/Vitis Tcl 与批处理脚本，以及当前已经验证过的 BIT、XSA 和 ELF。Vivado 的综合/实现缓存、Vitis 生成的平台和 BSP 工作区、临时日志均由 `.gitignore` 排除；在另一台电脑上可按上面的命令重新生成这些目录。建议先运行 Vivado 重建脚本，再运行 `Vitis/build_all.bat`，最后连接 JTAG 和串口进行实板验证。

目录结构如下：

```text
Vivado/                 Vivado 工程、Block Design、IP、约束、报告和比特流
Vitis/                  平台导出、裸机应用源码、构建脚本、XSA 和 ELF
hls/                    TinyFace HLS 源码、参数、测试平台及构建脚本
training/               模型训练、评估、INT8 导出脚本；不含现场图像和检查点
stereo/                 双目标定、采集与板端参数生成脚本
docs/                   检测器和双路视频架构说明
third_party/lpyolo/     未集成到当前板端程序的 LPYOLO 参考实验
Bootimage/              历史 BOOT.BIN 快照；当前双目版建议用 JTAG 下载 BIT 和 ELF
skill/                  可复用的联调与验证清单
report/                 设计说明、证据索引和未完成测量边界
README.md               构建、接线、验证边界和运行说明
```

## 已知警告与验证边界

- 两路 OV5640 PCLK 分别位于板卡固定引脚 AB9 和 Y11，均非专用时钟引脚，因此保留 `CLOCK_DEDICATED_ROUTE FALSE` 和 `PLCK-12` 警告。内部时序报告不能替代长期画面稳定性实测。
- OV5640 的 10 位数据、HREF、VSYNC 尚未加入板级 `set_input_delay`。准确数值依赖摄像头寄存器配置、模组和 PCB 走线，不能仅凭参考工程臆造。
- `CDC-6` 位于 AMD Video Timing Controller 自带的 AXI-Lite 多位 CDC 逻辑；两条 `CDC-15` 位于自动生成的 AXI Clock Converter，摄像头自定义 CDC 已修正。
- 其余 `PDCN-1569`、`RTSTAT-10`、`LUTAR-1`、`PDRC-190` 指向 AMD 调试核或 AXI/IP 内部逻辑，没有阻止比特流生成。
- 2026-10-06 实板验证：JTAG 链枚举出 Digilent JTAG-HS1、ARM Cortex-A9 和 `xc7z020`；AX7021 的 CP210x UART 枚举为 COM3，串口 115200 8N1 输出了 `OV5640 chip ID: 0x5640`、`OV5640 configured for 1280x720 RGB output` 和 `VIDEO RUNNING: camera -> DDR -> HDMI, 1280x720`。异常地址保持为 0，诊断阶段为 0x900。
- JTAG 读取帧缓存时，第二、第三帧缓存地址出现稳定的非零像素数据；这证明 OV5640→DVP→VDMA S2MM→DDR 正在写入。VDMA、VTC、动态时钟和两个复位 GPIO 均已读到运行态寄存器值。HDMI OUT 经 USB HDMI 采集卡接入电脑后，OBS 已显示实时摄像头画面，摄像头到 HDMI 的完整基础通路通过实板验证。
- 2026-10-07 固定绿色框版本已通过 JTAG 下载到实板。串口输出了 `BBOX overlay: (320,180)-(960,540)`、`OV5640 chip ID: 0x5640` 和 `VIDEO RUNNING: camera -> DDR -> HDMI, 1280x720`。JTAG 回读框控制寄存器得到 `0x41220000 = 0x83C00140`、`0x41220008 = 0x021C00B4`，分别对应使能位、X 坐标 320–960 和 Y 坐标 180–540；OBS 已确认绿色矩形框的位置、颜色和视频画面均正常。
- 2026-10-11 三帧 GenLock、新预处理和帧边界同步版本已通过实板串口验证。S2MM 使用标准 GenLock 主端，MM2S 使用延迟一帧的标准从端；启动时等待摄像头桥内部复位/FIFO 延时完成，再清除一次首帧锁存并要求三帧自检 `seen=0x7`。推理前等待当前写帧切换，随后读取刚完成的上一帧，串口已验证 `f0/f1/f2` 持续轮转且检测框坐标稳定。最终画面观感仍以 HDMI 采集卡上的 OBS 实时显示为准。
- 2026-10-11 检测框时序滤波版本已通过 JTAG 下载。启动阶段不再显示固定测试框；候选框需要连续 4 次、相邻 IoU 不低于 0.45、平均置信度不低于 0.93 才显示。已显示的框采用 3:1 坐标低通滤波，并允许短暂丢失 5 次，以减少框的闪烁和尺寸跳变。JTAG 连续读取 30 组框控制寄存器期间使能位保持稳定。当前 FDDB 验证集在 IoU 0.5 下最佳 F1 约为 0.51，若现场仍有稳定误检或框尺寸系统性偏差，需要增加同一摄像头采集的无人负样本及人脸框标注后重新训练，而不是继续依赖后处理掩盖模型误差。
- 2026-10-11 现场数据增强版本已完成训练、INT8 标定、HLS C 仿真、综合实现和 JTAG 下载。现场集包含 120 张人脸图（148 个框）和 74 张无人背景图；最终模型对背景图的离线误检由旧模型的 5/74 降至 1/74（阈值 0.94），FDDB 验证集 IoU 0.5 下最佳 F1 为 0.626。HLS C 仿真 1500 个输出全部匹配。下载后串口持续输出三缓冲轮转的 `FACE[f0/f1/f2]: none`，已确认无脸场景下主循环和推理持续运行；现场有脸画面的框位置与稳定性仍以 HDMI 采集卡上的 OBS 实时观察为准。
- 2026-10-12 多人框和距离标注版本已完成行为仿真、Vitis 编译、Vivado 综合实现与比特流生成。检测器最多输出 3 个经 NMS 筛选的候选框，3 个独立跟踪器分别驱动 3 组 AXI GPIO；叠加器采用三级 AXI4-Stream 流水线绘制绿框和 `PEOPLE x.xM` 字符。行为仿真输出 `BBOX_SIM_PASS`，最终 WNS 为 `+0.407 ns`。距离是按框高估算的演示值，仍需在实板已知距离处校准；多人框数量、位置和标签显示仍以本版本下载后 OBS 实时画面为准。
- 2026-10-13 多人框和距离标注版本已通过 JTAG 下载到实板。串口确认 `OV5640 chip ID: 0x5640`、三帧自检 `seen=0x7`、清除启动锁存后 VDMA 错误为 `0x0`，并输出 `BBOX overlay: 3 faces, PEOPLE distance labels enabled`。持续运行时同一帧同时输出 `FACE0` 和 `FACE1`，两个候选均包含坐标、置信度和距离值，证明多目标解码、跟踪及距离计算已在实板运行。绿框和字符的最终位置、清晰度及遮挡关系以 HDMI 采集卡上的 OBS 画面确认。
- 2026-10-15 第二镜头单路版本已完成 Vivado/Vitis 构建并通过 JTAG/UART 实板启动。正式时序报告为 WNS `+0.042 ns`、TNS `0 ns`、WHS `+0.022 ns`、THS `0 ns`，布线无失败网络。串口确认 `PS I2C1 camera2 ready at 40 kHz`、`OV5640 camera2 chip ID: 0x5640`、`FRAME_SYNC_READY: seen=0x7 current=f0 errors=0x0` 和 `VIDEO RUNNING: camera2 -> 3-frame GenLock DDR -> HDMI, 1280x720`；推理循环持续轮转 `f0/f1/f2`。第二路 PCLK 固定在非 CCIO 引脚 Y11，因此保留 `CLOCK_DEDICATED_ROUTE FALSE` 和 `PLCK-12` 警告；时序已经收敛，画面长期稳定性仍以 HDMI 采集卡实测为准。

## 当前双路版本验证边界

- 已完成 20 对有效棋盘格标定，双目 RMS `0.6420 px`，计算基线 `40.239 mm`；标定参数已写入 `stereo_calibration_params.h`。详见 `stereo/README.md`。
- 实板串口已出现双路摄像头识别、独立 DDR 环形缓存轮转及 `source=stereo` 的测距输出；这确认链路运行，不等于绝对测距精度已达标。
- 当前 `Vivado/reports/timing_summary.rpt` 中 WNS 为 `+0.294 ns`、TNS 为 `0 ns`。单路基线的资源占用和哈希不得直接当作本双路版本的指标。
- 现场人脸图像、训练检查点、棋盘格原始图像对和生成的标定 JSON 未提交仓库；已提交 INT8 参数头文件与板端标定头文件，工程可用这些参数构建，但完整训练和重新标定需要重新采集数据。

## 第二镜头分支恢复方法

若需要恢复原单镜头稳定版本，可在停止 Vivado/Vitis 构建并保存未提交修改后，从历史提交 `e19c8d6` 建立单独的恢复分支，再重新下载对应 BIT 和 ELF。不要在当前工作目录直接切换旧提交，以免覆盖未提交的改动。

```powershell
git switch -c restore-single-camera e19c8d6
.\Vitis\run_jtag.bat
```

切换 Git 分支只恢复本地文件，不会自动改变 FPGA 中已经下载的程序；必须再次执行 `run_jtag.bat`，才会把该提交保存的 BIT 和 ELF 下载到板卡。
