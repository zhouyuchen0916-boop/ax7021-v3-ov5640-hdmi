# AX7021 V3.0 + AN5642 单路 OV5640 到 HDMI 基础工程

本工程使用 Vivado/Vitis 2023.1，目标器件为 AX7021 V3.0 上的 `xc7z020clg484-2`。当前阶段已完成单路 OV5640 采集、DDR 帧缓存、HDMI 输出硬件平台和 Zynq 裸机控制程序，作为后续人脸检测加速器的基础。

## 当前数据通路

`AN5642/J16 单路 OV5640 -> DVP 接收 -> XPM 异步 FIFO -> AXI4-Stream -> VDMA S2MM -> DDR -> VDMA MM2S -> 目标框叠加 -> VTC/视频输出 -> HDMI OUT`

视频软件配置源文件采用 1280×720、RGB888。当前只接入 AN5642 的一个摄像头通道；尚未规定它在双目模组上对应左镜头还是右镜头，接板后以实际画面确认。

当前 PL 端加入了一个 AXI4-Stream 固定框叠加模块。PS 通过双通道 AXI GPIO 写入坐标，默认显示绿色矩形框 `(320,180)–(960,540)`；后续人脸检测程序只需更新同一组寄存器即可移动目标框。

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
- 验证报告：`Vivado/reports/`

## 从头生成 Vivado 工程

安装路径按本机设置为 `D:\Xilinx\Vivado\2023.1`。如果 Vivado 安装在其他位置，先修改 `create_project.bat` 中的路径。

在 Windows 命令提示符或 PowerShell 中执行：

```powershell
cd C:\Users\34249\Documents\ChatGPT\FPGA\projects\ax7021_v3_ov5640_base\Vivado\auto_create_project
.\create_project.bat
```

脚本会创建 Block Design、综合、实现、生成比特流、生成验证报告，并导出包含比特流的 XSA。成功标志为日志中的 `BUILD_OK`。

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
BBOX overlay: (320,180)-(960,540)
VIDEO RUNNING: camera -> DDR -> HDMI, 1280x720
```

只有看到 `OV5640 chip ID: 0x5640`，才能确认摄像头的供电、复位和 SCCB/I²C 通信已建立；只有显示器出现稳定画面，才能确认完整的摄像头到 HDMI 通路跑通。

## 最终构建验证

构建日期：2026-10-06。

- 实现和比特流生成：成功，0 Error、0 Critical Warning
- 框叠加 RTL 自检仿真：通过，输出 `BBOX_SIM_PASS`
- 时序：WNS `+0.567 ns`，TNS `0 ns`，WHS `+0.028 ns`，THS `0 ns`
- 布线：0 条失败网络，0 条未布线网络
- CDC：框坐标的 49 条有效跨域位均通过两级 `ASYNC_REG` 同步并被识别为 `CDC-3`；摄像头像素数据由 XPM 异步 FIFO 跨域
- 资源：6961 LUT、11737 FF、14 RAMB36、3 RAMB18、0 DSP；其中框叠加模块使用 130 LUT、122 FF
- BIT SHA-256：`093AC006F852BEC76E448B8D9FB3687B4389067F6D2F1598D371FA64E7098231`
- XSA SHA-256：`6059051F9B5E1149EF2F71C76846AC14CC28E2A44F378E8DAF6A033A220A6D57`
- Vitis standalone BSP：成功构建，stdin/stdout 均为 `ps7_uart_1`
- 裸机应用：成功构建，0 编译错误、0 编译警告；ELF32 ARM hard-float，入口地址 `0x00100000`
- ELF 代码/数据/BSS 统计：58160 B / 2676 B / 8430520 B；三帧缓存位于 `.noinit`
- ELF SHA-256：`909A416310486D937344C7DA55654BE3E4649F9E00441EC102F65612FF8A1D7B`

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
- `TIMING-9/CDC-6` 位于 AMD Video Timing Controller 自带的 AXI-Lite 多位 CDC 逻辑；摄像头自定义 CDC 已修正。
- 其余 `PDCN-1569`、`RTSTAT-10`、`LUTAR-1`、`PDRC-190` 指向 AMD 调试核或 AXI/IP 内部逻辑，没有阻止比特流生成。
- 2026-10-06 实板验证：JTAG 链枚举出 Digilent JTAG-HS1、ARM Cortex-A9 和 `xc7z020`；AX7021 的 CP210x UART 枚举为 COM3，串口 115200 8N1 输出了 `OV5640 chip ID: 0x5640`、`OV5640 configured for 1280x720 RGB output` 和 `VIDEO RUNNING: camera -> DDR -> HDMI, 1280x720`。异常地址保持为 0，诊断阶段为 0x900。
- JTAG 读取帧缓存时，第二、第三帧缓存地址出现稳定的非零像素数据；这证明 OV5640→DVP→VDMA S2MM→DDR 正在写入。VDMA、VTC、动态时钟和两个复位 GPIO 均已读到运行态寄存器值。HDMI OUT 经 USB HDMI 采集卡接入电脑后，OBS 已显示实时摄像头画面，摄像头到 HDMI 的完整基础通路通过实板验证。
- 2026-10-07 固定绿色框版本已通过 JTAG 下载到实板。串口输出了 `BBOX overlay: (320,180)-(960,540)`、`OV5640 chip ID: 0x5640` 和 `VIDEO RUNNING: camera -> DDR -> HDMI, 1280x720`。JTAG 回读框控制寄存器得到 `0x41220000 = 0x83C00140`、`0x41220008 = 0x021C00B4`，分别对应使能位、X 坐标 320–960 和 Y 坐标 180–540；还需在 OBS 中目视确认绿色框的位置和颜色。
- 当前没有人脸检测硬件加速器，资源报告中的 DSP 数量为 0。固定框通过实板验证后，再接入量化检测网络并用检测结果动态更新框坐标。
