# AX7021 V3.0 + AN5642 单路 OV5640 到 HDMI 基础工程

本工程使用 Vivado/Vitis 2023.1，目标器件为 AX7021 V3.0 上的 `xc7z020clg484-2`。当前阶段已完成单路 OV5640 采集、DDR 帧缓存、HDMI 输出、TinyFace INT8 HLS 加速核和 Zynq 裸机控制程序。

> `codex/camera2-bringup` 分支说明：本分支把原单路处理链切换到 AN5642 的第二个 OV5640，使用第二路 DVP 引脚和 PS I2C1，保留 TinyFace 人脸检测、最多 3 个绿框及 `PEOPLE x.xM` 标签。当前仍是“第二镜头单路显示与检测”，尚未同时采集左右两路，也尚未进入双目标定和视差测距。原实板稳定版本保留在 `main` 分支的 `e19c8d6`。

## 当前人脸检测路线

当前可综合、可下载的实现采用 `training/outputs/tiny_face_field_v2_neg4x.pt` 导出的 **TinyFace INT8 HLS 加速核**。该模型从随机权值开始训练，使用本项目中的 FDDB YOLO 数据和现场采集的 120 张人脸图、74 张无人背景图；背景负样本在训练时按 4 倍采样，未使用旧检查点继续训练。加速核输入为 160×120 灰度 UINT8，输出为 15×20×5 的 INT32 检测张量；权值和量化参数编译进 PL 端 ROM。摄像头写 VDMA 与 HDMI 读 VDMA 采用三个共享 DDR 帧缓存和 GenLock，显示从端比摄像头写主端延迟一帧，PS 同时读取当前写帧的上一帧；预处理按实测的 BGR888 字节顺序执行 BT.601 加权灰度，并对每个 8×6 像素块取均值缩小到 160×120，再启动 HLS 核、解码输出并通过 AXI GPIO 更新视频叠加框。

`third_party/lpyolo/` 保留了 LPYOLO 4W4A 的 ONNX 与 PC 端参考推理实验，但 FINN 版本尚未集成到当前 AX7021 比特流。仓库中的 BIT、XSA 和 ELF 对应 TinyFace HLS 路线，二者不能混用。

## 当前数据通路

`AN5642/J16 单路 OV5640 -> DVP 接收 -> XPM 异步 FIFO -> AXI4-Stream -> VDMA S2MM GenLock 主端 -> DDR 三帧循环缓存 -> VDMA MM2S 延迟一帧从端/HDMI 与 PS 最近完整帧推理 -> TinyFace HLS/DDR -> PS 解码坐标 -> AXI GPIO -> 目标框叠加 -> VTC/视频输出 -> HDMI OUT`

视频软件配置源文件采用 1280×720、RGB888。当前只接入 AN5642 的一个摄像头通道；尚未规定它在双目模组上对应左镜头还是右镜头，接板后以实际画面确认。

当前 PL 端加入了 AXI4-Stream 多目标框和字符叠加模块，最多同时显示 3 张人脸。PS 将检测候选按置信度排序并执行 IoU 0.35 的 NMS，再用 3 个独立跟踪器分别稳定各张人脸的位置；没有检测到人脸或推理出错时关闭相应框。每个绿框旁显示 `PEOPLE x.xM`，距离由人脸框高度按 `距离(分米)≈2100/框高(像素)` 估算，并限制在 0.3–9.9 m。该距离只用于现场演示，摄像头焦距、人员头部大小和姿态都会造成误差；可在已知距离站位后调整 `display_demo.c` 中的 `FACE_DISTANCE_SCALE_DM_PIXELS` 做单点标定。

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
- LPYOLO 模型与 PC 端参考实验：`third_party/lpyolo/`
- 人脸检测加速器结构：`docs/face_detector_architecture.md`
- 验证报告：`Vivado/reports/`

## 从头生成 Vivado 工程

安装路径按本机设置为 `D:\Xilinx\Vivado\2023.1`。如果 Vivado 安装在其他位置，先修改 `create_project.bat` 中的路径。

在 Windows 命令提示符或 PowerShell 中执行：

```powershell
cd C:\Users\34249\Documents\ChatGPT\FPGA\projects\ax7021_v3_ov5640_base
.\hls\build_hls.bat all

cd C:\Users\34249\Documents\ChatGPT\FPGA\projects\ax7021_v3_ov5640_base\Vivado\auto_create_project
.\create_project.bat
```

第一条命令使用仓库中已提交的 INT8 参数头文件运行 C 仿真、HLS 综合并打包 `tiny_face_accel` IP，不需要下载训练检查点。随后 Vivado 脚本会创建 Block Design、综合、实现、生成比特流、生成验证报告，并导出包含比特流的 XSA。HLS 成功标志为 `HLS_CSIM_MISMATCHES=0`，Vivado 成功标志为日志中的 `BUILD_OK`。

只修改约束且已有工程时，可执行：

```powershell
.\rebuild_constraints.bat
```

成功标志为 `REBUILD_OK`。

## 构建裸机程序

在 PowerShell 中执行：

```powershell
cd C:\Users\34249\Documents\ChatGPT\FPGA\projects\ax7021_v3_ov5640_base\Vitis
.\build_all.bat
```

首次执行会从 XSA 创建 Vitis standalone 平台并编译 BSP，通常需要几分钟；随后使用 Vitis 2023.1 自带的 `arm-none-eabi-gcc` 构建应用。若重新生成了 XSA，先执行 `Vitis/auto_create_vitis/update_platform.bat` 更新现有平台，再执行 `Vitis/build_all.bat`。也可以删除生成目录 `Vitis/design_1_wrapper` 后直接运行 `build_all.bat` 完整重建。应用源码位于 `Vitis/auto_create_vitis/src/an5642_single`，可只执行 `Vitis/manual_build/build.bat` 快速重编应用。

裸 JTAG 启动不会执行 FSBL，因此应用在 `main()` 开始处调用 `XTime_SetTime(0)` 启动 SCU 全局定时器；否则 standalone 的 `usleep()` 会一直等待。三帧 1280×720 RGB888 缓存放在链接脚本的 `.noinit` 区，并在其上方预留启动栈保护区，避免 C 运行库清零 BSS 时覆盖 Cortex-A9 异常栈。

由于本机完整路径较长，而且 Xilinx Tcl 在该 Windows 用户目录下会错误处理 `Documents` 路径，脚本临时使用 `P:`/`Q:` 映射工程根目录；源文件和输出仍保存在本工程目录中。

## 实板连接与运行

断电连接以下设备：

1. AN5642 双目 OV5640 模组接 AX7021 V3.0 的 `J16`，当前工程只使用其中一路。
2. 板卡 `HDMI OUT` 接显示器，或接 USB HDMI 采集卡后再接电脑。普通笔记本 HDMI 口通常只能输出，不能直接作为 HDMI 输入。
3. 板卡 UART 接电脑，串口终端设置为 `115200、8N1、无流控`。
4. 板卡 JTAG 接电脑，接入电源并开机。

先检查 JTAG：

```powershell
cd C:\Users\34249\Documents\ChatGPT\FPGA\projects\ax7021_v3_ov5640_base\Vitis
.\check_jtag.bat
```

输出的 `JTAG_TARGETS_BEGIN` 与 `JTAG_TARGETS_END` 之间应出现 Zynq 和 ARM Cortex-A9 目标。然后保持串口终端打开，执行：

```powershell
.\run_jtag.bat
```

程序依次下载 `Vivado/design_1_wrapper.bit` 和 `Vitis/manual_build/an5642_single.elf`。正常串口输出应包含：

```text
AX7021 OV5640 HDMI demo start
PS I2C ready at 40 kHz
OV5640 chip ID: 0x5640
OV5640 configured for 1280x720 RGB output
BBOX overlay: 3 faces, PEOPLE distance labels enabled
VDMA startup errors: 0x810 (clearing latched frame status)
VDMA errors after clear: 0x0
FRAME_SYNC_READY: seen=0x7 current=f0 errors=0x0
VIDEO RUNNING: camera -> 3-frame GenLock DDR -> HDMI, 1280x720
FRAME_SYNC: writing=f1, inference=f0
FRAME_SYNC: writing=f0, inference=f2
FRAME_SYNC: writing=f2, inference=f1
FACE0[f2]: (275,52)-(686,381), score=931/1000 distance=0.6m
FACE1[f2]: (810,96)-(1088,408), score=947/1000 distance=0.7m
```

只有看到 `OV5640 chip ID: 0x5640`，才能确认摄像头的供电、复位和 SCCB/I²C 通信已建立；只有显示器出现稳定画面，才能确认完整的摄像头到 HDMI 通路跑通。

## 最终构建验证

构建日期：2026-10-12。

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
NA/                     PS 配置摘要
Bootimage/              现有 BOOT.BIN 快照
README.md               构建、接线、验证边界和运行说明
```

## 已知警告与验证边界

- OV5640 PCLK 位于板卡固定引脚 AB9，该引脚不是专用时钟引脚，因此保留 `CLOCK_DEDICATED_ROUTE FALSE` 和 `PLCK-12` 警告。这来自板卡走线，最终内部时序已通过，但仍需上板验证图像稳定性。
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

## 第二镜头分支恢复方法

第二镜头实验只存在于本地 `codex/camera2-bringup` 分支。若第二镜头画面异常，需要恢复原单镜头稳定版本，可在停止 Vivado/Vitis 构建后执行：

```powershell
cd C:\Users\34249\Documents\ChatGPT\FPGA\projects\ax7021_v3_ov5640_base
git switch main
cd .\Vitis
.\run_jtag.bat
```

切换 Git 分支只恢复本地文件，不会自动改变 FPGA 中已经下载的程序；必须再次执行 `run_jtag.bat`，才会把 `main` 中保存的 BIT 和 ELF 重新下载到板卡。
