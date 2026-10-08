# AX7021 TinyFace HLS 加速核

本目录把 `training/outputs/tiny_face_fddb.pt` 导出的 INT8 权值和校准参数编译成面向 `xc7z020clg484-2` 的 Vitis HLS IP。核的输入是 160×120 灰度 UINT8，输出是 5×15×20 个 INT32 检测头值；输入和输出分别通过 `m_axi_gmem0`、`m_axi_gmem1` 访问 DDR，控制寄存器通过 `s_axi_control` 访问。

## 已验证结果

- C 仿真：真实 FDDB 验证图像，1500 个输出逐项匹配 Python 整数参考，`HLS_CSIM_MISMATCHES=0`。
- 综合目标器件：`xc7z020-clg484-2`，10 ns 时钟。
- 综合估计：7.300 ns，约 136.99 MHz；延迟 4,247,755 周期，100 MHz 下约 42.48 ms/帧，理论上限约 23.5 FPS。
- 资源估计：BRAM18K 97、DSP 35、FF 7062、LUT 12884。
- IP 打包：`component.xml` 和 `xilinx_com_hls_tiny_face_accel_1_0.zip` 已在本机生成过。

## 重新生成

在项目根目录执行：

```powershell
cd C:\Users\34249\Documents\ChatGPT\FPGA\projects\ax7021_v3_ov5640_base
powershell -ExecutionPolicy Bypass -File .\hls\run_vitis_hls.ps1 -Mode all
```

脚本只给当前 Vivado/Vitis 子进程设置启动路径，不修改 Windows 系统组件或系统环境变量。完成后应存在：

```text
hls\tiny_face_hls\solution1\impl\ip\component.xml
hls\output\tiny_face_accel.zip
```

## 接入 Vivado

`Vivado/auto_create_project/create_project.tcl` 已把上述 IP 目录加入 IP Catalog。`pl_config.tcl` 中的连接为：

```text
PS M_AXI_GP0 -> processing_system7_0_axi_periph/M07_AXI -> tiny_face_accel_0/s_axi_control
tiny_face_accel_0/m_axi_gmem0 -> axi_mem_intercon/S02_AXI -> PS S_AXI_HP0
tiny_face_accel_0/m_axi_gmem1 -> axi_mem_intercon/S03_AXI -> PS S_AXI_HP0
FCLK_CLK0 (100 MHz) -> ap_clk / HLS AXI-Lite / HLS DDR 从端口
FCLK_CLK1 (142.857 MHz) -> 原有摄像头和 HDMI VDMA 通路
```

先只校验 Block Design：

```powershell
cd .\Vivado\auto_create_project
cmd /d /c "..\..\hls\run_vivado_2023_1.bat" -notrace -mode batch -source create_project.tcl -tclargs validate
```

校验通过后再运行 `create_project.tcl` 的完整综合、实现和比特流流程。这个阶段会生成新的 `Vivado\design_1_wrapper.bit` 和 `Vitis\design_1_wrapper.xsa`，旧比特流不会被当作新加速器结果使用。

## Vitis 运行时

`Vitis/auto_create_vitis/src/an5642_single/tiny_face_runtime.c` 在每次检测时从当前 1280×720 RGB888 帧采样到 160×120 灰度输入，启动 HLS 核，轮询完成位，按校准 JSON 中的五个输出通道尺度解码，并把最高置信度框写入已有 `bbox_ctrl`。当前视频叠加器只有一组框寄存器，因此软件暂时显示最高置信度的人脸；PL 核本身输出完整 15×20 网格。

生成新 XSA 后，按原来的流程重新生成 Vitis 平台/BSP，再执行：

```powershell
cd .\Vitis
.\build_all.bat
```

最后再通过 JTAG 下载新的 bit 和 ELF。没有新 XSA/bit 时不要把现有 HDMI 画面当作已经运行了检测核。
