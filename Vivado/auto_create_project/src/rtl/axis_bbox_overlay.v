`timescale 1ns / 1ps

// AXI4-Stream RGB888 bounding-box overlay.
// cfg_x packing: bit 31 enable, bits 27:16 x_max, bits 11:0 x_min.
// cfg_y packing: bits 27:16 y_max, bits 11:0 y_min.
module axis_bbox_overlay #(
    parameter [23:0] BOX_COLOR = 24'h00FF00,
    parameter integer BOX_THICKNESS = 4
) (
    (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 ACLK CLK" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME ACLK, ASSOCIATED_BUSIF S_AXIS_VIDEO:M_AXIS_VIDEO, ASSOCIATED_RESET aresetn, FREQ_HZ 142857132" *)
    input  wire        aclk,

    (* X_INTERFACE_INFO = "xilinx.com:signal:reset:1.0 ARESETN RST" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME ARESETN, POLARITY ACTIVE_LOW" *)
    input  wire        aresetn,

    input  wire [31:0] cfg_x,
    input  wire [31:0] cfg_y,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS_VIDEO TDATA" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME S_AXIS_VIDEO, TDATA_NUM_BYTES 3, TUSER_WIDTH 1, HAS_TREADY 1, HAS_TKEEP 1, HAS_TLAST 1" *)
    input  wire [23:0] s_axis_video_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS_VIDEO TKEEP" *)
    input  wire [2:0]  s_axis_video_tkeep,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS_VIDEO TLAST" *)
    input  wire        s_axis_video_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS_VIDEO TUSER" *)
    input  wire        s_axis_video_tuser,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS_VIDEO TVALID" *)
    input  wire        s_axis_video_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 S_AXIS_VIDEO TREADY" *)
    output wire        s_axis_video_tready,

    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS_VIDEO TDATA" *)
    (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME M_AXIS_VIDEO, TDATA_NUM_BYTES 3, TUSER_WIDTH 1, HAS_TREADY 1, HAS_TKEEP 1, HAS_TLAST 1" *)
    output wire [23:0] m_axis_video_tdata,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS_VIDEO TKEEP" *)
    output wire [2:0]  m_axis_video_tkeep,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS_VIDEO TLAST" *)
    output wire        m_axis_video_tlast,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS_VIDEO TUSER" *)
    output wire        m_axis_video_tuser,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS_VIDEO TVALID" *)
    output wire        m_axis_video_tvalid,
    (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 M_AXIS_VIDEO TREADY" *)
    input  wire        m_axis_video_tready
);

    (* ASYNC_REG = "TRUE" *) reg [31:0] cfg_x_meta;
    (* ASYNC_REG = "TRUE" *) reg [31:0] cfg_x_sync;
    (* ASYNC_REG = "TRUE" *) reg [31:0] cfg_y_meta;
    (* ASYNC_REG = "TRUE" *) reg [31:0] cfg_y_sync;

    reg [11:0] pixel_x;
    reg [11:0] pixel_y;

    wire transfer = s_axis_video_tvalid && s_axis_video_tready;
    wire [11:0] current_x = s_axis_video_tuser ? 12'd0 : pixel_x;
    wire [11:0] current_y = s_axis_video_tuser ? 12'd0 : pixel_y;

    wire        box_enable = cfg_x_sync[31];
    wire [11:0] x_min = cfg_x_sync[11:0];
    wire [11:0] x_max = cfg_x_sync[27:16];
    wire [11:0] y_min = cfg_y_sync[11:0];
    wire [11:0] y_max = cfg_y_sync[27:16];

    wire [12:0] current_x_ext = {1'b0, current_x};
    wire [12:0] current_y_ext = {1'b0, current_y};
    wire [12:0] x_min_ext = {1'b0, x_min};
    wire [12:0] x_max_ext = {1'b0, x_max};
    wire [12:0] y_min_ext = {1'b0, y_min};
    wire [12:0] y_max_ext = {1'b0, y_max};

    wire inside_x = (current_x_ext >= x_min_ext) && (current_x_ext <= x_max_ext);
    wire inside_y = (current_y_ext >= y_min_ext) && (current_y_ext <= y_max_ext);
    wire top_edge = inside_x && (current_y_ext >= y_min_ext) &&
                    (current_y_ext < (y_min_ext + BOX_THICKNESS));
    wire bottom_edge = inside_x && (current_y_ext <= y_max_ext) &&
                       ((current_y_ext + BOX_THICKNESS) > y_max_ext);
    wire left_edge = inside_y && (current_x_ext >= x_min_ext) &&
                     (current_x_ext < (x_min_ext + BOX_THICKNESS));
    wire right_edge = inside_y && (current_x_ext <= x_max_ext) &&
                      ((current_x_ext + BOX_THICKNESS) > x_max_ext);
    wire draw_box = box_enable && (x_min <= x_max) && (y_min <= y_max) &&
                    (top_edge || bottom_edge || left_edge || right_edge);

    assign s_axis_video_tready = m_axis_video_tready;
    assign m_axis_video_tvalid = s_axis_video_tvalid;
    assign m_axis_video_tdata  = draw_box ? BOX_COLOR : s_axis_video_tdata;
    assign m_axis_video_tkeep  = s_axis_video_tkeep;
    assign m_axis_video_tlast  = s_axis_video_tlast;
    assign m_axis_video_tuser  = s_axis_video_tuser;

    always @(posedge aclk) begin
        if (!aresetn) begin
            cfg_x_meta <= 32'd0;
            cfg_x_sync <= 32'd0;
            cfg_y_meta <= 32'd0;
            cfg_y_sync <= 32'd0;
        end else begin
            cfg_x_meta <= cfg_x;
            cfg_x_sync <= cfg_x_meta;
            cfg_y_meta <= cfg_y;
            cfg_y_sync <= cfg_y_meta;
        end
    end

    always @(posedge aclk) begin
        if (!aresetn) begin
            pixel_x <= 12'd0;
            pixel_y <= 12'd0;
        end else if (transfer) begin
            if (s_axis_video_tuser) begin
                pixel_y <= s_axis_video_tlast ? 12'd1 : 12'd0;
                pixel_x <= s_axis_video_tlast ? 12'd0 : 12'd1;
            end else if (s_axis_video_tlast) begin
                pixel_x <= 12'd0;
                pixel_y <= pixel_y + 12'd1;
            end else begin
                pixel_x <= pixel_x + 12'd1;
            end
        end
    end

endmodule
